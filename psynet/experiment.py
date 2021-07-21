import json
import os
from datetime import datetime
from smtplib import SMTPAuthenticationError

import dallinger.experiment
import rpdb
from dallinger import db
from dallinger.command_line import log as dallinger_log
from dallinger.config import get_config
from dallinger.experiment import experiment_route, scheduled_task
from dallinger.experiment_server.dashboard import dashboard_tab
from dallinger.experiment_server.utils import error_response, success_response
from dallinger.models import Network
from dallinger.notifications import admin_notifier
from flask import jsonify, render_template, request
from pkg_resources import resource_filename

from psynet import __version__, data

from . import field
from .field import VarStore
from .page import InfoPage, SuccessfulEndPage
from .participant import Participant, get_participant
from .recruiters import CapRecruiter, DevCapRecruiter, StagingCapRecruiter  # noqa: F401
from .timeline import (
    DatabaseCheck,
    ExperimentSetupRoutine,
    FailedValidation,
    ParticipantFailRoutine,
    PreDeployRoutine,
    RecruitmentCriterion,
    Timeline,
)
from .utils import (
    call_function,
    get_arg_from_dict,
    get_logger,
    pretty_log_dict,
    serialise,
)

logger = get_logger()


def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError("Type not serializable")


class Experiment(dallinger.experiment.Experiment):
    # pylint: disable=abstract-method
    """
    The main experiment class from which to inherit when building experiments.

    There are a number of variables tied to an experiment all of which are documented below.
    They have been assigned reasonable default values which can be overridden when defining an experiment
    (see method ``_default_variables``). Also, they can be enriched with new variables in the following way:

    ::

        from psynet.experiment import Experiment

        class Exp(psynet.Experiment):
            variables = {
                "new_variable": "some-value",  # Adding a new variable
                "wage_per_hour": 12.0,         # Overriding an existing variable
            }

    These variables can then be changed in the course of experiment, just like
    (e.g.) participant variables.

    ::

        from psynet.timeline import CodeBlock

        CodeBlock(lambda experiment: experiment.var.set("custom-variable", 42))

    Default experiment variables accessible through `psynet.experiment.Experiment.var` are:

    max_participant_payment : `float`
        The maximum payment in US dollars a participant is allowed to get. Default: `25.0`.

    soft_max_experiment_payment : `float`
        The recruiting process stops if the amount of accumulated payments
        (incl. bonuses) in US dollars exceedes this value. Default: `1000.0`.

    hard_max_experiment_payment : `float`
        Guarantees that in an experiment no more is spent than the value assigned.
        Bonuses are not paid from the point this value is reached and a record of the amount
        of unpaid bonus is kept in the participant's `unpaid_bonus` variable. Default: `1100.0`.

    show_bonus : `bool`
        If ``True`` (default), then the participant's current estimated bonus is displayed
        at the bottom of the page.

    min_browser_version : `str`
        The minimum version of the Chrome browser a participant needs in order to take a HIT. Default: `80.0`.

    wage_per_hour : `float`
        The payment in US dollars the participant gets per hour. Default: `9.0`.

    There are also a few experiment variables that are set automatically and that should,
    in general, not be changed manually:

    psynet_version : `str`
        The version of the `psynet` package.

    hard_max_experiment_payment_email_sent : `bool`
        Whether an email to the experimenter has already been sent indicating the `hard_max_experiment_payment`
        had been reached. Default: `False`. Once this is `True`, no more emails will be sent about
        this payment limit being reached.

    soft_max_experiment_payment_email_sent : `bool`
        Whether an email to the experimenter has already been sent indicating the `soft_max_experiment_payment`
        had been reached. Default: `False`. Once this is `True`, no more emails will be sent about
        this payment limit being reached.


    Parameters
    ----------

    session:
        The experiment's connection to the database.
    """
    # Introduced this as a hotfix for a compatibility problem with macOS 10.13:
    # http://sealiesoftware.com/blog/archive/2017/6/5/Objective-C_and_fork_in_macOS_1013.html
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    timeline = Timeline(
        InfoPage("Placeholder timeline", time_estimate=5), SuccessfulEndPage()
    )

    __extra_vars__ = {}

    variables = {}
    pre_deploy_routines = []

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

        self.database_checks = []
        self.participant_fail_routines = []
        self.recruitment_criteria = []

        if session:
            if not self.setup_complete:
                self.setup()
            self.load()
        self.register_pre_deployment_routines()

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    def check_database():
        exp_class = dallinger.experiment.load()
        exp = exp_class.new(db.session)
        for c in exp.database_checks:
            c.run()

    @property
    def base_payment(self):
        config = get_config()
        return config.get("base_payment")

    @property
    def var(self):
        return self.experiment_network.var

    @property
    def experiment_network(self):
        return ExperimentNetwork.query.one()

    def register_participant_fail_routine(self, routine):
        self.participant_fail_routines.append(routine)

    def register_recruitment_criterion(self, criterion):
        self.recruitment_criteria.append(criterion)

    def register_database_check(self, task):
        self.database_checks.append(task)

    def register_pre_deployment_routines(self):
        for elt in self.timeline.elts:
            if isinstance(elt, PreDeployRoutine):
                self.pre_deploy_routines.append(elt)

    @classmethod
    def new(cls, session):
        return cls(session)

    @classmethod
    def amount_spent(cls):
        return sum(
            [
                (
                    0.0
                    if (not p.initialised or p.base_payment is None)
                    else p.base_payment
                )
                + (0.0 if p.bonus is None else p.bonus)
                for p in Participant.query.all()
            ]
        )

    @classmethod
    def estimated_max_bonus(cls, wage_per_hour):
        return cls.timeline.estimated_max_bonus(wage_per_hour)

    @classmethod
    def estimated_completion_time(cls, wage_per_hour):
        return cls.timeline.estimated_completion_time(wage_per_hour)

    @property
    def setup_complete(self):
        return self.experiment_network_exists

    @property
    def experiment_network_exists(self):
        return ExperimentNetwork.query.count() > 0

    def setup_experiment_network(self):
        logger.info("Setting up ExperimentNetwork.")
        network = ExperimentNetwork()
        db.session.add(network)
        db.session.commit()

    def setup(self):
        self.setup_experiment_network()
        self.setup_experiment_variables()
        db.session.commit()

    @property
    def _default_variables(self):
        return {
            "psynet_version": __version__,
            "min_browser_version": "80.0",
            "max_participant_payment": 25.0,
            "hard_max_experiment_payment": 1100.0,
            "hard_max_experiment_payment_email_sent": False,
            "soft_max_experiment_payment": 1000.0,
            "soft_max_experiment_payment_email_sent": False,
            "wage_per_hour": 9.0,
            "show_bonus": True,
        }

    @property
    def description(self):
        config = get_config()
        return config.get("description")

    @property
    def ad_requirements(self):
        return [
            'The experiment can only be performed using a <span style="font-weight: bold;">laptop</span> (desktop computers are not allowed).',
            'You should use an <span style="font-weight: bold;">updated Google Chrome</span> browser.',
            'You should be sitting in a <span style="font-weight: bold;">quiet environment</span>.',
            'You should be at least <span style="font-weight: bold;">18 years old</span>.',
            'You should be a <span style="font-weight: bold;">fluent English speaker</span>.',
        ]

    @property
    def ad_payment_information(self):
        return f"""
                We estimate that the task should take approximately <span style="font-weight: bold;">{round(self.estimated_duration_in_minutes)} minutes</span>. Upon completion of the full task,
                <br>
                you should receive a bonus of approximately
                <span style="font-weight: bold;">${'{:.2f}'.format(self.estimated_bonus_in_dollars)}</span> depending on the
                amount of work done.
                <br>
                In some cases, the experiment may finish early: this is not an error, and there is no need to write to us.
                <br>
                In this case you will be paid in proportion to the amount of the experiment that you completed.
                """

    @property
    def variables_initial_values(self):
        return {**self._default_variables, **self.variables}

    @property
    def estimated_duration_in_minutes(self):
        return self.timeline.estimated_time_credit.get_max(mode="time") / 60

    @property
    def estimated_bonus_in_dollars(self):
        return round(
            self.timeline.estimated_time_credit.get_max(
                mode="bonus",
                wage_per_hour=self.variables_initial_values["wage_per_hour"],
            ),
            2,
        )

    def setup_experiment_variables(self):
        # Note: the experiment network must be setup first before we can set these variables.
        dallinger_log(
            "Initializing experiment with variables \n"
            + pretty_log_dict(self.variables_initial_values, 4)
        )

        for key, value in self.variables_initial_values.items():
            self.var.set(key, value)

    def load(self):
        for elt in self.timeline.elts:
            if isinstance(elt, ExperimentSetupRoutine):
                elt.function(experiment=self)
            if isinstance(elt, DatabaseCheck):
                self.register_database_check(elt)
            if isinstance(elt, ParticipantFailRoutine):
                self.register_participant_fail_routine(elt)
            if isinstance(elt, RecruitmentCriterion):
                self.register_recruitment_criterion(elt)

    @classmethod
    def pre_deploy(cls):
        cls.check_config()
        for routine in cls.pre_deploy_routines:
            logger.info(f"Pre-deploying '{routine.label}'...")
            call_function(routine.function, routine.args)

    @classmethod
    def check_config(cls):
        config = get_config()
        if not config.ready:
            config.load()

        if not config.get("clock_on"):
            # We force the clock to be on because it's necessary for the check_networks functionality.
            raise RuntimeError(
                "PsyNet requires the clock process to be enabled; please set clock_on = true in the "
                + "'[Server]' section of the config.txt."
            )

        if config.get("disable_when_duration_exceeded"):
            raise RuntimeError(
                "PsyNet requires disable_when_duration_exceeded = False; please set disable_when_duration_exceeded = False "
                + " in the '[Recruitment strategy]' section of the config.txt."
            )

        n_char_title = len(config.get("title"))
        if n_char_title > 128:
            raise RuntimeError(
                f"The maximum title length is 128 characters (current = {n_char_title}), please fix this in config.txt."
            )

    def fail_participant(self, participant):
        logger.info(
            "Failing participant %i (%i routine(s) found)...",
            participant.id,
            len(self.participant_fail_routines),
        )
        participant.failed = True
        participant.time_of_death = datetime.now()
        for i, routine in enumerate(self.participant_fail_routines):
            logger.info(
                "Executing fail routine %i/%i ('%s')...",
                i + 1,
                len(self.participant_fail_routines),
                routine.label,
            )
            call_function(
                routine.function, {"participant": participant, "experiment": self}
            )

    @property
    def num_working_participants(self):
        return Participant.query.filter_by(status="working", failed=False).count()

    def recruit(self):
        if self.need_more_participants:
            logger.info("Conclusion: recruiting another participant.")
            self.recruiter.recruit(n=1)
        else:
            logger.info("Conclusion: no recruitment required.")
            self.recruiter.close_recruitment()

    @property
    def need_more_participants(self):
        if self.amount_spent() >= self.var.soft_max_experiment_payment:
            self.ensure_soft_max_experiment_payment_email_sent()
            return False

        need_more = False
        for i, criterion in enumerate(self.recruitment_criteria):
            logger.info(
                "Evaluating recruitment criterion %i/%i...",
                i + 1,
                len(self.recruitment_criteria),
            )
            res = call_function(criterion.function, {"experiment": self})
            assert isinstance(res, bool)
            logger.info(
                "Recruitment criterion %i/%i ('%s') %s.",
                i + 1,
                len(self.recruitment_criteria),
                criterion.label,
                (
                    "returned True (more participants needed)."
                    if res
                    else "returned False (no more participants needed)."
                ),
            )
            if res:
                need_more = True
        return need_more

    def ensure_hard_max_experiment_payment_email_sent(self):
        if not self.var.hard_max_experiment_payment_email_sent:
            self.send_email_hard_max_payment_reached()
            self.var.hard_max_experiment_payment_email_sent = True

    def send_email_hard_max_payment_reached(self):
        config = get_config()
        template = """Dear experimenter,

            This is an automated email from PsyNet. You are receiving this email because
            the total amount spent in the experiment has reached the HARD maximum of ${hard_max_experiment_payment}.
            Working participants' bonuses will not be paid out. Instead, the amount of unpaid
            bonus is saved in the participant's `unpaid_bonus` variable.

            The application id is: {app_id}

            To see the logs, use the command "dallinger logs --app {app_id}"
            To pause the app, use the command "dallinger hibernate --app {app_id}"
            To destroy the app, use the command "dallinger destroy --app {app_id}"

            The PsyNet developers.
            """
        message = {
            "subject": "HARD maximum experiment payment reached.",
            "body": template.format(
                hard_max_experiment_payment=self.var.hard_max_experiment_payment,
                app_id=config.get("id"),
            ),
        }
        logger.info(
            f"HARD maximum experiment payment "
            f"of ${self.var.hard_max_experiment_payment} reached!"
        )
        try:
            admin_notifier(config).send(**message)
        except SMTPAuthenticationError as e:
            logger.error(
                f"SMTPAuthenticationError sending 'hard_max_experiment_payment' reached email: {e}"
            )
        except Exception as e:
            logger.error(
                f"Unknown error sending 'hard_max_experiment_payment' reached email: {e}"
            )

    def ensure_soft_max_experiment_payment_email_sent(self):
        if not self.var.soft_max_experiment_payment_email_sent:
            self.send_email_soft_max_payment_reached()
            self.var.soft_max_experiment_payment_email_sent = True

    def send_email_soft_max_payment_reached(self):
        config = get_config()
        template = """Dear experimenter,

            This is an automated email from PsyNet. You are receiving this email because
            the total amount spent in the experiment has reached the soft maximum of ${soft_max_experiment_payment}.
            Recruitment ended.

            The application id is: {app_id}

            To see the logs, use the command "dallinger logs --app {app_id}"
            To pause the app, use the command "dallinger hibernate --app {app_id}"
            To destroy the app, use the command "dallinger destroy --app {app_id}"

            The PsyNet developers.
            """
        message = {
            "subject": "Soft maximum experiment payment reached.",
            "body": template.format(
                soft_max_experiment_payment=self.var.soft_max_experiment_payment,
                app_id=config.get("id"),
            ),
        }
        logger.info(
            f"Recruitment ended. Maximum experiment payment "
            f"of ${self.var.soft_max_experiment_payment} reached!"
        )
        try:
            admin_notifier(config).send(**message)
        except SMTPAuthenticationError as e:
            logger.error(
                f"SMTPAuthenticationError sending 'soft_max_experiment_payment' reached email: {e}"
            )
        except Exception as e:
            logger.error(
                f"Unknown error sending 'soft_max_experiment_payment' reached email: {e}"
            )

    def is_complete(self):
        return (not self.need_more_participants) and self.num_working_participants == 0

    def assignment_abandoned(self, participant):
        participant.append_failure_tags("assignment_abandoned", "premature_exit")
        super().assignment_abandoned(participant)

    def assignment_returned(self, participant):
        participant.append_failure_tags("assignment_returned", "premature_exit")
        super().assignment_returned(participant)

    def assignment_reassigned(self, participant):
        participant.append_failure_tags("assignment_reassigned", "premature_exit")
        super().assignment_reassigned(participant)

    def bonus(self, participant):
        """
        Calculates and returns the bonus payment the given participant gets when
        completing the experiment. Override :func:`~psynet.experiment.Experiment.calculate_bonus()` if you require another than the default bonus calculation.

        :param participant:
            The participant.
        :type participant:
            :attr:`~psynet.participant.Participant`
        :returns:
            The bonus payment as a ``float``.
        """
        bonus = self.calculate_bonus(participant)
        return self.check_bonus(bonus, participant)

    def calculate_bonus(self, participant):
        """
        Calculates and returns the bonus for the given participant.

        :param participant:
            The participant.
        :type participant:
            :attr:`~psynet.participant.Participant`
        :returns:
            The bonus as a ``float``.
        """
        return round(
            participant.time_credit.get_bonus() + participant.performance_bonus,
            ndigits=2,
        )

    def check_bonus(self, bonus, participant):
        """
        Ensures that a participant receives no more than a bonus of max_participant_payment.
        Additionally, checks if both soft_max_experiment_payment or max_participant_payment have
        been reached or exceeded, respectively. Emails are sent out warning the user if either is true.

        :param bonus: float
            The bonus calculated in :func:`~psynet.experiment.Experiment.calculate_bonus()`.
        :type participant:
            :attr: `~psynet.participant.Participant`
        :returns:
            The possibly reduced bonus as a ``float``.
        """

        # check hard_max_experiment_payment
        if (
            self.var.hard_max_experiment_payment_email_sent
            or self.amount_spent() + self.outstanding_base_payments() + bonus
            > self.var.hard_max_experiment_payment
        ):
            participant.var.set("unpaid_bonus", bonus)
            self.ensure_hard_max_experiment_payment_email_sent()

        # check soft_max_experiment_payment
        if self.amount_spent() + bonus >= self.var.soft_max_experiment_payment:
            self.ensure_soft_max_experiment_payment_email_sent()

        # check max_participant_payment
        if participant.amount_paid() + bonus > self.var.max_participant_payment:
            reduced_bonus = round(
                self.var.max_participant_payment - participant.amount_paid(), 2
            )
            participant.send_email_max_payment_reached(self, bonus, reduced_bonus)
            return reduced_bonus
        return bonus

    def outstanding_base_payments(self):
        return self.num_working_participants * self.base_payment

    def init_participant(self, participant_id, client_ip_address):
        logger.info(
            "Initialising participant %i, IP address %s...",
            participant_id,
            client_ip_address,
        )

        participant = get_participant(participant_id)
        participant.initialise(self, client_ip_address)

        self.timeline.advance_page(self, participant)

        self.save()
        return success_response()

    def process_response(
        self,
        participant_id,
        raw_answer,
        blobs,
        metadata,
        page_uuid,
        client_ip_address,
    ):
        logger.info(
            f"Received a response from participant {participant_id} on page {page_uuid}."
        )
        participant = get_participant(participant_id)
        if page_uuid == participant.page_uuid:
            event = self.timeline.get_current_elt(self, participant)
            response = event.process_response(
                raw_answer=raw_answer,
                blobs=blobs,
                metadata=metadata,
                experiment=self,
                participant=participant,
                client_ip_address=client_ip_address,
            )
            validation = event.validate(
                response, experiment=self, participant=participant
            )
            if isinstance(validation, FailedValidation):
                return self.response_rejected(message=validation.message)
            self.timeline.advance_page(self, participant)
            return self.response_approved(participant)
        else:
            logger.warn(
                f"Participant {participant_id} tried to submit data with the wrong page_uuid"
                + f"(submitted = {page_uuid}, required = {participant.page_uuid})."
            )
            return error_response()

    def response_approved(self, participant):
        logger.debug("The response was approved.")
        page = self.timeline.get_current_elt(self, participant)
        return success_response(submission="approved", page=page.__json__(participant))

    def response_rejected(self, message):
        logger.warning(
            "The response was rejected with the following message: '%s'.", message
        )
        return success_response(submission="rejected", message=message)

    @classmethod
    def extra_files(cls):
        return [
            (
                resource_filename("psynet", "templates"),
                "/templates",
            ),
            (
                resource_filename("psynet", "resources/favicon.ico"),
                "/static/favicon.ico",
            ),
            (
                resource_filename("psynet", "resources/logo.png"),
                "/static/images/logo.png",
            ),
            (
                resource_filename("psynet", "resources/logo.svg"),
                "/static/images/logo.svg",
            ),
            (
                resource_filename("psynet", "resources/images/princeton-consent.png"),
                "/static/images/princeton-consent.png",
            ),
            (
                resource_filename("psynet", "resources/images/unity_logo.png"),
                "/static/images/unity_logo.png",
            ),
            (
                resource_filename("psynet", "resources/scripts/dashboard_timeline.js"),
                "/static/scripts/dashboard_timeline.js",
            ),
            (
                resource_filename("psynet", "resources/css/dashboard_timeline.css"),
                "/static/css/dashboard_timeline.css",
            ),
            (
                resource_filename(
                    "psynet", "resources/libraries/raphael-2.3.0/raphael.min.js"
                ),
                "/static/scripts/raphael-2.3.0.min.js",
            ),
            (
                resource_filename("psynet", "resources/libraries/js-synthesizer"),
                "/static/scripts/js-synthesizer",
            ),
            (
                resource_filename("psynet", "resources/libraries/Tonejs"),
                "/static/scripts/Tonejs",
            ),
            (
                resource_filename("psynet", "templates/error.html"),
                "templates/error.html",
            ),
        ]

    @dashboard_tab("Timeline", after_route="monitoring")
    @classmethod
    def dashboard_timeline(cls):
        exp = cls.new(db.session)
        panes = exp.monitoring_panels()

        return render_template(
            "dashboard_timeline.html",
            title="Timeline modules",
            panes=panes,
            timeline_modules=json.dumps(exp.timeline.modules(), default=serialise),
        )

    @experiment_route("/get_participant_info_for_debug_mode", methods=["GET"])
    @staticmethod
    def get_participant_info_for_debug_mode():
        config = get_config()
        if not config.get("mode") == "debug":
            return error_response()

        participant = Participant.query.first()
        json_data = {
            "id": participant.id,
            "assignment_id": participant.assignment_id,
            "page_uuid": participant.page_uuid,
        }
        logger.debug(
            f"Returning from /get_participant_info_for_debug_mode: {json_data}"
        )
        return json.dumps(json_data, default=serialise)

    @experiment_route("/export", methods=["GET"])
    @staticmethod
    def export():
        class_name = request.args.get("class_name")
        exported_data = data.export(class_name)
        return json.dumps(exported_data, default=serialise)

    @experiment_route("/module/<module_id>", methods=["GET"])
    @classmethod
    def get_module_details_as_rendered_html(cls, module_id):
        exp = cls.new(db.session)
        trial_maker = exp.timeline.get_trial_maker(module_id)
        return trial_maker.visualize()

    @experiment_route("/module/<module_id>/tooltip", methods=["GET"])
    @classmethod
    def get_module_tooltip_as_rendered_html(cls, module_id):
        exp = cls.new(db.session)
        trial_maker = exp.timeline.get_trial_maker(module_id)
        return trial_maker.visualize_tooltip()

    @experiment_route("/module/progress_info", methods=["GET"])
    @classmethod
    def get_progress_info(cls):
        exp = cls.new(db.session)
        progress_info = {
            "spending": {
                "amount_spent": exp.amount_spent(),
                "soft_max_experiment_payment": exp.var.soft_max_experiment_payment,
                "hard_max_experiment_payment": exp.var.hard_max_experiment_payment,
            }
        }
        module_ids = request.args.getlist("module_ids[]")
        for module_id in module_ids:
            trial_maker = exp.timeline.get_trial_maker(module_id)
            progress_info.update(trial_maker.get_progress_info())

        return jsonify(progress_info)

    @experiment_route("/module/update_spending_limits", methods=["POST"])
    @classmethod
    def update_spending_limits(cls):
        hard_max_experiment_payment = request.values["hard_max_experiment_payment"]
        soft_max_experiment_payment = request.values["soft_max_experiment_payment"]
        exp = cls.new(db.session)
        exp.var.set("hard_max_experiment_payment", float(hard_max_experiment_payment))
        exp.var.set("soft_max_experiment_payment", float(soft_max_experiment_payment))
        logger.info(
            f"Experiment variable 'hard_max_experiment_payment set' set to {hard_max_experiment_payment}."
        )
        logger.info(
            f"Experiment variable 'soft_max_experiment_payment set' set to {soft_max_experiment_payment}."
        )
        db.session.commit()
        return success_response()

    @experiment_route("/start", methods=["GET"])
    @staticmethod
    def route_start():
        return render_template("start.html")

    @experiment_route("/debugger/<password>", methods=["GET"])
    @classmethod
    def route_debugger(cls, password):
        exp = cls.new(db.session)
        if password == "my-secure-password-195762":
            exp.new(db.session)
            rpdb.set_trace()
            return success_response()
        return error_response()

    @experiment_route("/node/<int:node_id>/fail", methods=["GET", "POST"])
    @staticmethod
    def fail_node(node_id):
        from dallinger.models import Node

        node = Node.query.filter_by(id=node_id).one()
        node.fail(reason="http_fail_route_called")
        db.session.commit()
        return success_response()

    @experiment_route("/info/<int:info_id>/fail", methods=["GET", "POST"])
    @staticmethod
    def fail_info(info_id):
        from dallinger.models import Info

        info = Info.query.filter_by(id=info_id).one()
        info.fail(reason="http_fail_route_called")
        db.session.commit()
        return success_response()

    @experiment_route("/network/<int:network_id>/grow", methods=["GET", "POST"])
    @classmethod
    def grow_network(cls, network_id):
        exp = cls.new(db.session)
        from .trial.main import TrialNetwork

        network = TrialNetwork.query.filter_by(id=network_id).one()
        trial_maker = exp.timeline.get_trial_maker(network.trial_maker_id)
        trial_maker._grow_network(network, participant=None, experiment=exp)
        db.session.commit()
        return success_response()

    @experiment_route(
        "/network/<int:network_id>/call_async_post_grow_network",
        methods=["GET", "POST"],
    )
    @staticmethod
    def call_async_post_grow_network(network_id):
        from .trial.main import TrialNetwork, call_async_post_grow_network

        network = TrialNetwork.query.filter_by(id=network_id).one()
        network.queue_async_process(call_async_post_grow_network)
        db.session.commit()
        return success_response()

    @staticmethod
    def get_client_ip_address():
        if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
            return request.environ["REMOTE_ADDR"]
        else:
            return request.environ["HTTP_X_FORWARDED_FOR"]

    @experiment_route("/timeline/<int:participant_id>/<assignment_id>", methods=["GET"])
    @classmethod
    def route_timeline(cls, participant_id, assignment_id):
        from dallinger.experiment_server.utils import error_page

        exp = cls.new(db.session)
        participant = get_participant(participant_id)
        mode = request.args.get("mode")

        if participant.assignment_id != assignment_id:
            logger.error(
                f"Mismatch between provided assignment_id ({assignment_id})  "
                + f"and actual assignment_id {participant.assignment_id} "
                f"for participant {participant_id}."
            )
            msg = (
                "There was a problem authenticating your session, "
                + "did you switch browsers? Unfortunately this is not currently "
                + "supported by our system."
            )
            return error_page(participant=participant, error_text=msg)

        else:
            if not participant.initialised:
                exp.init_participant(
                    participant_id, client_ip_address=cls.get_client_ip_address()
                )
            page = exp.timeline.get_current_elt(exp, participant)
            page.pre_render()
            exp.save()
            if mode == "json":
                return jsonify(page.__json__(participant))
            return page.render(exp, participant)

    @experiment_route("/response", methods=["POST"])
    @classmethod
    def route_response(cls):
        exp = cls.new(db.session)
        json_data = json.loads(request.values["json"])
        blobs = request.files.to_dict()

        participant_id = get_arg_from_dict(json_data, "participant_id")
        page_uuid = get_arg_from_dict(json_data, "page_uuid")
        raw_answer = get_arg_from_dict(
            json_data, "raw_answer", use_default=True, default=None
        )
        metadata = get_arg_from_dict(json_data, "metadata")
        client_ip_address = cls.get_client_ip_address()

        res = exp.process_response(
            participant_id,
            raw_answer,
            blobs,
            metadata,
            page_uuid,
            client_ip_address,
        )

        exp.save()
        return res

    @experiment_route(
        "/log/<level>/<int:participant_id>/<assignment_id>", methods=["POST"]
    )
    @staticmethod
    def http_log(level, participant_id, assignment_id):
        participant = get_participant(participant_id)
        message = request.values["message"]

        if participant.assignment_id != assignment_id:
            logger.warning(
                "Received wrong assignment_id for participant %i "
                "(expected %s, got %s).",
                participant_id,
                participant.assignment_id,
                assignment_id,
            )

        assert level in ["warning", "info", "error"]

        string = f"[CLIENT {participant_id}]: {message}"

        if level == "info":
            logger.info(string)
        elif level == "warning":
            logger.warning(string)
        elif level == "error":
            logger.error(string)
        else:
            raise RuntimeError("This shouldn't happen.")

        return success_response()

    @staticmethod
    def extra_routes():
        raise RuntimeError(
            "\n\n"
            + "Due to a recent update, the following line is no longer required in PsyNet experiments:\n\n"
            + "extra_routes = Exp().extra_routes()\n\n"
            + "Please delete it from your experiment.py file and try again.\n"
        )


class ExperimentNetwork(Network):
    __mapper_args__ = {"polymorphic_identity": "experiment_network"}
    __extra_vars__ = {}

    def __init__(self):
        self.role = "experiment"
        self.max_size = 0

    @property
    def var(self):
        return VarStore(self)

    def __json__(self):
        x = {
            **super().__json__(),
            "type": "experiment_network",
            "variables": self.details,
            "role": self.role,
        }
        field.json_clean(x, details=True)
        field.json_format_vars(x)
        x["variables"] = json.loads(x["variables"])
        return x

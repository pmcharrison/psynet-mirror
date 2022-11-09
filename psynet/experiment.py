import json
import os
import uuid
from collections import OrderedDict
from datetime import datetime
from platform import python_version
from smtplib import SMTPAuthenticationError

import dallinger.experiment
import dallinger.models
import rpdb
import sqlalchemy.orm.exc
from dallinger import db
from dallinger.command_line import __version__ as dallinger_version
from dallinger.compat import unicode
from dallinger.config import get_config
from dallinger.experiment import experiment_route, scheduled_task
from dallinger.experiment_server.dashboard import dashboard_tab
from dallinger.experiment_server.utils import error_response, success_response
from dallinger.notifications import admin_notifier
from dallinger.utils import get_base_url
from flask import jsonify, render_template, request
from pkg_resources import resource_filename

from psynet import __version__

from .command_line import log
from .data import SQLBase, SQLMixin, register_table
from .field import ImmutableVarStore
from .page import InfoPage, SuccessfulEndPage
from .participant import Participant, get_participant
from .recruiters import (  # noqa: F401
    CapRecruiter,
    DevCapRecruiter,
    DevLucidRecruiter,
    LucidRecruiter,
    StagingCapRecruiter,
)
from .timeline import (
    DatabaseCheck,
    ExperimentSetupRoutine,
    FailedValidation,
    ParticipantFailRoutine,
    PreDeployRoutine,
    RecruitmentCriterion,
    Response,
    Timeline,
)
from .trial.main import Trial
from .utils import (
    NoArgumentProvided,
    call_function,
    get_arg_from_dict,
    get_experiment,
    get_logger,
    pretty_log_dict,
    serialise,
    serialise_datetime,
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

        import psynet.experiment

        class Exp(psynet.experiment.Experiment):
            variables = {
                "new_variable": "some-value",  # Adding a new variable
                "wage_per_hour": 12.0,         # Overriding an existing variable
            }

    These variables can then be changed in the course of experiment, just like (e.g.) participant variables.

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

    min_accumulated_bonus_for_abort : `float`
        The threshold of bonus accumulated in US dollars for the participant to be able to receive
        compensation when aborting an experiment using the `Abort experiment` button. Default: `0.20`.

    show_abort_button : `bool`
        If ``True``, the `Ad` page displays an `Abort` button the participant can click to terminate the HIT,
        e.g. in case of an error where the participant is unable to finish the experiment. Clicking the button
        assures the participant is compensated on the basis of the amount of bonus that has been accumulated.
        Default ``False``.

    show_bonus : `bool`
        If ``True`` (default), then the participant's current estimated bonus is displayed
        at the bottom of the page.

    show_footer : `bool`
        If ``True`` (default), then a footer is displayed at the bottom of the page containing a 'Help' button
        and bonus information if `show_bonus` is set to `True`.

    show_progress_bar : `bool`
        If ``True`` (default), then a progress bar is displayed at the top of the page.

    min_browser_version : `str`
        The minimum version of the Chrome browser a participant needs in order to take a HIT. Default: `80.0`.

    wage_per_hour : `float`
        The payment in US dollars the participant gets per hour. Default: `9.0`.

    check_participant_opened_devtools : ``bool``
        If ``True``, whenever a participant opens the developer tools in the web browser,
        this is logged as participant.var.opened_devtools = ``True``,
        and the participant is shown a warning alert message.
        Default: ``False``.
        Note: Chrome does not currently expose an official way of checking whether
        the participant opens the developer tools. People therefore have to rely
        on hacks to detect it. These hacks can often be broken by updates to Chrome.
        We've therefore disabled this check by default, to reduce the risk of
        false positives. Experimenters wishing to enable the check for an individual
        experiment are recommended to verify that the check works appropriately
        before relying on it. We'd be grateful for any contributions of updated
        developer tools checks.

    window_width : ``int``
        Determines the width in pixels of the window that opens when the
        participant starts the experiment.
        Default: ``1024``.

    window_height : ``int``
        Determines the width in pixels of the window that opens when the
        participant starts the experiment.
        Default: ``768``.

    There are also a few experiment variables that are set automatically and that should,
    in general, not be changed manually:

    psynet_version : `str`
        The version of the `psynet` package.

    dallinger_version : `str`
        The version of the `Dallinger` package.

    python_version : `str`
        The version of the `Python`.

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
            if request and request.path == "/launch":
                self.on_launch()
            self.load()
        self.register_pre_deployment_routines()

    def on_launch(self):
        if not self.setup_complete:
            self.setup()
        self.var.launched = True

    def participant_constructor(self, *args, **kwargs):
        return Participant(experiment=self, *args, **kwargs)

    def initialize_bot(self, bot):
        """
        This function is called when a bot is created.
        It can be used to set stochastic random parameters corresponding
        to participant latent traits, for example.

        e.g.

        ```bot.var.musician = True``
        """
        pass

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    def check_database():
        exp = get_experiment()
        for c in exp.database_checks:
            c.run()

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    def run_recruiter_checks():
        exp = get_experiment()
        recruiter = exp.recruiter
        if hasattr(recruiter, "run_checks"):
            recruiter.run_checks()

    @property
    def base_payment(self):
        config = get_config()
        return config.get("base_payment")

    @property
    def var(self):
        if self.experiment_config_exists:
            return self.experiment_config.var
        else:
            return ImmutableVarStore(self.variables_initial_values)

    @property
    def experiment_config(self):
        return ExperimentConfig.query.one()

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
                (0.0 if p.base_payment is None else p.base_payment)
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
        return self.experiment_config_exists

    @property
    def experiment_config_exists(self):
        return ExperimentConfig.query.count() > 0

    def setup_experiment_config(self):
        if not self.experiment_config_exists:
            logger.info("Setting up ExperimentConfig.")
            network = ExperimentConfig()
            db.session.add(network)
            db.session.commit()

    def setup(self):
        self.setup_experiment_config()
        self.setup_experiment_variables()
        db.session.commit()

    @property
    def _default_variables(self):
        return {
            "psynet_version": __version__,
            "dallinger_version": dallinger_version,
            "python_version": python_version(),
            "launched": False,
            "min_browser_version": "80.0",
            "max_participant_payment": 25.0,
            "hard_max_experiment_payment": 1100.0,
            "hard_max_experiment_payment_email_sent": False,
            "soft_max_experiment_payment": 1000.0,
            "soft_max_experiment_payment_email_sent": False,
            "wage_per_hour": 9.0,
            "min_accumulated_bonus_for_abort": 0.20,
            "show_abort_button": False,
            "show_bonus": True,
            "show_footer": True,
            "show_progress_bar": True,
            "check_participant_opened_devtools": False,
            "window_width": 1024,
            "window_height": 768,
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
        log(
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
        bonus = participant.calculate_bonus()
        return self.check_bonus(bonus, participant)

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

    def with_lucid_recruitment(self):
        return self.recruiter.__class__.__name__ in [
            "DevLucidRecruiter",
            "LucidRecruiter",
        ]

    def process_response(
        self,
        participant_id,
        raw_answer,
        blobs,
        metadata,
        page_uuid,
        client_ip_address,
        answer=NoArgumentProvided,
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
                answer=answer,
            )
            validation = event.validate(
                response, experiment=self, participant=participant
            )
            if isinstance(validation, FailedValidation):
                return self.response_rejected(message=validation.message)
            participant.time_credit.increment(event.time_estimate)
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
                resource_filename("psynet", "resources/css/consent.css"),
                "/static/css/consent.css",
            ),
            (
                resource_filename("psynet", "resources/css/dashboard_timeline.css"),
                "/static/css/dashboard_timeline.css",
            ),
            (
                resource_filename(
                    "psynet", "resources/libraries/jQuery/jquery-3.6.0.min.js"
                ),
                "/static/scripts/jquery-3.6.0.min.js",
            ),
            (
                resource_filename(
                    "psynet", "resources/libraries/platform-1.3.6/platform.min.js"
                ),
                "/static/scripts/platform.min.js",
            ),
            (
                resource_filename(
                    "psynet", "resources/libraries/raphael-2.3.0/raphael.min.js"
                ),
                "/static/scripts/raphael-2.3.0.min.js",
            ),
            (
                resource_filename(
                    "psynet", "resources/libraries/jQuery-Knob/dist/jquery.knob.min.js"
                ),
                "/static/scripts/jquery.knob.min.js",
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
                resource_filename("psynet", "templates/mturk_error.html"),
                "templates/mturk_error.html",
            ),
            (
                resource_filename(
                    "psynet", "resources/scripts/prepare_docker_image.sh"
                ),
                "prepare_docker_image.sh",
            ),
        ]

    @classmethod
    def extra_parameters(cls):
        # We can put extra config variables here if we like, e.g.
        config = get_config()
        config.register("cap_recruiter_auth_token", unicode)
        config.register("lucid_api_key", unicode)
        config.register("lucid_sha1_hashing_key", unicode)
        config.register("lucid_recruitment_config", unicode)
        # config.register("keep_old_chrome_windows_in_debug_mode", bool)

    @dashboard_tab("Timeline", after_route="monitoring")
    @classmethod
    def dashboard_timeline(cls):
        exp = get_experiment()
        panes = exp.monitoring_panels()

        return render_template(
            "dashboard_timeline.html",
            title="Timeline modules",
            panes=panes,
            timeline_modules=json.dumps(exp.timeline.modules(), default=serialise),
        )

    @dashboard_tab("Participant", after_route="monitoring")
    @classmethod
    def participant(cls):
        message = ""
        participant = None

        assignment_id = request.args.get("assignment_id", default=None)
        participant_id = request.args.get("participant_id", default=None)
        worker_id = request.args.get("worker_id", default=None)

        try:
            if assignment_id is not None:
                participant = cls.get_participant_from_assignment_id(assignment_id)
            elif participant_id is not None:
                participant = cls.get_participant_from_participant_id(participant_id)
            elif worker_id is not None:
                participant = cls.get_participant_from_worker_id(worker_id)
            else:
                message = "Please select a participant."
        except ValueError:
            message = "Invalid ID."
        except sqlalchemy.orm.exc.NoResultFound:
            message = "Failed to find any matching participants."
        except sqlalchemy.orm.exc.MultipleResultsFound:
            message = "Found multiple participants matching those specifications."

        return render_template(
            "participant.html",
            title="Participant",
            participant=participant,
            message=message,
            app_base_url=get_base_url(),
        )

    @classmethod
    def get_participant_from_assignment_id(cls, assignment_id):
        """
        Get a participant with a specified ``assignment_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        assignment_id :
            ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        return Participant.query.filter_by(assignment_id=assignment_id).one()

    @classmethod
    def get_participant_from_participant_id(cls, participant_id):
        """
        Get a participant with a specified ``participant_id``.
        Throws a ``ValueError`` if the ``participant_id`` is not a valid integer,
        a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        participant_id :
            ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        _id = int(participant_id)
        return Participant.query.filter_by(id=_id).one()

    @classmethod
    def get_participant_from_worker_id(cls, worker_id):
        """
        Get a participant with a specified ``worker_id``.
        Throws a ``sqlalchemy.orm.exc.NoResultFound`` error if there is no such participant,
        or a ``sqlalchemy.orm.exc.MultipleResultsFound`` error if there are multiple such participants.

        Parameters
        ----------
        worker_id :
            ID of the participant to retrieve.

        Returns
        -------

        The corresponding participant object.
        """
        return Participant.query.filter_by(worker_id=worker_id).one()

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
            "auth_token": participant.auth_token,
            "page_uuid": participant.page_uuid,
        }
        logger.debug(
            f"Returning from /get_participant_info_for_debug_mode: {json_data}"
        )
        return json.dumps(json_data, default=serialise)

    @experiment_route("/error-page", methods=["POST", "GET"])
    @staticmethod
    def render_error():
        from psynet.utils import error_page

        request_data = request.form.get("request_data")
        participant_id = request.form.get("participant_id")
        participant = None
        if participant_id:
            participant = Participant.query.filter_by(id=participant_id).one()
        return error_page(participant=participant, request_data=request_data)

    @experiment_route("/module", methods=["POST"])
    @classmethod
    def get_module_details_as_rendered_html(cls):
        exp = get_experiment()
        trial_maker = exp.timeline.get_trial_maker(request.values["moduleId"])
        return trial_maker.visualize()

    @experiment_route("/module/tooltip", methods=["POST"])
    @classmethod
    def get_module_tooltip_as_rendered_html(cls):
        exp = get_experiment()
        trial_maker = exp.timeline.get_trial_maker(request.values["moduleId"])
        return trial_maker.visualize_tooltip()

    @experiment_route("/module/progress_info", methods=["GET"])
    @classmethod
    def get_progress_info(cls):
        exp = get_experiment()
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
        exp = get_experiment()
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
        exp = get_experiment()
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
        exp = get_experiment()
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
        from .trial.main import TrialNetwork

        network = TrialNetwork.query.filter_by(id=network_id).one()
        network.queue_async_method("call_async_post_grow_network")
        db.session.commit()
        return success_response()

    @staticmethod
    def get_client_ip_address():
        if request.environ.get("HTTP_X_FORWARDED_FOR") is None:
            return request.environ["REMOTE_ADDR"]
        else:
            return request.environ["HTTP_X_FORWARDED_FOR"]

    @experiment_route("/resume/<auth_token>", methods=["GET"])
    @classmethod
    def route_resume(cls, auth_token):
        return render_template("resume.html", auth_token=auth_token)

    @experiment_route("/set_participant_as_aborted/<assignment_id>", methods=["GET"])
    @classmethod
    def route_set_participant_as_aborted(cls, assignment_id):
        participant = cls.get_participant_from_assignment_id(assignment_id)
        participant.aborted = True
        modules = participant.modules.copy()
        try:
            current_module_log = modules[participant.current_module]
        except KeyError:
            current_module_log = {
                "time_started": [],
                "time_finished": [],
                "time_aborted": [],
            }
        time_now = serialise_datetime(datetime.now())
        current_module_log["time_aborted"] = [time_now]
        modules[participant.current_module] = current_module_log.copy()
        participant.modules = modules.copy()
        db.session.commit()
        logger.info(f"Aborted participant with ID '{participant.id}'.")
        return success_response()

    @experiment_route("/abort/<assignment_id>", methods=["GET"])
    @classmethod
    def route_abort(cls, assignment_id):
        try:
            template_name = "abort_not_possible.html"
            participant = None
            participant_abort_info = None
            if assignment_id is not None:
                participant = cls.get_participant_from_assignment_id(assignment_id)
                if (
                    participant.calculate_bonus()
                    >= cls.new(db.session).var.min_accumulated_bonus_for_abort
                ):
                    template_name = "abort_possible.html"
                    participant_abort_info = participant.abort_info()
        except ValueError:
            logger.error("Invalid assignment ID.")
        except sqlalchemy.orm.exc.NoResultFound:
            logger.error("Failed to find any matching participants.")
        except sqlalchemy.orm.exc.MultipleResultsFound:
            logger.error("Found multiple participants matching those specifications.")

        return render_template(
            template_name,
            participant=participant,
            participant_abort_info=participant_abort_info,
        )

    @experiment_route("/timeline", methods=["GET"])
    @classmethod
    def route_timeline(cls):
        participant_id = request.args.get("participant_id")
        auth_token = request.args.get("auth_token")

        from psynet.utils import error_page

        exp = get_experiment()
        mode = request.args.get("mode")
        participant = get_participant(participant_id)

        if participant.auth_token is None:
            participant.auth_token = str(uuid.uuid4())
        else:
            if not cls.validate_auth_token(participant, auth_token):
                msg = (
                    "There was a problem authenticating your session, "
                    + "did you switch browsers? Unfortunately this is not currently "
                    + "supported by our system."
                )
                return error_page(participant=participant, error_text=msg)

        participant.client_ip_address = cls.get_client_ip_address()

        page = exp.timeline.get_current_elt(exp, participant)
        page.pre_render()
        exp.save()
        if mode == "json":
            return jsonify(page.__json__(participant))
        return page.render(exp, participant)

    @staticmethod
    def validate_auth_token(participant, auth_token):
        valid = participant.auth_token == auth_token
        if not valid:
            logger.error(
                f"Mismatch between provided auth_token ({auth_token}) "
                + f"and actual auth_token {participant.auth_token} "
                f"for participant {participant.id}."
            )
        return valid

    @experiment_route("/timeline/progress_and_bonus", methods=["GET"])
    @classmethod
    def get_progress_and_bonus(cls):
        participant = get_participant(request.args.get("participantId"))
        progress_percentage = round(participant.progress * 100)
        min_pct = 5
        max_pct = 99
        if progress_percentage > max_pct:
            progress_percentage = max_pct
        elif progress_percentage < min_pct:
            progress_percentage = min_pct
        data = {
            "progressPercentage": progress_percentage,
            "progressPercentageStr": f"{progress_percentage}%",
        }
        if cls.new(db.session).var.show_bonus:
            performance_bonus = participant.performance_bonus
            basic_bonus = participant.time_credit.get_bonus()
            total_bonus = participant.calculate_bonus()
            data["bonus"] = {
                "basic": basic_bonus,
                "extra": performance_bonus,
                "total": total_bonus,
            }
        return data

    @experiment_route("/response", methods=["POST"])
    @classmethod
    def route_response(cls):
        exp = get_experiment()
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
        "/log/<level>/<int:participant_id>/<auth_token>", methods=["POST"]
    )
    @classmethod
    def http_log(cls, level, participant_id, auth_token):
        participant = get_participant(participant_id)
        cls.validate_auth_token(participant, auth_token)
        message = request.values["message"]

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

    @experiment_route(
        "/participant_opened_devtools/<int:participant_id>/<auth_token>",
        methods=["POST"],
    )
    @classmethod
    def participant_opened_devtools(cls, participant_id, auth_token):
        participant = get_participant(participant_id)

        Experiment.validate_auth_token(participant, auth_token)

        participant.var.opened_devtools = True
        db.session.commit()

        return success_response()

    def monitoring_statistics(self, **kwarg):
        stats = super().monitoring_statistics(**kwarg)

        del stats["Infos"]

        stats["Trials"] = OrderedDict(
            (
                ("count", Trial.query.count()),
                ("failed", Trial.query.filter_by(failed=True).count()),
            )
        )

        return stats


@register_table
class ExperimentConfig(SQLBase, SQLMixin):
    """
    This SQL-backed class provides a way to store experiment configuration variables
    that can change over the course of the experiment.
    See :class:`psynet.experiment.Experiment` documentation for example usage.
    """

    __tablename__ = "experiment"

    # Removing these fields because they don't make much sense for the experiment configuration object
    creation_time = None
    failed = None
    failed_reason = None
    time_of_death = None


def _patch_dallinger_models():
    # There are some Dallinger functions that rely on the ability to look up
    # models by name in dallinger.models. One example is the code for
    # generating dashboard tabs for SQL object types. We therefore need
    # to patch in certain PsyNet classes so that Dallinger can access them.
    dallinger.models.Trial = Trial
    dallinger.models.Response = Response


_patch_dallinger_models()

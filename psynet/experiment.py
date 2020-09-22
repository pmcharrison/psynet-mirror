from datetime import datetime
from flask import render_template_string, Blueprint, request, render_template, jsonify
from flask_login import login_required
import json
import os
import rpdb
from pkg_resources import resource_filename
from dallinger import (
    db
)

from dallinger.config import get_config

import dallinger.experiment
from dallinger.experiment_server.dashboard import (
    dashboard,
    dashboard_tabs
)

from dallinger.experiment_server.utils import (
    success_response,
    error_response
)

from .participant import get_participant, Participant
from .timeline import (
    get_template,
    Timeline,
    FailedValidation,
    ExperimentSetupRoutine,
    ParticipantFailRoutine,
    RecruitmentCriterion,
    BackgroundTask,
    StartModule
)
from .page import (
    InfoPage,
    SuccessfulEndPage
)
from .utils import (
    call_function,
    get_arg_from_dict,
    get_logger,
    serialise
)

logger = get_logger()

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

class Experiment(dallinger.experiment.Experiment):
    # pylint: disable=abstract-method

    # Introduced this as a hotfix for a compatibility problem with macOS 10.13:
    # http://sealiesoftware.com/blog/archive/2017/6/5/Objective-C_and_fork_in_macOS_1013.html
    os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"

    timeline = Timeline(
        InfoPage("Placeholder timeline", time_estimate=5),
        SuccessfulEndPage()
    )

    wage_per_hour = 9.0
    min_browser_version = "80.0"
    # min_working_participants = 5

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

        config = get_config()
        if not config.ready:
            config.load()

        self._background_tasks = []
        self.participant_fail_routines = []
        self.recruitment_criteria = []
        self.base_payment = config.get("base_payment")

        # self.register_recruitment_criterion(self.default_recruitment_criterion)

        if session:
            self.setup()

    # @property
    # def default_recruitment_criterion(self):
    #     def f():
    #         logger.info(
    #             "Number of working participants = %i, versus minimum of %i.",
    #             self.num_working_participants,
    #             self.min_working_participants
    #         )
    #         return self.num_working_participants < self.min_working_participants
    #     return RecruitmentCriterion(
    #         label="min_working_participants",
    #         function=f
    #     )

    def register_participant_fail_routine(self, routine):
        self.participant_fail_routines.append(routine)

    def register_recruitment_criterion(self, criterion):
        self.recruitment_criteria.append(criterion)

    # @property
    # def allotted_bonus_dollars(self):
    #     return self.timeline.estimate_time_credit().get_max("bonus", wage_per_hour=self.wage_per_hour)

    @property
    def background_tasks(self):
        return self._background_tasks

    def register_background_task(self, task):
        self._background_tasks.append(task)

    @classmethod
    def new(cls, session):
        return cls(session)

    def setup(self):
        for event in self.timeline.events:
            if isinstance(event, ExperimentSetupRoutine):
                event.function(experiment=self)
            if isinstance(event, BackgroundTask):
                self.register_background_task(event.daemon)
            if isinstance(event, ParticipantFailRoutine):
                self.register_participant_fail_routine(event)
            if isinstance(event, RecruitmentCriterion):
                self.register_recruitment_criterion(event)

        tab_title = "Timeline"
        if all(tab_title != tab.title for tab in dashboard_tabs):
            dashboard_tabs.insert_after_route(tab_title, "dashboard.timeline", "dashboard.monitoring")

    def fail_participant(self, participant):
        logger.info(
            "Failing participant %i (%i routine(s) found)...",
            participant.id,
            len(self.participant_fail_routines)
        )
        participant.failed = True
        participant.time_of_death = datetime.now()
        for i, routine in enumerate(self.participant_fail_routines):
            logger.info(
                "Executing fail routine %i/%i ('%s')...",
                i + 1,
                len(self.participant_fail_routines),
                routine.label
            )
            call_function(routine.function, {"participant": participant, "experiment": self})

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
        need_more = False
        for i, criterion in enumerate(self.recruitment_criteria):
            logger.info("Evaluating recruitment criterion %i/%i...", i + 1, len(self.recruitment_criteria))
            res = call_function(criterion.function, {"experiment": self})
            assert isinstance(res, bool)
            logger.info(
                "Recruitment criterion %i/%i ('%s') %s.",
                i + 1,
                len(self.recruitment_criteria),
                criterion.label,
                (
                    "returned True (more participants needed)." if res
                    else "returned False (no more participants needed)."
                )
            )
            if res:
                need_more = True
        return need_more

    def is_complete(self):
        return (not self.need_more_participants) and self.num_working_participants == 0

    def assignment_abandoned(self, participant):
        participant.append_failure_tags("assignment_abandoned", "premature_exit")
        super().assignment_abandoned(participant)

    def assignment_returned(self, participant):
        participant.append_failure_tags("assignment_returned", "premature_exit")
        super().assignment_abandoned(participant)

    def assignment_reassigned(self, participant):
        participant.append_failure_tags("assignment_reassigned", "premature_exit")
        super().assignment_abandoned(participant)

    def bonus(self, participant):
        return round(
            participant.time_credit.get_bonus() + participant.performance_bonus,
            ndigits=2
        )

    def init_participant(self, participant_id):
        logger.info("Initialising participant {}...".format(participant_id))

        participant = get_participant(participant_id)
        participant.initialise(self)

        self.timeline.advance_page(self, participant)

        self.save()
        return success_response()

    def process_response(self, participant_id, raw_answer, blobs, metadata, page_uuid):
        logger.info(f"Received a response from participant {participant_id} on page {page_uuid}.")
        participant = get_participant(participant_id)
        if page_uuid == participant.page_uuid:
            event = self.timeline.get_current_event(self, participant)
            response = event.process_response(
                raw_answer=raw_answer,
                blobs=blobs,
                metadata=metadata,
                experiment=self,
                participant=participant,
            )
            validation = event.validate(
                response,
                experiment=self,
                participant=participant
            )
            if isinstance(validation, FailedValidation):
                return self.response_rejected(message=validation.message)
            self.timeline.advance_page(self, participant)
            return self.response_approved()
        else:
            logger.warn(
                f"Participant {participant_id} tried to submit data with the wrong page_uuid" +
                f"(submitted = {page_uuid}, required = {participant.page_uuid})."
            )
            return error_response()

    def response_approved(self):
        logger.debug("The response was approved.")
        return success_response(
            submission="approved"
        )

    def response_rejected(self, message):
        logger.warning("The response was rejected with the following message: '%s'.", message)
        return success_response(
            submission="rejected",
            message=message
        )

    @classmethod
    def extra_files(cls):
        return [
            (resource_filename('psynet', 'resources/logo.png'), "/static/images/logo.png"),
            (resource_filename('psynet', 'resources/scripts/dashboard_timeline.js'), "/static/scripts/dashboard_timeline.js"),
            (resource_filename('psynet', 'resources/css/dashboard_timeline.css'), "/static/css/dashboard_timeline.css")
        ]

    def extra_routes(self):
        #pylint: disable=unused-variable

        routes = Blueprint(
            "extra_routes", __name__, template_folder="templates", static_folder="static"
        )

        @dashboard.route("/timeline")
        @login_required
        def timeline():
            exp = self.new(db.session)
            panes = exp.monitoring_panels()

            return render_template(
                "dashboard_timeline.html",
                title="Timeline modules",
                panes=panes,
                timeline_modules=json.dumps(exp.timeline.modules(), default=serialise)
            )

        @routes.route("/module/<module_id>", methods=["GET"])
        def get_module_details_as_rendered_html(module_id):
            trial_maker = self.timeline.get_trial_maker(module_id)
            return trial_maker.visualize()

        @routes.route("/module/<module_id>/tooltip", methods=["GET"])
        def get_module_tooltip_as_rendered_html(module_id):
            trial_maker = self.timeline.get_trial_maker(module_id)
            return trial_maker.visualize_tooltip()

        @routes.route("/module/progress_info", methods=["GET"])
        def get_progress_info():
            module_ids = request.args.getlist("module_ids[]")
            progress_info = {}
            for module_id in module_ids:
                trial_maker = self.timeline.get_trial_maker(module_id)
                progress_info.update(trial_maker.get_progress_info())

            return jsonify(progress_info)

        @routes.route("/start", methods=["GET"])
        def route_start():
            return render_template("start.html")

        @routes.route("/debugger/<password>", methods=["GET"])
        def route_debugger(password):
            if password == "my-secure-password-195762":
                exp = self.new(db.session)
                rpdb.set_trace()
                return success_response()
            return error_response()

        @routes.route("/metadata", methods=["GET"])
        def get_metadata():
            exp = self.new(db.session)
            return jsonify({
                "duration_seconds": exp.timeline.estimated_time_credit.get_max(mode="time"),
                "bonus_dollars": exp.timeline.estimated_time_credit.get_max(mode="bonus", wage_per_hour=exp.wage_per_hour),
                "wage_per_hour": exp.wage_per_hour,
                "base_payment": exp.base_payment
            })

        @routes.route("/consent")
        def consent():
            config = get_config()
            exp = self.new(db.session)
            return render_template(
                "consent.html",
                hit_id=request.args["hit_id"],
                assignment_id=request.args["assignment_id"],
                worker_id=request.args["worker_id"],
                mode=config.get("mode"),
                contact_email_on_error=config.get("contact_email_on_error"),
                min_browser_version=self.min_browser_version,
                wage_per_hour=f"{exp.wage_per_hour:.2f}"
            )

        @routes.route("/node/<int:node_id>/fail", methods=["GET", "POST"])
        def fail_node(node_id):
            from dallinger.models import Node
            node = Node.query.filter_by(id=node_id).one()
            node.fail()
            db.session.commit()
            return success_response()

        @routes.route("/info/<int:info_id>/fail", methods=["GET", "POST"])
        def fail_info(info_id):
            from dallinger.models import Info
            info = Info.query.filter_by(id=info_id).one()
            info.fail()
            db.session.commit()
            return success_response()

        @routes.route("/network/<int:network_id>/grow", methods=["GET", "POST"])
        def grow_network(network_id):
            from .trial.main import TrialNetwork
            network = TrialNetwork.query.filter_by(id=network_id).one()
            trial_maker = self.timeline.get_trial_maker(network.trial_maker_id)
            trial_maker._grow_network(network, participant=None, experiment=self)
            db.session.commit()
            return success_response()

        @routes.route("/network/<int:network_id>/call_async_post_grow_network", methods=["GET", "POST"])
        def call_async_post_grow_network(network_id):
            from .trial.main import TrialNetwork, call_async_post_grow_network
            network = TrialNetwork.query.filter_by(id=network_id).one()
            network.queue_async_process(call_async_post_grow_network)
            db.session.commit()
            return success_response()

        @routes.route("/timeline/<int:participant_id>/<assignment_id>", methods=["GET"])
        def route_timeline(participant_id, assignment_id):
            from dallinger.experiment_server.utils import error_page
            exp = self.new(db.session)
            participant = get_participant(participant_id)

            if participant.assignment_id != assignment_id:
                logger.error(
                    f"Mismatch between provided assignment_id ({assignment_id})  " +
                    f"and actual assignment_id {participant.assignment_id} "
                    f"for participant {participant_id}."
                )
                msg = (
                    "There was a problem authenticating your session, " +
                    "did you switch browsers? Unfortunately this is not currently " +
                    "supported by our system."
                )
                return error_page(
                    participant=participant,
                    error_text=msg
                )

            else:
                if not participant.initialised:
                    exp.init_participant(participant_id)
                exp.save()
                return exp.timeline.get_current_event(self, participant).render(exp, participant)

        @routes.route("/response", methods=["POST"])
        def route_response():
            exp = self.new(db.session)
            json_data = json.loads(request.values["json"])
            blobs = request.files.to_dict()

            participant_id = get_arg_from_dict(json_data, "participant_id")
            page_uuid = get_arg_from_dict(json_data, "page_uuid")
            raw_answer = get_arg_from_dict(json_data, "raw_answer", use_default=True, default=None)
            metadata = get_arg_from_dict(json_data, "metadata")

            res = exp.process_response(participant_id, raw_answer, blobs, metadata, page_uuid)

            exp.save()
            return res

        @routes.route("/log/<level>/<int:participant_id>/<assignment_id>", methods=["POST"])
        def log(level, participant_id, assignment_id):
            participant = get_participant(participant_id)
            message = request.values["message"]

            if participant.assignment_id != assignment_id:
                logger.warning(
                    "Received wrong assignment_id for participant %i "
                    "(expected %s, got %s).",
                    participant_id,
                    participant.assignment_id,
                    assignment_id
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

        return routes

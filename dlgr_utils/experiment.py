from datetime import datetime
from flask import render_template_string, Blueprint, request, render_template
import json
from json import dumps

from dallinger import db
import dallinger.experiment

from dallinger.experiment_server.utils import (
    success_response,
    error_response
)

from .participant import get_participant, Participant
from .timeline import (
    get_template, 
    Timeline, 
    InfoPage, 
    SuccessfulEndPage, 
    FailedValidation, 
    ExperimentSetupRoutine, 
    ParticipantFailRoutine,
    RecruitmentCriterion,
    BackgroundTask
)
from .utils import get_arg_from_dict, call_function

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

import rpdb

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

class Experiment(dallinger.experiment.Experiment):
    # pylint: disable=abstract-method

    timeline = Timeline(
        InfoPage("Placeholder timeline", time_estimate=5),
        SuccessfulEndPage()
    )

    wage_per_hour = 9.0
    min_working_participants = 5

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)
        
        self._background_tasks = []
        self.participant_fail_routines = []
        self.recruitment_criteria = []

        self.register_recruitment_criterion(self.default_recruitment_criterion)

        if session:
            self.setup()

    @property
    def default_recruitment_criterion(self):
        def f():
            logger.info(
                "Number of working participants = %i, versus minimum of %i.",
                self.num_working_participants,
                self.min_working_participants
            )
            return self.num_working_participants < self.min_working_participants
        return RecruitmentCriterion(
            label="min_working_participants",
            function=f
        )

    def register_participant_fail_routine(self, routine):
        self.participant_fail_routines.append(routine)

    def register_recruitment_criterion(self, criterion):
        self.recruitment_criteria.append(criterion)

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
        logger.info("Evaluating recruitment criteria (%i found)...", len(self.recruitment_criteria))
        complete = True
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
                complete = False
        if complete:
            logger.info("Conclusion: no recruitment required.")
            self.recruiter.close_recruitment()
        else:
            logger.info("Conclusion: recruiting another participant.")
            self.recruiter.recruit(n=1)

    def assignment_abandoned(self, participant):
        participant.append_failure_tags("assignment_abandoned", "premature_exit")

    def assignment_returned(self, participant):
        participant.append_failure_tags("assignment_returned", "premature_exit")

    def assignment_reassigned(self, participant):
        participant.append_failure_tags("assignment_reassigned", "premature_exit")

    def network_structure(self):
        from dallinger import models
        from dallinger.models import Vector, Network, Node, Info, Transformation, Participant

        jnodes = [n.__json__() for n in Node.query.all()]
        jnetworks = [n.__json__() for n in Network.query.all()]
        jinfos = [n.__json__() for n in Info.query.all()]
        jparticipants = [n.__json__() for n in Participant.query.all()]

        jvectors = [{
            "origin_id": v.origin_id,
            "destination_id": v.destination_id,
            "id": v.id,
            "failed": v.failed
        } for v in Vector.query.all()]

        return {
            "networks": jnetworks, 
            "nodes": jnodes,  
            "vectors": jvectors, 
            "infos": jinfos, 
            "participants": jparticipants,
            "trans": []
        }

    def network_stats(self):
        from dallinger import models
        from dallinger.models import Vector, Network, Node, Info, Transformation, Participant

        networks = Network.query.all()
        nodes = Node.query.all()
        infos = Info.query.all()
        participants = Participant.query.all()
    
        experiment_networks = set([net.id for net in networks if (net.role!= "practice")])
    
        failed_nodes = [node for node in nodes if node.failed]
        failed_infos = [info for info in infos if info.failed]

        pct_failed_nodes = round(100.0*len(failed_nodes)/(0.001+len(nodes)))
        pct_failed_infos = round(100.0*len(failed_infos)/(0.001+len(infos)))
    
        msg_networks = f"# networks = {len(networks)} (experiment= {len(experiment_networks)})"
        msg_nodes = f"# nodes = {len(nodes)} [failed= {len(failed_nodes)} ({pct_failed_nodes} %)]"
        msg_infos = f"# infos = {len(infos)} [failed= {len(failed_infos)} ({pct_failed_infos} %)]"
        
        active_participants = 0
        relevant_participants = [p for p in participants if (p.status=="working")]
        for participant in relevant_participants:
            nets_for_p = len([node for node in nodes if (node.participant_id == participant.id)])
            if (nets_for_p <= 1): # make sure player played at least one valid nodes
                continue
            active_participants = active_participants + 1
        msg_part = f"# participants = {len(participants)} working: {len(relevant_participants)} active: {active_participants}"

        return {
            'n_participants': len(participants),
            'n_networks': len(networks),
            'n_e_networks': len(experiment_networks),
            'nodes': len(nodes),
            'failed_nodes': len(failed_nodes),
            'infos': len(infos),
            'failed_infos': len(failed_infos),
            'msg_networks': msg_networks,
            'msg_nodes': msg_nodes,
            'msg_infos': msg_infos,
            'msg': f"{msg_part}\n{msg_networks}\n{msg_nodes}\n{msg_infos}\n"
        }
    
    def bonus(self, participant):
        return round(participant.time_credit.get_bonus(), ndigits=2)

    def render_monitor_template(self):
        res = self.network_structure()
        stat = self.network_stats()
        data = {"status": "success", "net_structure": res}
        msg = stat['msg'].replace("\n",'<br>')
        html = get_template("network-monitor.html")
        return render_template_string(html, my_data = dumps(data, default = json_serial), my_msg = msg)

    def init_participant(self, participant_id):
        logger.info("Initialising participant {}...".format(participant_id))

        participant = get_participant(participant_id)
        participant.initialise(self)
        
        self.timeline.advance_page(self, participant)
        
        self.save()
        return success_response()

    def process_response(self, participant_id, response, metadata, page_uuid):
        logger.info(f"Received a response from participant {participant_id} on page {page_uuid}.")
        participant = get_participant(participant_id)
        if page_uuid == participant.page_uuid:

            event = self.timeline.get_current_event(self, participant)
            parsed_response = event.process_response(
                response=response, 
                metadata=metadata,
                experiment=self,
                participant=participant,
            )
            validation = event.validate(
                parsed_response=parsed_response,
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
        logger.info("The response was approved.")
        return success_response(
            submission="approved"
        )

    def response_rejected(self, message):
        logger.info("The response was rejected with the following message: '%s'.", message)
        return success_response(
            submission="rejected",
            message=message
        )

    def extra_routes(self):
        #pylint: disable=unused-variable

        routes = Blueprint(
            "extra_routes", __name__, template_folder="templates", static_folder="static"
        )

        @routes.route("/monitor", methods=["GET"])
        def route_monitor():
            return self.render_monitor_template()

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
            message = json.loads(request.values["message"])
            participant_id = get_arg_from_dict(message, "participant_id")
            page_uuid = get_arg_from_dict(message, "page_uuid")
            data = json.loads(get_arg_from_dict(message, "data", use_default=True, default=None))
            metadata = json.loads(get_arg_from_dict(message, "metadata"))
            res = exp.process_response(participant_id, data, metadata, page_uuid)
            exp.save()
            return res

        return routes

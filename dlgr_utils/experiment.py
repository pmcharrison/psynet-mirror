from datetime import datetime
from flask import render_template_string, Blueprint, request, render_template
import json
from json import dumps

from dallinger import db
from dallinger.config import get_config
import dallinger.experiment

from dallinger.experiment_server.utils import (
    success_response,
    error_response
)

from .participant import Participant, get_participant
from .timeline import get_template, Timeline, Page, InfoPage, FinalPage, RejectedResponse
from .utils import get_arg_from_dict

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
    timeline = Timeline([
        InfoPage("Placeholder timeline"),
        FinalPage()
    ])

    # begin_page = BeginPage()

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

    @classmethod
    def new(cls, session):
        return cls(session)

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
        # participant.var.initialise()
        participant.elt_id = -1
        self.timeline.advance_page(self, participant)
        participant.complete = False
        
        self.save()
        return success_response()

    def process_response(self, participant_id, data, metadata, page_uuid):
        logger.info(f"Received a response from participant {participant_id} on page {page_uuid}.")
        participant = get_participant(participant_id)
        if page_uuid == participant.page_uuid:

            res = self.timeline.get_current_elt(
                self, participant
            ).process_response(
                input=data, 
                metadata=metadata,
                experiment=self,
                participant=participant,
            )

            if res is RejectedResponse:
                return self.response_rejected(message=res.message)            
            else:
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
        logger.info(f"The response was rejected with the following message: '{message}'.")
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

        @routes.route("/begin", methods=["GET"])
        def route_begin():
            return render_template("begin.html")

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
                return exp.timeline.get_current_elt(self, participant).render(exp, participant)

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

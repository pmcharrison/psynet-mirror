from datetime import datetime
from flask import render_template_string
from json import dumps

from dallinger.config import get_config
import dallinger.experiment

from . import page

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

class Experiment(dallinger.experiment.Experiment):

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

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
        html = page.get_template("network-monitor.html")
        return render_template_string(html, my_data = dumps(data, default = json_serial), my_msg = msg)

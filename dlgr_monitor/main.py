from datetime import datetime
from flask import render_template_string
from json import dumps

import importlib_resources as pkg_resources

from dallinger.config import get_config
import dallinger.experiment

from dlgr_monitor import templates

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")

class Experiment(dallinger.experiment.Experiment):
    """Define the structure of the experiment."""

    def __init__(self, session=None):
        super(Experiment, self).__init__(session)

    def network_structure(self):
        from dallinger import models
        from dallinger.models import Vector, Network, Node, Info, Transformation, Participant

        # get the necessary data
        networks = Network.query.all()
        nodes  =   Node.query.all()
        vectors =  Vector.query.all()
        infos =  Info.query.all()
        trans= Transformation.query.all() #this does not work
        participants= Participant.query.all()

        # jsources= []
        jnodes= []
        jnetworks= []
        jvectors= []
        jinfos= []
        jtrans=[] 
        jparticipants=[]
        for n in nodes:
            #self.log "node id: {} --------------------HERE--------".format(n.id)
            js=n.__json__()
            #self.log js
            jnodes.append(js)
        for net in networks:
            #self.log "network id: {} --------------------HERE--------".format(net.id)
            js=net.__json__()
            #self.log js
            jnetworks.append(js)
        for v in vectors:
            #self.log "now in vector -----------HERE ---------"
            orig=v.origin_id
            dest=v.destination_id
            vid=v.id
            vfail=v.failed
            js={'origin_id':orig, 'destination_id':dest,'id':vid, 'failed':vfail}
            #self.log js
            jvectors.append(js)
        for t in trans:
            #self.log "now in vector -----------HERE ---------"
            orig=t.info_in_id
            dest=t.info_out_id
            tid=t.id
            tfail=t.failed
            js={'origin_id':orig, 'destination_id':dest,'id':tid, 'failed':tfail}
            jtrans.append(js)
        for i in infos:
            #self.log "info id: {} --------------------HERE--------".format(i.id)
            js=i.__json__()
            #self.log js
            jinfos.append(js)
        for j in participants:
            #self.log "info id: {} --------------------HERE--------".format(i.id)
            js=j.__json__()
            #self.log js
            jparticipants.append(js)


        res={'networks':jnetworks, 'nodes':jnodes,  'vectors':jvectors, 'infos':jinfos, 'participants':jparticipants,'trans':jtrans}

        return res

    # MONITOR
    def network_stats(self):
        from dallinger import models
        from dallinger.models import Vector, Network, Node, Info, Transformation, Participant

        stat=dict()
        networks = Network.query.all()
        nodes  =   Node.query.all()
        # vectors =  Vector.query.all()
        infos =  Info.query.all()
        participants= Participant.query.all()

        experiment_networks=set([net.id for net in networks if (net.role!= "practice")])

        failed_nodes=[node for node in nodes if node.failed]
        # suc_nodes=[node for node in nodes if not(node.failed)]
        # suc_nodes_experiment=[node for node in nodes if (not(node.failed) and (node.network_id in experiment_networks))]
        failed_infos=[info for info in infos if info.failed]
        # suc_infos=[info for info in infos if not(info.failed)]


        msg_networks="# networks = {} (experiment= {})".format(len(networks),len(experiment_networks))
        msg_nodes=   "# nodes = {} [failed= {} ({} %)]".format(len(nodes), len(failed_nodes), round(100.0*len(failed_nodes)/(0.001+len(nodes))))
        msg_infos=   "# infos = {} [failed= {} ({} %)]".format(len(infos), len(failed_infos), round(100.0*len(failed_infos)/(0.001+len(infos))))

    
        stat['n_participants']=len(participants)
        stat['n_networks']=len(networks)
        stat['n_e_networks']=len(experiment_networks)
        stat['nodes']=len(nodes)
        stat['failed_nodes']=len(failed_nodes)
        stat['infos']=len(infos)
        stat['failed_infos']=len(failed_infos)
        stat['msg_networks']=msg_networks
        stat['msg_nodes']=msg_nodes
        stat['msg_infos']=msg_infos
        stat['msg']="{}\n{}\n{}\n".format(msg_networks,msg_nodes,msg_infos)
        
        
        return stat

    def render_monitor_template(self):
        res = self.network_structure()
        stat = self.network_stats()
        data = {"status": "success", "net_structure": res}
        msg = stat['msg'].replace("\n",'<br>')
        html = pkg_resources.read_text(templates, "network-monitor.html")
        return render_template_string(html, my_data = dumps(data, default = json_serial), my_msg = msg)

def get():
    return pkg_resources.read_text(templates, "network-monitor.html")

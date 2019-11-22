"""Monte Carlo Markov Chains with people."""
import random
import time
from operator import attrgetter
from datetime import datetime

from dallinger import recruiters
from jinja2 import TemplateNotFound
from flask import Blueprint, Response, request, render_template, abort
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from sqlalchemy import exc

from dallinger.bots import BotBase
from dallinger.experiment import Experiment
from dallinger import db, models
from dallinger.networks import Chain
from dallinger.experiment_server.utils import success_response
from dallinger.config import get_config
from dallinger.models import Vector, Network, Node, Info, Transformation, Participant
from dallinger.experiment_server.utils import (
    crossdomain,
    nocache,
    ValidatesBrowser,
    error_page,
    error_response,
    success_response,
    ExperimentError,
)


import json
from json import dumps

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)


# VSS
def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""

    if isinstance(obj, datetime):
        serial = obj.isoformat()
        return serial
    raise TypeError ("Type not serializable")



class Monitor(Experiment):
    """Define the structure of the experiment."""

          # MONITOR     
    def network_structure(self):

        # get the necessary data
        networks = Network.query.all()
        nodes  =   Node.query.all()
        vectors =  Vector.query.all()
        infos =  Info.query.all()
        trans= Transformation.query.all() #this does not work
        participants= Participant.query.all()

        jsources= []
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
        stat=dict()
        networks = Network.query.all()
        nodes  =   Node.query.all()
        vectors =  Vector.query.all()
        infos =  Info.query.all()
        participants= Participant.query.all()

        experiment_networks=set([net.id for net in networks if (net.role!= "practice")])

        failed_nodes=[node for node in nodes if node.failed]
        suc_nodes=[node for node in nodes if not(node.failed)]
        suc_nodes_experiment=[node for node in nodes if (not(node.failed) and (node.network_id in experiment_networks))]
        failed_infos=[info for info in infos if info.failed]
        suc_infos=[info for info in infos if not(info.failed)]


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



# MONITOR
@extra_routes.route("/monitor/", methods=["GET"])
def monitor():
    exp = MCMCP(db.session)
    res=exp.network_structure()
    stat=exp.network_stats()
    data = {"status": "success", "net_structure": res}

    msg=stat['msg'].replace("\n",'<br>')
    print (stat)
    return render_template('network-monitor.html',my_data=dumps(data, default=json_serial),my_msg=msg)






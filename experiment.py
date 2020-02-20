# This is a minimal experiment implementation for prototyping the monitor route.

from flask import Blueprint, Response, render_template, abort, request, Markup
from dallinger.experiment import Experiment
from dallinger.models import Network, Info, Transformation, Node
from dallinger.networks import Chain
from dallinger.nodes import Source
from dallinger import db, recruiters
from dallinger.models import Participant

from dallinger.experiment_server.utils import (
    success_response
)

import rpdb

import dlgr_utils.monitor
from dlgr_utils.misc import claim_field

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

Participant.test = claim_field(1, type=int)

class Exp(dlgr_utils.monitor.Experiment):
    # You can customise these parameters ####
    num_networks = 3
    num_nodes_per_network = 5
    num_infos_per_node = 2
    network_roles = ["practice", "experiment"]    
    use_sources = True
    use_transformations = True
    ####

    assert num_nodes_per_network > 0

    @property
    def num_non_source_nodes_per_network(self):
        return (
            self.num_nodes_per_network - 1
            if self.use_sources
            else self.num_nodes_per_network
        )

    def __init__(self, session=None):
        super().__init__(session)

        if session:
            self.setup()

    def setup(self):
        if not self.networks():
            for role in self.network_roles:
                for _ in range(self.num_networks):
                    self.setup_network(role=role)
            self.session.commit()

    def setup_network(self, role):
        net = Chain()
        net.role = role
        self.session.add(net)
        self.populate_network(net)

    def populate_network(self, network):
        if self.use_sources:
            source = Source(network)
            self.session.add(source)
            network.add_node(source)

        for _ in range(self.num_non_source_nodes_per_network):
            node = Node(network)
            self.session.add(node)
            self.populate_node(node)
            network.add_node(node)

    def populate_node(self, node):
        for _ in range(self.num_infos_per_node):
            info = Info(node)
            self.session.add(info)

extra_routes = Blueprint(
    "extra_routes", __name__, template_folder="templates", static_folder="static"
)

@extra_routes.route("/monitor", methods=["GET"])
def get_monitor():
    return Exp(db.session).render_monitor_template()

@extra_routes.route("/init-participant/<int:participant_id>", methods=["POST"])
def init_participant(participant_id):
    exp = Exp(db.session)

    logger.info("Initialising participant {}...".format(participant_id))

    participant = Participant.query.get(participant_id)
    participant.test = 3

    exp.save()
    return success_response()

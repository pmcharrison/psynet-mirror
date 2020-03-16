# This is a minimal experiment implementation for prototyping the monitor route.

from flask import Blueprint, Response, render_template, abort, request, Markup
from dallinger.experiment import Experiment
from dallinger.models import Network, Info, Transformation, Node
from dallinger.networks import Chain
from dallinger.nodes import Source
from dallinger import db, recruiters
# from dallinger.models import Participant

from dallinger.experiment_server.utils import (
    success_response
)

import rpdb

from dlgr_utils.experiment import Experiment
from dlgr_utils.field import claim_field
from dlgr_utils.participant import Participant, get_participant
from dlgr_utils.page import Page, InfoPage, Timeline, FinalPage

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)


class Exp(Experiment):
    # You can customise these parameters ####
    num_networks = 3
    num_nodes_per_network = 5
    num_infos_per_node = 2
    network_roles = ["practice", "experiment"]
#    network_roles = ["male", "female","other"] 
#    network_roles = ["role1", "role2","role3","role4","role5","role6"]    
    use_sources = True

    timeline = Timeline([
        InfoPage("Page 1"),
        InfoPage("Page 2"),
        FinalPage()
    ])

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

extra_routes = Exp().extra_routes()
   
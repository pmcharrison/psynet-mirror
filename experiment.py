# This is a minimal experiment implementation for prototyping the monitor route.

from flask import Blueprint, Response, render_template, abort, request, Markup
from dallinger.experiment import Experiment
from dallinger.models import Network, Info, Transformation, Node, Question
from dallinger.networks import Chain
from dallinger.nodes import Source
from dallinger import db, recruiters
# from dallinger.models import Participant

from dallinger.experiment_server.utils import (
    success_response
)

import rpdb

import dlgr_utils.experiment
from dlgr_utils.field import claim_field
from dlgr_utils.participant import Participant, get_participant
from dlgr_utils.timeline import (
    Page, 
    InfoPage, 
    Timeline,
    SuccessfulEndPage, 
    ReactivePage, 
    NAFCPage, 
    CodeBlock, 
    while_loop, 
    conditional, 
    switch
)

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

from datetime import datetime

# Weird bug: if you instead import Experiment from dlgr_utils.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(dlgr_utils.experiment.Experiment):
    # You can customise these parameters ####
    num_networks = 3
    num_nodes_per_network = 5
    num_infos_per_node = 2
    network_roles = ["practice", "experiment"]
#    network_roles = ["male", "female","other"] 
#    network_roles = ["role1", "role2","role3","role4","role5","role6"]    
    use_sources = True

    timeline = Timeline(
        InfoPage(
            "Welcome to the experiment!",
            time_allotted=5
        ),
        ReactivePage(            
            lambda experiment, participant: 
                InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
            time_allotted=5
        ),
        CodeBlock(lambda experiment, participant: participant.set_answer("Yes")),
        NAFCPage(
            label="chocolate",
            prompt="Do you like chocolate?",
            choices=["Yes", "No"],
            time_allotted=3
        ),
        conditional(
            "like_chocolate",
            lambda experiment, participant: participant.answer == "Yes",
            InfoPage(
                "It's nice to hear that you like chocolate!", 
                time_allotted=5
            ), 
            InfoPage(
                "I'm sorry to hear that you don't like chocolate...", 
                time_allotted=3
            ), 
            fix_time_credit=False
        ),
        CodeBlock(lambda experiment, participant: participant.set_answer("Yes")),
        while_loop(
            "example_loop",
            lambda experiment, participant: participant.answer == "Yes",
            NAFCPage(
                label="loop_nafc",
                prompt="Would you like to stay in this loop?",
                choices=["Yes", "No"],
                time_allotted=3
            ), 
            expected_repetitions=3,
            fix_time_credit=True
        ),
        NAFCPage(
            label="test_nafc",            
            prompt="What's your favourite colour?",
            choices=["Red", "Green", "Blue"],
            time_allotted=5
        ),
        switch(
            "colour",
            lambda experiment, participant: participant.answer,
            branches = {
                "Red": InfoPage("Red is a nice colour, wait 1s.", time_allotted=1),
                "Green": InfoPage("Green is quite a nice colour, wait 2s.", time_allotted=2),
                "Blue": InfoPage("Blue is an unpleasant colour, wait 3s.", time_allotted=3)
            }, 
            fix_time_credit=False
        ),
        CodeBlock(
            lambda experiment, participant:
                participant.set_var("favourite_colour", participant.answer)
        ),
        ReactivePage(
            lambda experiment, participant: 
                InfoPage(f"OK, your favourite colour is {participant.answer.lower()}."),
            time_allotted=3
        ),
        SuccessfulEndPage()
    )

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
        super().setup()
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
   
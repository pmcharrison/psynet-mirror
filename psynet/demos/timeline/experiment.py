# This is a minimal experiment implementation for prototyping the monitor route.
import dallinger.deployment
from dallinger.models import Info, Node, Transformation
from dallinger.networks import Chain
from dallinger.nodes import Source

import psynet.experiment
from psynet.timeline import (
    Timeline,
    PageMaker,
    CodeBlock,
    while_loop,
    conditional
)
from psynet.page import (
    InfoPage,
    SuccessfulEndPage,
    NAFCPage,
    TextInputPage,
    WaitPage,
)

from psynet.utils import get_logger
logger = get_logger()

from datetime import datetime

dallinger.deployment.MAX_ATTEMPTS = 1

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    # You can customise these parameters ####
    num_networks = 3
    num_nodes_per_network = 3
    num_infos_per_node = 2
    network_roles = ["practice", "experiment"]
#    network_roles = ["male", "female","other"]
#    network_roles = ["role1", "role2","role3","role4","role5","role6"]
    use_sources = False
    create_transformation = True

    timeline = Timeline(
        InfoPage(
            "Welcome to the experiment!",
            time_estimate=5
        ),
        PageMaker(
            lambda experiment, participant:
                InfoPage(f"The current time is {datetime.now().strftime('%H:%M:%S')}."),
            time_estimate=5
        ),
        TextInputPage(
            "message",
            "Write me a message!",
            time_estimate=5,
            one_line=False
        ),
        PageMaker(
            lambda participant: InfoPage(f"Your message: {participant.answer}"),
            time_estimate=5
        ),
        NAFCPage(
            label="chocolate",
            prompt="Do you like chocolate?",
            choices=["Yes", "No"],
            time_estimate=3,
            arrange_vertically=True
        ),
        conditional(
            "like_chocolate",
            lambda experiment, participant: participant.answer == "Yes",
            InfoPage(
                "It's nice to hear that you like chocolate!",
                time_estimate=5
            ),
            InfoPage(
                "I'm sorry to hear that you don't like chocolate...",
                time_estimate=3
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
                time_estimate=3
            ),
            expected_repetitions=3,
            fix_time_credit=True
        ),
        # NAFCPage(
        #     label="test_nafc",
        #     prompt="What's your favourite colour?",
        #     choices=["Red", "Green", "Blue"],
        #     time_estimate=5
        # ),
        # switch(
        #     "colour",
        #     lambda experiment, participant: participant.answer,
        #     branches = {
        #         "Red": InfoPage("Red is a nice colour, wait 1s.", time_estimate=1),
        #         "Green": InfoPage("Green is quite a nice colour, wait 2s.", time_estimate=2),
        #         "Blue": InfoPage("Blue is an unpleasant colour, wait 3s.", time_estimate=3)
        #     },
        #     fix_time_credit=False
        # ),
        # CodeBlock(
        #     lambda experiment, participant:
        #         participant.var.set("favourite_colour", participant.answer)
        # ),
        # PageMaker(
        #     lambda experiment, participant:
        #         InfoPage(f"OK, your favourite colour is {participant.answer.lower()}."),
        #     time_estimate=3
        # ),
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
        if self.create_transformation:
            info1 = Info(node)
            info2 = Info(node)
            self.session.add(info1)
            self.session.add(info2)
            Transformation(info_in=info2, info_out=info1)
        else:
            for _ in range(self.num_infos_per_node):
                info = Info(node)
                self.session.add(info)

extra_routes = Exp().extra_routes()

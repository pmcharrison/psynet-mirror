import random

from flask import Markup

from psynet.modular_page import ModularPage
from psynet.page import (
    DebugResponsePage,
    InfoPage
)
from psynet.timeline import join
from psynet.trial.mcmcp import (
    MCMCPNetwork, MCMCPTrial, MCMCPNode, MCMCPSource, MCMCPTrialMaker
)
from psynet.utils import rgb_to_hex

from .colour_2afc import Colour2AFCControl

def mcmcp_factory(config):
    targets = config["targets"]

    class CustomNetwork(MCMCPNetwork):
        __mapper_args__ = {"polymorphic_identity": "custom_network"}

        def make_definition(self):
            return {
                "target": self.balance_across_networks(targets)
            }

    class CustomTrial(MCMCPTrial):
        __mapper_args__ = {"polymorphic_identity": "custom_trial"}

        def show_trial(self, experiment, participant):
            target = self.network.definition["target"]
            prompt = Markup(
                "Choose which colour best matches the following word: "
                f"<strong>{target}</strong>"
            )
            colours = [
                rgb_to_hex(*self.first_stimulus["rgb"]),
                rgb_to_hex(*self.second_stimulus["rgb"])
            ]
            return ModularPage(
                "mcmcp_trial",
                prompt,
                Colour2AFCControl(colours),
                time_estimate=3
            )

    class CustomSource(MCMCPSource):
        __mapper_args__ = {"polymorphic_identity": "custom_source"}

        def generate_seed(self, network, experiment, participant):
            return {
                "rgb": [random.randint(0, 255) for _ in range(3)]
            }

    class CustomNode(MCMCPNode):
        __mapper_args__ = {"polymorphic_identity": "custom_node"}

        def get_proposal(self, state, experiment, participant):
            rgb = [
                (x + round(random.gauss(0, config["proposal_sigma"]))) % 256
                for x in state["rgb"]
            ]
            return {
                "rgb": rgb
            }

    class CustomTrialMaker(MCMCPTrialMaker):
        give_end_feedback_passed = True
        performance_threshold = -1.0

        def get_end_feedback_passed_page(self, score):
            score_to_display = "NA" if score is None else f"{(100 * score):.0f}"

            return InfoPage(
                Markup(f"Your consistency score was <strong>{score_to_display}&#37;</strong>."),
                time_estimate=5
            )

        def compute_bonus(self, score, passed):
            if self.phase == "practice":
                return 0.0
            elif self.phase == "experiment":
                return max(0.0, 2 * (score - 0.5))
            else:
                raise NotImplementedError

    instructions = join(
        InfoPage(
            """
            In each trial of this experiment you will be presented with a word
            and two colours. Your task will be to choose the colour that
            best matches this word.
            """,
            time_estimate=5
        ),
        InfoPage(
            """
            The quality of your responses will be automatically monitored,
            and you will receive a bonus at the end of the experiment
            in proportion to your quality score. The best way to achieve
            a high score is to concentrate and give each trial your best attempt.
            """,
            time_estimate=5
        )
    )

    return {
        "Network": CustomNetwork,
        "Node": CustomNode,
        "Source": CustomSource,
        "Trial": CustomTrial,
        "TrialMaker": CustomTrialMaker,
        "instructions": instructions
    }

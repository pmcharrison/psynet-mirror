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


from colour import hsl_dimensions, random_hsl_sample
from colour_2afc import Colour2AFCControl

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
                f"""
                <style>
                    .text_prompt {{
                        text-align: center;
                    }}
                </style>

                <div class="text_prompt">
                    <p>
                        Choose which colour best matches the following word:
                    </p>
                    <p>
                        <strong>{target}</strong>
                    </p>
                </div>
                """
            )
            colours = [
                self.first_stimulus["colour"],
                self.second_stimulus["colour"]
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
                "colour": [random_hsl_sample(i) for i in range(3)]
            }

    class CustomNode(MCMCPNode):
        __mapper_args__ = {"polymorphic_identity": "custom_node"}

        def get_proposal(self, state, experiment, participant):
            hsl_max_values = [x["max_value"] for x in hsl_dimensions]
            colour = [
                (origin + round(random.gauss(0, config["proposal_sigma"]))) % (max_value + 1)
                for origin, max_value in zip(state["colour"], hsl_max_values)
            ]
            return {
                "colour": colour
            }

    class CustomTrialMaker(MCMCPTrialMaker):
        give_end_feedback_passed = True
        performance_threshold = -1.0

        def compute_bonus(self, score, passed):
            if self.phase == "practice":
                return 0.0
            elif self.phase == "experiment":
                if score is None:
                    return 0.0
                else:
                    return max(0.0, 2 * (score - 0.5))
            else:
                raise NotImplementedError

    instructions = join(
        InfoPage(Markup(
            """
            <p>
                In each trial of this experiment you will be presented with a word
                and two colours. Your task will be to choose the colour that
                best matches this word.
            </p>
            <p>
                In some cases, no colour will match the word particularly well.
                If so, don't worry, and just give your best guess!
            </p>
            """),
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

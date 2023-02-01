# pylint: disable=unused-import,abstract-method,unused-argument

##########################################################################################
# Imports
##########################################################################################

import random
from typing import List, Optional

import numpy as np
from flask import Markup
from scipy import stats

import psynet.experiment
from psynet.consent import MainConsent
from psynet.graphics import Circle, Frame, GraphicPrompt
from psynet.modular_page import ModularPage
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline
from psynet.trial.graph import GraphChainNode, GraphChainTrial, GraphChainTrialMaker
from psynet.utils import get_logger

logger = get_logger()


##########################################################################################
# Stimuli
##########################################################################################
COLOR_OPTIONS = ["red", "green", "blue"]
NECKLACE_LENGTH = 9


class NecklaceCircle(Circle):
    """
    A Necklace circle object.

    Parameters
    ----------

    id_
        A unique identifier for the object.

    x
        x coordinate.

    y
        y coordinate.

    radius
        The circle's radius.

    **kwargs
        Additional parameters passed to :class:`~psynet.graphic.GraphicObject`.
    """

    def __init__(
        self,
        id_: str,
        x: int,
        y: int,
        radius: int,
        color_options: List[str],
        initial_color: int,
        interactive: bool,
        **kwargs,
    ):
        self.color_options = color_options
        self.initial_color = initial_color
        self.interactive = interactive
        super().__init__(id_, x, y, radius, click_to_answer=not interactive, **kwargs)

    @property
    def js_init(self):
        return [
            *super().js_init,
            f"""
            let initial_color = {self.initial_color};
            let color_options = {self.color_options};
            this.raphael.attr({{"stroke": color_options[initial_color], "fill": color_options[initial_color]}});

            if (psynet.response.staged.rawAnswer == undefined) {{
                psynet.response.staged.rawAnswer = {{}};
            }}

            let stage_color = function(index, circle_id) {{
                psynet.response.staged.rawAnswer[circle_id] = {{
                    color_index: index,
                    color_value: color_options[index]
                }};
            }};

            stage_color(initial_color, "{self.id}");

            this.raphael.click(function () {{
                if ("{self.interactive}" == "True") {{
                    let currentColor = this.attrs.fill;
                    let targetIdx = (color_options.findIndex(element => element == currentColor) + 1) % color_options.length
                    this.attr({{"stroke": color_options[targetIdx], "fill": color_options[targetIdx]}});
                    stage_color(targetIdx, "{self.id}");
                }}
            }});
            """,
        ]


class CustomGraphicPrompt(GraphicPrompt):
    def validate(self):
        return True


class NecklaceNAFCPage(ModularPage):
    def __init__(
        self,
        label: str,
        prompt: str,
        necklace_states: List[List[int]],
        color_options: List[str],
        time_estimate=10,
    ):
        self.color_options = color_options
        self.necklace_states = necklace_states

        super().__init__(
            label,
            prompt=CustomGraphicPrompt(
                text=prompt,
                dimensions=[640, 480],
                viewport_width=0.7,
                frames=[
                    Frame(
                        self.create_necklace_array(
                            px=150,
                            py=100,
                            size=20,
                            spacing=41,
                            vertical_spacing=75,
                            necklace_states=necklace_states,
                            color_options=color_options,
                            interactive=False,
                        ),
                        activate_control_submit=False,
                    )
                ],
                prevent_control_submit=True,
            ),
            time_estimate=time_estimate,
            bot_response=lambda: random.choice(range(len(self.necklace_states))),
        )

    def format_answer(self, raw_answer, **kwargs):
        chosen_necklace_id = int(raw_answer["clicked_object"].split("_")[1])
        return chosen_necklace_id

    def create_necklace(
        self, px, py, size, spacing, coloring, color_options, necklace_id, interactive
    ):
        translation = 0
        necklace = []
        for i in range(len(coloring)):
            necklace = necklace + [
                NecklaceCircle(
                    id_=necklace_id + "_circle_" + str(i),
                    x=px + translation,
                    y=py,
                    radius=size,
                    color_options=color_options,
                    initial_color=coloring[i],
                    interactive=interactive,
                )
            ]
            translation += spacing
        return necklace

    def create_necklace_array(
        self, necklace_states, vertical_spacing, px, py, **kwargs
    ):
        translation = 0
        necklace_array = []
        for i in range(len(necklace_states)):
            necklace_array = necklace_array + self.create_necklace(
                necklace_id="necklace_" + str(i),
                px=px,
                py=py + translation,
                coloring=necklace_states[i],
                **kwargs,
            )
            translation += vertical_spacing
        return necklace_array


class NecklaceInteractivePage(ModularPage):
    def __init__(
        self,
        label: str,
        prompt: str,
        necklace_state,
        color_options: List[str],
        time_estimate=10,
    ):
        self.color_options = color_options
        self.necklace_state = necklace_state

        super().__init__(
            label,
            prompt=GraphicPrompt(
                text=prompt,
                dimensions=[640, 480],
                viewport_width=0.7,
                frames=[
                    Frame(
                        self.create_necklace(
                            necklace_id="necklace",
                            px=140,
                            py=150,
                            size=20,
                            spacing=41,
                            coloring=necklace_state,
                            color_options=color_options,
                            interactive=True,
                        )
                    )
                ],
            ),
            time_estimate=time_estimate,
            bot_response=lambda: random.choice(range(len(COLOR_OPTIONS))),
        )

    def format_answer(self, raw_answer, **kwargs):
        chosen_state = [None for _ in range(len(raw_answer.keys()))]
        for key in raw_answer.keys():
            idx = int(key.split("_")[2])
            chosen_state[idx] = raw_answer[key]["color_index"]
        return chosen_state

    def create_necklace(
        self, px, py, size, spacing, coloring, color_options, necklace_id, interactive
    ):
        translation = 0
        necklace = []
        for i in range(len(coloring)):
            necklace = necklace + [
                NecklaceCircle(
                    id_=necklace_id + "_circle_" + str(i),
                    x=px + translation,
                    y=py,
                    radius=size,
                    color_options=color_options,
                    initial_color=coloring[i],
                    interactive=interactive,
                )
            ]
            translation += spacing
        return necklace


class CustomTrial(GraphChainTrial):
    accumulate_answers = True
    time_estimate = 20

    def show_trial(self, experiment, participant):
        options = [option["content"] for option in self.definition]

        page_1 = NecklaceNAFCPage(
            label="choose",
            prompt="Choose the necklace which you like most.",
            necklace_states=options,
            color_options=COLOR_OPTIONS,
        )

        page_2 = NecklaceInteractivePage(
            label="reproduce",
            prompt="Recolor the present necklace like the necklace you just chose.",
            necklace_state=CustomNode.generate_class_seed(),
            color_options=COLOR_OPTIONS,
        )

        return [page_1, page_2]


class CustomNode(GraphChainNode):
    @staticmethod
    def generate_class_seed():
        return [
            random.randint(0, len(COLOR_OPTIONS) - 1) for i in range(NECKLACE_LENGTH)
        ]

    def summarize_trials(self, trials: list, experiment, participant):
        answers = np.array([trial.answer["reproduce"] for trial in trials])
        summary = stats.mode(answers)
        return summary.mode.flatten().tolist()


class CustomTrialMaker(GraphChainTrialMaker):
    """
    This TrialMaker implements a square lattice graph of dimensions grid_dimension x grid_dimension
    """

    response_timeout_sec = 60
    check_timeout_interval_sec = 30

    def __init__(
        self,
        *,
        id_,
        node_class,
        trial_class,
        grid_dimension: int,
        chain_type: str,
        expected_trials_per_participant: int,
        max_trials_per_participant: int,
        chains_per_participant: Optional[int],
        trials_per_node: int,
        balance_across_chains: bool,
        check_performance_at_end: bool,
        check_performance_every_trial: bool,
        recruit_mode: str,
        target_n_participants=Optional[int],
        max_nodes_per_chain: Optional[int] = None,
        fail_trials_on_premature_exit: bool = False,
        fail_trials_on_participant_performance_check: bool = False,
        propagate_failure: bool = True,
        n_repeat_trials: int = 0,
        wait_for_networks: bool = False,
        allow_revisiting_networks_in_across_chains: bool = False,
    ):
        network_structure = self.generate_grid(grid_dimension)
        super().__init__(
            id_=id_,
            node_class=node_class,
            trial_class=trial_class,
            network_structure=network_structure,
            chain_type=chain_type,
            expected_trials_per_participant=expected_trials_per_participant,
            max_trials_per_participant=max_trials_per_participant,
            chains_per_participant=chains_per_participant,
            trials_per_node=trials_per_node,
            balance_across_chains=balance_across_chains,
            check_performance_at_end=check_performance_at_end,
            check_performance_every_trial=check_performance_every_trial,
            recruit_mode=recruit_mode,
            target_n_participants=target_n_participants,
            max_nodes_per_chain=max_nodes_per_chain,
            fail_trials_on_premature_exit=fail_trials_on_premature_exit,
            fail_trials_on_participant_performance_check=fail_trials_on_participant_performance_check,
            propagate_failure=propagate_failure,
            n_repeat_trials=n_repeat_trials,
            wait_for_networks=wait_for_networks,
            allow_revisiting_networks_in_across_chains=allow_revisiting_networks_in_across_chains,
        )

    def generate_grid(self, size):
        vertices = []
        edges = []
        for r in range(size):
            for c in range(size):
                v = int(np.ravel_multi_index([r, c], [size, size]))
                vertices.append(v)
                if r > 0:
                    upper_neighbour = int(
                        np.ravel_multi_index([r - 1, c], [size, size])
                    )
                    edges.append(
                        {
                            "origin": v,
                            "target": upper_neighbour,
                            "properties": {"type": "default"},
                        }
                    )
                    edges.append(
                        {
                            "origin": upper_neighbour,
                            "target": v,
                            "properties": {"type": "default"},
                        }
                    )
                if c < size - 1:
                    right_neighbour = int(
                        np.ravel_multi_index([r, c + 1], [size, size])
                    )
                    edges.append(
                        {
                            "origin": v,
                            "target": right_neighbour,
                            "properties": {"type": "default"},
                        }
                    )
                    edges.append(
                        {
                            "origin": right_neighbour,
                            "target": v,
                            "properties": {"type": "default"},
                        }
                    )
        return {"vertices": vertices, "edges": edges}


##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "Graph demo"

    timeline = Timeline(
        MainConsent(),
        InfoPage(
            Markup(
                """
            <p>
            This experiment implements a simple task on a square lattice.
            This is done by specifying an approppriate dictionary of edges and vertices which in
            turn is passed to <code>GraphChainTrialMaker</code> through <code>network_structure</code>.
            The dictionary should take the following form:
            </p>
            <code>
            {
                "vertices": [1,2],
                "edges": [{"origin": 1, "target": 2, "properties": {"type": "default"}}]
            }
            </code>
        """
            ),
            time_estimate=10,
        ),
        InfoPage(
            Markup(
                """
            The task itself consists of choosing a stimulus from one of your neighbours
            on the lattice and replicating it.
        """
            ),
            time_estimate=5,
        ),
        InfoPage("Let's begin!", time_estimate=3),
        CustomTrialMaker(
            id_="graph_demo",
            trial_class=CustomTrial,
            node_class=CustomNode,
            grid_dimension=3,
            chain_type="across",
            max_nodes_per_chain=5,
            expected_trials_per_participant=9,
            max_trials_per_participant=9,
            chains_per_participant=None,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="n_trials",
            target_n_participants=None,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

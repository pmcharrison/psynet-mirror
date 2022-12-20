# pylint: disable=unused-import,abstract-method,unused-argument,no-member

##########################################################################################
# About
##########################################################################################

# This is a version of the Gibbs demo that introduces failing of asynchronous
# processes on various nodes and trials. It is intended to demonstrate the
# pruning processes by which PsyNet copes with these failures. Try taking the experiment
# as a few participants then inspecting the monitor route.

##########################################################################################
# Imports
##########################################################################################

import random
import time
from typing import List, Union

from flask import Markup

import psynet.experiment
from psynet.bot import Bot
from psynet.consent import NoConsent
from psynet.experiment import scheduled_task
from psynet.modular_page import SliderControl
from psynet.page import InfoPage, ModularPage, Prompt, SuccessfulEndPage
from psynet.process import WorkerAsyncProcess
from psynet.timeline import Timeline
from psynet.trial.gibbs import GibbsNetwork, GibbsNode, GibbsTrial, GibbsTrialMaker
from psynet.utils import get_logger

logger = get_logger()

TARGETS = ["tree", "rock", "carrot", "banana"]
COLORS = ["red", "green", "blue"]


class ColorSliderPage(ModularPage):
    def __init__(
        self,
        label: str,
        prompt: Union[str, Markup],
        selected_idx: int,
        starting_values: List[int],
        reverse_scale: bool,
        directional: bool,
        time_estimate=None,
        **kwargs,
    ):
        assert selected_idx >= 0 and selected_idx < len(COLORS)
        self.prompt = prompt
        self.selected_idx = selected_idx
        self.starting_values = starting_values

        not_selected_idxs = list(range(len(COLORS)))
        not_selected_idxs.remove(selected_idx)
        not_selected_colors = [COLORS[i] for i in not_selected_idxs]
        not_selected_values = [starting_values[i] for i in not_selected_idxs]
        hidden_inputs = dict(zip(not_selected_colors, not_selected_values))
        kwargs["template_arg"] = {
            "hidden_inputs": hidden_inputs,
        }
        super().__init__(
            label=label,
            prompt=Prompt(prompt),
            control=SliderControl(
                start_value=starting_values[selected_idx],
                min_value=0,
                max_value=255,
                slider_id=COLORS[selected_idx],
                reverse_scale=reverse_scale,
                directional=directional,
                template_filename="color-slider.html",
                template_args={
                    "hidden_inputs": hidden_inputs,
                },
            ),
            time_estimate=time_estimate,
        )

    def metadata(self, **kwargs):
        return {
            "prompt": self.prompt.metadata,
            "selected_idx": self.selected_idx,
            "starting_values": self.starting_values,
        }


class CustomNetwork(GibbsNetwork):
    def make_definition(self):
        return {"target": self.balance_across_networks(TARGETS)}

    # Minimal example of an async_post_grow_network function
    run_async_post_grow_network = True

    def async_post_grow_network(self):
        logger.info(
            "Running custom async_post_grow_network function (network id = %i)", self.id
        )
        if self.n_alive_nodes > 1:
            if self.head.id % 3 == 0:
                assert False
            elif self.head.id % 4 == 0:
                import time

                time.sleep(1e6)


class CustomTrial(GibbsTrial):
    # If True, then the starting value for the free parameter is resampled
    # on each trial.
    resample_free_parameter = True

    time_estimate = 5

    def show_trial(self, experiment, participant):
        target = self.network.definition["target"]
        prompt = Markup(
            "Adjust the slider to match the following word as well as possible: "
            f"<strong>{target}</strong>"
        )
        return ColorSliderPage(
            "color_trial",
            prompt,
            starting_values=self.initial_vector,
            selected_idx=self.active_index,
            reverse_scale=self.reverse_scale,
            directional=False,
            time_estimate=self.time_estimate,
        )

    def show_feedback(self, experiment, participant):
        if self.failed:
            prompt = "Trial failed."
        else:
            prompt = "Trial was successful."

        return InfoPage(prompt, time_estimate=5)

    # Minimal example of an async_post_trial function
    run_async_post_trial = True

    def async_post_trial(self):
        logger.info("Running custom async post trial (id = %i)", self.id)
        if self.id % 3 == 0:
            assert False
        elif self.id % 4 == 0:
            import time

            time.sleep(1e6)

    def expensive_computation(self, seed):
        """
        This is a silly example of how one might define an expensive computation to be
        run asynchronously on ``Trial`` objects. Have a look at the ``scheduled_task`` definition
        in the ``Experiment`` class below to see how this is invoked.

        Parameters
        ----------

        seed:
            The input number to process.

        Returns
        -------

        Nothing; the output is instead saved in ``self.var.computation_output``.

        """
        time.sleep(0.5)
        self.var.computation_output = seed + 1


class CustomNode(GibbsNode):
    vector_length = 3

    def random_sample(self, i):
        return random.randint(0, 255)


class CustomTrialMaker(GibbsTrialMaker):
    give_end_feedback_passed = True
    performance_threshold = -1.0
    async_timeout_sec = 5
    check_timeout_interval_sec = 5
    give_end_feedback_passed = False


trial_maker = CustomTrialMaker(
    id_="async_pruning",
    network_class=CustomNetwork,
    trial_class=CustomTrial,
    node_class=CustomNode,
    chain_type="across",  # can be "within" or "across"
    expected_trials_per_participant=4,
    max_trials_per_participant=4,
    max_nodes_per_chain=5,  # note that the final node receives no trials
    chains_per_participant=None,  # set to None if chain_type="across"
    chains_per_experiment=4,  # set to None if chain_type="within"
    trials_per_node=1,
    balance_across_chains=True,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    propagate_failure=False,
    recruit_mode="n_participants",
    target_n_participants=10,
)

##########################################################################################
# Experiment
##########################################################################################


# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    label = "Asynchronous pruning demo"

    timeline = Timeline(
        NoConsent(),
        trial_maker,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)

        # Change this if you want to simulate multiple simultaneous participants.
        self.initial_recruitment_size = 1

    @scheduled_task("interval", minutes=1, max_instances=1)
    @staticmethod
    def add_random_var_to_trials():
        trials = CustomTrial.query.all()
        for t in trials:
            if not t.awaiting_async_process and not t.failed:
                # Often it's wise to make sure that the trial isn't already waiting
                # for a pre-existing asynchronous process to complete.
                # One might implement more complex checks here, for example only running the
                # task for trials that have already received a response from the participant.
                WorkerAsyncProcess(
                    function=CustomTrial.expensive_computation,
                    arguments={
                        "seed": random.randint(0, 10),
                    },
                )

    def test_check_bot(self, bot: Bot, **kwargs):
        trials = bot.all_trials
        trials.sort(key=lambda x: x.id)

        assert not trials[0].failed
        assert not trials[1].failed

        assert trials[2].failed
        assert trials[2].failed_reason.startswith(
            "Exception in asynchronous process: AssertionError"
        )

        assert trials[3].failed
        assert trials[3].failed_reason.startswith(
            "Exception in asynchronous process: JobTimeoutException"
        )

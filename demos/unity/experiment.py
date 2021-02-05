import json
import random

import psynet.experiment
from psynet.timeline import Timeline, CodeBlock
from psynet.page import (
    SuccessfulEndPage,
    UnityPage,
)
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.trial.non_adaptive import (
    NonAdaptiveTrialMaker,
    NonAdaptiveTrial,
    StimulusSet,
    StimulusSpec,
)

import logging
logger = logging.getLogger()


##########################################################################################
#### Stimuli
##########################################################################################
Debug = False
number_of_islands = 1  # How many islands to visit in each world
number_of_islands_final = 1  # How many islands to visit in the final world

# Permutations of colors
permutations = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]]

all_colors = ["red", "green", "yellow"]
all_types = [0, 1, 2]
all_rates = [0, 50, 100]


# Definition of network
stimulus_set = StimulusSet(
    "islands",
    [
        StimulusSpec(definition={"mtype": mtype}, phase="train")
        for mtype in all_types
    ],
)


stimulus_set_final = StimulusSet(
    "final_islands",
    [
        StimulusSpec(
            definition={"mtype": mtype},
            phase="experiment",
        )
        for mtype in all_types
    ],
)


class UnityIslandPage(UnityPage):
    def __init__(self, contents, session_id):
        self.title = "Unity Demo – Ferry Game"
        self.game_container_width = "960px"
        self.game_container_height = "600px"
        self.resources = "/static"
        self.time_estimate = 5
        self.debug = Debug
        self.contents = contents
        self.session_id = session_id

        super().__init__(
            title=self.title,
            resources=self.resources,
            contents=self.contents,
            session_id=self.session_id,
            debug=self.debug,
        )

    def format_answer(self, raw_answer, **kwargs):
        # Handle Unity answer
        logger.info("----------------- format answer -----------------")
        logger.info(raw_answer)

        return raw_answer


# A trial has several pages. Each island is a page. All islands are in one trial.
class IslandTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "island_trial"}
    num_pages = number_of_islands
    accumulate_answers = True

    # How we build the series of islands
    def show_trial(self, experiment, participant):
        network_content = self.definition
        mtype = int(network_content["mtype"])

        # Map type to a permutation that depends only on particpant number
        my_perm = participant.var.color_permutation

        # Save permutation in code for debugging and good practices
        participant.var.set("permutation", my_perm)

        # Based on type define variables that determine Unity behaviour.
        dashboard_rate = all_rates[mtype]
        feedback_rate = all_rates[mtype]

        # Use the participant specific permutation to determine color
        island_color = my_perm[mtype]

        # Prepare data for JSON
        data = {
            "dashboard_rate": dashboard_rate,
            "feedback_rate": feedback_rate,
            "island_color": island_color,
        }

        # Convert dictionary into a string as Unity wants the data as a string
        data_as_json = json.dumps(data)
        page = UnityIslandPage(
            # Send this string to Unity
            contents=data_as_json,
            # We stay in the same session. '* 1000' is not important for now
            session_id=str(participant.id * 1000),
        )
        list_of_pages = [page] * (self.num_pages)
        return list_of_pages



class FinalIslandTrial(NonAdaptiveTrial):
    __mapper_args__ = {"polymorphic_identity": "final_island_trial"}
    num_pages = number_of_islands_final
    accumulate_answers = True

    # How we build the series of islands
    def show_trial(self, experiment, participant):
        network_content = self.definition
        mtype = int(network_content["mtype"])

        # Map type to a permutation that depends only on particpant number
        my_perm = participant.var.color_permutation

        # Based on type define variables that determine Unity behaviour.
        dashboard_rate = all_rates[mtype]
        feedback_rate = all_rates[mtype]

        # Use the participant's choice for the final world
        island_color = my_perm.index(participant.var.final_world)

        # Prepare data for JSON
        data = {
            "dashboard_rate": dashboard_rate,
            "feedback_rate": feedback_rate,
            "island_color": island_color,
        }

        # Convert dictionary into a string as Unity wants the data as a string
        data_as_json = json.dumps(data)
        logger.info(f'Final island is: {participant.var.final_world}')
        page = UnityIslandPage(
            contents=data_as_json,
            session_id=str(participant.id * 1000),
        )
        list_of_pages = [page] * (self.num_pages)
        return list_of_pages


class IslandTrialMaker(NonAdaptiveTrialMaker):
    response_timeout_sec = 1000

    def compute_bonus(self, score, passed):
        bonus = score / 100
        logger.info(f"Accumulated score: {bonus}")
        return bonus

    def performance_check(self, experiment, participant, participant_trials):
        """
        Should return a tuple (score: float, passed: bool)
        """
        score = 0
        for trial in participant_trials:
            for answer in trial.answer:
                data = json.loads(answer)
                number_of_coins_in_trial = len(data["coins"])
                score = score + number_of_coins_in_trial

        logger.info(f"Accumulated score: {score}")
        passed = True

        return {"score": score, "passed": passed}


trial_maker = IslandTrialMaker(
    id_="Islands",
    trial_class=IslandTrial,
    phase="train",
    stimulus_set=stimulus_set,
    time_estimate_per_trial=3,
    max_trials_per_block=3,
    allow_repeated_stimuli=False,
    max_unique_stimuli_per_block=None,
    active_balancing_within_participants=True,
    active_balancing_across_participants=False,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    target_num_participants=1,
    target_num_trials_per_stimulus=None,
    recruit_mode="num_participants",
    num_repeat_trials=0,
)


final_trial_maker = IslandTrialMaker(
    id_="FinalIslands",
    trial_class=FinalIslandTrial,
    phase="experiment",
    stimulus_set=stimulus_set_final,
    time_estimate_per_trial=3,
    max_trials_per_block=1,
    allow_repeated_stimuli=False,
    max_unique_stimuli_per_block=None,
    active_balancing_within_participants=True,
    active_balancing_across_participants=False,
    check_performance_at_end=True,
    check_performance_every_trial=False,
    target_num_participants=1,
    target_num_trials_per_stimulus=None,
    recruit_mode="num_participants",
    num_repeat_trials=0,
)

##########################################################################################
#### Experiment
##############################################################wqsdQWDQWdqwdqwd############################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).
class Exp(psynet.experiment.Experiment):
    consent_audiovisual_recordings = False

    timeline = Timeline(
        CodeBlock(
            lambda participant: participant.var.set(
                "color_permutation", random.sample(permutations, 1)[0]
            )
        ),
        trial_maker,
        ModularPage(
            "choose_world",
            "In which world do you want to play for the rest of the game?",
            control=PushButtonControl(["0", "1", "2"]),
            time_estimate=5,
        ),
        CodeBlock(
            lambda participant: participant.var.set("final_world", int(participant.answer))
        ),
        final_trial_maker,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1


extra_routes = Exp().extra_routes()

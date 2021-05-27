# pylint: disable=unused-import,abstract-method

import logging
import random
from typing import List, Optional

import psynet.experiment
from psynet.page import SuccessfulEndPage, UnityPage
from psynet.timeline import CodeBlock, Timeline
from psynet.trial.static import StaticTrial, StaticTrialMaker, StimulusSet, StimulusSpec

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


##########################################################################################
#    Stimuli
##########################################################################################
DEBUG = False
NUMBER_OF_ISLANDS = 1  # How many islands to visit in each world
NUMBER_OF_FINAL_ISLANDS = 2  # How many islands to visit in each world

# Permutations of colors
POSSIBLE_WORLD_ORDERS = [
    [0, 1, 2],
    [0, 2, 1],
    [1, 0, 2],
    [1, 2, 0],
    [2, 0, 1],
    [2, 1, 0],
]

POSSIBLE_COLORS = ["red", "green", "yellow"]
WORLD_IDS = [0, 1, 2]
WORLD_FEEDBACK_RATES = [0, 50, 100]

SAME_SESSION_ID = "0"


# Definition of network
stimulus_set_initial = StimulusSet(
    "islands",
    [
        StimulusSpec(definition={"world_id": world_id}, phase="train")
        for world_id in WORLD_IDS
    ],
)


stimulus_set_final = StimulusSet(
    "final_islands",
    [
        StimulusSpec(
            definition={"world_id": world_id},
            phase="experiment",
            participant_group="{}".format(world_id),
        )
        for world_id in WORLD_IDS
    ],
)


class UnityIslandPage(UnityPage):
    def __init__(
        self,
        contents: dict,
        session_id: str,
        time_estimate: Optional[float] = None,
        **kwargs,
    ):

        super().__init__(
            title="Unity - FerryGov",
            resources="/static",
            contents=contents,
            session_id=session_id,
            debug=DEBUG,
            time_estimate=time_estimate,
            game_container_width="960px",
            game_container_height="600px",
        )

    def format_answer(self, raw_answer, **kwargs):
        logger.info("----------------- format answer -----------------")
        logger.info(raw_answer)

        return raw_answer


class UnityQuestionPage(UnityPage):
    def __init__(
        self,
        question: str,
        options: List[str],
        session_id: str,
        time_estimate: Optional[float] = None,
        **kwargs,
    ):
        contents = {"question": question, "options": options}
        super().__init__(
            title="Unity - FerryGov: question",
            resources="/static",
            contents=contents,
            session_id=session_id,
            debug=DEBUG,
            time_estimate=time_estimate,
            game_container_width="960px",
            game_container_height="600px",
        )

    def format_answer(self, raw_answer, **kwargs):
        return raw_answer["answer"]


# In this case the trial comprises multiple pages, each corresponding to an island.
class IslandTrial(StaticTrial):
    __mapper_args__ = {"polymorphic_identity": "island_trial"}
    num_pages = NUMBER_OF_ISLANDS
    accumulate_answers = True

    def show_trial(self, experiment, participant):
        network_content = self.definition
        world_id = int(network_content["world_id"])

        my_perm = participant.var.color_permutation

        dashboard_rate = WORLD_FEEDBACK_RATES[world_id]
        feedback_rate = WORLD_FEEDBACK_RATES[world_id]

        data = {
            "dashboard_rate": dashboard_rate,
            "feedback_rate": feedback_rate,
            "island_color": self.get_island_color(
                my_perm=my_perm, world_id=world_id, participant=participant
            ),
        }

        page = UnityIslandPage(
            contents=data, session_id=SAME_SESSION_ID, time_estimate=5
        )

        list_of_pages = [page] * self.num_pages
        return list_of_pages

    def get_island_color(self, **kwargs):
        return kwargs["my_perm"][kwargs["world_id"]]


class FinalIslandTrial(IslandTrial):
    __mapper_args__ = {"polymorphic_identity": "final_island_trial"}
    num_pages = NUMBER_OF_FINAL_ISLANDS

    def get_island_color(self, **kwargs):
        return kwargs["participant"].get_participant_group("FinalIslands")


class IslandTrialMaker(StaticTrialMaker):
    response_timeout_sec = 1000

    def compute_bonus(self, score, passed):
        return score / 100

    def performance_check(self, experiment, participant, participant_trials):
        """
        Should return a tuple (score: float, passed: bool)
        """
        score = 1
        for trial in participant_trials:
            for answer in trial.answer:
                data = answer
                number_of_coins_in_trial = len(data["coins"])
                score += number_of_coins_in_trial
        passed = True

        return {"score": score, "passed": passed}


trial_maker = IslandTrialMaker(
    id_="Islands",
    trial_class=IslandTrial,
    phase="train",
    stimulus_set=stimulus_set_initial,
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
# Experiment
##########################################################################################

# Weird bug: if you instead import Experiment from psynet.experiment,
# Dallinger won't allow you to override the bonus method
# (or at least you can override it but it won't work).


class Exp(psynet.experiment.Experiment):
    timeline = Timeline(
        CodeBlock(
            lambda participant: participant.var.set(
                "color_permutation", random.sample(POSSIBLE_WORLD_ORDERS, 1)[0]
            )
        ),
        trial_maker,
        # Use this to have question inside Unity:
        UnityQuestionPage(
            "Choose world?", ["0", "1", "2"], SAME_SESSION_ID, time_estimate=5
        ),
        # Uncomment below code to have a Psynet question page:
        # from psynet.modular_page import ModularPage, Prompt, PushButtonControl
        # ModularPage(
        #     "choose_world",
        #     Prompt("In which world do you want to play for the rest of the game?"),
        #     control=PushButtonControl(["0", "1", "2"]),
        #     time_estimate=5,
        # ),
        CodeBlock(
            lambda participant: participant.set_participant_group(
                "FinalIslands", participant.answer
            )
        ),
        final_trial_maker,
        SuccessfulEndPage(),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

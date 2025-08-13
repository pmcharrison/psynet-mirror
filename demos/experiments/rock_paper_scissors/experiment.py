from typing import List

from dominate import tags

import psynet.experiment
from psynet.bot import BotDriver, advance_past_wait_pages
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage
from psynet.participant import Participant
from psynet.sync import GroupBarrier, SimpleGrouper
from psynet.timeline import Timeline, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.utils import get_logger

logger = get_logger()


class RockPaperScissorsTrialMaker(StaticTrialMaker):
    pass


class RockPaperScissorsTrial(StaticTrial):
    time_estimate = 5
    accumulate_answers = True

    def show_trial(self, experiment, participant):
        return join(
            GroupBarrier(
                id_="wait_for_trial",
                group_type="rock_paper_scissors",
            ),
            self.choose_action(color=self.definition["color"]),
            GroupBarrier(
                id_="finished_trial",
                group_type="rock_paper_scissors",
                on_release=self.score_trial,
            ),
        )

    def choose_action(self, color):
        prompt = tags.p("Choose your action:", style=f"color: {color};")
        return ModularPage(
            "choose_action",
            prompt,
            PushButtonControl(
                choices=["rock", "paper", "scissors"],
            ),
            time_estimate=5,
            save_answer="last_action",
            # extras=ChatRoom(),
        )

    def show_feedback(self, experiment, participant):
        score = participant.var.last_trial["score"]
        if score == -1:
            outcome = "You lost."
        elif score == 0:
            outcome = "You drew."
        else:
            assert score == 1
            outcome = "You won!"

        prompt = (
            f"You chose {participant.var.last_trial['action_self']}, "
            + f"your partner chose {participant.var.last_trial['action_other']}. "
            + outcome
        )

        return InfoPage(
            prompt,
            time_estimate=5,
        )

    def score_trial(self, participants: List[Participant]):
        assert len(participants) == 2
        answers = [participant.var.last_action for participant in participants]
        score_0 = self.scoring_matrix[answers[0]][answers[1]]
        score_1 = -score_0
        participants[0].var.last_trial = {
            "action_self": answers[0],
            "action_other": answers[1],
            "score": score_0,
        }
        participants[1].var.last_trial = {
            "action_self": answers[1],
            "action_other": answers[0],
            "score": score_1,
        }

    scoring_matrix = {
        "rock": {
            "rock": 0,
            "paper": -1,
            "scissors": 1,
        },
        "paper": {
            "rock": 1,
            "paper": 0,
            "scissors": -1,
        },
        "scissors": {"rock": -1, "paper": 1, "scissors": 0},
    }


class Exp(psynet.experiment.Experiment):
    label = "Rock paper scissors demo"

    initial_recruitment_size = 1

    timeline = Timeline(
        SimpleGrouper(
            group_type="rock_paper_scissors",
            initial_group_size=2,
        ),
        RockPaperScissorsTrialMaker(
            id_="rock_paper_scissors",
            trial_class=RockPaperScissorsTrial,
            nodes=[
                StaticNode(definition={"color": color})
                for color in ["red", "green", "blue"]
            ],
            expected_trials_per_participant=3,
            max_trials_per_participant=3,
            sync_group_type="rock_paper_scissors",
        ),
    )

    test_n_bots = 2
    test_mode = "serial"

    def test_serial_run_bots(self, bots: List[BotDriver]):
        advance_past_wait_pages(bots)

        assert bots[0].current_page_label == "choose_action"
        bots[0].take_page(response="rock")
        assert bots[0].current_page_label == "wait"

        assert bots[1].current_page_label == "choose_action"
        bots[1].take_page(response="paper")

        advance_past_wait_pages(bots)

        assert (
            bots[0].current_page_text
            == "You chose rock, your partner chose paper. You lost."
        )
        assert (
            bots[1].current_page_text
            == "You chose paper, your partner chose rock. You won!"
        )

        bots[0].take_page()
        bots[1].take_page()
        advance_past_wait_pages(bots)

        bots[0].take_page(response="scissors")
        bots[1].take_page(response="paper")
        advance_past_wait_pages(bots)

        assert (
            bots[0].current_page_text
            == "You chose scissors, your partner chose paper. You won!"
        )
        assert (
            bots[1].current_page_text
            == "You chose paper, your partner chose scissors. You lost."
        )

        bots[0].take_page()
        bots[1].take_page()
        advance_past_wait_pages(bots)

        bots[0].take_page(response="scissors")
        bots[1].take_page(response="scissors")
        advance_past_wait_pages(bots)

        assert (
            bots[0].current_page_text
            == "You chose scissors, your partner chose scissors. You drew."
        ), (
            "A rare error sometimes occurs here. If you see it, please report it to Peter Harrison (pmcharrison) for "
            "further debugging."
        )
        assert (
            bots[1].current_page_text
            == "You chose scissors, your partner chose scissors. You drew."
        ), (
            "A rare error sometimes occurs here. If you see it, please report it to Peter Harrison (pmcharrison) for "
            "further debugging."
        )

        bots[0].take_page()
        bots[1].take_page()
        advance_past_wait_pages(bots)

        assert "That's the end of the experiment!" in bots[0].current_page_text
        assert "That's the end of the experiment!" in bots[1].current_page_text

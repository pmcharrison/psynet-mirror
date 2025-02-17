# pylint: disable=unused-import,abstract-method,unused-argument

# This is a clone of the imitation_chain demo,
# but with automatic bots that contribute data to the experiment.


import random
import re
import time
from statistics import mean

import psynet.experiment
from psynet.bot import Bot
from psynet.experiment import scheduled_task
from psynet.modular_page import ModularPage, Prompt, TextControl
from psynet.page import InfoPage
from psynet.timeline import FailedValidation, Timeline
from psynet.trial.imitation_chain import (
    ImitationChainNode,
    ImitationChainTrial,
    ImitationChainTrialMaker,
)
from psynet.utils import get_logger

logger = get_logger()


class FixedDigitInputPage(ModularPage):
    def __init__(
        self, label: str, prompt: str, time_estimate: float, correct_answer: int
    ):
        self.n_digits = 7

        super().__init__(
            label,
            Prompt(prompt),
            control=TextControl(
                block_copy_paste=True,
                bot_response=lambda bot: (
                    correct_answer
                    if bot.var.is_good_participant
                    else random.randint(0, 9999999)
                ),
            ),
            time_estimate=time_estimate,
        )

    def format_answer(self, raw_answer, **kwargs):
        try:
            pattern = re.compile("^[0-9]*$")
            assert len(raw_answer) == self.n_digits
            assert pattern.match(raw_answer)
            return int(raw_answer)
        except (ValueError, AssertionError):
            return "INVALID_RESPONSE"

    def validate(self, response, **kwargs):
        if response.answer == "INVALID_RESPONSE":
            return FailedValidation("Please enter a 7-digit number.")
        return None


class CustomTrial(ImitationChainTrial):
    time_estimate = 2 + 3

    def show_trial(self, experiment, participant):
        page_1 = InfoPage(
            f"Try to remember this 7-digit number: {self.definition:07d}",
            time_estimate=2,
        )
        page_2 = FixedDigitInputPage(
            "number",
            "What was the number?",
            time_estimate=3,
            correct_answer=self.definition,
        )

        return [page_1, page_2]


class CustomNode(ImitationChainNode):
    def create_initial_seed(self, experiment, participant):
        return random.randint(0, 9999999)

    def summarize_trials(self, trials: list, experiment, participant):
        return round(mean([trial.answer for trial in trials]))


class CustomTrialMaker(ImitationChainTrialMaker):
    response_timeout_sec = 60
    check_timeout_interval_sec = 30


class Exp(psynet.experiment.Experiment):
    label = "Bot demo (2)"

    timeline = Timeline(
        CustomTrialMaker(
            id_="imitation_demo",
            trial_class=CustomTrial,
            node_class=CustomNode,
            chain_type="within",
            max_nodes_per_chain=5,
            expected_trials_per_participant=5,
            max_trials_per_participant=5,
            chains_per_participant=1,
            chains_per_experiment=None,
            trials_per_node=1,
            balance_across_chains=True,
            check_performance_at_end=False,
            check_performance_every_trial=False,
            recruit_mode="n_participants",
            target_n_participants=10,
        ),
        InfoPage("You finished the experiment!", time_estimate=0),
    )

    def __init__(self, session=None):
        super().__init__(session)
        self.initial_recruitment_size = 1

    @staticmethod
    @scheduled_task("interval", seconds=10, max_instances=1)
    def run_bot_participant():
        # Every 10 seconds, runs a bot participant.
        from psynet.experiment import is_experiment_launched

        if is_experiment_launched():
            bot = Bot()
            bot.take_experiment()

    def initialize_bot(self, bot):
        bot.var.is_good_participant = random.sample([True, False], 1)[0]

    def test_experiment(self):
        from psynet.experiment import ExperimentStatus, Request

        super().test_experiment()
        all_requests = Request.query.all()
        assert len(all_requests) > 0
        assert all(
            [request.duration < 1 for request in all_requests]
        ), "Some pages took more than 1 second to load."

        # The status reports only get logged every 10 seconds, so we need to wait a bit.
        time.sleep(12.5)

        all_status = ExperimentStatus.query.all()
        assert len(all_status) > 0

        status = all_status[-1]
        assert status.cpu_usage_pct is not None
        assert status.ram_usage_pct > 0
        assert status.free_disk_space_gb > 0

        # The below test is flakey, because summarize_resource_use skips variables that do not change
        # during the testing period.
        # It's therefore commented out for now.
        #
        # from psynet.dashboard.resources import summarize_resource_use
        #
        # data = summarize_resource_use()
        # different_types = [
        #     "CPU usage (%)",
        #     "Median page loading time (%)",
        #     "Number of page loads",
        #     "RAM usage (%)",
        #     "Used disk space compared to min (%)",
        # ]
        #
        # reported_types = sorted(set([item["type"] for item in data]))
        # assert (
        #     reported_types == different_types
        # ), f"Expected types: {different_types}, but got: {reported_types}"

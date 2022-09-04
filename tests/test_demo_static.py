import logging
import time
from collections import Counter

import pytest
from selenium.webdriver.common.by import By

from psynet.participant import Participant
from psynet.pytest_psynet import assert_text, bot_class, next_page, path_to_demo
from psynet.trial.static import StaticNetwork, StaticTrial, Stimulus

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("static")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_exp(self, bot_recruits, db_session, trial_maker):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            networks = StaticNetwork.query.filter_by(trial_maker_id="animals").all()
            stimuli = Stimulus.query.all()

            assert networks[0].type == "StaticNetwork"
            assert stimuli[0].type == "Stimulus"

            assert len(networks) == 3
            assert len(stimuli) == len(networks) * 4

            assert sorted([n.block for n in networks]) == ["A", "B", "C"]

            # Do you want to enable custom stimulus filters?
            next_page(driver, "No")

            assert_text(driver, "trial-position", "Trial 1")
            next_page(driver, "A little")

            trial = StaticTrial.query.filter_by(id=1).one()
            assert trial.answer == "A little"
            assert trial.type == "AnimalTrial"

            assert_text(driver, "trial-position", "Trial 2")

            next_page(driver, "Very much")
            trial = StaticTrial.query.filter_by(id=2).one()
            assert trial.answer == "Very much"
            assert_text(driver, "trial-position", "Trial 3")

            num_remaining_trials = 4
            n_repeat_trials = 3

            for _ in range(num_remaining_trials + n_repeat_trials):
                next_page(driver, "Very much")

            assert_text(
                driver,
                "main-body",
                "You finished the animal questions! Your score was 9. Next",
            )

            trials = StaticTrial.query.all()

            trials_by_block = Counter(
                [
                    trial.block
                    for trial in trials
                    if trial.participant_id == 1 and not trial.is_repeat_trial
                ]
            )
            assert list(trials_by_block.values()) == [2, 2, 2]  # 2 trials in each block

            trials_by_stimulus = Counter(
                [
                    trial.stimulus_id
                    for trial in trials
                    if trial.participant_id == 1 and not trial.is_repeat_trial
                ]
            )
            assert list(trials_by_stimulus.values()) == [
                1,
                1,
                1,
                1,
                1,
                1,
            ]  # no stimulus comes twice

            assert len([t for t in trials if t.is_repeat_trial]) == 3  # 3 repeat trials

            participant = Participant.query.filter_by(id=1).one()
            p_trials = trial_maker.get_participant_trials(participant=participant)

            completed_stimuli = trial_maker.get_completed_stimuli(participant)
            for counter in completed_stimuli.values():
                for id_ in counter.keys():
                    assert isinstance(id_, int)

            assert len(p_trials) == 9
            for t in p_trials:
                assert t.participant_id == 1
                assert t.trial_maker_id == "animals"
                assert t.time_credit_from_trial == 3
                assert t.time_taken > 0

            next_page(driver, "next-button")

            assert_text(
                driver,
                "main-body",
                """
                That\'s the end of the experiment! In addition to your base payment of $0.10,
                you will receive a bonus of $0.11 for the time you spent on the experiment.
                You have also been awarded a performance bonus of $9.00! Thank you for taking part.
                Please click "Finish" to complete the HIT. Finish
                """,
            )

            next_page(driver, "next-button", finished=True)

    def test_custom_filters(self, bot_recruits, db_session, trial_maker):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            # Do you want to enable custom stimulus filters?
            next_page(driver, "Yes")

            next_page(driver, "A little")
            next_page(driver, "Very much")

            # This part tests that the custom_stimulus_filter works appropriately -
            # the fact that the previous answer was "Very much" means that
            # the next question will be about ponies
            assert (
                driver.find_element(By.ID, "question").text
                == "How much do you like ponies?"
            )

            num_remaining_trials = 4
            n_repeat_trials = 3

            for _ in range(num_remaining_trials + n_repeat_trials):
                next_page(driver, "Very much")

            next_page(driver, "next-button")
            next_page(driver, "next-button", finished=True)

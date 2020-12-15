import os
import pytest
import logging
import time
import re

from collections import Counter
from psynet.test import bot_class, next_page
from psynet.trial.non_adaptive import NonAdaptiveNetwork, Stimulus, StimulusVersion, NonAdaptiveTrial
from psynet.participant import Participant

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None

# @pytest.fixture(scope="class")
# def exp_dir(root):
#     global EXPERIMENT_MODULE
#     os.chdir(os.path.join(os.path.dirname(__file__), "..", "demos/non_adaptive"))
#
#     import psynet.utils
#     EXPERIMENT_MODULE = psynet.utils.import_local_experiment().get("module")
#
#     yield
#     os.chdir(root)

@pytest.mark.usefixtures("demo_non_adaptive")
class TestExp():

    def test_exp(self, bot_recruits, db_session, trial_maker):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(0.2)

            networks = NonAdaptiveNetwork.query.all()
            stimuli = Stimulus.query.all()
            stimulus_versions = StimulusVersion.query.all()

            assert len(networks) == 3
            assert len(stimuli) == len(networks) * 4
            assert len(stimulus_versions) == len(stimuli) * 3

            assert stimulus_versions[0].__json__()["media_url"] is None

            assert sorted([n.block for n in networks]) == ["A", "B", "C"]

            assert driver.find_element_by_id("trial-position").text == "Trial 1"
            next_page(driver, "A little")

            trial = NonAdaptiveTrial.query.filter_by(id=1).one()
            assert trial.answer == "A little"

            assert driver.find_element_by_id("trial-position").text == "Trial 2"

            next_page(driver, "Very much")
            trial = NonAdaptiveTrial.query.filter_by(id=2).one()
            assert trial.answer == "Very much"
            assert driver.find_element_by_id("trial-position").text == "Trial 3"

            num_remaining_trials = 4
            num_repeat_trials = 3

            for _ in range(num_remaining_trials + num_repeat_trials):
                next_page(driver, "Very much")

            assert driver.find_element_by_id("main-body").text == "You finished the animal questions! Your score was 0.\nNext"

            trials = NonAdaptiveTrial.query.all()

            trials_by_block = Counter([
                trial.block for trial in trials
                if trial.participant_id == 1 and not trial.is_repeat_trial
            ])
            assert list(trials_by_block.values()) == [2, 2, 2] # 2 trials in each block

            trials_by_stimulus = Counter([
                trial.stimulus_id for trial in trials
                if trial.participant_id == 1 and not trial.is_repeat_trial
            ])
            assert list(trials_by_stimulus.values()) == [1, 1, 1, 1, 1, 1]  # no stimuli comes twice

            assert len([t for t in trials if t.is_repeat_trial]) == 3 # 3 repeat trials

            participant = Participant.query.filter_by(id=1).one()
            p_trials = trial_maker.get_participant_trials(participant=participant)

            completed_stimuli = trial_maker.get_completed_stimuli_in_phase(participant)
            for counter in completed_stimuli.values():
                for id_ in counter.keys():
                    assert isinstance(id_, int)

            assert len(p_trials) == 9
            for t in p_trials:
                assert t.participant_id == 1
                assert t.trial_maker_id == "animals"

            next_page(driver, "next_button")
            next_page(driver, "next_button", finished=True)

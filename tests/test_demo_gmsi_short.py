import os
import pytest
import re
import logging
import time

from psynet.participant import Participant, get_participant
from psynet.test import bot_class, next_page

PYTEST_BOT_CLASS = bot_class()

@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "../demos/demography/gmsi_short"))
    yield
    os.chdir(root)

@pytest.mark.usefixtures("exp_dir")
class TestExp(object):

    @pytest.fixture
    def demo(self, db_session):
        from psynet.demos.timeline.experiment import Exp

        instance = Exp(db_session)
        yield instance

    def test_exp_selenium(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver

            next_page(driver, "next_button")
            next_page(driver, "1")
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "voice")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "No")

            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == ["gmsi"]
            assert set(list(modules["gmsi"].keys())) == {"time_started", "time_finished"}
            assert len(modules["gmsi"]["time_started"]) == 1
            assert len(modules["gmsi"]["time_finished"]) == 1
            assert participant.started_modules == ["gmsi"]
            assert participant.finished_modules == ["gmsi"]
            assert participant.var.gmsi['mean_scores_per_scale'] == {
                'General': 2.866667,
                'Emotions': 4.2,
                'Start Age': 7.0,
                'Instrument': "voice",
                'Absolute Pitch': "No",
                'Musical Training': 2.4,
                'Active Engagement': 3.333333,
                'Singing Abilities': 3.5,
                'Perceptual Abilities': 4.0,
            }

            next_page(driver, "next_button", finished=True)

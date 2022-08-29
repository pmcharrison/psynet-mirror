import time

import pytest

from psynet.participant import get_participant
from psynet.pytest_psynet import bot_class, next_page

PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize(
    "experiment_directory", ["../demos/demography/gmsi"], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp(object):
    def test_exp(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "next-button")
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
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "guitar")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "19")
            next_page(driver, "Yes")

            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == ["gmsi"]
            assert set(list(modules["gmsi"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert len(modules["gmsi"]["time_started"]) == 1
            assert len(modules["gmsi"]["time_finished"]) == 1
            assert participant.started_modules == ["gmsi"]
            assert participant.finished_modules == ["gmsi"]
            assert participant.current_module_id == "gmsi"
            assert participant.var.gmsi["mean_scores_per_scale"] == {
                "General": 3.444444,
                "Emotions": 4.5,
                "Start Age": None,
                "Instrument": "guitar",
                "Absolute Pitch": "Yes",
                "Musical Training": 3.714286,
                "Active Engagement": 2.555556,
                "Singing Abilities": 2.857143,
                "Perceptual Abilities": 5.777778,
            }

            next_page(driver, "next-button", finished=True)

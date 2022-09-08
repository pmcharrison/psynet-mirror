import time

import pytest

from psynet.participant import get_participant
from psynet.pytest_psynet import bot_class, next_page, path_to_demo

PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("demography/gmsi_short")], indirect=True
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
            next_page(driver, "voice")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "5")
            next_page(driver, "6")
            next_page(driver, "7")
            next_page(driver, "No")

            participant = get_participant(1)

            assert participant.started_modules == ["gmsi"]
            assert participant.finished_modules == ["gmsi"]
            assert participant.module_id == "gmsi"

            assert participant.var.gmsi["mean_scores_per_scale"] == {
                "General": 2.866667,
                "Emotions": 4.2,
                "Start Age": 7.0,
                "Instrument": "voice",
                "Absolute Pitch": "No",
                "Musical Training": 2.4,
                "Active Engagement": 3.333333,
                "Singing Abilities": 3.5,
                "Perceptual Abilities": 4.0,
            }

            next_page(driver, "next-button", finished=True)

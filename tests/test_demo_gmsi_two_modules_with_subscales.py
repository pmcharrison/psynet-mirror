import time

import pytest

from psynet.participant import get_participant
from psynet.test import bot_class, next_page

PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_gmsi_two_modules_with_subscales")
class TestExp(object):
    def test_exp(self, bot_recruits, db_session):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "next-button")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "1")
            next_page(driver, "next-button")
            next_page(driver, "7")
            next_page(driver, "7")
            next_page(driver, "1")
            next_page(driver, "7")
            next_page(driver, "7")
            next_page(driver, "7")
            next_page(driver, "1")

            participant = get_participant(1)
            modules = participant.modules
            assert list(modules.keys()) == ["gmsi_1", "gmsi_2"]
            assert set(list(modules["gmsi_1"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert set(list(modules["gmsi_2"].keys())) == {
                "time_started",
                "time_finished",
            }
            assert len(modules["gmsi_1"]["time_started"]) == 1
            assert len(modules["gmsi_1"]["time_finished"]) == 1
            assert len(modules["gmsi_2"]["time_started"]) == 1
            assert len(modules["gmsi_2"]["time_finished"]) == 1
            assert participant.started_modules == ["gmsi_1", "gmsi_2"]
            assert participant.finished_modules == ["gmsi_1", "gmsi_2"]
            assert participant.current_module == "gmsi_2"
            assert participant.var.gmsi_1["mean_scores_per_scale"] == {
                "Singing Abilities": 1.0,
            }
            assert participant.var.gmsi_2["mean_scores_per_scale"] == {
                "Musical Training": 7.0,
            }

            next_page(driver, "next-button", finished=True)

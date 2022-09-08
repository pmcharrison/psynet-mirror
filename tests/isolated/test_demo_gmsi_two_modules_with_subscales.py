import time

import pytest

from psynet.participant import get_participant
from psynet.pytest_psynet import bot_class, next_page, path_to_demo

PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_demo("demography/gmsi_two_modules_with_subscales")],
    indirect=True,
)
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

            assert list(participant.module_states) == ["gmsi_1", "gmsi_2"]
            for _module in ["gmsi_1", "gmsi_2"]:
                for _attr in ["time_started", "time_finished"]:
                    assert (
                        getattr(participant.module_states[_module][0], _attr)
                        is not None
                    )

            assert participant.started_modules == ["gmsi_1", "gmsi_2"]
            assert participant.finished_modules == ["gmsi_1", "gmsi_2"]
            assert participant.module_id == "gmsi_2"

            assert participant.var.gmsi_1["mean_scores_per_scale"] == {
                "Singing Abilities": 1.0,
            }
            assert participant.var.gmsi_2["mean_scores_per_scale"] == {
                "Musical Training": 7.0,
            }

            next_page(driver, "next-button", finished=True)

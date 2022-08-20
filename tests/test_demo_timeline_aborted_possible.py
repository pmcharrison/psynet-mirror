import logging
import time

import pytest
from selenium.webdriver.common.by import By

from psynet.participant import get_participant
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize("experiment_directory", ["../demos/timeline"], indirect=True)
class TestExp:
    def test_variables(self, db_session):
        from psynet.experiment import get_experiment

        exp = get_experiment()
        assert exp.var.min_accumulated_bonus_for_abort == 0.15
        assert exp.var.show_abort_button is True

    def test_abort(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "consent")
            next_page(driver, "next-button")
            next_page(driver, "next-button")
            next_page(driver, "next-button")

            driver.switch_to.window(driver.window_handles[0])
            abort_button = driver.find_element(By.ID, "abort-button")
            abort_button.click()
            driver.switch_to.window(driver.window_handles[2])
            assert_text(
                driver, "header", "Are you sure you want to abort the experiment?"
            )
            abort_button = driver.find_element(By.ID, "abort-button")
            abort_button.click()
            time.sleep(0.5)

            participant = get_participant(1)
            modules = participant.modules

            assert participant.aborted is True
            assert participant.aborted_modules == [
                "introduction",
            ]
            assert len(modules["introduction"]["time_aborted"]) == 1
            assert len(modules["introduction"]["time_finished"]) == 0

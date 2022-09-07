import logging
import time

import pytest
from selenium.webdriver.common.by import By

from psynet.participant import get_participant
from psynet.pytest_psynet import assert_text, bot_class, next_page, path_to_demo

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("timeline_with_error")], indirect=True
)
class TestExp:
    def test_variables(self, db_session):
        from psynet.experiment import get_experiment

        exp = get_experiment()
        assert exp.var.min_accumulated_bonus_for_abort == 0.10
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

            with pytest.raises(RuntimeError):
                next_page(driver, "next-button")

            assert_text(driver, "header", "Error!")
            assert_text(
                driver,
                "error-text",
                "There has been an error and so you are unable to continue, sorry!",
            )
            assert_text(
                driver,
                "error-text-main",
                "You may be able to abort the experiment using the Abort experiment button on the MTurk ad page. Once aborted, there is no need to contact us to receive the compensation; this should be awarded to you automatically via MTurk a few minutes after. If this is not the case, please contact us at computational.audition+online_running@gmail.com quoting the following information:",
            )

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

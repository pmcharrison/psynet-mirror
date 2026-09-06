import time

import pytest
from dallinger import db
from selenium.webdriver.common.by import By

from psynet.experiment import get_experiment
from psynet.participant import get_participant
from psynet.pytest_psynet import (
    assert_text,
    bot_class,
    next_page,
    path_to_test_experiment,
)
from psynet.utils import get_config

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_test_experiment("timeline_with_error")],
    indirect=True,
)
class TestExp:
    def test_variables(self, db_session):
        config = get_config()
        assert config.get("min_accumulated_reward_for_abort") == 0.10
        assert config.get("show_abort_button") is True

    def test_abort(self, bot_recruits, db_session):
        # Simulate mturk
        exp = get_experiment()
        exp.var.set("start_experiment_in_popup_window", True)
        db.session.commit()
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            driver.switch_to.window(driver.window_handles[0])
            assert not driver.find_elements(By.ID, "abort-button")
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

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
                "Your progress has been recorded. You can leave the experiment from this page.",
            )

            url = driver.current_url
            driver.find_element(By.ID, "early-exit-open").click()
            assert_text(driver, "early-exit-title", "Leave the study?")
            driver.find_element(By.ID, "early-exit-cancel").click()
            assert driver.current_url == url

            driver.find_element(By.ID, "early-exit-open").click()
            driver.find_element(By.ID, "early-exit-confirm").click()
            time.sleep(0.5)

            participant = get_participant(1)

            assert participant.aborted is True
            assert participant.failed is True
            assert participant.aborted_modules == [
                "introduction",
            ]
            assert participant.module_states["introduction"][0].aborted
            assert not participant.module_states["introduction"][0].finished

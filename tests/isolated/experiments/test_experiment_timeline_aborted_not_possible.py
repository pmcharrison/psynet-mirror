import time

import pytest
from selenium.webdriver.common.by import By

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
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_variables(self, db_session):
        config = get_config()
        assert config.get("min_accumulated_reward_for_abort") == 0.15
        assert config.get("show_abort_button") is True

    def test_abort(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "consent")
            next_page(driver, "next-button")
            next_page(driver, "next-button")

            exit_button = driver.find_element(By.ID, "terminate-button")
            exit_button.click()
            assert_text(driver, "early-exit-title", "Leaving is not available yet")
            assert not driver.find_elements(By.ID, "early-exit-confirm")
            driver.find_element(By.ID, "early-exit-cancel").click()

            next_page(driver, "next-button")

            driver.find_element(By.ID, "terminate-button").click()
            assert_text(driver, "early-exit-title", "Leave the experiment?")
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

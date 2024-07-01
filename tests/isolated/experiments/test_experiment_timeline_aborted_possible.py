import time

import pytest
from dallinger import db
from selenium.webdriver.common.by import By

from psynet.experiment import get_and_load_config, get_experiment
from psynet.participant import get_participant
from psynet.pytest_psynet import (
    assert_text,
    bot_class,
    next_page,
    path_to_test_experiment,
)

PYTEST_BOT_CLASS = bot_class()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_variables(self, db_session):
        config = get_and_load_config()
        assert config.get("min_accumulated_reward_for_abort") == 0.15
        assert config.get("show_abort_button") is True

    def test_abort(self, bot_recruits, db_session):
        # Simulate mturk
        exp = get_experiment()
        exp.var.set("start_experiment_in_popup_window", True)
        db.session.commit()

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

            assert participant.aborted is True
            assert participant.aborted_modules == [
                "introduction",
            ]
            assert participant.module_states["introduction"][0].aborted
            assert not participant.module_states["introduction"][0].finished

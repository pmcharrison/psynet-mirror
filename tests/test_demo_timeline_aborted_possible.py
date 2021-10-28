import logging
import os
import time

import pytest

from psynet.participant import get_participant
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.fixture(scope="class")
def exp_dir(root):
    os.chdir(os.path.join(os.path.dirname(__file__), "..", "demos/timeline"))
    yield
    os.chdir(root)


@pytest.mark.usefixtures("exp_dir")
class TestExp:
    def test_variables(self, db_session):
        from psynet.utils import import_local_experiment

        exp_class = import_local_experiment()["class"]
        exp = exp_class.new(db_session)
        assert exp.var.min_accumulated_bonus_for_abort == 0.15
        assert exp.var.show_abort_button is True

    def test_abort(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "standard-consent")
            next_page(driver, "next-button")
            next_page(driver, "next-button")
            next_page(driver, "next-button")

            driver.switch_to.window(driver.window_handles[0])
            abort_button = driver.find_element_by_id("abort-button")
            abort_button.click()
            driver.switch_to.window(driver.window_handles[2])
            assert_text(
                driver, "header", "Are you sure you want to abort the experiment?"
            )
            abort_button = driver.find_element_by_id("abort-button")
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

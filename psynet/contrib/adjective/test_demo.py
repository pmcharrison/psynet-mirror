import logging
import time

import pytest
from selenium.common.exceptions import UnexpectedAlertPresentException
from selenium.webdriver.common.by import By

from psynet.participant import get_participant
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_adjective_pipeline")
class TestExp(object):
    def test_exp(self, bot_recruits, db_session):  # two_iterations, bot_recruits):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            # Page 0
            time.sleep(1)

            assert list(get_participant(1).modules.keys()) == ["test"]
            assert_text(driver, "Single video", "Single video")
            next_page(driver, "Single video")
            time.sleep(1)

            # Try clicking next
            try:
                next_page(driver, "next_button")
            except UnexpectedAlertPresentException as e:
                assert e.alert_text == "You need to supply at least one new tag!"

            # View stimulus
            text_input = driver.find_element(By.CLASS_NAME, "tt-input")
            text_input.send_keys("a\n")
            next_page(driver, "next_button")
            time.sleep(1)

            # Bonus page
            main = driver.find_element(By.ID, "main-body")
            main.text.startswith('You just unlocked an entirely new word: "a"')
            participant = get_participant(1)
            assert (
                participant.performance_bonus == 0.02
            )  # 0.01 for the new tag (9*4/60^2) + 0.01 unlocked bonus
            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "next-button", finished=True)

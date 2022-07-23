import logging
import time

import pytest
from selenium.webdriver.common.by import By

from psynet.bot import Bot
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_bot")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        bots = [Bot() for _ in range(2)]

        for bot in bots:
            bot.take_experiment()

        assert bots[0].id == 1
        assert bots[1].id == 2

        assert not bots[0].failed
        assert bots[1].failed

        bot_1_answers = [r.answer for r in bots[0].all_responses]

        assert bot_1_answers[0] == "Fixed response"
        assert bot_1_answers[1].startswith("Stochastic response")
        assert (
            bot_1_answers[2] == "This response came from the CustomTextControl method."
        )

        # These bot_recruits are CI bots that *do* interact directly with the web browser.
        for bot in bot_recruits:
            driver = bot.driver
            time.sleep(1)

            for i in range(3):
                text_input = driver.find_element(By.ID, "text-input")
                text_input.send_keys("I am a real PsyNet participant!")
                next_page(driver, "next-button")

            next_page(driver, "next-button", finished=True)

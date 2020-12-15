import pytest
import logging
import time
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None

@pytest.mark.usefixtures("demo_mcmcp")
class TestExp():

    def test_exp(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(0.2)

            for i in range(10):
                next_page(driver, "1")

            next_page(driver, "next_button")
            next_page(driver, "next_button", finished=True)

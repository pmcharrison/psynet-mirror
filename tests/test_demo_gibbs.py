import pytest
import logging
import time
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None

@pytest.mark.usefixtures("demo_gibbs")
class TestExp():

    def test_exp(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(0.2)

            # What participant group would you like to join?
            participant_group = ["A", "B", "A", "B"][participant]
            next_page(driver, participant_group)

            assert driver.find_element_by_id("participant-group").text == f"Participant group = {participant_group}"

            for i in range(7):
                next_page(driver, "next_button")

            next_page(driver, "next_button")

            next_page(driver, "next_button", finished=True)

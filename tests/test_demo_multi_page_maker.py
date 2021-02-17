import logging
import os
import re
import time

import pytest

from psynet.participant import Participant, get_participant
from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()


@pytest.mark.usefixtures("demo_multi_page_maker")
class TestExp:
    def test_exp(self, bot_recruits):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(0.2)

            next_page(driver, "3")

            assert driver.find_element_by_id("main-body").text == "Page 1/3\nNext"
            next_page(driver, "next_button")
            assert driver.find_element_by_id("main-body").text == "Page 2/3\nNext"
            next_page(driver, "next_button")
            assert driver.find_element_by_id("main-body").text == "Page 3/3\nNext"
            next_page(driver, "next_button")

            next_page(driver, "next_button", finished=True)

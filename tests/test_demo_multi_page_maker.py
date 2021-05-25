import logging
import time

import pytest

from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()


@pytest.mark.usefixtures("demo_multi_page_maker")
class TestExp:
    def test_exp(self, bot_recruits):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "3")

            assert_text(driver, "main-body", "Page 1/3 Next")
            next_page(driver, "next_button")

            assert_text(driver, "main-body", "Page 2/3 Next")
            next_page(driver, "next_button")

            assert_text(driver, "main-body", "Page 3/3 Next")
            next_page(driver, "next_button")

            next_page(driver, "next_button", finished=True)

import logging
import time

import pytest

from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_pickle_page")
class TestExp(object):
    def test_exp(self, bot_recruits, db_session):  # two_iterations, bot_recruits):
        for i, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "next-button")
            assert_text(
                driver, "main-body", "This page was pickled in the database. Next"
            )
            next_page(driver, "next-button")
            next_page(driver, "next-button", finished=True)

import logging
import time

import pytest

from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_dense_color")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            next_page(driver, "1")
            next_page(driver, "2")
            next_page(driver, "3")
            next_page(driver, "4")
            next_page(driver, "1")
            next_page(driver, "2")

            assert_text(driver, "main-body", "You finished the experiment! Next")

            # Here we check that each adjective occurred exactly 3 times.
            # This should be enacted by active_balancing_within_participants = True.

            from psynet.trial.main import Trial

            trials = Trial.query.all()
            adjectives = [t.condition.definition["adjective"] for t in trials]
            adjectives.sort()
            assert adjectives == ["angry"] * 3 + ["happy"] * 3

            next_page(driver, "next_button")
            next_page(driver, "next_button", finished=True)

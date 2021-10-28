import logging
import time

import pytest

from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_mcmcp")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "standard_consent")
            for i in range(10):
                next_page(driver, "1")

            next_page(driver, "next_button")
            next_page(driver, "next_button", finished=True)

    def test_default_variables(self, db_session):
        from psynet.utils import import_local_experiment

        exp_class = import_local_experiment()["class"]
        exp = exp_class.new(db_session)
        assert exp.var.min_browser_version == "80.0"
        assert exp.var.max_participant_payment == 25.0
        assert exp.var.hard_max_experiment_payment == 1100.0
        assert exp.var.hard_max_experiment_payment_email_sent is False
        assert exp.var.soft_max_experiment_payment == 1000.0
        assert exp.var.soft_max_experiment_payment_email_sent is False
        assert exp.var.wage_per_hour == 9.0
        assert exp.var.min_accumulated_bonus_for_abort == 0.2
        assert exp.var.show_abort_button is True
        assert exp.var.show_bonus is True

import logging
import time

import pytest

from psynet.participant import Participant
from psynet.test import bot_class, next_page
from psynet.trial.mcmcp import MCMCPNetwork

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize("experiment_directory", ["../demos/mcmpc"], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
        for participant_id, bot in enumerate(bot_recruits):
            # Python zero-indexes, SQL one-indexes
            participant_id += 1

            driver = bot.driver
            time.sleep(1)

            driver.execute_script(
                "$('html').animate({ scrollTop: $(document).height() }, 0);"
            )
            next_page(driver, "consent")

            # Testing that network.participant works correctly
            # (we are in a within-participant experiment, so each chain
            # should be associated with a single participant).
            network = MCMCPNetwork.query.all()[0]
            assert isinstance(network.participant, Participant)
            assert network.participant.id == participant_id

            # Iterating through the trials
            for i in range(10):
                next_page(driver, "1")

            next_page(driver, "next-button")
            next_page(driver, "next-button", finished=True)

    def test_default_variables(self, db_session):
        from psynet.experiment import get_experiment

        exp = get_experiment()

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

import logging
import os
import shutil
import subprocess
import time

import pandas
import pytest
from selenium.webdriver.common.by import By

from psynet.test import bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_gibbs")
class TestExp:
    def test_exp(self, bot_recruits, db_session, experiment_module):
        for participant, bot in enumerate(bot_recruits):
            driver = bot.driver
            time.sleep(1)

            # What participant group would you like to join?
            participant_group = ["A", "B", "A", "B"][participant]
            next_page(driver, participant_group)

            assert (
                driver.find_element(By.ID, "participant-group").text
                == f"Participant group = {participant_group}"
            )

            for i in range(7):
                next_page(driver, "next-button")

            next_page(driver, "next-button")

            from psynet.participant import Participant

            pt = Participant.query.filter_by(id=participant + 1).one()
            trials = pt.trials()
            trials.sort(key=lambda x: x.id)
            network_ids = [t.network.id for t in trials]
            assert network_ids == sorted(network_ids)

            next_page(driver, "next-button", finished=True)

        self._test_export(experiment_module)

    def _test_export(self, experiment_module):
        app = "demo-app"

        # We need to use subprocess because otherwise psynet export messes up the next tests
        subprocess.call(["psynet", "export", "--app", app, "--local"])

        data_dir = os.path.join("data", f"data-{app}", "csv")

        participants_file = os.path.join(data_dir, "participant.csv")
        participants = pandas.read_csv(participants_file)
        nrow = participants.shape[0]
        assert nrow == 4

        coins_file = os.path.join(data_dir, "coin.csv")
        coins = pandas.read_csv(coins_file)
        nrow = coins.shape[0]
        assert nrow == 4

        # For CI robustness
        coins = experiment_module.Coin.query.all()
        coins.delete()

        shutil.rmtree("data")

import logging
import time

import pytest
from selenium.webdriver.common.by import By

from psynet.field import UndefinedVariableError
from psynet.participant import Participant
from psynet.process import AsyncProcess
from psynet.pytest_psynet import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.parametrize("experiment_directory", ["../demos/gibbs"], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
class TestExp:
    def test_exp(
        self, bot_recruits, db_session, data_root_dir, data_csv_dir, data_zip_file
    ):
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

            pt = Participant.query.filter_by(id=participant + 1).one()
            time.sleep(1)

            async_processes = AsyncProcess.query.all()
            assert len(async_processes) > 0

            for p in async_processes:
                assert p.finished

            post_trial_processes = [
                p for p in async_processes if p.label == "post_trial"
            ]
            for p in post_trial_processes:
                assert p.trial is not None
                assert p.network is not None
                assert p.trial_maker_id == "gibbs_demo"

            post_grow_network_processes = [
                p for p in async_processes if p.label == "post_grow_network"
            ]
            for p in post_grow_network_processes:
                assert p.trial is None
                assert p.network is not None
                assert p.trial_maker_id == "gibbs_demo"

            # This variable is set in a code block within the trial
            assert pt.var.test_variable == 123

            trials = pt.trials()
            trials.sort(key=lambda x: x.id)
            network_ids = [t.network.id for t in trials]
            assert network_ids == sorted(network_ids)

            with pytest.raises(UndefinedVariableError):
                pt.var.get("uninitialized_variable")

            assert pt.var.get("uninitialized_variable", default=123) == 123

            assert_text(driver, "main-body", "Did you like the experiment? Next")
            text_input = driver.find_element(By.ID, "text-input")
            text_input.send_keys("Yes, I loved it!")
            next_page(driver, "next-button")

            assert_text(
                driver, "main-body", "Did you find the experiment difficult? Next"
            )
            text_input = driver.find_element(By.ID, "text-input")
            text_input.send_keys("No, I found it easy.")
            next_page(driver, "next-button")

            assert_text(
                driver,
                "main-body",
                "Did you encounter any technical problems during the experiment? If so, please provide a few words describing the problem. Next",
            )
            text_input = driver.find_element(By.ID, "text-input")
            text_input.send_keys("No technical problems.")
            next_page(driver, "next-button")

            next_page(driver, "next-button", finished=True)

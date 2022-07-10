import logging
import os
import shutil
import tempfile
import time
import zipfile

import dallinger
import pandas
import pytest
from selenium.webdriver.common.by import By

from psynet.command_line import export_
from psynet.field import UndefinedVariableError
from psynet.test import assert_text, bot_class, next_page

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None


@pytest.mark.usefixtures("demo_gibbs")
class TestExp:
    def test_exp(self, bot_recruits, db_session):
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

        self._test_export()

    def _test_export(self):
        app = "demo-app"

        # OLD - We need to use subprocess because otherwise psynet export messes up the next tests.
        # NEW - Running the tests in isolated mode should have fixed this problem.
        # try:
        #     subprocess.check_output(["psynet", "export", "--app", app, "--local"])
        # except subprocess.CalledProcessError as e:
        #     raise RuntimeError(f"Error in psynet export: {e.output}")

        root_dir = os.path.join("data", f"data-{app}")
        data_dir = os.path.join(root_dir, "csv")
        zip_file = os.path.join(root_dir, "db-snapshot", f"{app}-data.zip")
        shutil.rmtree(root_dir, ignore_errors=True)

        export_(app, local=True)

        def test_participants_file(data_dir):
            participants_file = os.path.join(data_dir, "Participant.csv")
            participants = pandas.read_csv(participants_file)
            nrow = participants.shape[0]
            assert nrow == 4

        test_participants_file(data_dir)

        def test_coins_file(data_dir):
            coins_file = os.path.join(data_dir, "Coin.csv")
            coins = pandas.read_csv(coins_file)
            nrow = coins.shape[0]
            assert nrow == 4

        test_coins_file(data_dir)

        from psynet.data import _prepare_db_export

        def test_prepare_db_export():
            json = _prepare_db_export()
            assert sorted(list(json)) == [
                "Coin",
                "CustomNetwork",
                "CustomNode",
                "CustomSource",
                "CustomTrial",
                "ExperimentConfig",
                "Notification",
                "Participant",
                "Response",
                "Vector",
            ]
            assert len(json["Participant"]) == 4  # Number of participants

        test_prepare_db_export()

        def test_psynet_exports(data_dir):
            assert sorted(os.listdir(data_dir)) == [
                "Coin.csv",
                "CustomNetwork.csv",
                "CustomNode.csv",
                "CustomSource.csv",
                "CustomTrial.csv",
                "ExperimentConfig.csv",
                "Notification.csv",
                "Participant.csv",
                "Response.csv",
                "Vector.csv",
            ]

        test_psynet_exports(data_dir)

        def test_experiment_feedback(data_dir):
            df = pandas.read_csv(os.path.join(data_dir, "Response.csv"))

            df_ = df.query("question == 'liked_experiment'")
            assert df_.shape[0] == 4
            assert list(df_.participant_id) == [1, 2, 3, 4]
            assert list(df_.answer) == ["Yes, I loved it!"] * 4

            df_ = df.query("question == 'find_experiment_difficult'")
            assert df_.shape[0] == 4
            assert list(df_.participant_id) == [1, 2, 3, 4]
            assert list(df_.answer) == ["No, I found it easy."] * 4

            df_ = df.query("question == 'encountered_technical_problems'")
            assert df_.shape[0] == 4
            assert list(df_.participant_id) == [1, 2, 3, 4]
            assert list(df_.answer) == ["No technical problems."] * 4

        test_experiment_feedback(data_dir)

        def test_dallinger_exports(zip_file):
            with tempfile.TemporaryDirectory() as tempdir:
                with zipfile.ZipFile(zip_file, "r") as zip_ref:
                    zip_ref.extractall(tempdir)
                    dallinger_csv_files = sorted(
                        os.listdir(os.path.join(tempdir, "data"))
                    )
                    db_tables = sorted(list(dallinger.db.Base.metadata.tables.keys()))

                    # Dallinger CSV files should map one-to-one to database tables
                    assert dallinger_csv_files == [t + ".csv" for t in db_tables]

        test_dallinger_exports(zip_file)

        shutil.rmtree("data")

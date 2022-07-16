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

from psynet.command_line import export_, populate_db_from_zip_file
from psynet.field import UndefinedVariableError
from psynet.participant import Participant
from psynet.test import assert_text, bot_class, next_page
from psynet.timeline import Response
from psynet.trial.main import Trial

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None

app = "demo-app"


@pytest.fixture(scope="session")
def data_root_dir():
    path = os.path.join("data", f"data-{app}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def data_csv_dir(data_root_dir):
    return os.path.join(data_root_dir, "csv")


@pytest.fixture
def data_zip_file(data_root_dir):
    return os.path.join(data_root_dir, "db-snapshot", f"{app}-data.zip")


@pytest.fixture
def coin_class(experiment_module):
    return experiment_module.Coin


@pytest.mark.usefixtures("demo_gibbs")
class TestExp:
    def test_exp(self, bot_recruits, db_session, data_csv_dir, data_zip_file):
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

            import pydevd_pycharm

            pydevd_pycharm.settrace(
                "localhost", port=12345, stdoutToServer=True, stderrToServer=True
            )

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

        self._run_export_tests(data_csv_dir, data_zip_file)

    def _run_export_tests(self, data_csv_dir, data_zip_file):
        export_(app, local=True)

        def test_participants_file(data_csv_dir):
            participants_file = os.path.join(data_csv_dir, "Participant.csv")
            participants = pandas.read_csv(participants_file)
            nrow = participants.shape[0]
            assert nrow == 4

        test_participants_file(data_csv_dir)

        def test_coins_file(data_csv_dir):
            coins_file = os.path.join(data_csv_dir, "Coin.csv")
            coins = pandas.read_csv(coins_file)
            nrow = coins.shape[0]
            assert nrow == 4

        test_coins_file(data_csv_dir)

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

        def test_psynet_exports(data_csv_dir):
            assert sorted(os.listdir(data_csv_dir)) == [
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

        test_psynet_exports(data_csv_dir)

        def test_experiment_feedback(data_csv_dir):
            df = pandas.read_csv(os.path.join(data_csv_dir, "Response.csv"))

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

        test_experiment_feedback(data_csv_dir)

        def test_dallinger_exports(data_zip_file):
            with tempfile.TemporaryDirectory() as tempdir:
                with zipfile.ZipFile(data_zip_file, "r") as zip_ref:
                    zip_ref.extractall(tempdir)
                    dallinger_csv_files = sorted(
                        os.listdir(os.path.join(tempdir, "data"))
                    )
                    db_tables = sorted(list(dallinger.db.Base.metadata.tables.keys()))

                    # Dallinger CSV files should map one-to-one to database tables
                    assert dallinger_csv_files == [t + ".csv" for t in db_tables]

        test_dallinger_exports(data_zip_file)

    def test_populate_db_from_zip_file(self, data_zip_file, coin_class):
        """
        Here we test the process of loading the objects described in an exported zip file
        into the local database. This is an important part of the current implementation
        of data export, which works by first creating the zip file via Dallinger's export function,
        then loads it into the local database, and serializes it locally using PsyNet's
        export functions. The function relies on the zip file created in ``test_exp``;
        it would make sense to state this explicitly as a fixture, but it's proved
        to difficult to make that work in practice because of the way in which Dallinger's
        own pytest scopes have been defined.
        """
        populate_db_from_zip_file(data_zip_file)

        trials = Trial.query.all()
        assert len(trials) > 15
        assert all(t.participant_id in [1, 2, 3, 4] for t in trials)

        participants = Participant.query.all()
        assert len(participants) == 4
        assert sorted([p.id for p in participants]) == [1, 2, 3, 4]

        responses = Response.query.all()
        assert len(responses) > 15
        assert all(r.participant_id in [1, 2, 3, 4] for r in responses)

        coins = coin_class.query.all()
        assert len(coins) == 4
        assert all(c.participant_id in [1, 2, 3, 4] for c in coins)

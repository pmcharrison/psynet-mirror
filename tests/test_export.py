import logging
import os
import shutil
import tempfile
import zipfile

import dallinger
import pandas
import pytest
from dallinger import db

from psynet.asset import Asset, ExperimentAsset
from psynet.bot import Bot
from psynet.command_line import export_, populate_db_from_zip_file
from psynet.participant import Participant
from psynet.test import bot_class
from psynet.timeline import Response
from psynet.trial.main import Trial

logger = logging.getLogger(__file__)
PYTEST_BOT_CLASS = bot_class()
EXPERIMENT = None

app = "demo-app"


@pytest.fixture(scope="class")
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


@pytest.mark.usefixtures("demo_gibbs", "db_session")
class TestAssetExport:
    def test_exp(
        self,
        active_config,
        debug_experiment,
        data_root_dir,
        data_csv_dir,
        data_zip_file,
    ):
        # Creating a couple of personal and non-personal assets
        with tempfile.NamedTemporaryFile("w") as file:
            file.write("Test asset")
            asset = ExperimentAsset(
                label="test_personal_asset", input_path=file.name, personal=True
            )
            asset.deposit()

            asset_2 = ExperimentAsset(
                label="test_public_asset",
                input_path=file.name,
                personal=False,
            )
            asset_2.deposit()

        db.session.commit()

        assert Asset.query.count() == 2

        bot = Bot()
        bot.take_experiment()

        json_full = bot.__json__()
        json_anon = bot.scrub_pii(bot.__json__())

        assert "worker_id" in json_full
        assert "worker_id" not in json_anon

        from psynet.command_line import export_

        with tempfile.TemporaryDirectory() as tempdir:
            with pytest.raises(ValueError) as e:
                export_(export_path=tempdir)
            assert (
                str(e.value)
                == "Either the flag --local must be present or an app name must be provided via --app."
            )

            with pytest.raises(ValueError) as e:
                export_(app="my-app", local=True, export_path=tempdir)
            assert (
                str(e.value) == "You cannot provide both --local and --app arguments."
            )

            with pytest.raises(ValueError) as e:
                export_(local=True, export_path=tempdir, assets="asdasdoj")
            assert str(e.value) == "--assets must be either none, experiment, or all."

            with pytest.raises(ValueError) as e:
                export_(local=True, export_path=tempdir, anon="asdasdoj")
            assert str(e.value) == "--anon must be either yes, no, or both."

            export_(
                local=True,
                assets="all",
                anon="both",
                export_path=tempdir,
            )

            # Not relevant if we don't export code
            # self.assert_valid_code_zip(os.path.join(tempdir, "regular", "code.zip"))
            # self.assert_valid_code_zip(os.path.join(tempdir, "anonymous", "code.zip"))

            self.assert_regular_database_zip(
                os.path.join(tempdir, "regular", "database.zip")
            )
            self.assert_anonymous_database_zip(
                os.path.join(tempdir, "anonymous", "database.zip")
            )

            self.assert_regular_data(os.path.join(tempdir, "regular", "data"))
            self.assert_anonymous_data(os.path.join(tempdir, "anonymous", "data"))

    # def assert_valid_code_zip(self, path):
    #         archive = zipfile.ZipFile(path, "r")
    #         import pydevd_pycharm
    #         pydevd_pycharm.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)

    def assert_regular_database_zip(self, path):
        import pandas as pd

        archive = zipfile.ZipFile(
            path,
            "r",
        )

        files = [f.filename for f in archive.filelist]
        assert "data/experiment.csv" in files
        assert "data/response.csv" in files
        assert "data/network.csv" in files

        with archive.open("data/asset.csv") as f:
            asset_csv = pd.read_csv(f)

        assert asset_csv.shape[0] >= 2

        with archive.open("data/participant.csv") as f:
            participant_csv = pd.read_csv(f)

        assert all(
            len(id_) > 5 for id_ in participant_csv.worker_id
        )  # All participants should have their worker IDs

    def assert_anonymous_database_zip(self, path):
        import pandas as pd

        archive = zipfile.ZipFile(
            path,
            "r",
        )

        files = [f.filename for f in archive.filelist]
        assert "data/experiment.csv" in files
        assert "data/response.csv" in files
        assert "data/network.csv" in files

        with archive.open("data/asset.csv") as f:
            asset_csv = pd.read_csv(f)

        assert asset_csv.shape[0] >= 2  # There should still be quite a few assets

        with archive.open("data/participant.csv") as f:
            participant_csv = pd.read_csv(f)

        # Worker IDs should now be scrubbed and replaced with integers counting upwards from 1
        # (so their string representation is going to be shorter than 3 characters long)
        assert all(len(str(id_)) < 3 for id_ in participant_csv.worker_id)

    def assert_regular_data(self, path):
        import pandas as pd

        bots = pd.read_csv(os.path.join(path, "Bot.csv"))

        assert bots.shape[0] > 0
        assert all(bots.type == "Bot")
        assert "creation_time" in bots
        assert "worker_id" in bots

    def assert_anonymous_data(self, path):
        import pandas as pd

        bots = pd.read_csv(os.path.join(path, "Bot.csv"))

        assert bots.shape[0] > 0
        assert all(bots.type == "Bot")
        assert "creation_time" in bots
        assert "worker_id" not in bots  # Anonymous data has worker_id scrubbed


@pytest.mark.usefixtures("demo_gibbs", "db_session")
class TestExp:
    def test_exp(
        self,
        active_config,
        debug_experiment,
        data_root_dir,
        data_csv_dir,
        data_zip_file,
    ):
        import time

        time.sleep(1)
        for _ in range(4):
            bot = Bot()
            bot.take_experiment()

        self._run_export_tests(data_csv_dir, data_zip_file)

    def _run_export_tests(self, data_csv_dir, data_zip_file):
        export_(app, local=True, include_assets=True, n_parallel=None)

        def test_participants_file(data_csv_dir):
            participants_file = os.path.join(data_csv_dir, "Bot.csv")
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
                "Bot",
                "Coin",
                "CustomNetwork",
                "CustomNode",
                "CustomSource",
                "CustomTrial",
                "ExperimentConfig",
                "Response",
                "Vector",
            ]
            # No Notification table here as bots don't produce Notifications currently
            assert len(json["Bot"]) == 4  # Number of participants

        test_prepare_db_export()

        def test_psynet_exports(data_csv_dir):
            assert sorted(os.listdir(data_csv_dir)) == [
                "Bot.csv",
                "Coin.csv",
                "CustomNetwork.csv",
                "CustomNode.csv",
                "CustomSource.csv",
                "CustomTrial.csv",
                "ExperimentConfig.csv",
                # "Notification.csv",  # Bots don't produce notifications
                "Response.csv",
                "Vector.csv",
            ]

        test_psynet_exports(data_csv_dir)

        def test_experiment_feedback(data_csv_dir):
            df = pandas.read_csv(os.path.join(data_csv_dir, "Response.csv"))

            df_ = df.query("question == 'liked_experiment'")
            assert df_.shape[0] == 4
            assert list(df_.participant_id) == [1, 2, 3, 4]
            assert (
                list(df_.answer) == ["I'm a bot so I don't really have feelings..."] * 4
            )

            df_ = df.query("question == 'find_experiment_difficult'")
            assert df_.shape[0] == 4
            assert list(df_.participant_id) == [1, 2, 3, 4]
            assert list(df_.answer) == ["I'm a bot so I found it pretty easy..."] * 4

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

        def test_asset_exports(data_root_dir):
            import pydevd_pycharm

            pydevd_pycharm.settrace(
                "localhost", port=12345, stdoutToServer=True, stderrToServer=True
            )

        test_asset_exports(data_root_dir)

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

        test_populate_db_from_zip_file()

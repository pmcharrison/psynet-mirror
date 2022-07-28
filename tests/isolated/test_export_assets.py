import logging
import os
import shutil
import tempfile
import zipfile

import pytest
from dallinger import db

from psynet.asset import Asset, ExperimentAsset
from psynet.bot import Bot
from psynet.test import bot_class

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

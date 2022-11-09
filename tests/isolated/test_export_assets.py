import logging
import os
import shutil
import tempfile
import zipfile

import pytest
from dallinger import db

from psynet.asset import Asset, ExperimentAsset, ExternalAsset, FastFunctionAsset
from psynet.bot import Bot
from psynet.pytest_psynet import bot_class, path_to_demo

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


def generate_text_file(path):
    with open(path, "w") as file:
        file.write("Lorem ipsum")


def test_export_path__external_asset():
    asset = ExternalAsset(
        key="test_external_asset",
        url="https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
    )
    assert asset.export_path == "test_external_asset.wav"


def test_export_path__fast_function_asset():
    asset = FastFunctionAsset(
        function=generate_text_file, key="test_fast_function_asset", extension=".txt"
    )
    assert asset.export_path == "test_fast_function_asset.txt"


# @pytest.mark.usefixtures("db_session")  # Assuming we don't need this
@pytest.mark.parametrize("experiment_directory", [path_to_demo("gibbs")], indirect=True)
@pytest.mark.usefixtures("launched_experiment")
class TestAssetExport:
    def test_exp(
        self,
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

            asset_3 = ExternalAsset(
                key="test_external_asset",
                url="https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
            )
            asset_3.deposit()

            asset_4 = FastFunctionAsset(
                function=generate_text_file,
                key="test_fast_function_asset",
            )
            asset_4.deposit()

        db.session.commit()

        assert Asset.query.count() == 4

        self._test_asset_export_modes()

        bot = Bot()
        bot.take_experiment()

        json_full = bot.to_dict()
        json_anon = bot.scrub_pii(bot.to_dict())

        assert "worker_id" in json_full
        assert "worker_id" not in json_anon

        from psynet.command_line import export_

        # Calling export_ multiple times in the same process causes SQLAlchemy errors due to repeated imports...
        # Temporary fix for now is to call in subprocess
        # from psynet.utils import run_subprocess_with_live_output

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
                export_(local=True, export_path=tempdir, anonymize="asdasdoj")
            assert str(e.value) == "--anonymize must be either yes, no, or both."

            export_(
                local=True,
                assets="all",
                anonymize="both",
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

    def _test_asset_export_modes(self):
        from psynet.command_line import export_

        with tempfile.TemporaryDirectory() as tempdir:
            export_(local=True, export_path=tempdir, assets="none")

            path_1 = os.path.join(tempdir, "regular", "data")
            assert os.path.exists(path_1) and os.path.isdir(path_1)

            #  assets="none" so no assets should be exported
            path_1 = os.path.join(tempdir, "regular", "assets")
            assert not os.path.exists(path_1)

        with tempfile.TemporaryDirectory() as tempdir:
            export_(local=True, export_path=tempdir, assets="experiment")

            path = os.path.join(tempdir, "regular", "assets")
            assert os.path.exists(path) and os.path.isdir(path)

            assert os.path.exists(
                os.path.join(tempdir, "regular", "assets", "test_personal_asset")
            )
            assert not os.path.exists(
                os.path.join(tempdir, "anonymous", "assets", "test_personal_asset")
            )
            assert not os.path.exists(
                os.path.join(tempdir, "regular", "assets", "test_external_asset.wav")
            )
            assert not os.path.exists(
                os.path.join(tempdir, "regular", "assets", "test_fast_function_asset")
            )

        with tempfile.TemporaryDirectory() as tempdir:
            export_(local=True, export_path=tempdir, assets="all")

            assert os.path.exists(
                os.path.join(tempdir, "regular", "assets", "test_personal_asset")
            )
            assert os.path.exists(
                os.path.join(tempdir, "regular", "assets", "test_external_asset.wav")
            )  # now we have this
            assert os.path.exists(
                os.path.join(tempdir, "regular", "assets", "test_fast_function_asset")
            )  # and this

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

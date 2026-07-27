import os
import shutil
import tempfile
import zipfile

import pytest
from click import Context
from dallinger import db

from psynet.asset import Asset, ExperimentAsset, ExternalAsset, OnDemandAsset
from psynet.bot import Bot, BotDriver
from psynet.command_line import export__local
from psynet.pytest_psynet import path_to_test_experiment
from psynet.utils import generate_text_file

app = "demo-app"


@pytest.fixture(scope="class")
def data_root_dir():
    path = os.path.join("data", f"data-{app}")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def coin_class(experiment_module):
    return experiment_module.Coin


def test_export_path__external_asset():
    asset = ExternalAsset(
        key_within_experiment="test_external_asset",
        url="https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
    )
    assert asset.generate_export_path() == "test_external_asset.wav"


def test_export_path__on_demand_asset():
    asset = OnDemandAsset(
        function=generate_text_file,
        key_within_experiment="test_on_demand_asset",
        extension=".txt",
    )
    assert asset.generate_export_path() == "test_on_demand_asset.txt"


@pytest.fixture(scope="class")
def ctx():
    return Context(export__local)


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("gibbs")], indirect=True
)
@pytest.mark.usefixtures("launched_experiment")
class TestAssetExport:
    def test_exp(
        self,
        data_root_dir,
        ctx,
    ):
        # Creating a couple of personal and non-personal assets
        with tempfile.NamedTemporaryFile("w") as file:
            file.write("Test asset")
            asset = ExperimentAsset(
                local_key="test_personal_asset", input_path=file.name, personal=True
            )
            asset.deposit()

            asset_2 = ExperimentAsset(
                local_key="test_public_asset",
                input_path=file.name,
                personal=False,
            )
            asset_2.deposit()

            asset_3 = ExternalAsset(
                local_key="test_external_asset",
                url="https://s3.amazonaws.com/headphone-check/antiphase_HC_ISO.wav",
            )
            asset_3.deposit()

            asset_4 = OnDemandAsset(
                function=generate_text_file,
                local_key="test_on_demand_asset",
            )
            asset_4.deposit()

        db.session.commit()

        assert Asset.query.count() == 4

        self._test_asset_export_modes(ctx)

        bot_driver = BotDriver()
        bot_driver.take_experiment()

        bot = Bot.query.one()

        json_full = bot.to_dict()
        json_anon = bot.scrub_pii(bot.to_dict())

        for key in ["client_ip_address", "worker_id"]:
            assert key in json_full
            assert key not in json_anon

        with tempfile.TemporaryDirectory() as tempdir:
            with pytest.raises(ValueError) as e:
                ctx.invoke(export__local, path=tempdir, assets="asdasdoj")
            assert str(e.value) == "--assets must be either none, experiment, or all."

            ctx.invoke(export__local, path=tempdir, assets="all", legacy=True)

            self.assert_database_zip(os.path.join(tempdir, "database.zip"))
            self.assert_identifier_sidecar(
                os.path.join(tempdir, "participant_identifiers.csv")
            )
            assert os.path.exists(os.path.join(tempdir, "manifest.json"))

    def _test_asset_export_modes(self, ctx):
        for legacy in [True, False]:
            with tempfile.TemporaryDirectory() as tempdir:
                ctx.invoke(export__local, path=tempdir, assets="none", legacy=legacy)

                assert os.path.exists(os.path.join(tempdir, "database.zip"))
                assert not os.path.exists(os.path.join(tempdir, "assets"))

            with tempfile.TemporaryDirectory() as tempdir:
                ctx.invoke(
                    export__local, path=tempdir, assets="experiment", legacy=legacy
                )

                path = os.path.join(tempdir, "assets")
                assert os.path.exists(path) and os.path.isdir(path)

                assert os.path.exists(
                    os.path.join(tempdir, "assets", "common", "test_personal_asset")
                )
                assert os.path.exists(
                    os.path.join(tempdir, "assets", "common", "test_public_asset")
                )
                assert not os.path.exists(
                    os.path.join(
                        tempdir,
                        "assets",
                        "common",
                        "test_external_asset.wav",
                    )
                )
                assert not os.path.exists(
                    os.path.join(tempdir, "assets", "common", "test_on_demand_asset")
                )

            with tempfile.TemporaryDirectory() as tempdir:
                ctx.invoke(export__local, path=tempdir, assets="all", legacy=legacy)
                assert os.path.exists(
                    os.path.join(tempdir, "assets", "common", "test_personal_asset")
                )
                assert os.path.exists(
                    os.path.join(
                        tempdir,
                        "assets",
                        "common",
                        "test_external_asset.wav",
                    )
                )
                assert os.path.exists(
                    os.path.join(tempdir, "assets", "common", "test_on_demand_asset")
                )

    def assert_database_zip(self, path):
        import pandas as pd

        archive = zipfile.ZipFile(path, "r")

        files = [f.filename for f in archive.filelist]
        assert "data/participant.csv" in files
        assert "data/response.csv" in files
        assert "data/network.csv" in files
        assert "data/trial.csv" in files

        with archive.open("data/asset.csv") as f:
            asset_csv = pd.read_csv(f)

        assert asset_csv.shape[0] >= 2

        with archive.open("data/participant.csv") as f:
            participant_csv = pd.read_csv(f)

        # Pseudonyms replace recruiter worker IDs inside the zip.
        assert all(
            str(id_) == str(pid)
            for id_, pid in zip(participant_csv.worker_id, participant_csv.id)
        )

    def assert_identifier_sidecar(self, path):
        import pandas as pd

        sidecar = pd.read_csv(path)
        assert "participant_id" in sidecar.columns
        assert "worker_id" in sidecar.columns
        assert sidecar.shape[0] >= 1
        assert all(len(str(id_)) > 5 for id_ in sidecar.worker_id)

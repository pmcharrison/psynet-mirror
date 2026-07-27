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
        # Creating experiment assets with different keys
        with tempfile.NamedTemporaryFile("w") as file:
            file.write("Test asset")
            asset = ExperimentAsset(local_key="test_marked_asset", input_path=file.name)
            asset.deposit()

            asset_2 = ExperimentAsset(
                local_key="test_public_asset",
                input_path=file.name,
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

            with pytest.raises(TypeError, match="personal"):
                ExperimentAsset(
                    local_key="should_fail", input_path=file.name, personal=True
                )

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
            assert str(e.value) == "--assets must be either none, collected, or all."

            ctx.invoke(export__local, path=tempdir, assets="all", legacy=True)

            self.assert_database_zip(os.path.join(tempdir, "database.zip"))
            self.assert_identifier_sidecar(
                os.path.join(tempdir, "participant_identifiers.csv")
            )
            assert os.path.exists(os.path.join(tempdir, "manifest.json"))

    def _test_asset_export_modes(self, ctx):
        import csv

        for legacy in [True, False]:
            with tempfile.TemporaryDirectory() as tempdir:
                ctx.invoke(export__local, path=tempdir, assets="none", legacy=legacy)

                assert os.path.exists(os.path.join(tempdir, "database.zip"))
                assert not os.path.exists(os.path.join(tempdir, "assets"))

            with tempfile.TemporaryDirectory() as tempdir:
                ctx.invoke(
                    export__local, path=tempdir, assets="collected", legacy=legacy
                )

                path = os.path.join(tempdir, "assets")
                assert os.path.exists(path) and os.path.isdir(path)
                assert os.path.exists(os.path.join(path, "manifest.csv"))
                objects_dir = os.path.join(path, "objects", "sha256")
                assert os.path.isdir(objects_dir)
                object_files = [
                    name
                    for name in os.listdir(objects_dir)
                    if os.path.isfile(os.path.join(objects_dir, name))
                ]
                # Two ExperimentAssets share the same content, so one object file.
                assert len(object_files) == 1

                with open(os.path.join(path, "manifest.csv"), newline="") as csv_file:
                    rows = list(csv.DictReader(csv_file))
                labels = {row["local_key"] for row in rows}
                assert "test_marked_asset" in labels
                assert "test_public_asset" in labels
                assert "test_external_asset" not in labels
                assert "test_on_demand_asset" not in labels
                assert all(
                    row["object_path"].startswith("objects/sha256/") for row in rows
                )

            with tempfile.TemporaryDirectory() as tempdir:
                ctx.invoke(export__local, path=tempdir, assets="all", legacy=legacy)
                path = os.path.join(tempdir, "assets")
                with open(os.path.join(path, "manifest.csv"), newline="") as csv_file:
                    rows = list(csv.DictReader(csv_file))
                labels = {row["local_key"] for row in rows}
                assert "test_marked_asset" in labels
                assert "test_external_asset" in labels
                assert "test_on_demand_asset" in labels
                external_rows = [
                    row for row in rows if row["local_key"] == "test_external_asset"
                ]
                assert len(external_rows) == 1
                assert not external_rows[0]["object_path"]
                assert external_rows[0]["url"].startswith("https://")
                on_demand_rows = [
                    row for row in rows if row["local_key"] == "test_on_demand_asset"
                ]
                assert len(on_demand_rows) == 1
                assert on_demand_rows[0]["object_path"].startswith("objects/sha256/")
                assert os.path.exists(
                    os.path.join(path, on_demand_rows[0]["object_path"])
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

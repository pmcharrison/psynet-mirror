import os
import tempfile

import pytest

from psynet import deployment_info
from psynet.asset import Asset, list_files_in_s3_bucket__cached
from psynet.command_line import run_prepare_in_subprocess
from psynet.experiment import get_experiment
from psynet.pytest_psynet import path_to_test_experiment


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("static_audio")], indirect=True
)
def test_s3_asset_preparation(in_experiment_directory, monkeypatch, tmp_path):
    monkeypatch.setenv("PSYNET_MOCK_S3_ROOT", str(tmp_path / "mock-s3"))
    list_files_in_s3_bucket__cached.cache_clear()

    try:
        exp = get_experiment()
        exp.asset_storage.delete_all()
        deployment_info.init(
            redeploying_from_archive=False,
            mode="debug",
            is_local_deployment=True,
            is_ssh_deployment=False,
            server="",
            app="",
        )  # Prepare requires deployment_info to be initialized
        run_prepare_in_subprocess()

        assets = Asset.query.all()
        assert assets
        for asset in assets:
            assert asset.url.startswith("https://s3")

        with tempfile.NamedTemporaryFile() as f:
            assets[-1].export(f.name)
            assert os.path.getsize(f.name) > 100
    finally:
        list_files_in_s3_bucket__cached.cache_clear()

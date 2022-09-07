import os
import tempfile

import pytest

from psynet.asset import Asset
from psynet.command_line import run_prepare_in_subprocess
from psynet.experiment import get_experiment
from psynet.pytest_psynet import path_to_demo


@pytest.mark.parametrize(
    "experiment_directory", [path_to_demo("static_audio")], indirect=True
)
def test_s3_asset_preparation(in_experiment_directory):
    exp = get_experiment()
    exp.asset_storage.delete_all()
    run_prepare_in_subprocess()
    for asset in Asset.query.all():
        assert asset.url.startswith("https://s3")

    with tempfile.NamedTemporaryFile() as f:
        asset.export(f.name)
        assert os.path.getsize(f.name) > 100

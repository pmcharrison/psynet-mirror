import os
import tempfile

import pytest

from psynet.asset import Asset
from psynet.command_line import run_prepare_in_subprocess
from psynet.utils import get_experiment


@pytest.mark.usefixtures("demo_static_audio")
def test_s3_asset_preparation():
    exp = get_experiment()
    exp.asset_storage.delete_all()
    run_prepare_in_subprocess()
    asset = Asset.query.all()[0]
    assert asset.url.startswith("https://s3")

    with tempfile.NamedTemporaryFile() as f:
        asset.export(f.name)
        assert os.path.getsize(f.name) > 100

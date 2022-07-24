import tempfile

import pytest

from psynet import deployment_info
from psynet.utils import working_directory


def test_deployment_info():
    with tempfile.TemporaryDirectory() as tempdir:
        with working_directory(tempdir):
            with pytest.raises(KeyError):
                deployment_info.read("x")

            deployment_info.write(x=3)
            assert deployment_info.read("x") == 3

            deployment_info.reset()

            with pytest.raises(KeyError):
                deployment_info.read("x")

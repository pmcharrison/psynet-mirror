import os

import pytest

from psynet.pytest_psynet import path_to_demo
from psynet.utils import get_from_config


@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_config(in_experiment_directory):
    global_config_path = os.path.expanduser("~/.dallingerconfig")
    with open(global_config_path, "r") as file:
        lines = file.read()
    print("Printing from config:")
    print(lines)
    _debug_storage_root = get_from_config("debug_storage_root")
    print(f"Loading example value from config: {_debug_storage_root}")
    assert len(_debug_storage_root) > 3

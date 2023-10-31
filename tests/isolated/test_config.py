import os

import pytest
from dallinger.config import get_config

from psynet.experiment import get_experiment
from psynet.pytest_psynet import path_to_demo
from psynet.utils import get_from_config


@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_config(in_experiment_directory):
    global_config_path = os.path.expanduser("~/.dallingerconfig")
    with open(global_config_path, "r") as file:
        lines = file.read()
    print("Printing from config:")
    print(lines)
    _recruiter = get_from_config("recruiter")
    print(f"Loading example value from config: {_recruiter}")
    assert _recruiter == "prolific"


@pytest.mark.parametrize("experiment_directory", [path_to_demo("mcmcp")], indirect=True)
def test_secrets(in_experiment_directory):
    get_experiment()
    config = get_config()

    assert config.get("auto_recruit") is not None
    assert "auto_recruit" in config.as_dict()

    for secret in [
        "cap_recruiter_auth_token",
        "lucid_api_key",
        "lucid_sha1_hashing_key",
    ]:
        config.set(secret, "my-secret")
        assert config.get(secret) is not None
        assert secret not in config.as_dict()

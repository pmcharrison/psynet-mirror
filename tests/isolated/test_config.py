import pytest
from dallinger.config import get_config

from psynet.experiment import _get_dashboard_credentials, get_experiment
from psynet.pytest_psynet import path_to_test_experiment
from psynet.utils import get_from_config


_NO_DEFAULT = object()


class _StrictConfig:
    def __init__(self, values):
        self.values = values

    def get(self, key, default=_NO_DEFAULT):
        if key in self.values:
            return self.values[key]
        if default is _NO_DEFAULT:
            raise KeyError(key)
        return default


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
def test_config(in_experiment_directory):
    _recruiter = get_from_config("recruiter")
    assert _recruiter == "generic"


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
def test_secrets(in_experiment_directory):
    get_experiment()
    config = get_config()

    assert config.get("auto_recruit") is not None
    assert "auto_recruit" in config.as_dict()

    for secret in [
        "lab_recruiter_auth_token",
        "lucid_api_key",
        "lucid_sha1_hashing_key",
    ]:
        config.set(secret, "my-secret")
        assert config.get(secret) is not None
        assert secret not in config.as_dict()


@pytest.mark.parametrize(
    "experiment_directory", [path_to_test_experiment("timeline")], indirect=True
)
def test_prolific_screen_out_is_no_longer_supported(in_experiment_directory):
    get_experiment()
    config = get_config()

    with pytest.raises(ValueError, match="Prolific no longer supports"):
        config.set("prolific_enable_screen_out", True)


def test_dashboard_credentials_allow_missing_config_values():
    assert _get_dashboard_credentials(_StrictConfig({})) == {
        "dashboard_user": "admin",
        "dashboard_password": None,
    }


def test_dashboard_credentials_preserve_config_values():
    assert _get_dashboard_credentials(
        _StrictConfig(
            {
                "dashboard_user": "experimenter",
                "dashboard_password": "secret",
            }
        )
    ) == {
        "dashboard_user": "experimenter",
        "dashboard_password": "secret",
    }

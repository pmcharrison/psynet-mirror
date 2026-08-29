"""audio_gibbs launch check: fail when the baked experiment.py is the wrong variant."""

import importlib.util

import pytest

from psynet.utils import get_psynet_root


def _load_recruiter_variant():
    path = get_psynet_root() / "tests/deployment/audio_gibbs/recruiter_variant.py"
    spec = importlib.util.spec_from_file_location("recruiter_variant", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(recruiter):
    return type("C", (), {"get": lambda self, key: recruiter})()


@pytest.mark.parametrize(
    "expected, recruiter",
    [
        ("hotair", "hotair"),
        ("prolific", "prolific"),
        ("prolific", "devprolific"),
        ("lucid", "lucid-recruiter"),
        ("lucid", "lucid"),
    ],
)
def test_assert_expected_recruiter_accepts_aliases(expected, recruiter, monkeypatch):
    import dallinger.config

    module = _load_recruiter_variant()
    monkeypatch.setattr(dallinger.config, "get_config", lambda: _config(recruiter))
    module.assert_expected_recruiter(expected)


def test_assert_expected_recruiter_rejects_mismatched_image(monkeypatch):
    import dallinger.config

    module = _load_recruiter_variant()
    monkeypatch.setattr(dallinger.config, "get_config", lambda: _config("prolific"))
    with pytest.raises(RuntimeError, match="shared Docker image"):
        module.assert_expected_recruiter("lucid")

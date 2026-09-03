import pytest

from psynet.utils import TranslationNotFoundError, check_translation_is_available


def _check_missing_entry(monkeypatch, namespace):
    monkeypatch.setattr("psynet.experiment.in_deployment_package", lambda: False)
    monkeypatch.setattr(
        "psynet.utils.REGISTERED_TRANSLATIONS",
        {namespace: {"de": []}},
    )
    check_translation_is_available(
        "a string that is not in the catalog",
        "final-page-rewards",
        "de",
        namespace,
    )


def test_missing_package_entry_is_tolerated_in_feature_branch_tests(monkeypatch):
    _check_missing_entry(monkeypatch, "psynet")


def test_missing_package_entry_raises_outside_pytest(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(TranslationNotFoundError):
        _check_missing_entry(monkeypatch, "psynet")


def test_missing_package_entry_raises_on_release_branch(monkeypatch):
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "release-13.4")
    with pytest.raises(TranslationNotFoundError):
        _check_missing_entry(monkeypatch, "psynet")


def test_missing_experiment_entry_always_raises(monkeypatch):
    with pytest.raises(TranslationNotFoundError):
        _check_missing_entry(monkeypatch, "experiment")

import pytest

from psynet.pytest_psynet import is_release_branch
from psynet.utils import TranslationNotFoundError, check_translation_is_available


def test_is_release_branch(monkeypatch):
    monkeypatch.delenv("CI_COMMIT_REF_NAME", raising=False)
    assert not is_release_branch()
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "cursor/hide-zero-performance-reward")
    assert not is_release_branch()
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "release-13.4")
    assert is_release_branch()


def _missing_catalog(monkeypatch):
    monkeypatch.setattr("psynet.experiment.in_deployment_package", lambda: False)
    monkeypatch.setattr(
        "psynet.utils.REGISTERED_TRANSLATIONS",
        {"psynet": {"de": []}},
    )
    check_translation_is_available(
        "a string that is not in the catalog",
        "final-page-rewards",
        "de",
        "psynet",
    )


def test_missing_catalog_entry_does_not_raise_in_non_release_pytest(monkeypatch):
    _missing_catalog(monkeypatch)


def test_missing_catalog_entry_raises_outside_pytest(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(TranslationNotFoundError):
        _missing_catalog(monkeypatch)


def test_missing_catalog_entry_raises_on_release_pytest(monkeypatch):
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "release-13.4")
    with pytest.raises(TranslationNotFoundError):
        _missing_catalog(monkeypatch)

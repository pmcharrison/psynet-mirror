from psynet.pytest_psynet import is_release_branch
from psynet.utils import check_translation_is_available


def test_is_release_branch(monkeypatch):
    monkeypatch.delenv("CI_COMMIT_REF_NAME", raising=False)
    assert not is_release_branch()
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "cursor/hide-zero-performance-reward")
    assert not is_release_branch()
    monkeypatch.setenv("CI_COMMIT_REF_NAME", "release-13.4")
    assert is_release_branch()


def test_missing_catalog_entry_does_not_raise_outside_live(monkeypatch):
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

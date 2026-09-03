from psynet.utils import check_translation_is_available


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

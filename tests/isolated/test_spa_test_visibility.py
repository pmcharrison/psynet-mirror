"""SPA contract errors should be visible during local testing."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import requests

from psynet.experiment import Experiment
from psynet.participant import (
    _extract_server_error_details,
    _raise_for_status_with_server_details,
)
from psynet.timeline import Page, Timeline


def test_check_static_spa_contracts_fails_before_bots(monkeypatch):
    page = Page(
        label="dogfood_legacy",
        time_estimate=5,
        template_str='{% extends "timeline-page.html" %}',
    )
    experiment = MagicMock()
    experiment.timeline = Timeline(page)
    monkeypatch.setattr(
        "psynet.utils.get_config",
        lambda: SimpleNamespace(get=lambda key, default=None: True),
    )

    with pytest.raises(
        ValueError,
        match=r"error codes: complete_template",
    ):
        Experiment._check_static_spa_contracts(experiment)


def test_extract_server_error_details_finds_spa_message():
    body = """
    <html><body><pre>
    ValueError: Page 'dogfood_legacy' uses HTML/JS that needs a full browser reload between pages (error codes: complete_template).

PsyNet can usually update pages in place without reloading the browser.

What would you like to do?
1. Update this page to support in-place loading:
   https://psynetdev.gitlab.io/PsyNet/whats_new/upgrading_to_psynet_14.html
   (or in Cursor, run /upgrade-to-psynet-14)
2. Leave the HTML/JS as is, and allow full reloads for this page by passing requires_full_page_reload=True to the Page or ModularPage constructor (or set inplace_timeline_transitions = false in config.txt for a temporary experiment-wide opt-out)
    </pre></body></html>
    """

    details = _extract_server_error_details(body)
    assert "error codes: complete_template" in details
    assert "requires_full_page_reload=True" in details


def test_raise_for_status_includes_server_error_details():
    response = MagicMock()
    response.text = (
        "ValueError: Page 'dogfood_legacy' uses HTML/JS that needs a full browser "
        "reload between pages (error codes: complete_template).\n\n"
        "PsyNet can usually update pages in place without reloading the browser.\n\n"
        "What would you like to do?\n"
        "1. Update this page to support in-place loading:\n"
        "   https://example.test/upgrading_to_psynet_14.html\n"
        "   (or in Cursor, run /upgrade-to-psynet-14)\n"
        "2. Leave the HTML/JS as is, and allow full reloads for this page by "
        "passing requires_full_page_reload=True to the Page or ModularPage "
        "constructor (or set inplace_timeline_transitions = false in "
        "config.txt for a temporary experiment-wide opt-out)"
    )
    response.raise_for_status.side_effect = requests.HTTPError(
        "500 Server Error", response=response
    )

    with pytest.raises(
        requests.HTTPError,
        match=r"(?s)Server error details:.*complete_template",
    ):
        _raise_for_status_with_server_details(response)

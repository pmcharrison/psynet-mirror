import warnings

import pytest

from psynet.page import JsPsychPage, UnityPage
from psynet.timeline import Page


@pytest.mark.parametrize("argument_name", ["js_dependencies", "js_page_modules"])
@pytest.mark.parametrize(
    "invalid_value, error, match",
    [
        ([""], ValueError, "non-empty"),
        ([123], TypeError, "strings"),
        ("not-a-list", TypeError, "list or tuple"),
    ],
)
def test_page_validates_managed_javascript_urls(
    argument_name, invalid_value, error, match
):
    with pytest.raises(error, match=match):
        Page(
            template_fragment_str="<p>Managed JavaScript page</p>",
            **{argument_name: invalid_value},
        )


def test_page_normalizes_javascript_resources():
    page = Page(
        template_fragment_str="<p>Managed JavaScript page</p>",
        js_dependencies=[
            "/static/library.js",
            "/static/other-library.js",
            "/static/library.js",
        ],
        js_page_modules=[
            "/static/page.js",
            "/static/other-page.js",
            "/static/page.js",
        ],
    )

    assert page.js_dependencies == [
        "/static/library.js",
        "/static/other-library.js",
    ]
    assert page.js_page_modules == [
        "/static/page.js",
        "/static/other-page.js",
    ]


def test_page_rejects_javascript_url_with_conflicting_lifecycles():
    with pytest.raises(ValueError, match="both js_dependencies and js_page_modules"):
        Page(
            template_fragment_str="<p>Conflicting JavaScript page</p>",
            js_dependencies=["/static/shared.js"],
            js_page_modules=["/static/shared.js"],
        )


@pytest.mark.parametrize(
    "value, expected",
    [
        ("window.first = true;", ["window.first = true;"]),
        (
            ("window.first = true;", "window.second = true;"),
            ["window.first = true;", "window.second = true;"],
        ),
    ],
)
def test_page_normalizes_js_page_code(value, expected):
    page = Page(
        template_fragment_str="<p>Inline page code</p>",
        js_page_code=value,
    )

    assert page.js_page_code == expected


@pytest.mark.parametrize(
    "value, error, match",
    [
        (123, TypeError, "string, list, or tuple"),
        ([123], TypeError, "entries must be strings"),
        ([""], ValueError, "entries must be non-empty"),
    ],
)
def test_page_validates_js_page_code(value, error, match):
    with pytest.raises(error, match=match):
        Page(
            template_fragment_str="<p>Invalid inline page code</p>",
            js_page_code=value,
        )


def test_page_supports_deprecated_javascript_arguments():
    with pytest.warns(FutureWarning) as warning_log:
        page = Page(
            template_fragment_str="<p>Legacy JavaScript API</p>",
            js_links=["/static/legacy.js"],
            scripts=["window.legacySetup = true;"],
        )

    assert [str(item.message) for item in warning_log] == [
        "js_links is deprecated; migrate to js_dependencies or js_page_modules.",
        "scripts is deprecated; migrate to js_page_code.",
    ]
    assert page.js_links == ["/static/legacy.js"]
    assert page.js_page_code == ["window.legacySetup = true;"]


def test_empty_deprecated_javascript_arguments_do_not_warn():
    with warnings.catch_warnings(record=True) as warning_log:
        warnings.simplefilter("always")
        page = Page(
            template_fragment_str="<p>Empty legacy JavaScript API</p>",
            js_links=[],
            scripts=[],
        )

    assert warning_log == []
    assert page.js_links == []
    assert page.js_page_code == []


@pytest.mark.parametrize(
    "timeline",
    [
        "templates/reaction-time-task.html",
        "/static/reaction-time-task.htm",
    ],
)
def test_jspsych_page_rejects_html_timeline_api(timeline):
    with pytest.raises(
        ValueError,
        match=r"JsPsychPage.*no longer accepts HTML.*migrate-page-javascript",
    ):
        JsPsychPage(
            "task",
            timeline=timeline,
            time_estimate=1,
            js_dependencies=[],
            css_links=[],
        )


def test_jspsych_page_detects_old_jinja_timeline_template(tmp_path):
    timeline = tmp_path / "timeline.txt"
    timeline.write_text(
        '{% extends "jspsych-page.html" %}\n{% block timeline %}{% endblock %}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"old Jinja timeline template"):
        JsPsychPage(
            "task",
            timeline=str(timeline),
            time_estimate=1,
            js_dependencies=[],
            css_links=[],
        )


def test_jspsych_page_configures_timeline_module():
    page = JsPsychPage(
        "task",
        timeline="/static/reaction-time-task.js",
        time_estimate=1,
        js_dependencies=["/static/jspsych.js"],
        css_links=["/static/jspsych.css"],
        js_vars={"welcome": "Hello"},
    )

    assert page.js_vars == {
        "welcome": "Hello",
        "jspsych_timeline_module": "/static/reaction-time-task.js",
    }
    assert page.js_dependencies == ["/static/jspsych.js"]
    assert page.js_page_modules == ["/static/scripts/jspsych-page.js"]
    assert "<script" not in page.template_str


def test_document_owning_pages_require_full_reload():
    assert Page.requires_full_page_reload is False
    assert JsPsychPage.requires_full_page_reload is True
    assert UnityPage.requires_full_page_reload is True

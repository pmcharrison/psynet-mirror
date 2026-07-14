import pytest

from psynet.page import JsPsychPage
from psynet.timeline import Page


@pytest.mark.parametrize("argument_name", ["js_dependencies", "js_page_scripts"])
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
        js_page_scripts=[
            "/static/page.js",
            "/static/other-page.js",
            "/static/page.js",
        ],
    )

    assert page.js_dependencies == [
        "/static/library.js",
        "/static/other-library.js",
    ]
    assert page.js_page_scripts == [
        "/static/page.js",
        "/static/other-page.js",
    ]


def test_page_rejects_javascript_url_with_conflicting_lifecycles():
    with pytest.raises(ValueError, match="both js_dependencies and js_page_scripts"):
        Page(
            template_fragment_str="<p>Conflicting JavaScript page</p>",
            js_dependencies=["/static/shared.js"],
            js_page_scripts=["/static/shared.js"],
        )


@pytest.mark.parametrize(
    "legacy_argument, value",
    [
        ("js_links", ["/static/legacy.js"]),
        ("scripts", ["window.legacySetup = true;"]),
        ("js_links", []),
        ("scripts", []),
    ],
)
def test_page_rejects_removed_javascript_arguments(legacy_argument, value):
    with pytest.raises(
        ValueError,
        match=rf"Page\(\) no longer accepts {legacy_argument}.*migrate-page-javascript",
    ):
        Page(
            template_fragment_str="<p>Removed JavaScript API</p>",
            **{legacy_argument: value},
        )


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
    assert page.js_page_scripts == ["/static/scripts/jspsych-page.js"]
    assert "<script" not in page.template_str

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
            "  /static/other-library.js  ",
            "/static/library.js",
            " /static/library.js ",
        ],
        js_page_modules=[
            "/static/page.js",
            " /static/other-page.js ",
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


@pytest.mark.parametrize(
    "value, error, match",
    [
        (123, TypeError, r"\bscripts\b.*string, list, or tuple"),
        ([123], TypeError, r"\bscripts\b.*entries must be strings"),
        ([""], ValueError, r"\bscripts\b.*entries must be non-empty"),
    ],
)
def test_page_validates_deprecated_scripts_argument(value, error, match):
    with pytest.raises(error, match=match):
        Page(
            template_fragment_str="<p>Invalid legacy scripts</p>",
            scripts=value,
        )


def test_page_supports_deprecated_javascript_arguments():
    with pytest.warns(FutureWarning) as warning_log:
        page = Page(
            template_fragment_str="<p>Legacy JavaScript API</p>",
            js_links=["/static/legacy.js"],
            scripts=["var legacyGlobal = true;"],
            js_page_code="window.managed = true;",
        )

    assert [str(item.message) for item in warning_log] == [
        "js_links is deprecated; migrate to js_dependencies or js_page_modules.",
        "scripts is deprecated; migrate to js_page_code.",
    ]
    assert page.legacy_js_links == ["/static/legacy.js"]
    assert page.legacy_scripts == ["var legacyGlobal = true;"]
    assert page.js_page_code == ["window.managed = true;"]
    assert page.requires_full_page_reload is True


def test_empty_deprecated_javascript_arguments_do_not_warn():
    with warnings.catch_warnings(record=True) as warning_log:
        warnings.simplefilter("always")
        page = Page(
            template_fragment_str="<p>Empty legacy JavaScript API</p>",
            js_links=[],
            scripts=[],
        )

    assert warning_log == []
    assert page.legacy_js_links == []
    assert page.legacy_scripts == []
    assert page.js_page_code == []
    assert page.requires_full_page_reload is False


def test_legacy_js_links_alone_force_full_reload():
    with pytest.warns(FutureWarning, match="js_links is deprecated"):
        page = Page(
            template_fragment_str="<p>Legacy links only</p>",
            js_links=["/static/legacy.js"],
        )

    assert page.requires_full_page_reload is True
    assert page.legacy_js_links == ["/static/legacy.js"]
    assert page.legacy_scripts == []
    assert page.js_page_code == []


def test_wait_page_gates_auto_advance_on_page_ready():
    from psynet.page import WaitPage

    page = WaitPage(
        wait_time=1.5,
        js_page_code="window.afterWaitSetup = true;",
    )

    assert page.js_page_code[0] == (
        'trial.onEvent("pageReady", () => {\n'
        "    trial.setTimer(() => psynet.nextPage(), 1500);\n"
        "});"
    )
    assert page.js_page_code[1] == "window.afterWaitSetup = true;"
    assert "psynet.trial.setTimer" not in page.template_str
    assert "setTimer" not in page.template_str


def test_response_approved_defers_fragment_rendering(monkeypatch):
    from types import SimpleNamespace

    import psynet.experiment as experiment_module

    monkeypatch.setattr(experiment_module, "success_response", lambda **kwargs: kwargs)

    page = SimpleNamespace(
        is_timeline_hold=False,
        requires_full_page_reload=False,
        __json__=lambda participant: {},
    )
    exp = experiment_module.Experiment.__new__(experiment_module.Experiment)
    exp.timeline = SimpleNamespace(get_current_elt=lambda *args: page)
    payload = experiment_module.Experiment.response_approved(exp, object())

    assert "timeline_fragment" not in payload


def test_response_approved_returns_timeline_hold_without_rendering_fragment(
    monkeypatch,
):
    from types import SimpleNamespace

    import psynet.experiment as experiment_module

    monkeypatch.setattr(experiment_module, "success_response", lambda **kwargs: kwargs)

    hold = {"barrier_id": "round", "message": "Waiting for your partner…"}
    page = SimpleNamespace(
        is_timeline_hold=True,
        requires_full_page_reload=False,
        timeline_hold_payload=lambda participant: hold,
        __json__=lambda participant: {"attributes": {"page_uuid": "hold-uuid"}},
    )
    exp = experiment_module.Experiment.__new__(experiment_module.Experiment)
    exp.timeline = SimpleNamespace(get_current_elt=lambda *args: page)

    payload = experiment_module.Experiment.response_approved(exp, object())

    assert payload["submission"] == "approved"
    assert payload["timeline_hold"] == hold
    assert "timeline_fragment" not in payload


def test_response_approved_reuses_resolved_page(monkeypatch):
    from types import SimpleNamespace

    import psynet.experiment as experiment_module

    monkeypatch.setattr(experiment_module, "success_response", lambda **kwargs: kwargs)
    page = SimpleNamespace(
        is_timeline_hold=False,
        requires_full_page_reload=False,
        __json__=lambda participant: {"attributes": {"page_uuid": "resolved"}},
    )
    exp = experiment_module.Experiment.__new__(experiment_module.Experiment)
    exp.timeline = SimpleNamespace(
        get_current_elt=lambda *args: pytest.fail("Page was resolved twice.")
    )

    payload = experiment_module.Experiment.response_approved(
        exp,
        object(),
        page=page,
    )

    assert payload["page"]["attributes"]["page_uuid"] == "resolved"


@pytest.mark.parametrize("pgcode", ["40001", "40P01", "55P03"])
def test_transient_transaction_errors_are_retryable(pgcode):
    from types import SimpleNamespace

    from psynet.experiment import Experiment

    error = SimpleNamespace(orig=SimpleNamespace(pgcode=pgcode))
    assert Experiment._is_transient_transaction_error(error)


def test_other_database_errors_are_not_retryable():
    from types import SimpleNamespace

    from psynet.experiment import Experiment

    error = SimpleNamespace(orig=SimpleNamespace(pgcode="23505"))
    assert not Experiment._is_transient_transaction_error(error)


def test_busy_response_is_retryable_http_503():
    from flask import Flask

    from psynet.experiment import Experiment

    app = Flask(__name__)
    with app.app_context():
        response, status = Experiment.busy_response()

    assert status == 503
    data = response.get_json()
    assert data["status"] == "busy"
    assert data["submission"] == "busy"
    assert "temporarily busy" in data["message"]


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
        match=r"(?s)JsPsychPage.*jspsych_html_timeline.*upgrade-to-psynet-14",
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

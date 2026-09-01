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


def test_response_prepare_error_returns_busy_for_transient_lock(monkeypatch):

    import sqlalchemy
    from flask import Flask
    from psycopg2.errors import LockNotAvailable

    from psynet.experiment import Experiment

    class FakeOperationalError(sqlalchemy.exc.OperationalError):
        pass

    err = FakeOperationalError("stmt", {}, LockNotAvailable())
    monkeypatch.setattr(
        Experiment,
        "_is_transient_transaction_error",
        classmethod(lambda cls, error: True),
    )
    app = Flask(__name__)
    with app.app_context():
        response, status = Experiment._handle_response_prepare_error(
            Experiment.__new__(Experiment),
            participant_id=1,
            error=err,
        )
    assert status == 503
    assert response.get_json()["submission"] == "busy"


def test_process_response_reraises_transient_lock_errors(monkeypatch):
    from types import SimpleNamespace

    import sqlalchemy

    from psynet.experiment import Experiment

    orig = SimpleNamespace(pgcode="55P03")
    err = sqlalchemy.exc.OperationalError("stmt", {}, orig)
    handled = {}

    class Query:
        def with_for_update(self, **kwargs):
            return self

        def populate_existing(self):
            return self

        def get(self, participant_id):
            return SimpleNamespace(
                id=participant_id,
                page_uuid="page",
                current_trial=None,
            )

    def raise_lock(*args, **kwargs):
        raise err

    exp = Experiment.__new__(Experiment)
    exp.timeline = SimpleNamespace(get_current_elt=raise_lock)
    exp.handle_error = lambda *args, **kwargs: handled.setdefault("called", True)
    monkeypatch.setattr("psynet.experiment.Participant.query", Query())

    with pytest.raises(sqlalchemy.exc.OperationalError):
        exp.process_response(
            participant_id=1,
            raw_answer=None,
            blobs={},
            metadata={},
            page_uuid="page",
            client_ip_address="127.0.0.1",
        )
    assert "called" not in handled


def test_response_render_error_after_commit_does_not_return_busy(monkeypatch):
    from types import SimpleNamespace

    import sqlalchemy
    from psycopg2.errors import LockNotAvailable

    from psynet.experiment import Experiment

    class FakeOperationalError(sqlalchemy.exc.OperationalError):
        pass

    err = FakeOperationalError("stmt", {}, LockNotAvailable())
    monkeypatch.setattr(
        Experiment,
        "_is_transient_transaction_error",
        classmethod(lambda cls, error: True),
    )
    handled = {}

    class FakeExperiment:
        HandledError = type("HandledError", (Exception,), {})

        def handle_error(self, error, **kwargs):
            handled["error"] = error

    monkeypatch.setattr(
        "psynet.experiment.Participant.query.get",
        lambda participant_id: SimpleNamespace(current_trial=None, id=participant_id),
    )
    monkeypatch.setattr(
        "psynet.experiment.error_response",
        lambda **kwargs: ("error-page", 500),
    )
    result = Experiment._handle_response_render_error(
        FakeExperiment(),
        participant_id=1,
        error=err,
    )
    assert result == ("error-page", 500)
    assert "error" in handled


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

import json
from unittest.mock import Mock, call, patch

import pytest
import requests

from psynet.deploy_launch import (
    _is_ssl_error,
    _wait_reason,
    handle_launch_data,
    patch_dallinger_handle_launch_data,
)


class RecordingSpinner:
    def __init__(self, text=""):
        self.texts = []
        self._text = ""
        self.ok_called = None
        self.fail_called = None
        self.text = text

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, value):
        self._text = value
        self.texts.append(value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ok(self, msg=""):
        self.ok_called = msg

    def fail(self, msg=""):
        self.fail_called = msg


def _spinner_factory(spinner):
    def factory(text):
        spinner.text = text
        return spinner

    return factory


def _json_response(payload, status_code=200, ok=None, text=""):
    response = Mock()
    response.ok = (status_code < 400) if ok is None else ok
    response.status_code = status_code
    response.text = text or ""
    response.json.return_value = payload
    response.raise_for_status = Mock()
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError()
    return response


def test_ssl_errors_show_progress_then_succeed():
    error = Mock()
    spinner = RecordingSpinner()
    ssl_error = requests.exceptions.SSLError(
        "HTTPSConnectionPool(host='example.test', port=443): "
        "Max retries exceeded with url: /launch "
        "(Caused by SSLError(SSLError(1, "
        "'[SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error')))"
    )
    responses = [
        ssl_error,
        ssl_error,
        _json_response({"message": "ok", "status": "success", "recruitment_msg": "hi"}),
    ]

    def fake_post(_url):
        item = responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    with patch("psynet.deploy_launch.requests.post", side_effect=fake_post):
        result = handle_launch_data(
            "https://example.test/launch",
            error=error,
            delay=0.01,
            attempts=3,
            sleep=lambda _seconds: None,
            spinner_factory=_spinner_factory(spinner),
        )

    assert result["recruitment_msg"] == "hi"
    error.assert_not_called()
    assert spinner.ok_called == "✔"
    assert spinner.fail_called is None
    assert any("HTTPS/SSL" in text for text in spinner.texts)
    assert any("[" in text and ("█" in text or "░" in text) for text in spinner.texts)
    assert not any(
        "Experiment launch failed. Trying again" in text for text in spinner.texts
    )


def test_ssl_timeout_reports_the_real_error():
    error = Mock()
    spinner = RecordingSpinner()
    ssl_error = requests.exceptions.SSLError("tlsv1 alert internal error")

    with patch(
        "psynet.deploy_launch.requests.post",
        side_effect=ssl_error,
    ):
        with pytest.raises(requests.exceptions.ConnectionError):
            handle_launch_data(
                "https://example.test/launch",
                error=error,
                delay=0.01,
                attempts=3,
                context="ssh",
                dns_host="example.test",
                dozzle_password="secret",
                sleep=lambda _seconds: None,
                spinner_factory=_spinner_factory(spinner),
            )

    messages = [call.args[0] for call in error.call_args_list]
    assert any("tlsv1 alert internal error" in message for message in messages)
    assert "Experiment launch failed after multiple attempts." in messages
    assert not any("Trying again" in message for message in messages)
    assert spinner.fail_called == "✖"
    assert spinner.ok_called is None


def test_http_errors_are_quiet_until_the_final_failure():
    error = Mock()
    spinner = RecordingSpinner()
    failing = _json_response(
        {"message": "msg!"}, status_code=500, ok=False, text="Failure"
    )

    with patch("psynet.deploy_launch.requests.post", return_value=failing):
        with pytest.raises(requests.exceptions.HTTPError):
            handle_launch_data(
                "/some-launch-url",
                error=error,
                delay=0.05,
                attempts=3,
                sleep=lambda _seconds: None,
                spinner_factory=_spinner_factory(spinner),
            )

    error.assert_has_calls(
        [
            call("Error accessing /some-launch-url (500):\nFailure"),
            call("Experiment launch failed after multiple attempts."),
            call("msg!"),
        ]
    )
    assert error.call_count == 3


def test_success_on_first_attempt_does_not_report_an_error():
    error = Mock()
    payload = {"message": "msg!"}
    with patch(
        "psynet.deploy_launch.requests.post",
        return_value=_json_response(payload),
    ):
        assert (
            handle_launch_data(
                "/some-launch-url",
                error=error,
                spinner_factory=_spinner_factory(RecordingSpinner()),
            )
            == payload
        )
    error.assert_not_called()


def test_non_json_response_is_retried_quietly_then_reported():
    error = Mock()
    response = Mock(
        ok=False,
        status_code=502,
        text="<html>starting</html>",
        json=Mock(side_effect=json.decoder.JSONDecodeError("Expecting value", "", 0)),
        raise_for_status=Mock(side_effect=requests.exceptions.HTTPError()),
    )
    with patch("psynet.deploy_launch.requests.post", return_value=response):
        with pytest.raises(requests.exceptions.HTTPError):
            handle_launch_data(
                "https://example.test/launch",
                error=error,
                delay=0.01,
                attempts=2,
                sleep=lambda _seconds: None,
                spinner_factory=_spinner_factory(RecordingSpinner()),
            )

    messages = [call.args[0] for call in error.call_args_list]
    assert any("Error parsing response" in message for message in messages)
    assert not any("Trying again" in message for message in messages)


def test_unexpected_value_error_is_reported_immediately():
    error = Mock()
    response = Mock(
        json=Mock(side_effect=ValueError()),
        text="Big, unexpected problem.",
    )
    with patch("psynet.deploy_launch.requests.post", return_value=response):
        with pytest.raises(ValueError):
            handle_launch_data(
                "/some-launch-url",
                error=error,
                spinner_factory=_spinner_factory(RecordingSpinner()),
            )

    error.assert_called_once_with(
        "Error parsing response from /some-launch-url, check server logs for details.\n\n"
        "Big, unexpected problem."
    )


def test_ssh_context_prints_dozzle_hint_only_after_timeout():
    error = Mock()
    failing = _json_response(
        {"message": "msg!"}, status_code=500, ok=False, text="Failure"
    )
    with (
        patch("psynet.deploy_launch.requests.post", return_value=failing),
        patch("psynet.deploy_launch.print_bold") as print_bold,
    ):
        with pytest.raises(requests.exceptions.HTTPError):
            handle_launch_data(
                "https://example.com/launch",
                error=error,
                delay=0.01,
                attempts=2,
                context="ssh",
                dns_host="example.com",
                dozzle_password="secret",
                sleep=lambda _seconds: None,
                spinner_factory=_spinner_factory(RecordingSpinner()),
            )

    print_bold.assert_called_once_with(
        "Check the detailed server logs at https://logs.example.com "
        "(user = dallinger, password = secret)"
    )


def test_ssl_reason_detection():
    wrapped = requests.exceptions.ConnectionError(
        requests.exceptions.SSLError("tlsv1 alert internal error")
    )
    wrapped.__cause__ = requests.exceptions.SSLError("tlsv1 alert internal error")
    assert _is_ssl_error(wrapped)
    assert "HTTPS/SSL" in _wait_reason(exc=wrapped)
    assert "reverse proxy" in _wait_reason(status_code=502)
    assert "experiment process" in _wait_reason(parse_error=True)


def test_patch_installs_progress_handler_on_dallinger():
    import importlib

    docker_ssh = importlib.import_module("dallinger.command_line.docker_ssh")
    import dallinger.deployment as deployment

    installed = patch_dallinger_handle_launch_data()

    assert getattr(installed, "reports_transient_errors_as_progress", False)
    assert getattr(
        deployment.handle_launch_data, "reports_transient_errors_as_progress", False
    )
    assert getattr(
        docker_ssh.handle_launch_data, "reports_transient_errors_as_progress", False
    )
    patch_dallinger_handle_launch_data()
    assert deployment.handle_launch_data is installed

"""Quiet launch retries while a remote experiment becomes reachable.

``psynet debug ssh`` and ``psynet deploy ssh`` POST to ``/launch`` as soon as
Caddy has reloaded. HTTPS certificates and the web process are often still
starting, so the first requests fail with SSL handshake errors, connection
errors, or non-JSON proxy pages. Dallinger used to print those as launch
failures even though later retries usually succeed.

This module replaces that reporter with a progress display. Transient startup
failures stay off the error stream; the last error is printed only when the
retry budget is exhausted. Please review this module docstring for accuracy.
"""

from __future__ import annotations

import json
import sys
import time

import requests
from dallinger.utils import print_bold
from yaspin import yaspin

# Keep retry timing aligned with dallinger.deployment.
DEFAULT_DELAY = 1
BACKOFF_FACTOR = 2
MAX_ATTEMPTS = 6
TRANSIENT_HTTP_STATUS_CODES = frozenset({404, 502, 503, 504})
_PROGRESS_BAR_WIDTH = 22
_PROGRESS_TICK_SECONDS = 0.25
_LAUNCH_IMPORT_SITES = (
    "dallinger.command_line.docker_ssh",
    "dallinger.command_line.docker",
    "dallinger.command_line.develop",
)


class _NullSpinner:
    """No-op spinner used when launch does not show a progress display."""

    def __init__(self, text="", **_kwargs):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ok(self, _msg=""):
        return None

    def fail(self, _msg=""):
        return None


def _inter_attempt_sleeps(delay, attempts, backoff=BACKOFF_FACTOR):
    """Return the sleep before each retry, matching Dallinger's backoff."""
    sleeps = []
    current = delay
    for _ in range(max(0, attempts - 1)):
        current *= backoff
        sleeps.append(current)
    return sleeps


def _progress_bar(fraction, width=_PROGRESS_BAR_WIDTH):
    """Return a fixed-width bar for ``fraction`` in ``[0, 1]``."""
    fraction = min(max(fraction, 0.0), 1.0)
    filled = int(round(width * fraction))
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


def _status_text(reason, elapsed, total, attempt, attempts):
    """Return spinner text with an approximate completion bar."""
    if total > 0:
        fraction = min(elapsed / total, 0.99)
        bar = _progress_bar(fraction)
        percent = int(fraction * 100)
        return f"{reason}  [{bar}]  {percent}%  · attempt {attempt}/{attempts}"
    return f"{reason}  · attempt {attempt}/{attempts}"


def _is_ssl_error(exc):
    """Return whether ``exc`` is an SSL/TLS handshake failure."""
    current = exc
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, requests.exceptions.SSLError):
            return True
        name = type(current).__name__.lower()
        if "ssl" in name:
            return True
        message = str(current).lower()
        if "sslerror" in message or "tlsv1" in message or "[ssl:" in message:
            return True
        nxt = getattr(current, "__cause__", None)
        if nxt is None:
            nxt = getattr(current, "__context__", None)
        current = nxt
    return False


def _wait_reason(*, exc=None, status_code=None, parse_error=False):
    """Return a calm status line for a launch attempt that is not ready yet."""
    if parse_error:
        return "Waiting for the experiment process to start"
    if exc is not None and _is_ssl_error(exc):
        return "Waiting for HTTPS/SSL to become ready"
    if exc is not None:
        return "Waiting for the web server to become ready"
    if status_code in TRANSIENT_HTTP_STATUS_CODES:
        return "Waiting for the reverse proxy to become ready"
    if status_code:
        return "Waiting for the experiment to finish launching"
    return "Waiting for the experiment to become ready"


def _make_spinner(spinner_factory, text, use_progress):
    """Return a spinner context manager for the launch wait."""
    if spinner_factory is not None:
        return spinner_factory(text)
    if use_progress:
        return yaspin(text=text, color="green")
    return _NullSpinner(text)


def _sleep_with_progress(
    seconds,
    *,
    elapsed,
    total,
    spinner,
    reason,
    attempt,
    attempts,
    sleep,
):
    """Sleep while advancing the progress bar."""
    remaining = seconds
    while remaining > 0:
        step = min(_PROGRESS_TICK_SECONDS, remaining)
        sleep(step)
        elapsed += step
        remaining -= step
        spinner.text = _status_text(reason, elapsed, total, attempt, attempts)
    return elapsed


class _LaunchParseError(ValueError):
    """Unexpected non-JSON-decode failure while reading a launch response."""


def _attempt_launch(url):
    """POST once to ``url``.

    Returns ``(launch_data, launch_request, failure)``. ``failure`` is
    ``None`` on success, otherwise ``(wait_reason, error_message)``.
    Unexpected parse errors raise :class:`_LaunchParseError`.
    """
    try:
        launch_request = requests.post(url)
    except requests.exceptions.RequestException as err:
        reason = _wait_reason(exc=err)
        return None, None, (reason, f"Error accessing {url}:\n{err}")

    try:
        launch_data = launch_request.json()
    except json.decoder.JSONDecodeError:
        reason = _wait_reason(parse_error=True)
        message = (
            f"Error parsing response from {url}, "
            f"check server logs for details.\n{launch_request.text}"
        )
        return None, launch_request, (reason, message)
    except ValueError as err:
        message = (
            f"Error parsing response from {url}, "
            f"check server logs for details.\n{err}\n{launch_request.text}"
        )
        raise _LaunchParseError(message) from err

    if launch_request.ok:
        return launch_data, launch_request, None

    reason = _wait_reason(status_code=launch_request.status_code)
    message = "Error accessing {} ({}):\n{}".format(
        url, launch_request.status_code, launch_request.text
    )
    return launch_data, launch_request, (reason, message)


def _report_final_failure(
    error,
    last_error_message,
    *,
    launch_data,
    launch_request,
    context,
    dns_host,
    dozzle_password,
):
    """Print the real launch failure after retries are exhausted."""
    if last_error_message:
        error(last_error_message)
    error("Experiment launch failed after multiple attempts.")
    if launch_data and launch_data.get("message"):
        error(launch_data["message"])

    if context == "heroku":
        print_bold(
            "For detailed server logs, visit the Papertrail add-on in your Heroku dashboard"
        )
    elif context == "ssh" and dns_host and dozzle_password:
        print_bold(
            f"Check the detailed server logs at https://logs.{dns_host} "
            f"(user = dallinger, password = {dozzle_password})"
        )

    if launch_request is not None:
        launch_request.raise_for_status()
    raise requests.exceptions.ConnectionError


def handle_launch_data(
    url,
    error,
    delay=DEFAULT_DELAY,
    attempts=MAX_ATTEMPTS,
    dns_host=None,
    dozzle_password=None,
    context=None,
    *,
    sleep=time.sleep,
    spinner_factory=None,
):
    """POST to the launch URL, retrying with exponential backoff.

    Intermediate startup failures are shown as progress rather than errors.
    If every attempt fails, ``error`` receives the last failure and this
    function raises.

    Extra keyword-only arguments are for tests: ``sleep`` replaces
    ``time.sleep``, and ``spinner_factory`` replaces yaspin.
    """
    launch_data = None
    launch_request = None
    last_error_message = None
    wait_reason = "Waiting for the experiment to become ready"
    sleeps = _inter_attempt_sleeps(delay, attempts)
    total_wait = sum(sleeps)
    elapsed = 0.0
    use_progress = attempts > 1
    spinner = _make_spinner(spinner_factory, "Launching experiment...", use_progress)

    with spinner:
        for index in range(attempts):
            attempt_number = index + 1
            try:
                launch_data, launch_request, failure = _attempt_launch(url)
            except _LaunchParseError as err:
                spinner.text = "Experiment launch failed"
                spinner.fail("✖")
                error(str(err))
                raise

            if failure is None:
                spinner.text = "Experiment launched"
                spinner.ok("✔")
                return launch_data

            wait_reason, last_error_message = failure
            spinner.text = _status_text(
                wait_reason, elapsed, total_wait, attempt_number, attempts
            )
            if index < len(sleeps):
                elapsed = _sleep_with_progress(
                    sleeps[index],
                    elapsed=elapsed,
                    total=total_wait,
                    spinner=spinner,
                    reason=wait_reason,
                    attempt=attempt_number,
                    attempts=attempts,
                    sleep=sleep,
                )

        spinner.text = "Experiment launch failed"
        spinner.fail("✖")

    _report_final_failure(
        error,
        last_error_message,
        launch_data=launch_data,
        launch_request=launch_request,
        context=context,
        dns_host=dns_host,
        dozzle_password=dozzle_password,
    )


handle_launch_data.reports_transient_errors_as_progress = True


def _bind_handle_launch_data(func):
    """Point already-imported Dallinger launch callers at ``func``."""
    for name in _LAUNCH_IMPORT_SITES:
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "handle_launch_data"):
            module.handle_launch_data = func


def patch_dallinger_handle_launch_data():
    """Install progress-style launch retries on Dallinger's launch helper.

    No-ops when Dallinger already reports startup failures as progress, so the
    patch can stay in place until PsyNet drops the Dallinger pin that still
    prints retry errors.
    """
    import dallinger.deployment as deployment

    current = getattr(deployment, "handle_launch_data", None)
    if getattr(current, "reports_transient_errors_as_progress", False):
        _bind_handle_launch_data(current)
        return current

    deployment.handle_launch_data = handle_launch_data
    _bind_handle_launch_data(handle_launch_data)
    return handle_launch_data

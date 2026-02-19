from unittest.mock import Mock

import botocore
import pytest

from psynet.media import _run_bucket_operation_with_retry
from psynet.timeline import MediaSpec


def _operation_aborted_error():
    return botocore.exceptions.ClientError(
        {
            "Error": {
                "Code": "OperationAborted",
                "Message": "A conflicting conditional operation is currently in progress.",
            }
        },
        "PutBucketAcl",
    )


def _access_denied_error():
    return botocore.exceptions.ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}},
        "PutBucketAcl",
    )


def test_run_bucket_operation_with_retry_retries_operation_aborted(monkeypatch):
    attempts = 0
    sleep_delays = []
    monkeypatch.setattr("psynet.media.time.sleep", sleep_delays.append)

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise _operation_aborted_error()

    _run_bucket_operation_with_retry(
        operation=operation,
        operation_name="set ACL",
        max_attempts=4,
        initial_delay_seconds=0.1,
    )

    assert attempts == 3
    assert sleep_delays == [0.1, 0.2]


def test_run_bucket_operation_with_retry_does_not_retry_non_transient_errors(
    monkeypatch,
):
    sleeper = Mock()
    monkeypatch.setattr("psynet.media.time.sleep", sleeper)

    def operation():
        raise _access_denied_error()

    with pytest.raises(botocore.exceptions.ClientError, match="AccessDenied"):
        _run_bucket_operation_with_retry(
            operation=operation,
            operation_name="set ACL",
            max_attempts=4,
            initial_delay_seconds=0.1,
        )

    sleeper.assert_not_called()


def test_run_bucket_operation_with_retry_raises_after_max_attempts(monkeypatch):
    attempts = 0
    sleep_delays = []
    monkeypatch.setattr("psynet.media.time.sleep", sleep_delays.append)

    def operation():
        nonlocal attempts
        attempts += 1
        raise _operation_aborted_error()

    with pytest.raises(botocore.exceptions.ClientError, match="OperationAborted"):
        _run_bucket_operation_with_retry(
            operation=operation,
            operation_name="set ACL",
            max_attempts=3,
            initial_delay_seconds=0.1,
        )

    assert attempts == 3
    assert sleep_delays == [0.1, 0.2]


def test_ids():
    media = MediaSpec(
        audio={
            "bier": "/static/audio/bier.wav",
            "batch": {
                "url": "/static/audio/some_filename.mp3",
                "ids": ["funk_game_loop", "honey_bee", "there_it_is"],
                "type": "batch",
            },
        },
        video={"vid1": "my-video.mp4"},
    )
    assert media.ids == {
        "audio": {"bier", "funk_game_loop", "honey_bee", "there_it_is"},
        "image": set(),
        "html": set(),
        "video": {"vid1"},
    }

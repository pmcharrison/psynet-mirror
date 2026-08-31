from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from psynet.page import WaitPage, wait_while
from psynet.timeline import (
    StartFixTimeCredit,
    _while_loop_state_key,
    _while_loop_timed_out,
)
from psynet.timeline_hold import TimelineHoldRecord, _safely_queue_timeline_hold_wake
from psynet.utils import serialise


def participant():
    obj = SimpleNamespace(
        time_credit=0.0,
        time_credit_fixes=[],
        total_wait_page_time=0.0,
    )

    def inc_time_credit(seconds):
        obj.time_credit += seconds

    obj.inc_time_credit = inc_time_credit
    return obj


def test_timeline_hold_accounts_release_to_resume_once():
    start = datetime(2026, 1, 1)
    record = TimelineHoldRecord(
        started_at=start,
        expected_wait=1.5,
        max_wait_time=20,
        fix_time_credit=False,
    )
    p = participant()

    record.mark_released(p, start + timedelta(seconds=3))
    record.settle(p, start + timedelta(seconds=5))
    record.settle(p, start + timedelta(seconds=5))

    assert record.released_at == start + timedelta(seconds=3)
    assert record.resumed_at == start + timedelta(seconds=5)
    assert record.actual_wait_seconds == pytest.approx(5)
    assert record.credited_wait_seconds == pytest.approx(5)
    assert p.time_credit == pytest.approx(5)
    assert p.total_wait_page_time == pytest.approx(5)


def test_timeline_hold_caps_credit_but_not_diagnostics():
    start = datetime(2026, 1, 1)
    record = TimelineHoldRecord(
        started_at=start,
        expected_wait=2,
        max_wait_time=4,
        fix_time_credit=False,
    )
    p = participant()

    record.settle(p, start + timedelta(seconds=7))

    assert record.actual_wait_seconds == pytest.approx(7)
    assert record.credited_wait_seconds == pytest.approx(4)
    assert p.time_credit == pytest.approx(4)
    assert p.total_wait_page_time == pytest.approx(7)


def test_fixed_timeline_hold_records_expected_credit():
    start = datetime(2026, 1, 1)
    record = TimelineHoldRecord(
        started_at=start,
        expected_wait=2,
        max_wait_time=10,
        fix_time_credit=True,
    )
    p = participant()

    record.settle(p, start + timedelta(seconds=7))

    assert record.actual_wait_seconds == pytest.approx(7)
    assert record.credited_wait_seconds == pytest.approx(2)
    assert p.time_credit == 0
    assert p.total_wait_page_time == pytest.approx(7)


def test_separate_hold_visits_do_not_recredit_earlier_waiting():
    start = datetime(2026, 1, 1)
    p = participant()
    first = TimelineHoldRecord(
        started_at=start,
        expected_wait=1,
        max_wait_time=10,
        fix_time_credit=False,
    )
    second = TimelineHoldRecord(
        started_at=start + timedelta(seconds=2),
        expected_wait=1,
        max_wait_time=10,
        fix_time_credit=False,
    )

    first.settle(p, start + timedelta(seconds=1))
    second.settle(p, start + timedelta(seconds=3))

    assert p.time_credit == pytest.approx(2)
    assert p.total_wait_page_time == pytest.approx(2)


def test_while_loop_timeout_uses_exact_elapsed_time():
    start = datetime(2026, 1, 1)
    key = _while_loop_state_key("wait_while", "loop_start_time")
    p = SimpleNamespace(
        var=SimpleNamespace(
            get=lambda name, default=None: {key: serialise(start)}.get(name, default)
        )
    )

    assert not _while_loop_timed_out(
        p, "wait_while", 2, now=start + timedelta(seconds=1.999)
    )
    assert _while_loop_timed_out(p, "wait_while", 2, now=start + timedelta(seconds=2))


def test_wait_while_defaults_to_timeline_hold():
    logic = wait_while(lambda: True, expected_wait=3)
    holds = [elt for elt in logic if getattr(elt, "is_timeline_hold", False)]

    assert len(holds) == 1
    assert holds[0].time_estimate == 3
    assert not any(isinstance(elt, WaitPage) for elt in logic)
    assert not any(isinstance(elt, StartFixTimeCredit) for elt in logic)


def test_wait_while_preserves_explicit_wait_page_behavior():
    logic = wait_while(lambda: True, expected_wait=3, wait_page=WaitPage)

    assert any(isinstance(elt, WaitPage) for elt in logic)
    assert not any(getattr(elt, "is_timeline_hold", False) for elt in logic)
    assert any(isinstance(elt, StartFixTimeCredit) for elt in logic)


def test_wait_while_can_fix_timeline_hold_credit():
    logic = wait_while(
        lambda: True,
        expected_wait=3,
        fix_time_credit=True,
    )

    assert any(getattr(elt, "is_timeline_hold", False) for elt in logic)
    assert any(isinstance(elt, StartFixTimeCredit) for elt in logic)


def test_wait_while_accepts_custom_hold_content():
    logic = wait_while(
        lambda: True,
        expected_wait=1,
        content="Custom hold message",
    )
    hold = next(elt for elt in logic if getattr(elt, "is_timeline_hold", False))

    assert hold.content == "Custom hold message"


def test_safe_hold_wake_does_not_propagate_notification_errors(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError("wake failed")

    monkeypatch.setattr(
        "psynet.timeline_hold._queue_timeline_hold_wake",
        fail,
    )

    _safely_queue_timeline_hold_wake(1)

    assert "Failed to queue a timeline hold wake" in caplog.text

"""Durable in-place waiting for server-side timeline conditions.

Timeline holds preserve the currently rendered participant page while the
server waits for a condition to clear. This module owns the durable accounting
record and the internal page protocol shared by barriers and ``wait_while``.
"""

import json
import uuid
from datetime import timedelta

from dallinger import db
from dallinger.models import timenow
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    event,
)
from sqlalchemy.orm import relationship

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.timeline import Page, get_template
from psynet.utils import call_function_with_context, get_logger, get_translator

_TIMELINE_HOLD_CHANNEL = "psynet_timeline_hold"
_PENDING_WAKE_KEY = "psynet_timeline_hold_wakes"
logger = get_logger()


def _enqueue_timeline_hold_wake(participant_id, *, page_uuid=None, reason=None):
    """Queue a targeted hold wake for publication after the next commit."""
    if page_uuid is None:
        from psynet.participant import Participant

        page_uuid = (
            Participant.query.with_entities(Participant.page_uuid)
            .filter_by(id=participant_id)
            .scalar()
        )
    if page_uuid is None:
        return
    active_hold = TimelineHoldRecord.query.filter_by(
        participant_id=participant_id,
        page_uuid=page_uuid,
        resumed_at=None,
    ).first()
    if active_hold is None:
        return
    wake = {
        "wake_token": active_hold.wake_token,
        "reason": reason,
    }
    db.session.info.setdefault(_PENDING_WAKE_KEY, {})[active_hold.wake_token] = wake


def _queue_timeline_hold_wake(participant_id, *, page_uuid=None, reason=None):
    """Queue a wake without allowing notification failure to break core work."""
    try:
        _enqueue_timeline_hold_wake(
            participant_id,
            page_uuid=page_uuid,
            reason=reason,
        )
    except Exception:
        logger.warning(
            "Failed to queue a timeline hold wake for participant %s.",
            participant_id,
            exc_info=True,
        )


@event.listens_for(db.session, "after_commit")
def _publish_timeline_hold_wakes(session):
    wakes = list(session.info.pop(_PENDING_WAKE_KEY, {}).values())
    if not wakes:
        return
    try:
        db.redis_conn.publish(
            _TIMELINE_HOLD_CHANNEL,
            json.dumps({"type": "timeline_hold_wake", "targets": wakes}),
        )
    except Exception:
        logger.warning("Failed to publish timeline hold wake.", exc_info=True)


@event.listens_for(db.session, "after_rollback")
def _discard_timeline_hold_wakes(session):
    session.info.pop(_PENDING_WAKE_KEY, None)


@register_table
class TimelineHoldRecord(SQLBase, SQLMixin):
    """Store timing, compensation, and lifecycle data for one timeline hold."""

    __tablename__ = "timeline_hold"

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant", backref="timeline_holds"
    )
    page_uuid = Column(String, unique=True, index=True)
    wake_token = Column(
        String, unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    hold_id = Column(String, index=True)
    started_at = Column(DateTime)
    deadline_at = Column(DateTime)
    released_at = Column(DateTime)
    resumed_at = Column(DateTime)
    expected_wait = Column(Float, default=0.0)
    max_wait_time = Column(Float)
    fix_time_credit = Column(Boolean, default=False)
    actual_wait_seconds = Column(Float, default=0.0)
    credited_wait_seconds = Column(Float, default=0.0)

    def _elapsed_at(self, timestamp):
        return max(0.0, (timestamp - self.started_at).total_seconds())

    def account_until(self, participant, timestamp):
        """Account newly elapsed visible waiting time through ``timestamp``."""
        if self.resumed_at is not None and timestamp > self.resumed_at:
            timestamp = self.resumed_at
        elapsed = self._elapsed_at(timestamp)
        previous_actual = self.actual_wait_seconds or 0.0
        if elapsed <= previous_actual:
            return

        participant.total_wait_page_time = (participant.total_wait_page_time or 0.0) + (
            elapsed - previous_actual
        )
        self.actual_wait_seconds = elapsed

        if not self.fix_time_credit:
            target_credit = elapsed
            if self.max_wait_time is not None:
                target_credit = min(target_credit, self.max_wait_time)
            previous_credit = self.credited_wait_seconds or 0.0
            if target_credit > previous_credit:
                participant.inc_time_credit(target_credit - previous_credit)
                self.credited_wait_seconds = target_credit

    def mark_released(self, participant, timestamp=None):
        """Record a durable release and account waiting through that point."""
        if timestamp is None:
            timestamp = timenow()
        if self.released_at is None:
            self.released_at = timestamp
        self.account_until(participant, timestamp)

    def settle(self, participant, timestamp=None):
        """Finalize this hold exactly once when the participant resumes."""
        if self.resumed_at is not None:
            return
        if timestamp is None:
            timestamp = timenow()
        if self.released_at is None:
            self.released_at = timestamp
        self.account_until(participant, timestamp)
        self.resumed_at = timestamp
        if self.fix_time_credit:
            previous_credit = self.credited_wait_seconds or 0.0
            target_credit = self.expected_wait or 0.0
            if target_credit > previous_credit:
                participant.inc_time_credit(target_credit - previous_credit)
            self.credited_wait_seconds = target_credit

    @property
    def deadline(self):
        """Return the authoritative timeout deadline, if configured."""
        return self.deadline_at


class _TimelineHoldPage(Page):
    """Internal page checkpoint that preserves the preceding browser page."""

    is_timeline_hold = True

    def __init__(
        self,
        *,
        hold_id,
        expected_wait,
        max_wait_time,
        fix_time_credit,
        check_interval,
        content=None,
        message_kind=None,
        fail_on_timeout=True,
        on_timeout=None,
    ):
        self.hold_id = hold_id
        self.expected_wait = expected_wait
        self.max_wait_time = max_wait_time
        self.fix_time_credit = fix_time_credit
        self.check_interval = check_interval
        self.content = content
        self.message_kind = message_kind
        self._fail_on_timeout = fail_on_timeout
        self.on_timeout = on_timeout
        super().__init__(
            label="wait",
            time_estimate=expected_wait,
            save_answer=False,
            template_str=get_template("timeline-hold-page.html"),
            template_arg={"content": content},
            framework_owned_template=True,
        )

    def consume(self, experiment, participant):
        super().consume(experiment, participant)
        now = timenow()
        deadline_at = (
            None
            if self.max_wait_time is None
            else now + timedelta(seconds=self.max_wait_time)
        )
        record = TimelineHoldRecord(
            participant=participant,
            page_uuid=participant.page_uuid,
            wake_token=str(uuid.uuid4()),
            hold_id=self.hold_id,
            started_at=now,
            deadline_at=deadline_at,
            expected_wait=self.expected_wait,
            max_wait_time=self.max_wait_time,
            fix_time_credit=self.fix_time_credit,
            actual_wait_seconds=0.0,
            credited_wait_seconds=0.0,
        )
        db.session.add(record)
        participant._timeline_hold_record = record
        self.on_hold_record_created(participant, record)

    def on_hold_record_created(self, participant, record):
        """Run subclass-specific linking after creating the hold record."""

    def get_hold_record(self, participant):
        """Return the record belonging to the participant's current hold page."""
        cached = getattr(participant, "_timeline_hold_record", None)
        if cached is not None and cached.page_uuid == participant.page_uuid:
            return cached
        record = TimelineHoldRecord.query.filter_by(
            participant_id=participant.id,
            page_uuid=participant.page_uuid,
        ).one()
        participant._timeline_hold_record = record
        return record

    def participant_can_resume(self, experiment, participant):
        """Return whether the authoritative waiting condition has cleared."""
        raise NotImplementedError

    def participant_timed_out(self, participant):
        """Return whether the authoritative hold deadline has passed."""
        deadline = self.get_hold_record(participant).deadline
        return deadline is not None and timenow() >= deadline

    def prepare_resume_if_ready(self, experiment, participant):
        """Prepare a cleared or timed-out hold and return whether it can resume."""
        if participant.pending_redirect is not None or participant.failed:
            self.prepare_to_resume(participant)
            return True
        if self.participant_can_resume(experiment, participant):
            self.prepare_to_resume(participant)
            return True
        if self.participant_timed_out(participant):
            self.prepare_to_resume(participant)
            self.apply_timeout(participant)
            return True
        return False

    def prepare_to_resume(self, participant):
        """Run subclass-specific cleanup immediately before settlement."""

    @property
    def fail_on_timeout(self):
        """Return whether exceeding the deadline should fail the participant."""
        return self._fail_on_timeout

    def apply_timeout(self, participant):
        """Run timeout side effects and optionally fail the participant."""
        if self.on_timeout is not None:
            call_function_with_context(self.on_timeout, participant=participant)
        if self.fail_on_timeout:
            participant.append_failure_tags(
                f"timeline_hold:{self.hold_id}",
                "fail_on_timeout",
            )
            participant.fail()

    def account_wait(self, participant, settle=False):
        """Update actual wait diagnostics and compensation."""
        record = self.get_hold_record(participant)
        if settle:
            record.settle(participant)
        else:
            record.account_until(participant, timenow())

    def translated_content(self):
        """Translate framework-provided hold messages for this participant."""
        _p = get_translator(context=True)
        if self.message_kind == "barrier":
            return _p("timeline_hold", "Waiting for other participants…")
        if self.message_kind == "generic":
            return _p(
                "timeline_hold",
                "Please wait, the experiment should continue shortly...",
            )
        return self.content

    def timeline_hold_payload(self, participant):
        """Return browser configuration for this hold visit."""
        record = self.get_hold_record(participant)
        remaining_timeout_ms = None
        if record.deadline is not None:
            remaining_timeout_ms = max(
                0, round((record.deadline - timenow()).total_seconds() * 1000)
            )
        return {
            "channel": _TIMELINE_HOLD_CHANNEL,
            "hold_id": self.hold_id,
            "message": self.translated_content(),
            "page_uuid": participant.page_uuid,
            "wake_token": record.wake_token,
            "safety_poll_ms": round(self.check_interval * 1000),
            "timeout_ms": remaining_timeout_ms,
        }

    def attributes(self, participant):
        attributes = super().attributes(participant)
        attributes["timeline_hold"] = self.timeline_hold_payload(participant)
        return attributes

    def get_bot_response(self, experiment, bot):
        return None


class _ConditionHoldPage(_TimelineHoldPage):
    """Timeline hold whose release is determined by an arbitrary condition."""

    def __init__(self, *, condition, **kwargs):
        self.condition = condition
        super().__init__(**kwargs)

    def participant_can_resume(self, experiment, participant):
        return not call_function_with_context(
            self.condition,
            experiment=experiment,
            participant=participant,
        )

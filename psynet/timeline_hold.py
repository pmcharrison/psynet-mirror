"""Durable in-place waiting for server-side timeline conditions.

Timeline holds preserve the currently rendered participant page while the
server waits for a condition to clear. This module owns the durable accounting
record and the internal page protocol shared by barriers and ``wait_while``.
"""

from datetime import timedelta

from dallinger import db
from dallinger.models import timenow
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.timeline import Page, get_template
from psynet.utils import call_function_with_context

TIMELINE_HOLD_CHANNEL = "psynet_timeline_hold"


@register_table
class TimelineHoldRecord(SQLBase, SQLMixin):
    """Store timing, compensation, and lifecycle data for one timeline hold."""

    __tablename__ = "timeline_hold"

    id = Column(Integer, primary_key=True)
    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    participant = relationship(
        "psynet.participant.Participant", backref="timeline_holds"
    )
    page_uuid = Column(String, unique=True, index=True)
    hold_id = Column(String, index=True)
    started_at = Column(DateTime)
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
        elapsed = self._elapsed_at(timestamp)
        previous_actual = self.actual_wait_seconds or 0.0
        if elapsed <= previous_actual:
            return

        participant.total_wait_page_time = (
            participant.total_wait_page_time or 0.0
        ) + (elapsed - previous_actual)
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
            self.credited_wait_seconds = self.expected_wait

    @property
    def deadline(self):
        """Return the authoritative timeout deadline, if configured."""
        if self.max_wait_time is None:
            return None
        return self.started_at + timedelta(seconds=self.max_wait_time)


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
        content,
    ):
        self.hold_id = hold_id
        self.expected_wait = expected_wait
        self.max_wait_time = max_wait_time
        self.fix_time_credit = fix_time_credit
        self.check_interval = check_interval
        self.content = content
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
        record = TimelineHoldRecord(
            participant=participant,
            page_uuid=participant.page_uuid,
            hold_id=self.hold_id,
            started_at=timenow(),
            expected_wait=self.expected_wait,
            max_wait_time=self.max_wait_time,
            fix_time_credit=self.fix_time_credit,
            actual_wait_seconds=0.0,
            credited_wait_seconds=0.0,
        )
        db.session.add(record)
        self.on_hold_record_created(participant, record)

    def on_hold_record_created(self, participant, record):
        """Run subclass-specific linking after creating the hold record."""

    def get_hold_record(self, participant):
        """Return the record belonging to the participant's current hold page."""
        return TimelineHoldRecord.query.filter_by(
            participant_id=participant.id,
            page_uuid=participant.page_uuid,
        ).one()

    def participant_can_resume(self, experiment, participant):
        """Return whether the authoritative waiting condition has cleared."""
        raise NotImplementedError

    def participant_timed_out(self, participant):
        """Return whether the authoritative hold deadline has passed."""
        deadline = self.get_hold_record(participant).deadline
        return deadline is not None and timenow() >= deadline

    def should_resume(self, experiment, participant):
        """Return whether this hold should advance or follow a redirect."""
        return (
            participant.pending_redirect is not None
            or participant.failed
            or self.participant_can_resume(experiment, participant)
            or self.participant_timed_out(participant)
        )

    def account_wait(self, participant, settle=False):
        """Update actual wait diagnostics and compensation."""
        record = self.get_hold_record(participant)
        if settle:
            record.settle(participant)
        else:
            record.account_until(participant, timenow())

    def timeline_hold_payload(self, participant):
        """Return browser configuration for this hold visit."""
        record = self.get_hold_record(participant)
        remaining_timeout_ms = None
        if record.deadline is not None:
            remaining_timeout_ms = max(
                0, round((record.deadline - timenow()).total_seconds() * 1000)
            )
        return {
            "channel": TIMELINE_HOLD_CHANNEL,
            "hold_id": self.hold_id,
            "message": self.content,
            "page_uuid": participant.page_uuid,
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

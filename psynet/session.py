"""Live sessions for real-time PsyNet interactions."""

from __future__ import annotations

from dallinger import db
from pydantic import Field
from sqlalchemy import Boolean, Column, String

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict, PythonList
from psynet.modular_page import Control, NoArgumentProvided
from psynet.websocket import WebSocketMessage

STATE_REQUEST_EVENT = "stateRequest"
STATE_SNAPSHOT_EVENT = "stateSnapshot"
READY_EVENT = "ready"
SESSION_END_EVENT = "sessionEnd"


class StateRequestMessage(WebSocketMessage):
    """Request the latest authoritative state for a live session."""

    session_id: str = Field(min_length=1)


class ReadyMessage(WebSocketMessage):
    """Notify the server that a participant is ready for a live session to start."""

    session_id: str = Field(min_length=1)


class _LiveSessionMixin:
    """Shared columns and behavior for persisted live-session rows."""

    session_id = Column(String(256), unique=True, index=True)
    state = Column(PythonDict, default=lambda: {})
    participant_ids = Column(PythonList, default=lambda: [])
    ready_participant_ids = Column(PythonList, default=lambda: [])
    started = Column(Boolean, default=False)
    ended = Column(Boolean, default=False)

    @classmethod
    def build_session_id(cls, participant, group, control):
        """Return the live-session ID for a participant/group/control context."""

        return f"{cls.__name__}:group:{int(group.id)}"

    @classmethod
    def build_initial_state(cls, participant_ids, participant, group, control):
        """Return initial public state for a new live session."""

        return {}

    @classmethod
    def build_params(cls, participant, group, control):
        """Return extra browser-facing live-session config."""

        return {}

    @classmethod
    def get(cls, session_id: str, *, for_update=False):
        """Return the live session for a session ID, if it exists."""

        query = cls.query.filter_by(session_id=session_id)
        if for_update:
            query = query.with_for_update(of=cls).populate_existing()
        return query.one_or_none()

    @classmethod
    def get_or_create(
        cls,
        session_id: str,
        *,
        state: dict | None = None,
        participant_ids: list[int] | None = None,
        for_update=False,
    ):
        """Return an existing live-session row or create it."""

        live_session = cls.get(session_id, for_update=for_update)
        if live_session is None:
            live_session = cls(
                session_id=session_id,
                state=state or {},
                participant_ids=[
                    int(participant_id) for participant_id in (participant_ids or [])
                ],
                ready_participant_ids=[],
                started=False,
                ended=False,
            )
            db.session.add(live_session)
            db.session.flush()
        return live_session

    def mark_ready(self, participant):
        """Mark a participant ready and return whether this started the session."""

        participant_id = int(getattr(participant, "id", participant))
        ready = {int(value) for value in (self.ready_participant_ids or [])}
        ready.add(participant_id)
        self.ready_participant_ids = sorted(ready)

        started_now = False
        expected = {int(value) for value in (self.participant_ids or [])}
        if expected and expected.issubset(ready) and not self.started:
            self.started = True
            started_now = True

        return started_now

    def mark_ended(self):
        """Mark this live session ended if it has not already ended."""

        if self.ended:
            return False
        self.ended = True
        return True

    def end(self, experiment):
        """Mark this live session ended and emit the built-in sessionEnd event."""

        if self.mark_ended():
            self.send_session_end(experiment)
            return True
        return False

    def snapshot_payload(self) -> dict:
        """Return a JSON-serializable state snapshot payload."""

        return {
            "session_id": self.session_id,
            "state": self.state or {},
            "participant_ids": [str(value) for value in (self.participant_ids or [])],
            "ready_participant_ids": [
                str(value) for value in (self.ready_participant_ids or [])
            ],
            "started": bool(self.started),
            "ended": bool(self.ended),
        }

    def send_snapshot(self, experiment, participants=None):
        """Send the current snapshot to all live-session participants or a subset."""

        if participants is None:
            participants = self.participant_ids or []
        experiment.websocket.send(
            participants,
            STATE_SNAPSHOT_EVENT,
            self.snapshot_payload(),
        )

    def send_session_end(self, experiment):
        """Send the built-in session end event to live-session participants."""

        experiment.websocket.send(
            self.participant_ids or [],
            SESSION_END_EVENT,
            self.snapshot_payload(),
        )


@register_table
class LiveSession(_LiveSessionMixin, SQLBase, SQLMixin):
    """Generic persisted live session."""

    __tablename__ = "live_session"


class LiveSessionControl(Control):
    """Control base class that configures a live session for browser code."""

    session_class = LiveSession

    def __init__(
        self,
        *,
        participant,
        group_type: str,
        params: dict | None = None,
        bot_response=NoArgumentProvided,
        buttons=None,
        show_next_button: bool | None = False,
    ):
        super().__init__(
            bot_response=bot_response,
            buttons=buttons,
            show_next_button=show_next_button,
        )
        self.participant = participant
        self.group_type = group_type
        self.group = self._get_group(participant, group_type)
        self.group_id = int(self.group.id)
        self.participant_ids = [
            int(p.id) for p in sorted(self.group.participants, key=lambda p: p.id)
        ]
        self.participant_id = int(participant.id)
        self.session_id = self.session_class.build_session_id(
            participant, self.group, self
        )
        initial_state = self.session_class.build_initial_state(
            self.participant_ids, participant, self.group, self
        )
        self.live_session = self.session_class.get_or_create(
            self.session_id,
            state=initial_state,
            participant_ids=self.participant_ids,
        )
        custom_params = self.session_class.build_params(participant, self.group, self)
        self.live_session_config = {
            "session_id": self.session_id,
            "group_id": self.group_id,
            "participant_id": self.participant_id,
            "participant_ids": self.participant_ids,
            **(custom_params or {}),
            **(params or {}),
        }

    @staticmethod
    def _get_group(participant, group_type: str):
        active_sync_groups = getattr(participant, "active_sync_groups", {}) or {}
        if group_type in active_sync_groups:
            return active_sync_groups[group_type]

        sync_group = getattr(participant, "sync_group", None)
        if sync_group is not None:
            return sync_group

        raise ValueError(
            f"Could not derive live-session group {group_type!r} for participant."
        )


def handle_state_request(experiment, participant, message: StateRequestMessage):
    """Send the latest state snapshot to the requesting participant."""

    live_session = LiveSession.get(message.session_id)
    if live_session is not None:
        experiment.websocket.send(
            participant,
            STATE_SNAPSHOT_EVENT,
            live_session.snapshot_payload(),
        )


def handle_ready_event(experiment, participant, message: ReadyMessage):
    """Mark a participant ready and send the resulting snapshot."""

    live_session = LiveSession.get(message.session_id, for_update=True)
    if live_session is None:
        return
    live_session.mark_ready(participant)
    live_session.send_snapshot(experiment)
    db.session.commit()


def trigger_session_end_event(experiment, session_id):
    """Mark a live session ended and send its built-in sessionEnd event."""

    from psynet.db import transaction

    with transaction():
        live_session = LiveSession.get(session_id, for_update=True)
        if live_session is None:
            return False
        return live_session.end(experiment)

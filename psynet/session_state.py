"""Shared authoritative state for real-time PsyNet sessions."""

from __future__ import annotations

from dallinger import db
from pydantic import Field
from sqlalchemy import Boolean, Column, String, UniqueConstraint

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict, PythonList
from psynet.websocket import WebSocketMessage

STATE_REQUEST_EVENT = "stateRequest"
STATE_SNAPSHOT_EVENT = "stateSnapshot"
READY_EVENT = "ready"


class StateRequestMessage(WebSocketMessage):
    """Request the latest authoritative state for a session."""

    namespace: str = Field(default="default", min_length=1)
    session_id: str = Field(min_length=1)


class ReadyMessage(WebSocketMessage):
    """Notify the server that a participant is ready for a session to start."""

    namespace: str = Field(default="default", min_length=1)
    session_id: str = Field(min_length=1)


@register_table
class SessionState(SQLBase, SQLMixin):
    """Persisted authoritative state for one real-time session."""

    __tablename__ = "session_state"
    __table_args__ = (UniqueConstraint("namespace", "session_id"),)

    namespace = Column(String(128), index=True)
    session_id = Column(String(256), index=True)
    state = Column(PythonDict, default=lambda: {})
    participant_ids = Column(PythonList, default=lambda: [])
    ready_participant_ids = Column(PythonList, default=lambda: [])
    started = Column(Boolean, default=False)

    @classmethod
    def get(cls, namespace: str, session_id: str, *, for_update=False):
        """Return the session state for a namespace/session pair, if it exists."""

        query = cls.query.filter_by(namespace=namespace, session_id=session_id)
        if for_update:
            query = query.with_for_update(of=cls).populate_existing()
        return query.one_or_none()

    @classmethod
    def get_or_create(
        cls,
        namespace: str,
        session_id: str,
        *,
        state: dict | None = None,
        participant_ids: list[int] | None = None,
        for_update=False,
    ):
        """Return an existing session state row or create it."""

        session_state = cls.get(namespace, session_id, for_update=for_update)
        if session_state is None:
            session_state = cls(
                namespace=namespace,
                session_id=session_id,
                state=state or {},
                participant_ids=[
                    int(participant_id) for participant_id in (participant_ids or [])
                ],
                ready_participant_ids=[],
                started=False,
            )
            db.session.add(session_state)
            db.session.flush()
        return session_state

    def mark_ready(self, participant):
        """Mark a participant ready and return whether the session has started."""

        participant_id = int(getattr(participant, "id", participant))
        ready = {int(value) for value in (self.ready_participant_ids or [])}
        ready.add(participant_id)
        self.ready_participant_ids = sorted(ready)

        expected = {int(value) for value in (self.participant_ids or [])}
        if expected and expected.issubset(ready):
            self.started = True

        return self.started

    def snapshot_payload(self) -> dict:
        """Return a JSON-serializable state snapshot payload."""

        return {
            "namespace": self.namespace,
            "session_id": self.session_id,
            "state": self.state or {},
            "participant_ids": [str(value) for value in (self.participant_ids or [])],
            "ready_participant_ids": [
                str(value) for value in (self.ready_participant_ids or [])
            ],
            "started": bool(self.started),
        }

    def send_snapshot(self, experiment, participants=None):
        """Send the current snapshot to all session participants or a subset."""

        if participants is None:
            participants = self.participant_ids or []
        experiment.websocket.send(
            participants,
            STATE_SNAPSHOT_EVENT,
            self.snapshot_payload(),
        )


def handle_state_request(experiment, participant, message: StateRequestMessage):
    """Send the latest state snapshot to the requesting participant."""

    session_state = SessionState.get(message.namespace, message.session_id)
    if session_state is not None:
        experiment.websocket.send(
            participant,
            STATE_SNAPSHOT_EVENT,
            session_state.snapshot_payload(),
        )


def handle_ready_event(experiment, participant, message: ReadyMessage):
    """Mark a participant ready and broadcast the resulting snapshot."""

    session_state = SessionState.get(
        message.namespace, message.session_id, for_update=True
    )
    if session_state is None:
        return
    session_state.mark_ready(participant)
    session_state.send_snapshot(experiment)
    db.session.commit()

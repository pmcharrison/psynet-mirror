"""Live sessions for real-time PsyNet interactions."""

from __future__ import annotations

from dallinger import db
from pydantic import Field
from sqlalchemy import Boolean, Column, String, UniqueConstraint
from sqlalchemy.orm import declared_attr

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict, PythonList
from psynet.modular_page import Control, NoArgumentProvided
from psynet.websocket import WebSocketMessage

STATE_REQUEST_EVENT = "stateRequest"
STATE_SNAPSHOT_EVENT = "stateSnapshot"
READY_EVENT = "ready"
SESSION_END_EVENT = "sessionEnd"

LIVE_SESSION_CLASSES = {}


def _camel_to_snake(name: str) -> str:
    """Convert a CamelCase class name to a snake_case table name."""

    chars = []
    for i, char in enumerate(name):
        if char.isupper() and i > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


class StateRequestMessage(WebSocketMessage):
    """Request the latest authoritative state for a live session."""

    namespace: str = Field(default="default", min_length=1)
    session_id: str = Field(min_length=1)


class ReadyMessage(WebSocketMessage):
    """Notify the server that a participant is ready for a live session to start."""

    namespace: str = Field(default="default", min_length=1)
    session_id: str = Field(min_length=1)


def register_live_session_class(cls):
    """Register a concrete live-session class for generic websocket handlers."""

    namespace = getattr(cls, "live_session_namespace", None)
    if namespace:
        LIVE_SESSION_CLASSES[namespace] = cls
    return cls


def get_live_session_class(namespace: str):
    """Return the concrete live-session class for a namespace."""

    return LIVE_SESSION_CLASSES.get(namespace, LiveSession)


class LiveSessionMixin:
    """Shared columns and behavior for persisted live-session rows."""

    live_session_namespace = None

    namespace = Column(String(128), index=True)
    session_id = Column(String(256), index=True)
    state = Column(PythonDict, default=lambda: {})
    participant_ids = Column(PythonList, default=lambda: [])
    ready_participant_ids = Column(PythonList, default=lambda: [])
    started = Column(Boolean, default=False)
    ended = Column(Boolean, default=False)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        register_live_session_class(cls)

    @declared_attr
    def __tablename__(cls):
        return _camel_to_snake(cls.__name__)

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint("namespace", "session_id"),)

    @classmethod
    def get_namespace(cls):
        """Return the namespace handled by this live-session class."""

        namespace = getattr(cls, "live_session_namespace", None)
        if not namespace:
            raise ValueError(f"{cls.__name__} must define live_session_namespace.")
        return namespace

    @classmethod
    def build_session_id(cls, participant, group, control):
        """Return the live-session ID for a participant/group/control context."""

        return f"{cls.get_namespace()}:group:{int(group.id)}"

    @classmethod
    def build_initial_state(cls, participant_ids, participant, group, control):
        """Return initial public state for a new live session."""

        return {}

    @classmethod
    def build_params(cls, participant, group, control):
        """Return extra browser-facing live-session config."""

        return {}

    @classmethod
    def get(cls, session_id: str, *, namespace: str | None = None, for_update=False):
        """Return the live session for a namespace/session pair, if it exists."""

        namespace = namespace or cls.get_namespace()
        query = cls.query.filter_by(namespace=namespace, session_id=session_id)
        if for_update:
            query = query.with_for_update(of=cls).populate_existing()
        return query.one_or_none()

    @classmethod
    def get_or_create(
        cls,
        session_id: str,
        *,
        namespace: str | None = None,
        state: dict | None = None,
        participant_ids: list[int] | None = None,
        for_update=False,
    ):
        """Return an existing live-session row or create it."""

        namespace = namespace or cls.get_namespace()
        live_session = cls.get(session_id, namespace=namespace, for_update=for_update)
        if live_session is None:
            live_session = cls(
                namespace=namespace,
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
            "namespace": self.namespace,
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
class LiveSession(LiveSessionMixin, SQLBase, SQLMixin):
    """Generic persisted live session."""

    live_session_namespace = "default"


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
        self.namespace = self.session_class.get_namespace()
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
            "namespace": self.namespace,
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

    live_session_class = get_live_session_class(message.namespace)
    live_session = live_session_class.get(
        message.session_id, namespace=message.namespace
    )
    if live_session is not None:
        experiment.websocket.send(
            participant,
            STATE_SNAPSHOT_EVENT,
            live_session.snapshot_payload(),
        )


def handle_ready_event(experiment, participant, message: ReadyMessage):
    """Mark a participant ready and send the resulting snapshot."""

    live_session_class = get_live_session_class(message.namespace)
    live_session = live_session_class.get(
        message.session_id, namespace=message.namespace, for_update=True
    )
    if live_session is None:
        return
    live_session.mark_ready(participant)
    live_session.send_snapshot(experiment)
    db.session.commit()


def trigger_session_end_event(experiment, live_session_class, namespace, session_id):
    """Mark a live session ended and send its built-in sessionEnd event."""

    from psynet.db import transaction

    with transaction():
        live_session = live_session_class.get(
            session_id, namespace=namespace, for_update=True
        )
        if live_session is None:
            return False
        return live_session.end(experiment)

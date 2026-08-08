"""Live sessions for real-time PsyNet interactions."""

from __future__ import annotations

from dallinger import db
from pydantic import Field
from sqlalchemy import Boolean, Column, String
from sqlalchemy.orm import relationship

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict, PythonList
from psynet.modular_page import Control, NoArgumentProvided
from psynet.utils import model_name_to_snake_case
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
    def build_session_id(cls, group, trial):
        """Return the live-session ID for a group/trial."""

        parts = [model_name_to_snake_case(cls.__name__)]
        parts.extend(["network", str(int(trial.network.id))])
        parts.extend(["group", str(int(group.id))])
        return ":".join(parts)

    @classmethod
    def build_initial_state(cls, participant_ids, group, trial):
        """Return initial public state for a new live session."""

        return {}

    @classmethod
    def get(cls, session_id: str, *, for_update=False):
        """Return the live session for a session ID, if it exists."""

        query = cls.query.filter_by(session_id=session_id)
        if for_update:
            query = query.with_for_update(of=cls).populate_existing()
        return query.one_or_none()

    @classmethod
    def create(
        cls,
        session_id: str,
        *,
        state: dict | None = None,
        participant_ids: list[int] | None = None,
    ):
        """Create a live-session row."""

        live_session = cls(
            session_id=session_id,
            state=state or {},
            participant_ids=[
                int(participant_id) for participant_id in participant_ids or []
            ],
            ready_participant_ids=[],
            started=False,
            ended=False,
        )
        db.session.add(live_session)
        db.session.flush()
        return live_session

    @classmethod
    def prepare_for_group(cls, *, group):
        """Create and link the live session for a synchronized group of trials."""

        leader = group.leader
        if leader is None:
            raise ValueError(f"Group {group.id} has no leader.")

        participants = sorted(group.active_participants, key=lambda p: p.id)
        participant_ids = [int(participant.id) for participant in participants]
        trials = [participant.current_trial for participant in participants]
        leader_trial = leader.current_trial
        if leader_trial is None:
            raise ValueError(
                f"Live session group {group.id} has no trial for leader {leader.id}."
            )
        if any(trial is None for trial in trials):
            raise ValueError(f"Live session group {group.id} has missing trials.")

        session_id = cls.build_session_id(group, leader_trial)
        live_session = cls.get(session_id)
        if live_session is None:
            live_session = cls.create(
                session_id,
                state=cls.build_initial_state(
                    participant_ids,
                    group,
                    leader_trial,
                ),
                participant_ids=participant_ids,
            )

        for trial in trials:
            live_session.link_trial(trial)

        return live_session

    def mark_ready(self, participant):
        """Mark a participant ready and return whether this started the session."""

        if not self.has_participant(participant):
            return False

        participant_id = int(participant.id)
        ready = {int(value) for value in (self.ready_participant_ids or [])}
        ready.add(participant_id)
        self.ready_participant_ids = sorted(ready)

        started_now = False
        expected = {int(value) for value in (self.participant_ids or [])}
        if expected and expected.issubset(ready) and not self.started:
            self.started = True
            started_now = True

        return started_now

    def has_participant(self, participant):
        """Return whether a participant belongs to this live session."""

        participant_id = int(participant.id)
        expected = {int(value) for value in (self.participant_ids or [])}
        return participant_id in expected

    @property
    def participants(self):
        """Return participant objects linked to this live session."""

        trials = sorted(
            (trial for trial in (self.trials or []) if not trial.failed),
            key=lambda trial: trial.participant_id,
        )
        return [trial.participant for trial in trials]

    @classmethod
    def get_current_for_participant(
        cls, participant, session_id: str, *, for_update=False
    ):
        """Return a participant's current live session if it matches a session ID."""

        trial = participant.current_trial
        live_session = trial.live_session if trial is not None else None
        if live_session is None or live_session.session_id != session_id:
            return None

        if for_update:
            live_session = cls.get(live_session.session_id, for_update=True)
            if live_session is None:
                return None

        if not live_session.has_participant(participant):
            return None
        return live_session

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
            participants = self.participants
        experiment.websocket.send(
            participants,
            STATE_SNAPSHOT_EVENT,
            self.snapshot_payload(),
        )

    def send_session_end(self, experiment):
        """Send the built-in session end event to live-session participants."""

        experiment.websocket.send(
            self.participants,
            SESSION_END_EVENT,
            self.snapshot_payload(),
        )

    def link_trial(self, trial):
        """Associate a participant trial with this live session."""

        current_id = trial.live_session_id
        if (
            current_id is not None
            and self.id is not None
            and int(current_id) != int(self.id)
        ):
            raise ValueError(
                f"Trial {trial.id} is already linked to live session {current_id}."
            )
        trial.live_session = self
        return trial

    @classmethod
    def handle_state_request(
        cls, experiment, participant, message: StateRequestMessage
    ):
        """Send the latest state snapshot to the requesting participant."""

        live_session = cls.get_current_for_participant(participant, message.session_id)
        if live_session is not None:
            live_session.send_snapshot(experiment, participants=participant)

    @classmethod
    def handle_ready_event(cls, experiment, participant, message: ReadyMessage):
        """Mark a participant ready and send the resulting snapshot."""

        live_session = cls.get_current_for_participant(
            participant, message.session_id, for_update=True
        )
        if live_session is None:
            return
        live_session.mark_ready(participant)
        live_session.send_snapshot(experiment)
        db.session.commit()

    @classmethod
    def trigger_end_event(cls, experiment, session_id):
        """Mark a live session ended and send its built-in sessionEnd event."""

        from psynet.db import transaction

        with transaction():
            live_session = cls.get(session_id, for_update=True)
            if live_session is None:
                return False
            return live_session.end(experiment)


@register_table
class LiveSession(_LiveSessionMixin, SQLBase, SQLMixin):
    """Generic persisted live session."""

    __tablename__ = "live_session"
    trials = relationship(
        "psynet.trial.main.Trial",
        back_populates="live_session",
    )


class LiveSessionControl(Control):
    """Control base class that configures a live session for browser code."""

    def __init__(
        self,
        *,
        participant,
        trial,
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
        self.trial = trial
        self.session_class = self._resolve_session_class(trial)
        self.group = self._resolve_group(trial)
        self.group_id = int(self.group.id)
        self.participant_ids = [
            int(p.id) for p in sorted(self.group.participants, key=lambda p: p.id)
        ]
        self.participant_id = int(participant.id)
        self.session_id = self.session_class.build_session_id(self.group, trial)
        self.live_session = trial.live_session
        if self.live_session is None:
            self.live_session = self.session_class.get(self.session_id)
        if self.live_session is None:
            raise RuntimeError(
                f"Trial {trial.id} has no prepared live session {self.session_id!r}."
            )
        if self.live_session.session_id != self.session_id:
            raise RuntimeError(
                f"Trial {trial.id} is linked to live session "
                f"{self.live_session.session_id!r}, expected {self.session_id!r}."
            )
        custom_params = self.build_control_params()
        self.live_session_config = {
            "session_id": self.session_id,
            "group_id": self.group_id,
            "participant_id": self.participant_id,
            "participant_ids": self.participant_ids,
            **(custom_params or {}),
            **(params or {}),
        }

    def build_control_params(self):
        """Return extra browser-facing live-session config."""

        return {}

    @classmethod
    def _resolve_session_class(cls, trial):
        if trial is None:
            raise ValueError("LiveSessionControl currently requires a trial.")

        session_class = trial.live_session_class
        if session_class is None:
            raise ValueError(
                f"Trial {trial.__class__.__name__} must define live_session_class "
                "to use LiveSessionControl."
            )
        return session_class

    @staticmethod
    def _resolve_group(trial):
        group = trial.sync_group
        if group is None:
            raise ValueError(
                f"Trial {trial.__class__.__name__} must belong to a sync group "
                "to use LiveSessionControl."
            )
        return group

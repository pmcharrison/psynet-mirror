"""Live sessions for real-time PsyNet interactions."""

from __future__ import annotations

from dallinger import db
from pydantic import Field
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict, PythonList
from psynet.modular_page import Control, NoArgumentProvided
from psynet.page import WaitPage
from psynet.sync import GroupBarrier
from psynet.utils import model_name_to_snake_case
from psynet.websocket import WebSocketMessage

STATE_REQUEST_EVENT = "stateRequest"
STATE_SNAPSHOT_EVENT = "stateSnapshot"
READY_EVENT = "ready"
SESSION_STATUS_EVENT = "sessionStatus"
SESSION_END_EVENT = "sessionEnd"


class StateRequestMessage(WebSocketMessage):
    """Request the latest authoritative state for a live session."""

    session_id: int = Field(ge=1)
    fields: list[str] | None = None


class ReadyMessage(WebSocketMessage):
    """Notify the server that a participant is ready for a live session to start."""

    session_id: int = Field(ge=1)


class _LiveSessionMixin:
    """Shared columns and behavior for persisted live-session rows."""

    session_type = Column(String(256), index=True)
    group_type = Column(String(256), index=True)
    initializer_id = Column(String(256), index=True)
    state = Column(PythonDict, default=lambda: {})
    participant_ids = Column(PythonList, default=lambda: [])
    ready_participant_ids = Column(PythonList, default=lambda: [])
    started = Column(Boolean, default=False)
    ended = Column(Boolean, default=False)

    @declared_attr
    def sync_group_id(cls):
        return Column(Integer, ForeignKey("sync_group.id"), index=True)

    @declared_attr
    def node_id(cls):
        return Column(Integer, ForeignKey("node.id"), index=True, nullable=True)

    @declared_attr
    def network_id(cls):
        return Column(Integer, ForeignKey("network.id"), index=True, nullable=True)

    @declared_attr
    def sync_group(cls):
        return relationship("psynet.sync.SyncGroup", foreign_keys=[cls.sync_group_id])

    @classmethod
    def session_type_label(cls):
        """Return the persistent label for this live-session class."""

        return model_name_to_snake_case(cls.__name__)

    @classmethod
    def build_initial_state(cls, participant_ids, group, context=None):
        """Return initial public state for a new live session."""

        return {}

    @classmethod
    def get(cls, session_id: int, *, for_update=False):
        """Return the live session for a browser-facing row ID, if it exists."""

        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return None

        query = cls.query.filter_by(id=session_id)
        if for_update:
            query = query.with_for_update(of=cls).populate_existing()
        return query.one_or_none()

    @classmethod
    def create(
        cls,
        state: dict | None = None,
        participant_ids: list[int] | None = None,
        group_type: str | None = None,
        sync_group_id: int | None = None,
        initializer_id: str | None = None,
        node_id: int | None = None,
        network_id: int | None = None,
    ):
        """Create a live-session row."""

        live_session = cls(
            session_type=cls.session_type_label(),
            group_type=group_type,
            sync_group_id=sync_group_id,
            initializer_id=initializer_id,
            node_id=node_id,
            network_id=network_id,
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
    def _current_trial_context(cls, group):
        """Return optional node/network context from the group leader's trial."""

        leader = group.leader
        trial = leader.current_trial if leader is not None else None
        if trial is None:
            return {
                "trial": None,
                "node": None,
                "network": None,
                "node_id": None,
                "network_id": None,
            }

        node = trial.node
        network = trial.network
        node_id = trial.node_id if trial.node_id is not None else node.id
        network_id = trial.network_id if trial.network_id is not None else network.id

        return {
            "trial": trial,
            "node": node,
            "network": network,
            "node_id": int(node_id) if node_id is not None else None,
            "network_id": int(network_id) if network_id is not None else None,
        }

    @classmethod
    def create_for_group(cls, *, group, initializer, participant=None):
        """Create a live session from a leader-owned initializer barrier release."""

        leader = group.leader
        if leader is None:
            raise ValueError(f"Group {group.id} has no leader.")

        if participant is not None and int(participant.id) != int(leader.id):
            raise ValueError("Only the group leader can initialize a live session.")

        participants = sorted(group.active_participants, key=lambda p: p.id)
        participant_ids = [int(participant.id) for participant in participants]
        context = cls._current_trial_context(group)
        context.update(
            {
                "group": group,
                "participants": participants,
                "initializer": initializer,
                "initializer_id": initializer.id,
            }
        )
        return cls.create(
            state=cls.build_initial_state(participant_ids, group, context),
            participant_ids=participant_ids,
            group_type=getattr(group, "group_type", None),
            sync_group_id=int(group.id),
            initializer_id=initializer.id,
            node_id=context["node_id"],
            network_id=context["network_id"],
        )

    @classmethod
    def get_for_group(
        cls,
        *,
        group,
        initializer_id: str,
        node_id: int | None = None,
        network_id: int | None = None,
        for_update=False,
    ):
        """Return an existing live session for group/session metadata."""

        query = cls.query.filter_by(
            session_type=cls.session_type_label(),
            group_type=getattr(group, "group_type", None),
            sync_group_id=int(group.id),
            initializer_id=initializer_id,
        )
        query = query.filter(
            cls.node_id.is_(None) if node_id is None else cls.node_id == node_id
        )
        query = query.filter(
            cls.network_id.is_(None)
            if network_id is None
            else cls.network_id == network_id
        )
        if for_update:
            query = query.with_for_update(of=cls).populate_existing()
        matches = query.all()
        if len(matches) > 1:
            raise RuntimeError(
                f"Multiple live sessions found for initializer {initializer_id!r} "
                f"in group {group.id}."
            )
        return matches[0] if matches else None

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
        """Return participant objects belonging to this live session."""

        if self.sync_group is not None:
            return sorted(self.sync_group.active_participants, key=lambda p: p.id)

        participant_ids = [int(value) for value in (self.participant_ids or [])]
        if not participant_ids:
            return []

        from psynet.participant import Participant

        participants = Participant.query.filter(
            Participant.id.in_(participant_ids)
        ).all()
        return sorted(participants, key=lambda participant: participant.id)

    @property
    def node(self):
        """Return the node context used to initialize this session, if any."""

        if self.node_id is None:
            return None
        from psynet.trial.main import TrialNode

        return TrialNode.query.get(int(self.node_id))

    @property
    def network(self):
        """Return the network context used to initialize this session, if any."""

        if self.network_id is None:
            return None
        from psynet.trial.main import TrialNetwork

        return TrialNetwork.query.get(int(self.network_id))

    @classmethod
    def get_current_for_participant(
        cls, participant, session_id: int, *, for_update=False
    ):
        """Return a participant's live session if they belong to the session."""

        live_session = cls.get(session_id, for_update=for_update)
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

    def snapshot_payload(self, fields: list[str] | None = None) -> dict:
        """Return a JSON-serializable state snapshot payload."""

        state = self.state or {}
        if fields is not None:
            state = {field: state[field] for field in fields if field in state}
        payload = {
            "session_id": int(self.id),
            "state": state,
            "participant_ids": [str(value) for value in (self.participant_ids or [])],
            "ready_participant_ids": [
                str(value) for value in (self.ready_participant_ids or [])
            ],
            "started": bool(self.started),
            "ended": bool(self.ended),
        }
        return payload

    def status_payload(self) -> dict:
        """Return JSON-serializable live-session lifecycle status."""

        return {
            "session_id": int(self.id),
            "participant_ids": [str(value) for value in (self.participant_ids or [])],
            "ready_participant_ids": [
                str(value) for value in (self.ready_participant_ids or [])
            ],
            "started": bool(self.started),
            "ended": bool(self.ended),
        }

    def send_snapshot(
        self, experiment, participants=None, fields: list[str] | None = None
    ):
        """Send the current snapshot to all live-session participants or a subset."""

        if participants is None:
            participants = self.participants
        experiment.websocket.send(
            participants,
            STATE_SNAPSHOT_EVENT,
            self.snapshot_payload(fields=fields),
        )

    def send_status(self, experiment, participants=None):
        """Send the current lifecycle status to live-session participants."""

        if participants is None:
            participants = self.participants
        experiment.websocket.send(
            participants,
            SESSION_STATUS_EVENT,
            self.status_payload(),
        )

    def send_session_end(self, experiment):
        """Send the built-in session end event to live-session participants."""

        experiment.websocket.send(
            self.participants,
            SESSION_END_EVENT,
            self.snapshot_payload(),
        )

    @classmethod
    def handle_state_request(
        cls, experiment, participant, message: StateRequestMessage
    ):
        """Send the latest state snapshot to the requesting participant."""

        live_session = cls.get_current_for_participant(participant, message.session_id)
        if live_session is not None:
            live_session.send_snapshot(
                experiment, participants=participant, fields=message.fields
            )

    @classmethod
    def handle_ready_event(cls, experiment, participant, message: ReadyMessage):
        """Mark a participant ready and send the resulting snapshot."""

        live_session = cls.get_current_for_participant(
            participant, message.session_id, for_update=True
        )
        if live_session is None:
            return
        live_session.mark_ready(participant)
        live_session.send_status(experiment)
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


def _create_live_session_on_release(group, participants, participant, barrier):
    """Create the live session owned by a released group barrier."""

    barrier.session_class.create_for_group(
        group=group,
        initializer=barrier,
        participant=participant,
    )


class LiveSessionInitializer(GroupBarrier):
    """Timeline element that creates a group-owned live session."""

    def __init__(
        self,
        id_: str,
        group_type: str,
        session_class=LiveSession,
        waiting_logic=NoArgumentProvided,
        waiting_logic_expected_repetitions=3,
        max_wait_time=20,
        fix_time_credit=False,
    ):
        self.session_class = session_class
        if waiting_logic is NoArgumentProvided:
            waiting_logic = WaitPage(wait_time=0.5, save_answer=False)
        super().__init__(
            id_=id_,
            group_type=group_type,
            waiting_logic=waiting_logic,
            waiting_logic_expected_repetitions=waiting_logic_expected_repetitions,
            max_wait_time=max_wait_time,
            on_release=_create_live_session_on_release,
            fix_time_credit=fix_time_credit,
        )


class LiveSessionControl(Control):
    """Control base class that configures a live session for browser code."""

    def __init__(
        self,
        *,
        participant,
        session_class,
        group_type: str,
        session_initializer_id: str,
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
        self.session_class = session_class
        self.group_type = group_type
        self.session_initializer_id = session_initializer_id
        self._session_id = None

    def _get_group(self):
        """Return the participant's active group for this live session."""

        try:
            group = self.participant.active_sync_groups[self.group_type]
        except KeyError as exc:
            raise ValueError(
                f"Participant {self.participant.id} has no active sync group "
                f"for group_type {self.group_type!r}."
            ) from exc
        if group is None:
            raise ValueError("LiveSessionControl requires an active sync group.")
        return group

    def _resolve_session_id(self):
        """Resolve the initialized live-session row ID for this control."""

        if self._session_id is not None:
            return self._session_id

        group = self._get_group()
        context = self.session_class._current_trial_context(group)
        live_session = self.session_class.get_for_group(
            group=group,
            initializer_id=self.session_initializer_id,
            node_id=context["node_id"],
            network_id=context["network_id"],
        )
        if live_session is None:
            raise RuntimeError(
                f"No live session prepared for initializer "
                f"{self.session_initializer_id!r} in group {int(group.id)}."
            )
        if live_session.id is None:
            raise RuntimeError("Live session must be flushed before rendering.")
        self._session_id = int(live_session.id)
        return self._session_id

    @property
    def live_session_config(self):
        """Return browser-facing live-session transport config."""

        return {
            "session_id": self._resolve_session_id(),
            "participant_id": int(self.participant.id),
        }

    def pre_render(self):
        """Resolve the live-session ID before rendering the control template."""

        self._resolve_session_id()

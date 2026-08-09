from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, String

from psynet.session import (
    LiveSession,
    LiveSessionControl,
    LiveSessionInitializer,
    ReadyMessage,
    SessionEndMessage,
    StateRequestMessage,
)


class PolymorphicDemoLiveSession(LiveSession):
    """Demo custom live session that shares the generic live_session table."""

    custom_value = Column(String)

    @classmethod
    def build_initial_state(cls, participant_ids, group, context=None):
        context = context or {}
        return {
            "participant_ids": participant_ids,
            "node_id": context.get("node_id"),
        }


def _participants():
    return [
        SimpleNamespace(id=1, page_uuid="page-1", module_state=None),
        SimpleNamespace(id=2, page_uuid="page-2", module_state=None),
    ]


def _state():
    participants = _participants()
    state = LiveSession(
        state={"score": 3},
        participant_ids=[1, 2],
        ready_participant_ids=[],
        started=False,
        ended=False,
    )
    state.id = 1
    state.__dict__["sync_group"] = SimpleNamespace(active_participants=participants)
    return state


def _capture_server_sends(monkeypatch):
    sent = []

    def send(self, participants):
        sent.append((participants, self))

    monkeypatch.setattr("psynet.websocket.ServerWebSocketMessage.send", send)
    return sent


def _group(*, leader_trial=True):
    participants = _participants()
    node = SimpleNamespace(id=11, network_id=12, definition={"value": "node"})
    network = SimpleNamespace(id=12)
    trial = (
        SimpleNamespace(
            id=7,
            node_id=11,
            network_id=12,
            node=node,
            network=network,
            definition={"value": "trial"},
        )
        if leader_trial
        else None
    )
    participants[0].current_trial = trial
    participants[1].current_trial = SimpleNamespace(id=8, node_id=11, network_id=12)
    group = SimpleNamespace(
        id=9,
        group_type="demo_group",
        participants=participants,
        active_participants=participants,
        leader=participants[0],
    )
    for participant in participants:
        participant.active_sync_groups = {"demo_group": group}
    return group


def test_live_session_tracks_ready_participants_and_started(monkeypatch):
    """LiveSession starts once all expected participants are ready."""

    start_time = datetime(2026, 1, 1, 12, 0, 0)
    monkeypatch.setattr("psynet.session.timenow", lambda: start_time)
    state = _state()

    assert state.mark_ready(SimpleNamespace(id=1)) is False
    assert state.ready_participant_ids == [1]
    assert state.started is False
    assert state.start_time is None

    assert state.mark_ready(SimpleNamespace(id=2)) is True
    assert state.ready_participant_ids == [1, 2]
    assert state.started is True
    assert state.start_time == start_time


def test_live_session_rejects_unknown_ready_participant():
    """Readiness only accepts expected live-session participants."""

    state = _state()

    assert state.mark_ready(SimpleNamespace(id=3)) is False
    assert state.ready_participant_ids == []
    assert state.started is False


def test_live_session_snapshot_payload_is_json_ready():
    """Snapshots expose state, readiness, and participant IDs as browser data."""

    state = _state()
    state.mark_ready(SimpleNamespace(id=1))

    assert state.snapshot_payload() == {
        "session_id": 1,
        "state": {"score": 3},
        "participant_ids": ["1", "2"],
        "ready_participant_ids": ["1"],
        "started": False,
        "ended": False,
    }


def test_live_session_snapshot_payload_can_filter_state_fields():
    """Snapshots can include only selected public state fields."""

    state = _state()
    state.state = {"score": 3, "round": 2}

    assert state.snapshot_payload(fields=["score", "missing"])["state"] == {"score": 3}


def test_live_session_status_payload_is_json_ready():
    """Status payloads expose readiness without public state."""

    state = _state()
    state.mark_ready(SimpleNamespace(id=1))

    assert state.status_payload() == {
        "session_id": 1,
        "participant_ids": ["1", "2"],
        "ready_participant_ids": ["1"],
        "started": False,
        "ended": False,
    }


def test_state_request_sends_snapshot_to_requesting_participant(monkeypatch):
    """StateRequest sends a snapshot through the experiment websocket helper."""

    state = _state()
    sent = _capture_server_sends(monkeypatch)
    experiment = SimpleNamespace()
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    StateRequestMessage(session_id=1).handle(
        experiment=experiment,
        participant=participant,
        receive_time=None,
    )
    assert sent == [(participant, state.snapshot_message())]


def test_state_request_can_send_partial_state(monkeypatch):
    """StateRequest forwards requested public state fields."""

    state = _state()
    state.state = {"score": 3, "round": 2}
    sent = _capture_server_sends(monkeypatch)
    experiment = SimpleNamespace()
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    StateRequestMessage(session_id=1, fields=["round"]).handle(
        experiment=experiment,
        participant=participant,
        receive_time=None,
    )
    assert sent == [(participant, state.snapshot_message(fields=["round"]))]


def test_state_request_rejects_non_member(monkeypatch):
    """StateRequest does not disclose snapshots to non-members."""

    state = _state()
    sent = _capture_server_sends(monkeypatch)
    experiment = SimpleNamespace()
    participant = SimpleNamespace(id=3)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    StateRequestMessage(session_id=1).handle(
        experiment=experiment,
        participant=participant,
        receive_time=None,
    )

    assert sent == []


def test_ready_event_marks_state_and_sends_status(monkeypatch):
    """ReadyEvent updates the row and sends status without a state snapshot."""

    state = _state()
    sent = _capture_server_sends(monkeypatch)
    experiment = SimpleNamespace()
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", MagicMock())

    ReadyMessage(session_id=1).handle(
        experiment=experiment,
        participant=participant,
        receive_time=None,
    )

    assert state.ready_participant_ids == [1]
    assert sent == [(state.participants, state.status_message())]


def test_ready_event_rejects_non_member(monkeypatch):
    """ReadyEvent does not mutate sessions for non-members."""

    state = _state()
    sent = _capture_server_sends(monkeypatch)
    experiment = SimpleNamespace()
    participant = SimpleNamespace(id=3)
    commit = MagicMock()
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", commit)

    ReadyMessage(session_id=1).handle(
        experiment=experiment,
        participant=participant,
        receive_time=None,
    )

    assert state.ready_participant_ids == []
    assert sent == []
    commit.assert_not_called()


def test_live_session_end_marks_ended_and_notifies(monkeypatch):
    """Live sessions can explicitly emit the built-in sessionEnd event."""

    end_time = datetime(2026, 1, 1, 12, 5, 0)
    monkeypatch.setattr("psynet.session.timenow", lambda: end_time)
    state = _state()
    sent = _capture_server_sends(monkeypatch)

    assert state.end() is True
    assert state.ended is True
    assert state.end_time == end_time
    assert sent == [(state.participants, SessionEndMessage(**state.snapshot_payload()))]
    assert state.end() is False


def test_create_for_group_is_leader_owned(monkeypatch):
    """The initializer creates exactly one session from the group leader context."""

    added = MagicMock()
    monkeypatch.setattr("psynet.session.db.session.add", added)
    monkeypatch.setattr("psynet.session.db.session.flush", MagicMock())
    group = _group()
    initializer = SimpleNamespace(id="demo_session")

    live_session = PolymorphicDemoLiveSession.create_for_group(
        group=group,
        initializer=initializer,
        participant=group.leader,
    )

    assert live_session.session_type == "polymorphic_demo_live_session"
    assert live_session.group_type == "demo_group"
    assert live_session.sync_group_id == 9
    assert live_session.initializer_id == "demo_session"
    assert live_session.node_id == 11
    assert live_session.network_id == 12
    assert live_session.participant_ids == [1, 2]
    assert live_session.start_time is None
    assert live_session.end_time is None
    assert live_session.state == {"participant_ids": [1, 2], "node_id": 11}
    added.assert_called_once_with(live_session)


def test_create_for_group_rejects_non_leader(monkeypatch):
    """Only the group leader may create the live session."""

    group = _group()
    initializer = SimpleNamespace(id="demo_session")

    with pytest.raises(ValueError, match="Only the group leader"):
        PolymorphicDemoLiveSession.create_for_group(
            group=group,
            initializer=initializer,
            participant=group.active_participants[1],
        )


def test_current_trial_context_is_optional():
    """Group-level sessions can initialize without node/network context."""

    group = _group(leader_trial=False)

    assert PolymorphicDemoLiveSession._current_trial_context(group) == {
        "trial": None,
        "node": None,
        "network": None,
        "node_id": None,
        "network_id": None,
    }


def test_live_session_initializer_delegates_creation_to_leader(monkeypatch):
    """The initializer's barrier callback delegates creation to the session class."""

    group = _group()
    created = MagicMock()
    monkeypatch.setattr(PolymorphicDemoLiveSession, "create_for_group", created)
    initializer = LiveSessionInitializer(
        id_="demo_session",
        group_type="demo_group",
        session_class=PolymorphicDemoLiveSession,
    )

    initializer.on_release(
        group=group,
        participants=group.active_participants,
        participant=group.leader,
        barrier=initializer,
    )

    created.assert_called_once_with(
        group=group,
        initializer=initializer,
        participant=group.leader,
    )


def test_live_session_control_derives_config(monkeypatch):
    """LiveSessionControl derives transport config from participant and group."""

    live_session = None
    get_for_group_calls = []

    def get_for_group(cls, **kwargs):
        get_for_group_calls.append(kwargs)
        return live_session

    monkeypatch.setattr(
        PolymorphicDemoLiveSession, "get_for_group", classmethod(get_for_group)
    )

    class DemoControl(LiveSessionControl):
        macro = "demo"

        def __init__(self, participant):
            self.custom_value = 10
            super().__init__(
                participant=participant,
                session_class=PolymorphicDemoLiveSession,
                group_type="demo_group",
                session_initializer_id="demo_session",
            )

    group = _group()
    participant = group.active_participants[0]

    control = DemoControl(participant)
    assert get_for_group_calls == []

    live_session = SimpleNamespace(
        id=5,
        sync_group_id=9,
        participant_ids=[1, 2],
        node_id=11,
        network_id=12,
    )
    control.pre_render()

    assert control.custom_value == 10
    assert not hasattr(control, "session")
    assert control.live_session_config == {
        "session_id": 5,
        "participant_id": 1,
    }
    assert get_for_group_calls == [
        {
            "group": group,
            "initializer_id": "demo_session",
            "node_id": 11,
            "network_id": 12,
        }
    ]


def test_live_session_control_requires_existing_session(monkeypatch):
    """Controls fail clearly at render time if no initializer row exists."""

    monkeypatch.setattr(
        PolymorphicDemoLiveSession,
        "get_for_group",
        classmethod(lambda cls, **kwargs: None),
    )

    class DemoControl(LiveSessionControl):
        def __init__(self, participant):
            super().__init__(
                participant=participant,
                session_class=PolymorphicDemoLiveSession,
                group_type="demo_group",
                session_initializer_id="missing_session",
            )

    control = DemoControl(participant=_group().active_participants[0])

    with pytest.raises(RuntimeError, match="No live session prepared"):
        control.pre_render()


def test_trigger_session_end_event_marks_ended_and_notifies(monkeypatch):
    """SessionEnd can be triggered from a session class and row ID."""

    state = _state()
    sent = _capture_server_sends(monkeypatch)

    monkeypatch.setattr("psynet.db.transaction", lambda: MagicMock())
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    LiveSession.trigger_end_event(1)

    assert state.ended is True
    assert sent == [(state.participants, SessionEndMessage(**state.snapshot_payload()))]


def test_live_session_uses_shared_polymorphic_table():
    """Custom live-session classes share the generic live_session table."""

    assert LiveSession.__tablename__ == "live_session"
    assert PolymorphicDemoLiveSession.__table__ is LiveSession.__table__
    assert "custom_value" in LiveSession.__table__.columns
    assert "session_id" not in LiveSession.__table__.columns
    assert "session_type" in LiveSession.__table__.columns
    assert "node_id" in LiveSession.__table__.columns
    assert "network_id" in LiveSession.__table__.columns

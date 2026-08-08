from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, String

from psynet.session import (
    LiveSession,
    LiveSessionControl,
    LiveSessionInitializer,
    ReadyMessage,
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


def test_live_session_tracks_ready_participants_and_started():
    """LiveSession starts once all expected participants are ready."""

    state = _state()

    assert state.mark_ready(SimpleNamespace(id=1)) is False
    assert state.ready_participant_ids == [1]
    assert state.started is False

    assert state.mark_ready(SimpleNamespace(id=2)) is True
    assert state.ready_participant_ids == [1, 2]
    assert state.started is True


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
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    LiveSession.handle_state_request(
        experiment,
        participant,
        StateRequestMessage(session_id=1),
    )
    experiment.websocket.send.assert_called_once_with(
        participant,
        "stateSnapshot",
        state.snapshot_payload(),
    )


def test_state_request_can_send_partial_state(monkeypatch):
    """StateRequest forwards requested public state fields."""

    state = _state()
    state.state = {"score": 3, "round": 2}
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    LiveSession.handle_state_request(
        experiment,
        participant,
        StateRequestMessage(session_id=1, fields=["round"]),
    )
    experiment.websocket.send.assert_called_once_with(
        participant,
        "stateSnapshot",
        state.snapshot_payload(fields=["round"]),
    )


def test_state_request_rejects_non_member(monkeypatch):
    """StateRequest does not disclose snapshots to non-members."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=3)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    LiveSession.handle_state_request(
        experiment,
        participant,
        StateRequestMessage(session_id=1),
    )

    experiment.websocket.send.assert_not_called()


def test_ready_event_marks_state_and_sends_status(monkeypatch):
    """ReadyEvent updates the row and sends status without a state snapshot."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", MagicMock())

    LiveSession.handle_ready_event(
        experiment,
        participant,
        ReadyMessage(session_id=1),
    )

    assert state.ready_participant_ids == [1]
    experiment.websocket.send.assert_called_once_with(
        state.participants,
        "sessionStatus",
        state.status_payload(),
    )


def test_ready_event_rejects_non_member(monkeypatch):
    """ReadyEvent does not mutate sessions for non-members."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=3)
    commit = MagicMock()
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", commit)

    LiveSession.handle_ready_event(
        experiment,
        participant,
        ReadyMessage(session_id=1),
    )

    assert state.ready_participant_ids == []
    experiment.websocket.send.assert_not_called()
    commit.assert_not_called()


def test_live_session_end_marks_ended_and_notifies():
    """Live sessions can explicitly emit the built-in sessionEnd event."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())

    assert state.end(experiment) is True
    assert state.ended is True
    experiment.websocket.send.assert_called_once_with(
        state.participants, "sessionEnd", state.snapshot_payload()
    )
    assert state.end(experiment) is False


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

    live_session = SimpleNamespace(
        id=5,
        sync_group_id=9,
        participant_ids=[1, 2],
        node_id=11,
        network_id=12,
    )
    monkeypatch.setattr(
        PolymorphicDemoLiveSession,
        "get_for_group",
        classmethod(lambda cls, **kwargs: live_session),
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

    assert control.session is live_session
    assert control.custom_value == 10
    assert control.live_session_config == {
        "session_id": 5,
        "participant_id": 1,
        "participant_ids": [1, 2],
    }


def test_live_session_control_requires_existing_session(monkeypatch):
    """Controls fail clearly if the initializer has not created a row."""

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

    with pytest.raises(RuntimeError, match="No live session prepared"):
        DemoControl(participant=_group().active_participants[0])


def test_trigger_session_end_event_marks_ended_and_notifies(monkeypatch):
    """SessionEnd can be triggered from a session class and row ID."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())

    monkeypatch.setattr("psynet.db.transaction", lambda: MagicMock())
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    LiveSession.trigger_end_event(
        experiment,
        1,
    )

    assert state.ended is True
    experiment.websocket.send.assert_called_once_with(
        state.participants, "sessionEnd", state.snapshot_payload()
    )


def test_live_session_uses_shared_polymorphic_table():
    """Custom live-session classes share the generic live_session table."""

    assert LiveSession.__tablename__ == "live_session"
    assert PolymorphicDemoLiveSession.__table__ is LiveSession.__table__
    assert "custom_value" in LiveSession.__table__.columns
    assert "session_id" not in LiveSession.__table__.columns
    assert "session_type" in LiveSession.__table__.columns
    assert "node_id" in LiveSession.__table__.columns
    assert "network_id" in LiveSession.__table__.columns

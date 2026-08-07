from types import SimpleNamespace
from unittest.mock import MagicMock

from psynet.session import (
    LIVE_SESSION_CLASSES,
    LiveSession,
    LiveSessionControl,
    ReadyMessage,
    StateRequestMessage,
    handle_ready_event,
    handle_state_request,
    register_live_session_class,
    trigger_session_end_event,
)


def _state():
    return LiveSession(
        namespace="default",
        session_id="session-1",
        state={"score": 3},
        participant_ids=[1, 2],
        ready_participant_ids=[],
        started=False,
    )


def test_live_session_tracks_ready_participants_and_started():
    """LiveSession starts once all expected participants are ready."""

    state = _state()

    assert state.mark_ready(SimpleNamespace(id=1)) is False
    assert state.ready_participant_ids == [1]
    assert state.started is False

    assert state.mark_ready(SimpleNamespace(id=2)) is True
    assert state.ready_participant_ids == [1, 2]
    assert state.started is True


def test_live_session_snapshot_payload_is_json_ready():
    """Snapshots expose state, readiness, and participant IDs as browser data."""

    state = _state()
    state.mark_ready(1)

    assert state.snapshot_payload() == {
        "namespace": "default",
        "session_id": "session-1",
        "state": {"score": 3},
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

    handle_state_request(
        experiment,
        participant,
        StateRequestMessage(namespace="default", session_id="session-1"),
    )
    experiment.websocket.send.assert_called_once_with(
        participant,
        "stateSnapshot",
        state.snapshot_payload(),
    )


def test_ready_event_marks_state_and_sends_snapshot(monkeypatch):
    """ReadyEvent updates the row and sends the resulting snapshot."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", MagicMock())

    handle_ready_event(
        experiment,
        participant,
        ReadyMessage(namespace="default", session_id="session-1"),
    )

    assert state.ready_participant_ids == [1]
    experiment.websocket.send.assert_called_once()


def test_live_session_end_marks_ended_and_notifies():
    """Live sessions can explicitly emit the built-in sessionEnd event."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())

    assert state.end(experiment) is True
    assert state.ended is True
    experiment.websocket.send.assert_called_once_with(
        [1, 2], "sessionEnd", state.snapshot_payload()
    )
    assert state.end(experiment) is False


def test_live_session_control_derives_config(monkeypatch):
    """LiveSessionControl derives transport config from participant and group."""

    class DemoSession:
        live_session_namespace = "demo"

        @classmethod
        def get_namespace(cls):
            return cls.live_session_namespace

        @classmethod
        def build_session_id(cls, participant, group, control):
            return f"demo:{group.id}"

        @classmethod
        def build_initial_state(cls, participant_ids, participant, group, control):
            return {"participant_ids": participant_ids}

        @classmethod
        def build_params(cls, participant, group, control):
            return {"custom": control.custom_value}

        @classmethod
        def get_or_create(cls, session_id, **kwargs):
            cls.created_with = {"session_id": session_id, **kwargs}
            return SimpleNamespace(session_id=session_id)

    class DemoControl(LiveSessionControl):
        session_class = DemoSession
        macro = "demo"

        def __init__(self, participant):
            self.custom_value = 10
            super().__init__(
                participant=participant,
                group_type="demo_group",
                params={"extra": "value"},
            )

    participants = [SimpleNamespace(id=2), SimpleNamespace(id=1)]
    group = SimpleNamespace(id=9, participants=participants)
    participant = SimpleNamespace(
        id=1, active_sync_groups={"demo_group": group}, sync_group=None
    )

    control = DemoControl(participant)

    assert control.live_session_config == {
        "namespace": "demo",
        "session_id": "demo:9",
        "group_id": 9,
        "participant_id": 1,
        "participant_ids": [1, 2],
        "custom": 10,
        "extra": "value",
    }
    assert DemoSession.created_with == {
        "session_id": "demo:9",
        "state": {"participant_ids": [1, 2]},
        "participant_ids": [1, 2],
    }


def test_trigger_session_end_event_marks_ended_and_notifies(monkeypatch):
    """SessionEnd can be triggered from a session class and ID."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())

    class DemoSession:
        @classmethod
        def get(cls, *args, **kwargs):
            return state

    monkeypatch.setattr("psynet.db.transaction", lambda: MagicMock())

    trigger_session_end_event(
        experiment,
        DemoSession,
        "default",
        "session-1",
    )

    assert state.ended is True
    experiment.websocket.send.assert_called_once_with(
        [1, 2], "sessionEnd", state.snapshot_payload()
    )


def test_register_live_session_class_restores_namespace():
    """Concrete live-session classes are looked up by namespace."""

    previous = dict(LIVE_SESSION_CLASSES)

    class DemoSession:
        live_session_namespace = "registered-demo"

    try:
        register_live_session_class(DemoSession)
        assert LIVE_SESSION_CLASSES["registered-demo"] is DemoSession
    finally:
        LIVE_SESSION_CLASSES.clear()
        LIVE_SESSION_CLASSES.update(previous)


def test_live_session_mixin_derives_table_name_and_constraint():
    """Concrete live-session classes inherit generic table metadata."""

    assert LiveSession.__tablename__ == "live_session"
    constraint = next(
        constraint
        for constraint in LiveSession.__table__.constraints
        if {column.name for column in constraint.columns} == {"namespace", "session_id"}
    )
    assert constraint is not None

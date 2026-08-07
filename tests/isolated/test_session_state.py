from types import SimpleNamespace
from unittest.mock import MagicMock

from psynet.session_state import (
    ReadyMessage,
    SessionState,
    StateRequestMessage,
    handle_ready_event,
    handle_state_request,
)


def _state():
    return SessionState(
        namespace="demo",
        session_id="session-1",
        state={"score": 3},
        participant_ids=[1, 2],
        ready_participant_ids=[],
        started=False,
    )


def test_session_state_tracks_ready_participants_and_started():
    """SessionState starts once all expected participants are ready."""

    state = _state()

    assert state.mark_ready(SimpleNamespace(id=1)) is False
    assert state.ready_participant_ids == [1]
    assert state.started is False

    assert state.mark_ready(SimpleNamespace(id=2)) is True
    assert state.ready_participant_ids == [1, 2]
    assert state.started is True


def test_session_state_snapshot_payload_is_json_ready():
    """Snapshots expose state, readiness, and participant IDs as browser data."""

    state = _state()
    state.mark_ready(1)

    assert state.snapshot_payload() == {
        "namespace": "demo",
        "session_id": "session-1",
        "state": {"score": 3},
        "participant_ids": ["1", "2"],
        "ready_participant_ids": ["1"],
        "started": False,
    }


def test_state_request_sends_snapshot_to_requesting_participant(monkeypatch):
    """StateRequest sends a snapshot through the experiment websocket helper."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(SessionState, "get", classmethod(lambda *args, **kwargs: state))

    handle_state_request(
        experiment,
        participant,
        StateRequestMessage(namespace="demo", session_id="session-1"),
    )
    experiment.websocket.send.assert_called_once_with(
        participant,
        "stateSnapshot",
        state.snapshot_payload(),
    )


def test_ready_event_marks_state_and_broadcasts(monkeypatch):
    """ReadyEvent updates the row and broadcasts the resulting snapshot."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(id=1)
    monkeypatch.setattr(SessionState, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session_state.db.session.commit", MagicMock())

    handle_ready_event(
        experiment,
        participant,
        ReadyMessage(namespace="demo", session_id="session-1"),
    )

    assert state.ready_participant_ids == [1]
    experiment.websocket.send.assert_called_once()

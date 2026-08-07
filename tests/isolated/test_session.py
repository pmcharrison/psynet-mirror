from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Column, String

from psynet.session import (
    LiveSession,
    LiveSessionControl,
    ReadyMessage,
    StateRequestMessage,
)


class PolymorphicDemoLiveSession(LiveSession):
    """Demo custom live session that shares the generic live_session table."""

    custom_value = Column(String)


def _state():
    return LiveSession(
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


def test_live_session_rejects_unknown_ready_participant():
    """Readiness only accepts expected live-session participants."""

    state = _state()

    assert state.mark_ready(SimpleNamespace(id=3)) is False
    assert state.ready_participant_ids == []
    assert state.started is False


def test_live_session_snapshot_payload_is_json_ready():
    """Snapshots expose state, readiness, and participant IDs as browser data."""

    state = _state()
    state.mark_ready(1)

    assert state.snapshot_payload() == {
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
    participant = SimpleNamespace(
        id=1, current_trial=SimpleNamespace(live_session=state)
    )

    LiveSession.handle_state_request(
        experiment,
        participant,
        StateRequestMessage(session_id="session-1"),
    )
    experiment.websocket.send.assert_called_once_with(
        participant,
        "stateSnapshot",
        state.snapshot_payload(),
    )


def test_state_request_rejects_non_member(monkeypatch):
    """StateRequest does not disclose snapshots to non-members."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(
        id=3, current_trial=SimpleNamespace(live_session=state)
    )

    LiveSession.handle_state_request(
        experiment,
        participant,
        StateRequestMessage(session_id="session-1"),
    )

    experiment.websocket.send.assert_not_called()


def test_ready_event_marks_state_and_sends_snapshot(monkeypatch):
    """ReadyEvent updates the row and sends the resulting snapshot."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(
        id=1, current_trial=SimpleNamespace(live_session=state)
    )
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", MagicMock())

    LiveSession.handle_ready_event(
        experiment,
        participant,
        ReadyMessage(session_id="session-1"),
    )

    assert state.ready_participant_ids == [1]
    experiment.websocket.send.assert_called_once()


def test_ready_event_rejects_non_member(monkeypatch):
    """ReadyEvent does not mutate sessions for non-members."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())
    participant = SimpleNamespace(
        id=3, current_trial=SimpleNamespace(live_session=state)
    )
    commit = MagicMock()
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))
    monkeypatch.setattr("psynet.session.db.session.commit", commit)

    LiveSession.handle_ready_event(
        experiment,
        participant,
        ReadyMessage(session_id="session-1"),
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
        [1, 2], "sessionEnd", state.snapshot_payload()
    )
    assert state.end(experiment) is False


def test_live_session_control_derives_config(monkeypatch):
    """LiveSessionControl derives transport config from participant and group."""

    class DemoSession:
        @classmethod
        def build_session_id(cls, group, trial):
            return f"demo:{group.id}"

        @classmethod
        def build_initial_state(cls, participant_ids, group, trial):
            return {"participant_ids": participant_ids}

    class DemoControl(LiveSessionControl):
        macro = "demo"

        def __init__(self, participant, trial):
            self.custom_value = 10
            super().__init__(
                participant=participant,
                group_type="demo_group",
                trial=trial,
                params={"extra": "value"},
            )

        def build_control_params(self):
            return {"custom": self.custom_value}

    participants = [SimpleNamespace(id=2), SimpleNamespace(id=1)]
    group = SimpleNamespace(id=9, participants=participants)
    participant = SimpleNamespace(
        id=1, active_sync_groups={"demo_group": group}, sync_group=None
    )
    live_session = SimpleNamespace(session_id="demo:9")
    trial = SimpleNamespace(
        id=7,
        live_session=live_session,
        live_session_class=DemoSession,
    )

    control = DemoControl(participant, trial=trial)

    assert control.live_session_config == {
        "session_id": "demo:9",
        "group_id": 9,
        "participant_id": 1,
        "participant_ids": [1, 2],
        "custom": 10,
        "extra": "value",
    }


def test_live_session_control_requires_trial():
    """LiveSessionControl currently consumes a prepared trial."""

    with pytest.raises(ValueError, match="requires a trial"):
        LiveSessionControl._resolve_session_class(None)


def test_live_session_control_requires_trial_session_class():
    """Trial-backed live controls derive the session class from the trial."""

    trial = SimpleNamespace(live_session_class=None)

    with pytest.raises(ValueError, match="must define live_session_class"):
        LiveSessionControl._resolve_session_class(trial)


def test_live_session_links_trials_by_participant():
    """LiveSession tracks participant trials associated with a shared session."""

    state = _state()
    state.id = 10
    trial = SimpleNamespace(
        id=7,
        participant_id=1,
        failed=False,
        live_session_id=None,
        live_session=None,
    )

    assert state.link_trial(trial) is trial
    assert trial.live_session is state

    state.__dict__["trials"] = [trial]
    assert state.get_participant_trial(1) is trial
    assert state.get_participant_trial(SimpleNamespace(id=2)) is None


def test_live_session_prepare_for_group_creates_and_links_trials(monkeypatch):
    """Live sessions are prepared once for a synchronized trial group."""

    added = MagicMock()
    monkeypatch.setattr("psynet.session.db.session.add", added)
    monkeypatch.setattr("psynet.session.db.session.flush", MagicMock())
    monkeypatch.setattr(
        PolymorphicDemoLiveSession,
        "get",
        classmethod(lambda cls, session_id: None),
    )

    trials = [
        SimpleNamespace(
            id=7,
            participant_id=1,
            failed=False,
            live_session_id=None,
            live_session=None,
            network=SimpleNamespace(id=11),
        ),
        SimpleNamespace(
            id=8,
            participant_id=2,
            failed=False,
            live_session_id=None,
            live_session=None,
            network=SimpleNamespace(id=12),
        ),
    ]
    participants = [
        SimpleNamespace(id=2, current_trial=trials[1]),
        SimpleNamespace(id=1, current_trial=trials[0]),
    ]
    group = SimpleNamespace(
        id=9,
        participants=participants,
        active_participants=participants,
        leader=participants[0],
    )

    live_session = PolymorphicDemoLiveSession.prepare_for_group(group=group)

    assert live_session.session_id == "polymorphic_demo_live_session:network:12:group:9"
    assert live_session.participant_ids == [1, 2]
    assert [trial.live_session for trial in trials] == [live_session, live_session]
    added.assert_called_once_with(live_session)


def test_live_session_prepare_for_group_requires_leader_trial(monkeypatch):
    """A synchronized live session must be derived from the group leader's trial."""

    monkeypatch.setattr(
        PolymorphicDemoLiveSession,
        "get",
        classmethod(lambda cls, session_id: None),
    )

    follower_trial = SimpleNamespace(
        id=7,
        participant_id=1,
        failed=False,
        live_session_id=None,
        live_session=None,
        network=SimpleNamespace(id=12),
    )
    participants = [
        SimpleNamespace(id=2, current_trial=None),
        SimpleNamespace(id=1, current_trial=follower_trial),
    ]
    group = SimpleNamespace(
        id=9,
        participants=participants,
        active_participants=participants,
        leader=participants[0],
    )

    with pytest.raises(ValueError, match="no trial for leader"):
        PolymorphicDemoLiveSession.prepare_for_group(group=group)


def test_live_session_default_session_id_uses_class_and_network():
    """Default live-session IDs include the session class and shared network."""

    group = SimpleNamespace(id=9)
    trial = SimpleNamespace(network=SimpleNamespace(id=12))

    assert (
        PolymorphicDemoLiveSession.build_session_id(group, trial)
        == "polymorphic_demo_live_session:network:12:group:9"
    )


def test_live_session_rejects_mismatched_trial_link():
    """A trial cannot be silently moved to a different live session."""

    state = _state()
    state.id = 10
    trial = SimpleNamespace(id=7, live_session_id=11)

    with pytest.raises(ValueError, match="already linked"):
        state.link_trial(trial)


def test_trigger_session_end_event_marks_ended_and_notifies(monkeypatch):
    """SessionEnd can be triggered from a session class and ID."""

    state = _state()
    experiment = SimpleNamespace(websocket=MagicMock())

    monkeypatch.setattr("psynet.db.transaction", lambda: MagicMock())
    monkeypatch.setattr(LiveSession, "get", classmethod(lambda *args, **kwargs: state))

    LiveSession.trigger_end_event(
        experiment,
        "session-1",
    )

    assert state.ended is True
    experiment.websocket.send.assert_called_once_with(
        [1, 2], "sessionEnd", state.snapshot_payload()
    )


def test_live_session_uses_shared_polymorphic_table():
    """Custom live-session classes share the generic live_session table."""

    assert LiveSession.__tablename__ == "live_session"
    assert PolymorphicDemoLiveSession.__table__ is LiveSession.__table__
    assert "custom_value" in LiveSession.__table__.columns
    assert LiveSession.__table__.columns["session_id"].unique is True

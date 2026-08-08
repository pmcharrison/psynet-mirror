import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import Field

from psynet.session import LiveSession
from psynet.websocket import (
    ExperimentWebSocket,
    ParticipantWebSocket,
    WebSocketMessage,
    _ConnectionManager,
    collect_websocket_handlers,
    dispatch_websocket_frame,
    extract_websocket_event_type,
    make_frame,
    parse_websocket_frame,
    websocket_handler,
)


class EchoMessage(WebSocketMessage):
    """Message used to exercise Pydantic validation."""

    value: int = Field(gt=0)


class DoneMessage(WebSocketMessage):
    """Server message used to exercise serialization."""

    answer: list[str] | None = None


class BroadcastMessage(WebSocketMessage):
    """Message used to exercise typed handling plus outbound broadcast."""

    session_id: str
    value: int


class EchoExperiment:
    def __init__(self):
        self._native_websocket_handlers = collect_websocket_handlers(self)
        self.websocket = MagicMock()

    @websocket_handler("echo", model=EchoMessage)
    def echo(self, participant, message, receive_time):
        participant.handled_value = message.value
        participant.handled_receive_time = receive_time
        return message.value

    @websocket_handler("raw")
    def raw(self, participant, message):
        participant.raw_message = message
        return message


class BroadcastExperiment:
    def __init__(self):
        self.websocket = ExperimentWebSocket(self)
        self._native_websocket_handlers = collect_websocket_handlers(self)

    @websocket_handler("broadcast", model=BroadcastMessage)
    def broadcast(self, participant, message):
        live_session = LiveSession.get_current_for_participant(
            participant, message.session_id
        )
        if live_session is not None:
            live_session.send_snapshot(self)


def _participant(page_uuid="current-page"):
    return SimpleNamespace(id=7, page_uuid=page_uuid)


def _live_session_with_participants(n_participants=4):
    participants = [
        SimpleNamespace(id=i, page_uuid=f"page-{i}")
        for i in range(1, n_participants + 1)
    ]
    live_session = LiveSession(
        session_id="session-1",
        state={"value": 1},
        participant_ids=[participant.id for participant in participants],
        ready_participant_ids=[],
        started=True,
        ended=False,
    )
    trials = []
    for participant in participants:
        trial = SimpleNamespace(
            id=participant.id,
            participant_id=participant.id,
            participant=participant,
            live_session=live_session,
            failed=False,
        )
        participant.current_trial = trial
        trials.append(trial)
    live_session.__dict__["trials"] = trials
    return live_session, participants


def test_decorated_experiment_handler_validates_and_dispatches_event():
    """A direct experiment handler receives validated message payloads."""

    participant = _participant()
    experiment = EchoExperiment()
    receive_time = datetime(2026, 7, 8, 16, 30, tzinfo=UTC)

    result = dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={
            "type": "echo",
            "message": {"value": 3},
            "page_uuid": "current-page",
        },
        receive_time=receive_time,
    )

    assert result == 3
    assert participant.handled_value == 3
    assert participant.handled_receive_time == receive_time


def test_raw_experiment_handler_receives_unvalidated_message():
    """String handlers can receive arbitrary JSON-compatible messages."""

    participant = _participant()
    experiment = EchoExperiment()
    message = {"coords": [60, 64], "type": "bullet"}

    result = dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={"type": "raw", "message": message, "page_uuid": "current-page"},
    )

    assert result == message
    assert participant.raw_message == message


def test_dispatch_rejects_stale_page_uuid():
    """Client event dispatch rejects messages from stale pages."""

    participant = _participant()
    experiment = EchoExperiment()

    assert (
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame={"type": "echo", "message": {"value": 1}, "page_uuid": "old"},
        )
        is None
    )
    assert not hasattr(participant, "handled_value")


def test_dispatch_rejects_missing_page_uuid():
    """Client event dispatch requires the current page UUID."""

    participant = _participant()
    experiment = EchoExperiment()

    assert (
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame={"type": "echo", "message": {"value": 1}},
        )
        is None
    )
    assert not hasattr(participant, "handled_value")


def test_dispatch_rejects_invalid_payload():
    """Pydantic validation failures stop dispatch before the handler runs."""

    participant = _participant()
    experiment = EchoExperiment()

    assert (
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame={
                "type": "echo",
                "message": {"value": 0},
                "page_uuid": "current-page",
            },
        )
        is None
    )
    assert not hasattr(participant, "handled_value")


def test_websocket_message_handling_and_broadcast_stays_fast(monkeypatch):
    """Typed inbound handling plus outbound broadcast stays below 5 ms."""

    class FakeRedis:
        publish_count = 0

        def publish(self, channel, payload):
            self.publish_count += 1

    fake_redis = FakeRedis()
    monkeypatch.setattr("psynet.websocket.redis_conn", fake_redis)

    live_session, session_participants = _live_session_with_participants()
    participant = session_participants[0]
    experiment = BroadcastExperiment()
    raw_frame = json.dumps(
        {
            "type": "broadcast",
            "message": {"session_id": live_session.session_id, "value": 1},
            "page_uuid": participant.page_uuid,
        }
    )
    receive_time = datetime(2026, 7, 8, 16, 30, tzinfo=UTC)

    for _ in range(20):
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame=parse_websocket_frame(raw_frame),
            receive_time=receive_time,
        )

    n_messages = 1000
    start = time.perf_counter()
    for _ in range(n_messages):
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame=parse_websocket_frame(raw_frame),
            receive_time=receive_time,
        )
    elapsed = time.perf_counter() - start

    assert elapsed / n_messages < 0.005
    assert fake_redis.publish_count == n_messages + 20


def test_event_type_extraction():
    """Utilities can inspect raw JSON frames."""

    assert extract_websocket_event_type(json.dumps({"type": "echo"})) == "echo"


def test_make_frame_serializes_server_event_models():
    """Outbound message models serialize to compact WebSocket frame payloads."""

    frame = make_frame("done", DoneMessage(answer=None))
    assert frame == {"type": "done", "message": {}}


def test_participant_websocket_publishes_targeted_event(monkeypatch):
    """Participant helpers publish targeted Redis fanout frames."""

    published = []

    class FakeRedis:
        def publish(self, channel, payload):
            published.append((channel, json.loads(payload)))

    monkeypatch.setattr("psynet.websocket.redis_conn", FakeRedis())

    participant = _participant()
    ParticipantWebSocket(participant).send("serverMessage", "hello")

    assert len(published) == 1
    channel, envelope = published[0]
    assert channel == "psynet:websocket:outbound"
    assert envelope == {
        "page_uuids": ["current-page"],
        "payload": json.dumps(
            {"type": "serverMessage", "message": "hello"}, separators=(",", ":")
        ),
    }
    assert json.loads(envelope["payload"]) == {
        "type": "serverMessage",
        "message": "hello",
    }


def test_experiment_websocket_send_accepts_one_or_many_participants(monkeypatch):
    """Experiment helpers publish to one participant or a participant list."""

    published = []

    class FakeRedis:
        def publish(self, channel, payload):
            published.append(json.loads(payload))

    monkeypatch.setattr("psynet.websocket.redis_conn", FakeRedis())

    websocket = ExperimentWebSocket(SimpleNamespace())
    websocket.send(SimpleNamespace(id=7, page_uuid="page-7"), "one", "hello")
    websocket.send(
        [
            SimpleNamespace(id=8, page_uuid="page-8"),
            SimpleNamespace(id=9, page_uuid="page-9"),
        ],
        "many",
        {"ok": True},
    )

    assert published == [
        {
            "page_uuids": ["page-7"],
            "payload": json.dumps(
                {"type": "one", "message": "hello"}, separators=(",", ":")
            ),
        },
        {
            "page_uuids": ["page-8", "page-9"],
            "payload": json.dumps(
                {"type": "many", "message": {"ok": True}}, separators=(",", ":")
            ),
        },
    ]


def test_experiment_websocket_send_rejects_participant_ids(monkeypatch):
    """Page-scoped delivery requires participant objects, not raw IDs."""

    websocket = ExperimentWebSocket(SimpleNamespace())

    with pytest.raises(TypeError, match="Participant objects"):
        websocket.send(7, "one", "hello")


def test_connection_manager_filters_stale_page_sockets():
    """Outbound frames only reach sockets for the participant's current page."""

    sent = {"current": [], "old": []}

    class FakeSocket:
        def __init__(self, key):
            self.key = key

        def send(self, payload):
            sent[self.key].append(json.loads(payload))

    manager = _ConnectionManager()
    manager.add(7, "current-page", FakeSocket("current"))
    manager.add(7, "old-page", FakeSocket("old"))

    manager.send_to_pages(
        ["current-page"],
        json.dumps({"type": "serverMessage", "message": "hello"}),
    )

    assert sent["current"] == [{"type": "serverMessage", "message": "hello"}]
    assert sent["old"] == []

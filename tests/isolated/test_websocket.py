import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from pydantic import Field

from psynet.websocket import (
    ExperimentWebSocket,
    ParticipantWebSocket,
    WebSocketMessage,
    _extract_websocket_participant_id,
    collect_websocket_handlers,
    dispatch_websocket_frame,
    extract_websocket_event_type,
    make_frame,
    websocket_handler,
)


class EchoMessage(WebSocketMessage):
    """Message used to exercise Pydantic validation."""

    value: int = Field(gt=0)


class DoneMessage(WebSocketMessage):
    """Server message used to exercise serialization."""

    answer: list[str] | None = None


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


def _participant(page_uuid="current-page"):
    return SimpleNamespace(id=7, page_uuid=page_uuid)


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


def test_dispatch_rejects_invalid_payload():
    """Pydantic validation failures stop dispatch before the handler runs."""

    participant = _participant()
    experiment = EchoExperiment()

    assert (
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame={"type": "echo", "message": {"value": 0}},
        )
        is None
    )
    assert not hasattr(participant, "handled_value")


def test_event_type_and_participant_extraction():
    """Utilities can inspect raw JSON frames."""

    assert extract_websocket_event_type(json.dumps({"type": "echo"})) == "echo"
    assert _extract_websocket_participant_id(json.dumps({"participant_id": 13})) == 13


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
    channel, frame = published[0]
    assert channel == "psynet:websocket:outbound"
    assert frame == {
        "type": "serverMessage",
        "message": "hello",
        "target_participant_ids": ["7"],
    }


def test_experiment_websocket_send_accepts_one_or_many_targets(monkeypatch):
    """Experiment helpers publish to one participant or a list of IDs."""

    published = []

    class FakeRedis:
        def publish(self, channel, payload):
            published.append(json.loads(payload))

    monkeypatch.setattr("psynet.websocket.redis_conn", FakeRedis())

    websocket = ExperimentWebSocket(SimpleNamespace())
    websocket.send(SimpleNamespace(id=7), "one", "hello")
    websocket.send([7, SimpleNamespace(id=8)], "many", {"ok": True})

    assert published == [
        {
            "type": "one",
            "message": "hello",
            "target_participant_ids": ["7"],
        },
        {
            "type": "many",
            "message": {"ok": True},
            "target_participant_ids": ["7", "8"],
        },
    ]

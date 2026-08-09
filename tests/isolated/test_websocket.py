import json
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from dallinger import db
from pydantic import Field
from sqlalchemy import Column, Integer

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.session import LiveSession
from psynet.session import session as session_context
from psynet.websocket import (
    INBOUND,
    OUTBOUND,
    REDIS_SAVE_QUEUE,
    ClientWebSocketMessage,
    ExperimentWebSocket,
    ParticipantWebSocket,
    ServerWebSocketMessage,
    _ConnectionManager,
    dispatch_websocket_frame,
    drain_websocket_message_event_queue_once,
    extract_websocket_event_type,
    get_client_websocket_message_type,
    get_websocket_message_event_model,
    make_frame,
    parse_websocket_frame,
)


class EchoMessage(ClientWebSocketMessage):
    """Message used to exercise Pydantic validation."""

    event_type = "echo"
    value: int = Field(gt=0)

    def handle(self, experiment, participant, receive_time):
        participant.handled_value = self.value
        participant.handled_receive_time = receive_time
        return self.value


class TransientMessage(ClientWebSocketMessage):
    """Message used to exercise persistence opt-out."""

    event_type = "transient"
    save = False
    value: int = Field(gt=0)

    def handle(self, experiment, participant, receive_time):
        participant.transient_value = self.value
        return self.value


class DoneMessage(ServerWebSocketMessage):
    """Server message used to exercise serialization."""

    event_type = "done"
    answer: list[str] | None = None


class BroadcastMessage(ClientWebSocketMessage):
    """Message used to exercise typed handling plus outbound broadcast."""

    event_type = "broadcast"
    save = False
    value: int

    def handle(self, experiment, participant, receive_time):
        live_session = LiveSession.get_current_for_participant(
            participant, self.session_id
        )
        if live_session is not None:
            state = live_session.state or {}
            message_count = int(state.get("message_count", 0)) + 1
            state["message_count"] = message_count
            live_session.state = state
            db.session.add(
                WebSocketBenchmarkEvent(
                    session_id=live_session.id,
                    participant_id=participant.id,
                    message_count=message_count,
                )
            )
            live_session.send_snapshot(experiment)


class SessionEchoMessage(ClientWebSocketMessage):
    """Message used to exercise session injection without locking."""

    event_type = "sessionEcho"

    @session_context()
    def handle(self, experiment, participant, session: LiveSession, receive_time):
        participant.injected_session = session
        participant.injected_receive_time = receive_time
        return session.id


class LockedSessionEchoMessage(ClientWebSocketMessage):
    """Message used to exercise locked session injection."""

    event_type = "lockedSessionEcho"

    @session_context(for_update=True)
    def handle(self, experiment, participant, session: LiveSession, receive_time):
        participant.locked_session = session
        return session.id


@register_table
class WebSocketBenchmarkEvent(SQLBase, SQLMixin):
    """Synthetic event row used by the WebSocket performance test."""

    __tablename__ = "websocket_benchmark_event"

    session_id = Column(Integer)
    participant_id = Column(Integer)
    message_count = Column(Integer)


class FakeRedis:
    def __init__(self):
        self.publish_count = 0
        self.published = []
        self.lists = {}

    def publish(self, channel, payload):
        self.publish_count += 1
        self.published.append((channel, payload))

    def rpush(self, key, *values):
        stored_values = self.lists.setdefault(key, [])
        stored_values.extend(values)
        return len(stored_values)

    def lpush(self, key, *values):
        stored_values = self.lists.setdefault(key, [])
        for value in values:
            stored_values.insert(0, value)
        return len(stored_values)

    def lpop(self, key):
        values = self.lists.get(key, [])
        if not values:
            return None
        return values.pop(0)

    def blpop(self, keys, timeout=0):
        key = keys[0] if isinstance(keys, (list, tuple)) else keys
        value = self.lpop(key)
        if value is None:
            return None
        return key, value


@pytest.fixture(autouse=True)
def fake_websocket_redis(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr("psynet.websocket.redis_conn", fake_redis)
    return fake_redis


def _saved_websocket_event_records(fake_redis):
    return [
        json.loads(payload) for payload in fake_redis.lists.get(REDIS_SAVE_QUEUE, [])
    ]


class EchoExperiment:
    def __init__(self):
        self.websocket = MagicMock()


class BroadcastExperiment:
    def __init__(self):
        self.websocket = ExperimentWebSocket(self)


def _participant(page_uuid="current-page"):
    return SimpleNamespace(id=7, page_uuid=page_uuid)


def _live_session_with_participants(n_participants=4):
    participants = [
        SimpleNamespace(id=i, page_uuid=f"page-{i}")
        for i in range(1, n_participants + 1)
    ]
    live_session = LiveSession(
        state={"value": 1},
        participant_ids=[participant.id for participant in participants],
        ready_participant_ids=[],
        started=True,
        ended=False,
    )
    live_session.id = 1
    live_session.__dict__["sync_group"] = SimpleNamespace(
        active_participants=participants
    )
    return live_session, participants


def test_client_message_validates_and_dispatches_to_handle_method():
    """A typed client message receives validated message payloads."""

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


def test_client_message_subclass_registers_by_event_type():
    """Client message subclasses are auto-registered by event type."""

    assert get_client_websocket_message_type("echo") is EchoMessage


def test_client_messages_have_nullable_session_id_field():
    """All client messages carry a nullable session_id field."""

    message = EchoMessage(value=3)

    assert "session_id" in EchoMessage.model_fields
    assert message.session_id is None


def test_dispatch_saves_accepted_message_by_default(fake_websocket_redis):
    """Accepted typed messages are queued for model-specific persistence."""

    participant = _participant()
    experiment = EchoExperiment()
    receive_time = datetime(2026, 7, 8, 16, 30, tzinfo=UTC)

    dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={
            "type": "echo",
            "message": {"value": 3},
            "page_uuid": "current-page",
        },
        receive_time=receive_time,
    )

    assert _saved_websocket_event_records(fake_websocket_redis) == [
        {
            "participant_id": 7,
            "event_type": "echo",
            "page_uuid": "current-page",
            "direction": INBOUND,
            "message_time": "2026-07-08T16:30:00+00:00",
            "table_name": "echo_message",
            "values": {"value": 3},
        }
    ]


def test_websocket_message_model_generates_typed_event_table():
    """Typed message persistence creates one table with model-field columns."""

    event_model = get_websocket_message_event_model(BroadcastMessage)

    assert event_model.__name__ == "BroadcastMessage"
    assert event_model.__tablename__ == "broadcast_message"
    assert {
        "participant_id",
        "event_type",
        "page_uuid",
        "direction",
        "message_time",
        "session_id",
        "value",
    }.issubset(event_model.__table__.columns.keys())


def test_dispatch_can_opt_out_of_generic_message_saving(fake_websocket_redis):
    """Handlers can disable default persistence for transient messages."""

    participant = _participant()
    experiment = EchoExperiment()

    result = dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={
            "type": "transient",
            "message": {"value": 3},
            "page_uuid": "current-page",
        },
    )

    assert result == 3
    assert participant.transient_value == 3
    assert _saved_websocket_event_records(fake_websocket_redis) == []


def test_session_decorator_injects_resolved_session(monkeypatch):
    """Decorated handlers receive the participant-owned live session."""

    participant = _participant()
    experiment = EchoExperiment()
    receive_time = datetime(2026, 7, 8, 16, 30, tzinfo=UTC)
    live_session = SimpleNamespace(id=123)
    calls = []

    def fake_get_current_for_participant(
        cls, participant_arg, session_id, *, for_update
    ):
        calls.append((participant_arg, session_id, for_update))
        return live_session

    monkeypatch.setattr(
        LiveSession,
        "get_current_for_participant",
        classmethod(fake_get_current_for_participant),
    )

    result = dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={
            "type": "sessionEcho",
            "message": {"session_id": 123},
            "page_uuid": "current-page",
        },
        receive_time=receive_time,
    )

    assert result == 123
    assert calls == [(participant, 123, False)]
    assert participant.injected_session is live_session
    assert participant.injected_receive_time == receive_time


def test_session_decorator_passes_for_update(monkeypatch):
    """Decorated handlers can request a locked live-session row."""

    participant = _participant()
    experiment = EchoExperiment()
    live_session = SimpleNamespace(id=124)
    calls = []

    def fake_get_current_for_participant(
        cls, participant_arg, session_id, *, for_update
    ):
        calls.append((participant_arg, session_id, for_update))
        return live_session

    monkeypatch.setattr(
        LiveSession,
        "get_current_for_participant",
        classmethod(fake_get_current_for_participant),
    )

    result = dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={
            "type": "lockedSessionEcho",
            "message": {"session_id": 124},
            "page_uuid": "current-page",
        },
    )

    assert result == 124
    assert calls == [(participant, 124, True)]
    assert participant.locked_session is live_session


def test_session_decorator_skips_handler_when_session_is_missing(monkeypatch):
    """Decorated handlers require a participant-owned live session."""

    participant = _participant()
    experiment = EchoExperiment()

    def fake_get_current_for_participant(
        cls, participant_arg, session_id, *, for_update
    ):
        return None

    monkeypatch.setattr(
        LiveSession,
        "get_current_for_participant",
        classmethod(fake_get_current_for_participant),
    )

    result = dispatch_websocket_frame(
        experiment,
        participant=participant,
        frame={
            "type": "sessionEcho",
            "message": {"session_id": 999},
            "page_uuid": "current-page",
        },
    )

    assert result is None
    assert not hasattr(participant, "injected_session")


def test_dispatch_does_not_save_rejected_message(fake_websocket_redis):
    """Rejected messages never reach the persistence queue."""

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
    assert _saved_websocket_event_records(fake_websocket_redis) == []


def test_dispatch_rejects_unknown_message_type(fake_websocket_redis):
    """Inbound messages must resolve to a registered client message class."""

    participant = _participant()
    experiment = EchoExperiment()

    assert (
        dispatch_websocket_frame(
            experiment,
            participant=participant,
            frame={
                "type": "unknown",
                "message": {"value": 1},
                "page_uuid": "current-page",
            },
        )
        is None
    )
    assert _saved_websocket_event_records(fake_websocket_redis) == []


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
    added_events = []
    monkeypatch.setattr(db.session, "add", added_events.append)

    live_session, session_participants = _live_session_with_participants()
    monkeypatch.setattr(
        LiveSession,
        "get",
        classmethod(lambda cls, session_id, **kwargs: live_session),
    )
    participant = session_participants[0]
    experiment = BroadcastExperiment()
    raw_frame = json.dumps(
        {
            "type": "broadcast",
            "message": {"session_id": live_session.id, "value": 1},
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
    assert live_session.state["message_count"] == n_messages + 20
    assert len(added_events) == n_messages + 20
    assert isinstance(added_events[-1], WebSocketBenchmarkEvent)


def test_websocket_message_event_queue_drains_to_database(
    fake_websocket_redis, monkeypatch
):
    """Queued message records are converted to ORM rows in batches."""

    fake_websocket_redis.rpush(
        REDIS_SAVE_QUEUE,
        json.dumps(
            {
                "table_name": "echo_message",
                "participant_id": 7,
                "event_type": "echo",
                "page_uuid": "current-page",
                "direction": INBOUND,
                "message_time": "2026-07-08T16:30:00+00:00",
                "values": {"value": 3},
            }
        ),
    )
    added_events = []
    commits = []

    monkeypatch.setattr(db.session, "add_all", added_events.extend)
    monkeypatch.setattr(db.session, "commit", lambda: commits.append(True))
    monkeypatch.setattr(db.session, "rollback", lambda: None)

    assert drain_websocket_message_event_queue_once() == 1
    assert commits == [True]
    assert len(added_events) == 1
    event = added_events[0]
    assert isinstance(event, get_websocket_message_event_model(EchoMessage))
    assert event.participant_id == 7
    assert event.event_type == "echo"
    assert event.page_uuid == "current-page"
    assert event.direction == INBOUND
    assert event.message_time == datetime(2026, 7, 8, 16, 30, tzinfo=UTC)
    assert event.value == 3


def test_event_type_extraction():
    """Utilities can inspect raw JSON frames."""

    assert extract_websocket_event_type(json.dumps({"type": "echo"})) == "echo"


def test_make_frame_serializes_server_event_models():
    """Outbound message models serialize to compact WebSocket frame payloads."""

    frame = make_frame(DoneMessage(answer=None))
    assert frame == {"type": "done", "message": {}}


def test_participant_websocket_publishes_targeted_event(fake_websocket_redis):
    """Participant helpers publish targeted Redis fanout frames."""

    participant = _participant()
    ParticipantWebSocket(participant).send(DoneMessage(answer=["hello"]))

    assert len(fake_websocket_redis.published) == 1
    channel, raw_envelope = fake_websocket_redis.published[0]
    envelope = json.loads(raw_envelope)
    assert channel == "psynet:websocket:outbound"
    assert envelope == {
        "page_uuids": ["current-page"],
        "payload": json.dumps(
            {"type": "done", "message": {"answer": ["hello"]}},
            separators=(",", ":"),
        ),
    }
    assert json.loads(envelope["payload"]) == {
        "type": "done",
        "message": {"answer": ["hello"]},
    }
    records = _saved_websocket_event_records(fake_websocket_redis)
    assert len(records) == 1
    assert records[0]["direction"] == OUTBOUND
    assert records[0]["event_type"] == "done"
    assert records[0]["participant_id"] == 7
    assert records[0]["values"] == {"answer": ["hello"]}


def test_experiment_websocket_send_accepts_one_or_many_participants(
    fake_websocket_redis,
):
    """Experiment helpers publish to one participant or a participant list."""

    websocket = ExperimentWebSocket(SimpleNamespace())
    websocket.send(
        SimpleNamespace(id=7, page_uuid="page-7"),
        DoneMessage(answer=["one"]),
    )
    websocket.send(
        [
            SimpleNamespace(id=8, page_uuid="page-8"),
            SimpleNamespace(id=9, page_uuid="page-9"),
        ],
        DoneMessage(answer=["many"]),
    )

    published = [json.loads(payload) for _, payload in fake_websocket_redis.published]
    assert published == [
        {
            "page_uuids": ["page-7"],
            "payload": json.dumps(
                {"type": "done", "message": {"answer": ["one"]}},
                separators=(",", ":"),
            ),
        },
        {
            "page_uuids": ["page-8", "page-9"],
            "payload": json.dumps(
                {"type": "done", "message": {"answer": ["many"]}},
                separators=(",", ":"),
            ),
        },
    ]
    records = _saved_websocket_event_records(fake_websocket_redis)
    assert [record["participant_id"] for record in records] == [7, 8, 9]
    assert all(record["direction"] == OUTBOUND for record in records)
    assert records[1]["values"] == {"answer": ["many"]}
    assert records[2]["values"] == {"answer": ["many"]}


def test_experiment_websocket_send_rejects_participant_ids(monkeypatch):
    """Page-scoped delivery requires participant objects, not raw IDs."""

    websocket = ExperimentWebSocket(SimpleNamespace())

    with pytest.raises(TypeError, match="Participant objects"):
        websocket.send(7, DoneMessage(answer=["one"]))


def test_outbound_send_requires_server_message():
    """Outbound helpers require typed server message objects."""

    with pytest.raises(TypeError, match="ServerWebSocketMessage"):
        ParticipantWebSocket(_participant()).send("hello")


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

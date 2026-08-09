"""Native WebSocket helpers for PsyNet experiments.

The public API is intentionally small:

* JavaScript sends browser events with ``psynet.websocket.send(type, message)``.
* Python receives them with auto-registered ``ClientWebSocketMessage`` classes.
* Server code sends browser events with typed ``ServerWebSocketMessage`` objects
  via ``participant.websocket.send(message)`` or
  ``experiment.websocket.send(participant_or_participants, message)``.

Browser sockets are owned by the web process that accepted the connection.
Outbound server messages are therefore fanned out through Redis so scheduled
tasks and other worker processes can still address connected participants.
Inbound messages are dispatched directly in the socket-owning process. Outbound
messages travel through Redis as private routing envelopes whose payload is the
exact browser-visible frame.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from types import UnionType
from typing import ClassVar, Type, Union, get_args, get_origin

from dallinger.db import redis_conn
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict, PythonList, PythonObject
from psynet.utils import get_logger, model_name_to_snake_case

logger = get_logger()

WEBSOCKET_ROUTE = "/psynet/websocket"
REDIS_OUTBOUND_CHANNEL = "psynet:websocket:outbound"
REDIS_SAVE_QUEUE = "psynet:websocket:save"
WEBSOCKET_SAVE_BATCH_SIZE = 100
WEBSOCKET_SAVE_POLL_TIMEOUT = 1
INTERNAL_FRAME_KEYS = {
    "type",
    "message",
    "page_uuid",
}
INBOUND = "inbound"
OUTBOUND = "outbound"
_ABSTRACT_WEBSOCKET_MESSAGE_CLASS_NAMES = {
    "WebSocketMessage",
    "ClientWebSocketMessage",
    "ServerWebSocketMessage",
}
_CLIENT_WEBSOCKET_MESSAGE_TYPES: dict[str, Type["ClientWebSocketMessage"]] = {}
_WEBSOCKET_MESSAGE_EVENT_MODELS: dict[Type[BaseModel], Type[SQLBase]] = {}
_WEBSOCKET_MESSAGE_EVENT_MODELS_BY_TABLE: dict[str, Type[SQLBase]] = {}
_WEBSOCKET_MESSAGE_METADATA_COLUMNS = {
    "id",
    "participant_id",
    "event_type",
    "page_uuid",
    "direction",
    "message_time",
}


class WebSocketMessage(BaseModel):
    """Base class for typed WebSocket message payloads."""

    event_type: ClassVar[str]
    save: ClassVar[bool] = True
    model_config = ConfigDict(extra="forbid", strict=True)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in _ABSTRACT_WEBSOCKET_MESSAGE_CLASS_NAMES:
            return
        _validate_websocket_message_class(cls)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        if cls.__name__ in _ABSTRACT_WEBSOCKET_MESSAGE_CLASS_NAMES:
            return
        # Pydantic populates model_fields after __init_subclass__, so generated
        # SQL tables must wait until this hook.
        get_websocket_message_event_model(cls)


class ClientWebSocketMessage(WebSocketMessage):
    """Browser-to-server WebSocket message with class-owned handling logic."""

    session_id: int | None = Field(default=None, ge=1)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__name__ in _ABSTRACT_WEBSOCKET_MESSAGE_CLASS_NAMES:
            return
        _register_client_websocket_message_type(cls)

    def handle(self, experiment, participant, receive_time):
        """Handle this accepted browser message."""

        raise NotImplementedError


class ServerWebSocketMessage(WebSocketMessage):
    """Server-to-browser WebSocket message payload."""


def _validate_websocket_message_class(message_class: Type[WebSocketMessage]):
    event_type = getattr(message_class, "event_type", None)
    if not isinstance(event_type, str) or not event_type:
        raise ValueError(
            f"{message_class.__name__}.event_type must be a non-empty string."
        )
    if not isinstance(getattr(message_class, "save", True), bool):
        raise TypeError(f"{message_class.__name__}.save must be a boolean.")


def _register_client_websocket_message_type(
    message_class: Type[ClientWebSocketMessage],
):
    if "handle" not in message_class.__dict__:
        raise TypeError(
            f"{message_class.__name__} must define a handle("
            "experiment, participant, receive_time) method."
        )
    event_type = message_class.event_type
    existing = _CLIENT_WEBSOCKET_MESSAGE_TYPES.get(event_type)
    if existing is not None and existing is not message_class:
        raise ValueError(
            "Client WebSocket message event types must be unique; "
            f"{message_class.__name__!r} conflicts with {existing.__name__!r} "
            f"for event type {event_type!r}."
        )
    _CLIENT_WEBSOCKET_MESSAGE_TYPES[event_type] = message_class


def get_client_websocket_message_type(event_type: str):
    """Return the registered client message class for an inbound event type."""

    return _CLIENT_WEBSOCKET_MESSAGE_TYPES.get(event_type)


def _json_dumps(data) -> str:
    return json.dumps(data, separators=(",", ":"))


def _normalize_message(message):
    if isinstance(message, BaseModel):
        return message.model_dump(mode="json", exclude_none=True)
    return message


def _strip_optional(annotation):
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return annotation


def _column_for_annotation(annotation):
    annotation = _strip_optional(annotation)
    origin = get_origin(annotation)

    if annotation is int:
        return Column(Integer, nullable=True)
    if annotation is float:
        return Column(Float, nullable=True)
    if annotation is bool:
        return Column(Boolean, nullable=True)
    if annotation is str:
        return Column(String, nullable=True)
    if annotation is datetime:
        return Column(DateTime(timezone=True), nullable=True)
    if annotation is list or origin is list:
        return Column(PythonList, nullable=True)
    if annotation is dict or origin is dict:
        return Column(PythonDict, nullable=True)
    return Column(PythonObject, nullable=True)


def _websocket_message_model_columns(message_model: Type[BaseModel]):
    conflicting_fields = set(message_model.model_fields).intersection(
        _WEBSOCKET_MESSAGE_METADATA_COLUMNS
    )
    if conflicting_fields:
        fields = ", ".join(sorted(conflicting_fields))
        raise ValueError(
            "WebSocket message field names cannot shadow saved-message "
            f"metadata columns: {fields}."
        )

    return {
        field_name: _column_for_annotation(field_info.annotation)
        for field_name, field_info in message_model.model_fields.items()
    }


def _base_websocket_message_event_columns():
    return {
        "participant_id": Column(Integer, index=True, nullable=False),
        "event_type": Column(String(128), index=True, nullable=False),
        "page_uuid": Column(String(128), index=True, nullable=False),
        "direction": Column(String(16), index=True, nullable=False),
        "message_time": Column(DateTime(timezone=True), nullable=False),
    }


def get_websocket_message_event_model(message_model: Type[BaseModel]):
    """Return the SQL model used to persist accepted messages of this type."""

    if message_model in _WEBSOCKET_MESSAGE_EVENT_MODELS:
        return _WEBSOCKET_MESSAGE_EVENT_MODELS[message_model]

    table_name = model_name_to_snake_case(message_model.__name__)
    if table_name in _WEBSOCKET_MESSAGE_EVENT_MODELS_BY_TABLE:
        existing_model = _WEBSOCKET_MESSAGE_EVENT_MODELS_BY_TABLE[table_name]
        existing_message_model = getattr(
            existing_model, "__websocket_message_model__", None
        )
        if existing_message_model is message_model:
            _WEBSOCKET_MESSAGE_EVENT_MODELS[message_model] = existing_model
            return existing_model
        raise ValueError(
            "Saved WebSocket message table names must be unique; "
            f"{message_model.__name__!r} maps to existing table {table_name!r}."
        )

    attrs = {
        "__tablename__": table_name,
        "__module__": __name__,
        "__doc__": (
            "Persisted record of an accepted PsyNet WebSocket message "
            f"serialized as {message_model.__name__}."
        ),
        "__websocket_message_model__": message_model,
        **_base_websocket_message_event_columns(),
        **_websocket_message_model_columns(message_model),
    }
    event_model = register_table(
        type(message_model.__name__, (SQLBase, SQLMixin), attrs)
    )
    _WEBSOCKET_MESSAGE_EVENT_MODELS[message_model] = event_model
    _WEBSOCKET_MESSAGE_EVENT_MODELS_BY_TABLE[table_name] = event_model
    return event_model


def _websocket_message_event_model_from_table_name(table_name: str):
    try:
        return _WEBSOCKET_MESSAGE_EVENT_MODELS_BY_TABLE[table_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown WebSocket message event table: {table_name}"
        ) from exc


def _serialize_message_time(message_time):
    if message_time is None:
        message_time = datetime.now(timezone.utc)
    return message_time.isoformat()


def _deserialize_message_time(message_time):
    return datetime.fromisoformat(message_time)


def _make_websocket_message_event_record(
    *,
    participant,
    page_uuid: str,
    message: WebSocketMessage,
    message_time,
    direction: str,
):
    message_model = type(message)
    event_model = get_websocket_message_event_model(message_model)
    message_values = _normalize_message(message)
    values = {
        field_name: message_values[field_name]
        for field_name in message_model.model_fields
        if field_name in message_values
    }

    return {
        "table_name": event_model.__tablename__,
        "participant_id": int(participant.id),
        "event_type": message_model.event_type,
        "page_uuid": page_uuid,
        "direction": direction,
        "message_time": _serialize_message_time(message_time),
        "values": values,
    }


def enqueue_websocket_message_event(record: dict):
    """Queue an accepted WebSocket message event for batched persistence."""

    enqueue_websocket_message_events([record])


def enqueue_websocket_message_events(records):
    """Queue accepted WebSocket message events for batched persistence."""

    records = list(records)
    if not records:
        return

    try:
        redis_conn.rpush(
            REDIS_SAVE_QUEUE,
            *[_json_dumps(record) for record in records],
        )
    except Exception as exc:  # pragma: no cover - depends on Redis availability
        logger.warning("Failed to queue websocket message events for saving: %s", exc)


def queue_websocket_message_event(
    *,
    participant,
    page_uuid: str,
    message: WebSocketMessage,
    message_time,
    direction: str,
):
    """Build and queue one WebSocket message event."""

    enqueue_websocket_message_event(
        _make_websocket_message_event_record(
            participant=participant,
            page_uuid=page_uuid,
            message=message,
            message_time=message_time,
            direction=direction,
        )
    )


def _decode_websocket_message_event_payload(payload):
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    return json.loads(payload)


def _pop_websocket_message_event_payloads(max_batch_size, *, block: bool):
    payloads = []
    if block:
        item = redis_conn.blpop([REDIS_SAVE_QUEUE], timeout=WEBSOCKET_SAVE_POLL_TIMEOUT)
        if item is None:
            return payloads
        payloads.append(item[1])

    while len(payloads) < max_batch_size:
        payload = redis_conn.lpop(REDIS_SAVE_QUEUE)
        if payload is None:
            break
        payloads.append(payload)
    return payloads


def _requeue_websocket_message_event_payloads(payloads):
    if not payloads:
        return
    try:
        redis_conn.lpush(REDIS_SAVE_QUEUE, *reversed(payloads))
    except Exception as exc:  # pragma: no cover - depends on Redis availability
        logger.warning(
            "Failed to requeue websocket message events after error: %s", exc
        )


def _websocket_message_event_from_record(record):
    event_model = _websocket_message_event_model_from_table_name(record["table_name"])
    return event_model(
        participant_id=record["participant_id"],
        event_type=record["event_type"],
        page_uuid=record["page_uuid"],
        direction=record["direction"],
        message_time=_deserialize_message_time(record["message_time"]),
        **record.get("values", {}),
    )


def drain_websocket_message_event_queue_once(
    max_batch_size=WEBSOCKET_SAVE_BATCH_SIZE,
    *,
    block: bool = False,
):
    """Persist one batch of queued WebSocket message events."""

    from dallinger import db

    try:
        payloads = _pop_websocket_message_event_payloads(max_batch_size, block=block)
    except Exception as exc:  # pragma: no cover - depends on Redis availability
        logger.warning("Failed to read websocket message event save queue: %s", exc)
        return 0

    events = []
    valid_payloads = []
    for payload in payloads:
        try:
            record = _decode_websocket_message_event_payload(payload)
            events.append(_websocket_message_event_from_record(record))
            valid_payloads.append(payload)
        except Exception as exc:
            logger.warning("Discarded invalid websocket message event payload: %s", exc)

    if not events:
        return 0

    try:
        db.session.add_all(events)
        db.session.commit()
    except Exception as exc:  # pragma: no cover - depends on database availability
        db.session.rollback()
        _requeue_websocket_message_event_payloads(valid_payloads)
        logger.warning("Failed to save websocket message event batch: %s", exc)
        return 0

    return len(events)


def make_frame(message: WebSocketMessage, **extra):
    """Return the JSON-serializable WebSocket frame for an event."""

    if not isinstance(message, WebSocketMessage):
        raise TypeError("WebSocket frames must be built from WebSocketMessage objects.")

    frame = {"type": type(message).event_type, **extra}
    frame["message"] = _normalize_message(message)
    return frame


def _extract_frame_type(frame: dict):
    event_type = frame.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("WebSocket frame must include a non-empty string 'type'.")
    return event_type


def _extract_message(frame: dict):
    if "message" in frame:
        return frame["message"]
    return {
        key: value for key, value in frame.items() if key not in INTERNAL_FRAME_KEYS
    }


def _coerce_participant_id(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _participant_targets(participants):
    if not isinstance(participants, (list, tuple, set)):
        participants = [participants]

    # Outbound delivery is page-scoped. Raw participant IDs would require a DB
    # lookup here, so server code passes participant objects with page UUIDs.
    targets = []
    for participant in participants:
        if participant is None:
            continue

        if isinstance(participant, int):
            raise TypeError(
                "WebSocket targets must be Participant objects, not participant IDs."
            )

        participant_id = int(participant.id)
        if not participant.page_uuid:
            raise ValueError(
                f"Participant {participant_id} has no page UUID for WebSocket delivery."
            )
        targets.append((participant, participant.page_uuid))

    return targets


def _page_uuid_targets(participants):
    return [page_uuid for _, page_uuid in _participant_targets(participants)]


def extract_websocket_event_type(message):
    """Extract the ``type`` field from a raw WebSocket JSON message."""

    frame = parse_websocket_frame(message)
    return _extract_frame_type(frame)


def parse_websocket_frame(message) -> dict:
    """Parse a raw WebSocket message into a frame dictionary."""

    try:
        data = json.loads(message)
    except json.JSONDecodeError as exc:
        raise ValueError("WebSocket message is not valid JSON.") from exc

    if not isinstance(data, dict):
        raise ValueError("WebSocket message must be a JSON object.")

    _extract_frame_type(data)
    return data


def dispatch_websocket_frame(
    experiment,
    *,
    participant,
    frame: dict,
    receive_time=None,
):
    """Dispatch an incoming native WebSocket frame to an experiment handler."""

    event_type = _extract_frame_type(frame)
    if participant is None:
        logger.warning(
            "Rejected websocket event: missing participant (event_type=%s)",
            event_type,
        )
        return None

    message_class = get_client_websocket_message_type(event_type)
    if message_class is None:
        logger.warning(
            "Rejected websocket event: no client message class registered "
            "(participant_id=%s, event_type=%s)",
            participant.id,
            event_type,
        )
        return None

    # A refreshed page gets a new page UUID; reject messages from older browser
    # contexts so stale pages cannot mutate the current trial/session.
    page_uuid = frame.get("page_uuid")
    if not page_uuid or page_uuid != participant.page_uuid:
        logger.warning(
            "Rejected websocket event: stale page UUID "
            "(participant_id=%s, event_type=%s)",
            participant.id,
            event_type,
        )
        return None

    message = _extract_message(frame)
    try:
        message = message_class.model_validate(message)
    except ValidationError as exc:
        logger.warning(
            "Rejected websocket event: validation failed "
            "(participant_id=%s, event_type=%s, error=%s)",
            participant.id,
            event_type,
            str(exc),
        )
        return None

    if message.save:
        queue_websocket_message_event(
            participant=participant,
            page_uuid=page_uuid,
            message=message,
            message_time=receive_time,
            direction=INBOUND,
        )

    return message.handle(
        experiment=experiment,
        participant=participant,
        receive_time=receive_time,
    )


class _Connection:
    def __init__(self, participant_id: int, page_uuid: str, ws):
        self.participant_id = int(participant_id)
        self.page_uuid = page_uuid
        self.ws = ws

    def send_payload(self, payload: str):
        self.ws.send(payload)


class _ConnectionManager:
    # Connections are only known to the web process that accepted them. Redis
    # fanout lets each process inspect outbound envelopes and deliver to its
    # own matching sockets.

    def __init__(self):
        self._connections_by_page_uuid: dict[str, set[_Connection]] = {}
        self._lock = threading.RLock()

    def add(self, participant_id: int, page_uuid: str, ws):
        connection = _Connection(participant_id, page_uuid, ws)
        with self._lock:
            self._connections_by_page_uuid.setdefault(page_uuid, set()).add(connection)
        return connection

    def remove(self, connection: _Connection):
        with self._lock:
            connections = self._connections_by_page_uuid.get(connection.page_uuid)
            if not connections:
                return
            connections.discard(connection)
            if not connections:
                self._connections_by_page_uuid.pop(connection.page_uuid, None)

    def send_to_pages(self, page_uuids: list[str], payload: str):
        stale_connections = []
        with self._lock:
            connections = [
                connection
                for page_uuid in page_uuids
                for connection in self._connections_by_page_uuid.get(page_uuid, set())
            ]

        for connection in connections:
            try:
                connection.send_payload(payload)
            except Exception as exc:  # pragma: no cover - depends on socket runtime
                logger.warning(
                    "Failed to send websocket frame to participant %s: %s",
                    connection.participant_id,
                    exc,
                )
                stale_connections.append(connection)

        for connection in stale_connections:
            self.remove(connection)


connection_manager = _ConnectionManager()
_redis_listener_started = False
_redis_listener_lock = threading.Lock()
_websocket_message_event_drainer_started = False
_websocket_message_event_drainer_lock = threading.Lock()


def _make_outbound_envelope(page_uuids: list[str], payload: str):
    # The envelope is private transport metadata; payload is the serialized
    # browser frame that matching sockets will receive unchanged.
    return {
        "page_uuids": page_uuids,
        "payload": payload,
    }


def _handle_outbound_envelope(envelope):
    page_uuids = envelope["page_uuids"]
    if page_uuids:
        connection_manager.send_to_pages(page_uuids, envelope["payload"])


def _redis_listener_loop():  # pragma: no cover - exercised in live experiments
    pubsub = redis_conn.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(REDIS_OUTBOUND_CHANNEL)
    for item in pubsub.listen():
        if item.get("type") != "message":
            continue
        try:
            raw = item["data"]
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            envelope = json.loads(raw)
            if isinstance(envelope, dict):
                _handle_outbound_envelope(envelope)
        except Exception as exc:
            logger.warning("Failed to process outbound websocket frame: %s", exc)


def start_redis_listener():
    """Start the per-process Redis listener used for outbound WebSocket fanout."""

    global _redis_listener_started
    with _redis_listener_lock:
        if _redis_listener_started:
            return
        thread = threading.Thread(
            target=_redis_listener_loop,
            name="psynet-websocket-redis-listener",
            daemon=True,
        )
        thread.start()
        _redis_listener_started = True


def _websocket_message_event_drainer_loop():  # pragma: no cover - live runtime path
    while True:
        drain_websocket_message_event_queue_once(block=True)
        time.sleep(0)


def start_websocket_message_event_drainer():
    """Start the per-process drainer for saved WebSocket messages."""

    global _websocket_message_event_drainer_started
    with _websocket_message_event_drainer_lock:
        if _websocket_message_event_drainer_started:
            return
        thread = threading.Thread(
            target=_websocket_message_event_drainer_loop,
            name="psynet-websocket-message-event-drainer",
            daemon=True,
        )
        thread.start()
        _websocket_message_event_drainer_started = True


def publish_websocket_event(participants, message: ServerWebSocketMessage):
    """Publish a typed outbound event to one or more participants."""

    if not isinstance(message, ServerWebSocketMessage):
        raise TypeError(
            "Outbound WebSocket events must be ServerWebSocketMessage objects."
        )

    targets = _participant_targets(participants)
    if not targets:
        return

    send_time = datetime.now(timezone.utc)
    page_uuids = [page_uuid for _, page_uuid in targets]
    if message.save:
        enqueue_websocket_message_events(
            _make_websocket_message_event_record(
                participant=participant,
                page_uuid=page_uuid,
                message=message,
                message_time=send_time,
                direction=OUTBOUND,
            )
            for participant, page_uuid in targets
        )

    payload = _json_dumps(make_frame(message))
    envelope = _make_outbound_envelope(page_uuids, payload)
    redis_conn.publish(REDIS_OUTBOUND_CHANNEL, _json_dumps(envelope))


class ParticipantWebSocket:
    """Outbound WebSocket helper bound to one participant."""

    def __init__(self, participant):
        self.participant = participant

    def send(self, message: ServerWebSocketMessage):
        """Send an event to this participant's connected browser sockets."""

        publish_websocket_event(self.participant, message)


class ExperimentWebSocket:
    """Outbound WebSocket helper bound to an experiment instance."""

    def __init__(self, experiment):
        self.experiment = experiment

    def send(self, participants, message: ServerWebSocketMessage):
        """Send an event to one or more participants."""

        publish_websocket_event(participants, message)


def _participant_from_request():
    from flask import request

    from psynet.participant import Participant

    # Participant identity is bound when the socket connects. Individual
    # browser messages do not repeat participant_id or unique_id.
    participant_id = _coerce_participant_id(request.args.get("participant_id"))
    unique_id = request.args.get("unique_id")
    page_uuid = request.args.get("page_uuid")

    query = Participant.query
    if unique_id:
        query = query.filter_by(unique_id=unique_id)
    elif participant_id is not None:
        query = query.filter_by(id=participant_id)
    else:
        return None

    participant = query.one_or_none()
    if participant is None:
        return None

    if participant_id is not None and int(participant.id) != participant_id:
        return None

    if not page_uuid or page_uuid != participant.page_uuid:
        return None

    return participant


def _handle_socket(ws):  # pragma: no cover - exercised in live experiments
    from psynet.experiment import get_experiment

    participant = _participant_from_request()
    if participant is None:
        logger.warning("Rejected websocket connection: unknown participant.")
        return

    experiment = get_experiment()
    start_redis_listener()
    start_websocket_message_event_drainer()
    connection = connection_manager.add(participant.id, participant.page_uuid, ws)

    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            try:
                frame = parse_websocket_frame(raw)
            except ValueError as exc:
                logger.warning(
                    "Rejected websocket message: %s (participant_id=%s)",
                    exc,
                    participant.id,
                )
                continue
            dispatch_websocket_frame(
                experiment,
                participant=participant,
                frame=frame,
                receive_time=datetime.now(timezone.utc),
            )
    finally:
        connection_manager.remove(connection)


def _register_route():
    try:
        from dallinger.experiment import Experiment as DallingerExperiment
        from flask_sock import Sock
    except ImportError as exc:  # pragma: no cover - dependency/runtime specific
        logger.warning("Could not register native PsyNet websocket route: %s", exc)
        return

    sock = Sock()

    @sock.route(WEBSOCKET_ROUTE, bp=DallingerExperiment.experiment_routes)
    def psynet_websocket(ws):
        _handle_socket(ws)


_register_route()

"""Native WebSocket helpers for PsyNet experiments.

The public API is intentionally small:

* JavaScript sends browser events with ``psynet.websocket.send(type, message)``.
* Experiment classes receive them with ``@websocket_handler(type)`` methods.
* Server code sends browser events with ``participant.websocket.send(type, message)``
  or ``experiment.websocket.send(participant_or_participants, type, message)``.

Browser sockets are owned by the web process that accepted the connection.
Outbound server messages are therefore fanned out through Redis so scheduled
tasks and other worker processes can still address connected participants.
"""

from __future__ import annotations

import inspect
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional, Type

from dallinger.db import redis_conn
from pydantic import BaseModel, ConfigDict, ValidationError

from psynet.utils import get_logger

logger = get_logger()

WEBSOCKET_ROUTE = "/psynet/websocket"
REDIS_OUTBOUND_CHANNEL = "psynet:websocket:outbound"
INTERNAL_FRAME_KEYS = {
    "type",
    "message",
    "participant_id",
    "unique_id",
    "page_uuid",
}


class WebSocketMessage(BaseModel):
    """Base class for typed WebSocket message payloads."""

    model_config = ConfigDict(extra="forbid", strict=True)


@dataclass(frozen=True)
class WebSocketHandlerSpec:
    """Description of a direct experiment-level WebSocket handler."""

    event_type: str
    method_name: str
    model: Optional[Type[BaseModel]] = None


def websocket_handler(event_type: str, *, model: Optional[Type[BaseModel]] = None):
    """Decorate an experiment method as a native WebSocket event handler.

    Parameters
    ----------
    event_type
        Event type sent by the browser through ``psynet.websocket.send``.

    model
        Optional Pydantic model used to validate the incoming message payload
        before it is passed to the handler.
    """

    if not isinstance(event_type, str) or not event_type:
        raise ValueError("websocket_handler event_type must be a non-empty string.")

    if model is not None and not issubclass(model, BaseModel):
        raise TypeError("websocket_handler model must be a Pydantic BaseModel class.")

    def decorate(method):
        method._psynet_websocket_handler = WebSocketHandlerSpec(
            event_type=event_type,
            method_name=method.__name__,
            model=model,
        )
        return method

    return decorate


def collect_websocket_handlers(experiment) -> dict[str, WebSocketHandlerSpec]:
    """Collect direct WebSocket handlers declared on an experiment instance."""

    handlers: dict[str, WebSocketHandlerSpec] = {}
    for cls in reversed(experiment.__class__.__mro__):
        for method_name, method in cls.__dict__.items():
            spec = getattr(method, "_psynet_websocket_handler", None)
            if spec is not None:
                handlers[spec.event_type] = WebSocketHandlerSpec(
                    event_type=spec.event_type,
                    method_name=method_name,
                    model=spec.model,
                )
    return handlers


def _json_dumps(data) -> str:
    return json.dumps(data, separators=(",", ":"))


def _normalize_message(message):
    if isinstance(message, BaseModel):
        return message.model_dump(mode="json", exclude_none=True)
    return message


def make_frame(event_type: str, message=None, **extra):
    """Return the JSON-serializable WebSocket frame for an event."""

    if not isinstance(event_type, str) or not event_type:
        raise ValueError("WebSocket event type must be a non-empty string.")

    frame = {"type": event_type, **extra}
    if message is not None:
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


def _participant_id_from_frame(frame: dict):
    participant_id = _coerce_participant_id(frame.get("participant_id"))
    if participant_id is not None:
        return participant_id

    return None


def extract_websocket_event_type(message):
    """Extract the ``type`` field from a raw WebSocket JSON message."""

    frame = parse_websocket_frame(message)
    return _extract_frame_type(frame)


def _extract_websocket_participant_id(message):
    """Extract a participant ID from a raw WebSocket JSON message, if present."""

    try:
        frame = json.loads(message)
    except json.JSONDecodeError:
        return None

    if not isinstance(frame, dict):
        return None
    return _participant_id_from_frame(frame)


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
    try:
        spec = experiment._native_websocket_handlers[event_type]
    except KeyError:
        logger.warning(
            "Rejected websocket event: no handler registered "
            "(participant_id=%s, event_type=%s)",
            getattr(participant, "id", None),
            event_type,
        )
        return None

    if participant is None:
        logger.warning(
            "Rejected websocket event: missing participant (event_type=%s)",
            event_type,
        )
        return None

    page_uuid = frame.get("page_uuid")
    if page_uuid is not None and page_uuid != participant.page_uuid:
        logger.warning(
            "Rejected websocket event: stale page UUID "
            "(participant_id=%s, event_type=%s)",
            participant.id,
            event_type,
        )
        return None

    message = _extract_message(frame)
    if spec.model is not None:
        try:
            message = spec.model.model_validate(message)
        except ValidationError as exc:
            logger.warning(
                "Rejected websocket event: validation failed "
                "(participant_id=%s, event_type=%s, error=%s)",
                participant.id,
                event_type,
                str(exc),
            )
            return None

    return _call_handler(
        getattr(experiment, spec.method_name),
        experiment=experiment,
        participant=participant,
        message=message,
        event=message,
        receive_time=receive_time,
    )


def _call_handler(method: Callable, **context):
    """Call a handler with the subset of context arguments it requests."""

    signature = inspect.signature(method)
    if any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    ):
        return method(**context)

    kwargs = {name: context[name] for name in signature.parameters if name in context}
    return method(**kwargs)


class _Connection:
    def __init__(self, participant_id: int, ws):
        self.participant_id = int(participant_id)
        self.ws = ws

    def send_frame(self, frame: dict):
        self.ws.send(_json_dumps(frame))


class _ConnectionManager:
    def __init__(self):
        self._connections_by_participant: dict[int, set[_Connection]] = {}
        self._lock = threading.RLock()

    def add(self, participant_id: int, ws):
        connection = _Connection(participant_id, ws)
        with self._lock:
            self._connections_by_participant.setdefault(participant_id, set()).add(
                connection
            )
        return connection

    def remove(self, connection: _Connection):
        with self._lock:
            connections = self._connections_by_participant.get(
                connection.participant_id
            )
            if not connections:
                return
            connections.discard(connection)
            if not connections:
                self._connections_by_participant.pop(connection.participant_id, None)

    def send_to_participants(self, participant_ids: list[int], frame: dict):
        stale_connections = []
        with self._lock:
            connections = [
                connection
                for participant_id in participant_ids
                for connection in self._connections_by_participant.get(
                    int(participant_id), set()
                )
            ]

        for connection in connections:
            try:
                connection.send_frame(frame)
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


def _target_participant_ids(frame):
    ids = frame.get("target_participant_ids", [])
    if frame.get("target_participant_id") is not None:
        ids = [*ids, frame["target_participant_id"]]
    return [
        participant_id
        for participant_id in (_coerce_participant_id(value) for value in ids)
        if participant_id is not None
    ]


def _handle_outbound_frame(frame):
    participant_ids = _target_participant_ids(frame)
    if participant_ids:
        connection_manager.send_to_participants(participant_ids, frame)


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
            frame = json.loads(raw)
            if isinstance(frame, dict):
                _handle_outbound_frame(frame)
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


def publish_websocket_event(participant_ids, event_type: str, message=None):
    """Publish an outbound event to one or more participants."""

    if not isinstance(participant_ids, (list, tuple, set)):
        participant_ids = [participant_ids]

    target_participant_ids = [
        int(participant_id)
        for participant_id in participant_ids
        if participant_id is not None
    ]
    if not target_participant_ids:
        return

    frame = make_frame(
        event_type,
        message,
        target_participant_ids=[
            str(participant_id) for participant_id in target_participant_ids
        ],
    )
    redis_conn.publish(REDIS_OUTBOUND_CHANNEL, _json_dumps(frame))


class ParticipantWebSocket:
    """Outbound WebSocket helper bound to one participant."""

    def __init__(self, participant):
        self.participant = participant

    def send(self, event_type: str, message=None):
        """Send an event to this participant's connected browser sockets."""

        publish_websocket_event([self.participant.id], event_type, message)


class ExperimentWebSocket:
    """Outbound WebSocket helper bound to an experiment instance."""

    def __init__(self, experiment):
        self.experiment = experiment

    def send(self, participants, event_type: str, message=None):
        """Send an event to one or more participants."""

        if isinstance(participants, (list, tuple, set)):
            participant_ids = [
                getattr(participant, "id", participant) for participant in participants
            ]
        else:
            participant_ids = [getattr(participants, "id", participants)]
        publish_websocket_event(participant_ids, event_type, message)


def _participant_from_request():
    from flask import request

    from psynet.participant import Participant

    participant_id = _coerce_participant_id(request.args.get("participant_id"))
    unique_id = request.args.get("unique_id")

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

    return participant


def _handle_socket(ws):  # pragma: no cover - exercised in live experiments
    from psynet.experiment import get_experiment

    participant = _participant_from_request()
    if participant is None:
        logger.warning("Rejected websocket connection: unknown participant.")
        return

    start_redis_listener()
    connection = connection_manager.add(participant.id, ws)
    experiment = get_experiment()

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

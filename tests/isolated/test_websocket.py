import json
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Literal, Optional
from unittest.mock import MagicMock

import pytest
from pydantic import Field, ValidationError

from psynet.timeline import NullElt
from psynet.websocket import (
    ClientWebSocketEvent,
    ServerWebSocketEvent,
    ValidatedWebSocketElt,
    WebSocketEventService,
    websocket_handler,
)


class EchoService(WebSocketEventService):
    class EchoEvent(ClientWebSocketEvent):
        """An event used to exercise validated dispatch."""

        type: Literal["echo"]
        value: int = Field(gt=0)

    @websocket_handler(EchoEvent)
    def echo(self, event):
        """Record the event and publish a response."""
        self.participant.handled_value = event.value
        self.participant.handled_receive_time = event.receive_time
        self.publish({"type": "echoed", "value": event.value})
        return event.value


class EnableEcho(NullElt, ValidatedWebSocketElt):
    channel = "echo_channel"
    service_class = EchoService


class ExplodingService(WebSocketEventService):
    class ExplodeEvent(ClientWebSocketEvent):
        type: Literal["explode"]

    @websocket_handler(ExplodeEvent)
    def explode(self, event):
        """Raise a domain error after successful parsing."""
        raise ValueError("handler failure")


class EnableExploding(NullElt, ValidatedWebSocketElt):
    channel = "explode_channel"
    service_class = ExplodingService


def _participant(page_uuid="current-page"):
    return SimpleNamespace(id=7, page_uuid=page_uuid)


def _experiment():
    experiment = MagicMock()
    experiment.publish_to_subscribers = MagicMock()
    return experiment


def test_decorated_service_handler_parses_and_dispatches_event():
    """A decorated service method handles its registered Pydantic event model."""
    service = EchoService(_participant(), _experiment(), "echo_channel")

    assert EchoService.get_rejection_log_label() == "EchoService"

    result = service.dispatch(
        json.dumps({"type": "echo", "page_uuid": "current-page", "value": 3})
    )

    assert result == 3
    assert service.participant.handled_value == 3
    payload = json.loads(service.experiment.publish_to_subscribers.call_args[0][0])
    assert payload == {"type": "echoed", "value": 3}


def test_validated_websocket_elt_uses_configured_service():
    """ValidatedWebSocketElt delegates incoming messages to its service class."""
    participant = _participant()
    experiment = _experiment()

    EnableEcho().handle_message(
        json.dumps({"type": "echo", "page_uuid": "current-page", "value": 5}),
        channel_name="echo_channel",
        participant=participant,
        node=None,
        receive_time=None,
        experiment=experiment,
    )

    assert participant.handled_value == 5
    experiment.publish_to_subscribers.assert_called_once()


def test_client_event_rejects_stale_page_uuid():
    """Client event dispatch rejects messages from stale pages."""
    service = EchoService(_participant(), _experiment(), "echo_channel")

    assert (
        service.dispatch(
            json.dumps({"type": "echo", "page_uuid": "old-page", "value": 1})
        )
        is None
    )

    assert not hasattr(service.participant, "handled_value")
    service.experiment.publish_to_subscribers.assert_not_called()


def test_dispatch_stamps_event_with_receive_time():
    """Dispatch passes server receive time through validated events."""
    receive_time = datetime(2026, 7, 8, 16, 30)
    service = EchoService(
        _participant(),
        _experiment(),
        "echo_channel",
        receive_time=receive_time,
    )
    service.dispatch(
        json.dumps({"type": "echo", "page_uuid": "current-page", "value": 3})
    )

    assert service.participant.handled_receive_time == datetime(
        2026, 7, 8, 16, 30, tzinfo=UTC
    )


def test_invalid_or_unknown_messages_are_rejected():
    """Unknown types and invalid payloads fail before dispatch."""
    with pytest.raises(ValueError):
        EchoService.parse_event(json.dumps({"type": "unknown"}))

    with pytest.raises(ValidationError):
        EchoService.parse_event(
            json.dumps({"type": "echo", "page_uuid": "current-page", "value": 0})
        )

    experiment = _experiment()
    EnableEcho().handle_message(
        "not JSON",
        channel_name="echo_channel",
        participant=_participant(),
        node=None,
        receive_time=None,
        experiment=experiment,
    )
    experiment.publish_to_subscribers.assert_not_called()


def test_handler_value_errors_are_not_swallowed():
    """Handler errors propagate after a message has been validated."""
    with pytest.raises(ValueError, match="handler failure"):
        EnableExploding().handle_message(
            json.dumps({"type": "explode", "page_uuid": "current-page"}),
            channel_name="explode_channel",
            participant=_participant(),
            node=None,
            receive_time=None,
            experiment=_experiment(),
        )


def test_outbound_message_serialization_excludes_none():
    """Outbound message models serialize to compact WebSocket JSON payloads."""

    class DoneMessage(ServerWebSocketEvent):
        type: Literal["done"] = "done"
        answer: Optional[list[str]] = None

    assert json.loads(DoneMessage().to_json()) == {"type": "done"}

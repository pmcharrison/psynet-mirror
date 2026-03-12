import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from dallinger import db
from sqlalchemy.orm.attributes import flag_modified

from psynet.chatroom import ChatMessage, EnableChatrooms
from psynet.experiment import get_experiment
from psynet.participant import Participant
from psynet.pytest_psynet import path_to_test_experiment


def _random_id():
    return str(uuid.uuid4())


def _new_participant(experiment):
    participant = Participant(
        experiment=experiment,
        recruiter_id="hotair",
        worker_id=_random_id(),
        hit_id="XYZ",
        assignment_id=_random_id(),
        mode="debug",
    )
    db.session.add(participant)
    return participant


def _mock_experiment():
    """Return a minimal mock that records publish_to_subscribers calls."""
    exp = MagicMock()
    exp.publish_to_subscribers = MagicMock()
    return exp


def _published_payloads(mock_exp):
    """Return all JSON payloads passed to publish_to_subscribers."""
    return [
        json.loads(call_args[0][0])
        for call_args in mock_exp.publish_to_subscribers.call_args_list
    ]


class TestEnableChatroomsConfig:

    def test_consume_is_noop(self):
        """consume() must exist and return None (transparent timeline element)."""
        handler = EnableChatrooms()
        assert handler.consume(None, None) is None


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_test_experiment("consents")],
    indirect=True,
)
class TestHandleMessage:
    """
    Tests for EnableChatrooms.handle_message()
    """

    @staticmethod
    def _handler_and_exp():
        return EnableChatrooms(), _mock_experiment()

    @staticmethod
    def _send(handler, exp, participant, payload, node=None):
        time = datetime.now(UTC)
        handler.handle_message(
            json.dumps(payload),
            handler.channel,
            participant,
            node,
            time,
            exp,
        )
        return time

    # -- missing room_id --

    def test_message_without_room_id_is_ignored(
        self, in_experiment_directory, db_session
    ):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(handler, exp, participant, {"type": "join_room"})  # no room_id
        db.session.commit()

        exp.publish_to_subscribers.assert_not_called()

    # -- join_room --

    def test_join_room_persists_details(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_A"}
        )
        db.session.commit()
        db.session.expire(participant)

        assert participant.details.get("chatroom_subscribed") is True
        assert participant.details.get("chatroom_room_id") == "room_A"

    def test_leave_room_persists_details(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_B"}
        )
        db.session.commit()

        self._send(
            handler, exp, participant, {"type": "leave_room", "room_id": "room_B"}
        )
        db.session.commit()
        db.session.expire(participant)

        assert participant.details.get("chatroom_subscribed") is False

    def test_join_room_broadcasts_occupancy(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_A"}
        )
        db.session.commit()

        exp.publish_to_subscribers.assert_called_once()
        payload = _published_payloads(exp)[0]
        assert payload["type"] == "occupancy_update"
        assert payload["room_id"] == "room_A"

    def test_rejoin_room_rebroadcasts(self, in_experiment_directory, db_session):
        """Joining a room a second time still broadcasts (so the participant list is refreshed)."""
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_A"}
        )
        db.session.commit()
        exp.publish_to_subscribers.reset_mock()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_A"}
        )
        db.session.commit()

        exp.publish_to_subscribers.assert_called_once()

    # -- leave_room --

    def test_leave_room_clears_subscription(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_B"}
        )
        db.session.commit()
        exp.publish_to_subscribers.reset_mock()

        self._send(
            handler, exp, participant, {"type": "leave_room", "room_id": "room_B"}
        )
        db.session.commit()

        assert participant.details.get("chatroom_subscribed", False) is False

    def test_leave_room_broadcasts_occupancy(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "join_room", "room_id": "room_B"}
        )
        db.session.commit()
        exp.publish_to_subscribers.reset_mock()

        self._send(
            handler, exp, participant, {"type": "leave_room", "room_id": "room_B"}
        )
        db.session.commit()

        exp.publish_to_subscribers.assert_called_once()
        payload = _published_payloads(exp)[0]
        assert payload["type"] == "occupancy_update"
        assert payload["room_id"] == "room_B"

    # -- message --

    def test_message_persisted_to_db(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        send_time = self._send(
            handler,
            exp,
            participant,
            {"type": "message", "room_id": "room_C", "content": "hello"},
        )
        db.session.commit()

        records = ChatMessage.query.filter_by(room_id="room_C").all()
        assert len(records) == 1
        record = records[0]
        assert record.content == "hello"
        assert record.participant_id == participant.id
        assert record.receive_time == send_time

    def test_request_state_sends_history(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        # Pre-seed a message
        db.session.add(
            ChatMessage(
                participant_id=participant.id,
                node_id=None,
                room_id="room_E",
                content="prior message",
                receive_time=datetime.now(UTC),
            )
        )
        db.session.commit()
        exp.publish_to_subscribers.reset_mock()

        self._send(
            handler, exp, participant, {"type": "request_state", "room_id": "room_E"}
        )

        payloads = _published_payloads(exp)
        types = {p["type"] for p in payloads}
        assert "occupancy_update" in types
        assert "history" in types

        history = next(p for p in payloads if p["type"] == "history")
        assert history["room_id"] == "room_E"
        assert history["target_participant_id"] == str(participant.id)
        assert len(history["messages"]) == 1
        assert history["messages"][0]["content"] == "prior message"

    def test_request_state_empty_history(self, in_experiment_directory, db_session):
        handler, exp = self._handler_and_exp()
        experiment = get_experiment()
        participant = _new_participant(experiment)
        db.session.flush()

        self._send(
            handler, exp, participant, {"type": "request_state", "room_id": "room_F"}
        )

        history = next(p for p in _published_payloads(exp) if p["type"] == "history")
        assert history["messages"] == []


@pytest.mark.parametrize(
    "experiment_directory",
    [path_to_test_experiment("consents")],
    indirect=True,
)
class TestOccupantIds:
    def test_returns_subscribed_participants_for_room(
        self, in_experiment_directory, db_session
    ):
        handler = EnableChatrooms()
        experiment = get_experiment()

        p1 = _new_participant(experiment)
        p2 = _new_participant(experiment)
        p3 = _new_participant(experiment)
        db.session.flush()

        p1.details["chatroom_subscribed"] = True
        p1.details["chatroom_room_id"] = "room_X"
        flag_modified(p1, "details")

        p2.details["chatroom_subscribed"] = True
        p2.details["chatroom_room_id"] = "room_Y"  # different room
        flag_modified(p2, "details")

        # p3 is not subscribed
        db.session.commit()

        ids_X = handler._occupant_ids("room_X")
        assert str(p1.id) in ids_X
        assert str(p2.id) not in ids_X
        assert str(p3.id) not in ids_X

        ids_Y = handler._occupant_ids("room_Y")
        assert str(p2.id) in ids_Y
        assert str(p1.id) not in ids_Y

    def test_returns_empty_when_no_subscribers(
        self, in_experiment_directory, db_session
    ):
        handler = EnableChatrooms()
        experiment = get_experiment()
        _new_participant(experiment)
        db.session.flush()
        db.session.commit()

        assert handler._occupant_ids("room_empty") == []

"""Domain logic for the WebSocket rock-paper-scissors demo.

This module keeps the game mechanics separate from the PsyNet timeline in
``experiment.py``. The sections below mirror the architecture:

* constants and scoring define the game rules;
* Pydantic models define the WebSocket wire protocol;
* ``RockPaperScissorsGameService`` performs runtime authorization, persistence,
  and publishing;
* SQLAlchemy models store the authoritative game state and per-round choices.
"""

import random
from dataclasses import dataclass
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

import psynet.experiment
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict
from psynet.modular_page import Control
from psynet.participant import Participant
from psynet.timeline import NullElt, WebSocketElt
from psynet.utils import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# Game constants and scoring
# ---------------------------------------------------------------------------
#
# These definitions are pure game rules. They have no PsyNet, database, or
# websocket dependencies, which makes them safe to reuse from both real-time
# event handling and bot/final-score code.

GROUP_TYPE = "rock_paper_scissors"
CHANNEL = "rock_paper_scissors"
CHOICES = ["rock", "paper", "scissors"]
N_ROUNDS = 5

Choice = Literal["rock", "paper", "scissors"]

# ``SCORING_MATRIX[a][b]`` is the score (win = +1, draw = 0, loss = -1) for a
# player who plays ``a`` against an opponent who plays ``b``. The matrix is
# antisymmetric: ``SCORING_MATRIX[a][b] == -SCORING_MATRIX[b][a]``.
SCORING_MATRIX = {
    "rock": {"rock": 0, "paper": -1, "scissors": 1},
    "paper": {"rock": 1, "paper": 0, "scissors": -1},
    "scissors": {"rock": -1, "paper": 1, "scissors": 0},
}


def score_round(action_self, action_other):
    return SCORING_MATRIX[action_self][action_other]


# ---------------------------------------------------------------------------
# WebSocket wire models
# ---------------------------------------------------------------------------
#
# Pydantic models define the JSON contract at the browser/server boundary.
# They validate untrusted websocket messages before any game state or database
# code runs. Outbound messages use the same style so the browser-facing payload
# remains explicit and easy to inspect.


class PageScopedWebSocketEvent(BaseModel):
    """A websocket event authorized by the current PsyNet page UUID."""

    model_config = ConfigDict(extra="ignore", strict=True)

    page_uuid: str = Field(min_length=1)


class ChooseEvent(PageScopedWebSocketEvent):
    """A participant's committed choice for one websocket game round."""

    type: Literal["choose"]
    room_id: str = Field(min_length=1)
    round: int = Field(ge=1, le=N_ROUNDS)
    action: Choice

    def handle(self, service):
        """Apply this event to the running websocket game."""
        if service.record_choice(self):
            service.broadcast_reveal_if_complete(self)


class RevealEvent(BaseModel):
    """A server-authored snapshot for rendering a completed round."""

    model_config = ConfigDict(extra="forbid", strict=True)

    type: Literal["reveal"] = "reveal"
    target: str
    round: int
    result: str
    scoreboard: str
    status: str
    finished: bool
    answer: Optional[List[str]] = None

    def to_json(self):
        """Serialize the reveal snapshot as a websocket JSON message."""
        return self.model_dump_json(exclude_none=True)


def parse_client_event(message):
    """Parse a raw websocket message into a supported client event."""
    return ChooseEvent.model_validate_json(message)


# ---------------------------------------------------------------------------
# Runtime service layer
# ---------------------------------------------------------------------------
#
# The service is the bridge between validated wire events and persistent game
# state. It knows about the participant, page authorization, SQLAlchemy
# transactions, and websocket publishing. It deliberately keeps those side
# effects out of the Pydantic event models and the SQLAlchemy state methods.


@dataclass(frozen=True)
class RockPaperScissorsGameService:
    """Runtime services available to websocket event handlers."""

    participant: Participant
    experiment: psynet.experiment.Experiment
    channel: str

    def warn_rejected_event(self, reason, event=None):
        """Log a rejected websocket event with participant context."""
        event_type = getattr(event, "type", None)
        logger.warning(
            "Rejected rock-paper-scissors websocket event: %s "
            "(participant_id=%s, event_type=%s)",
            reason,
            getattr(self.participant, "id", None),
            event_type,
        )

    def accepts_event(self, event: PageScopedWebSocketEvent):
        """Return whether an event is authorized for the participant's current page."""
        if event.page_uuid != self.participant.page_uuid:
            self.warn_rejected_event("stale page UUID", event)
            return False
        if isinstance(event, ChooseEvent):
            sync_group_id = getattr(self.participant.sync_group, "id", None)
            if sync_group_id is None:
                self.warn_rejected_event("participant has no sync group", event)
                return False
            if event.room_id != f"rps_room_{sync_group_id}":
                self.warn_rejected_event("wrong room ID", event)
                return False
        return True

    def record_choice(self, event: ChooseEvent):
        """Persist the state snapshot and audit row for a participant choice."""
        from dallinger import db

        game_state = self._get_or_create_game_state(event.room_id)
        rejection_reason = game_state.rejection_reason_for_choice(
            event.round, self.participant.id
        )
        if rejection_reason is not None:
            self.warn_rejected_event(rejection_reason, event)
            return False
        game_state.record_choice(event.round, self.participant.id, event.action)
        db.session.add(game_state)
        db.session.commit()
        return True

    @staticmethod
    def _get_or_create_game_state(room_id):
        game_state = (
            RockPaperScissorsGameState.query.filter_by(room_id=room_id)
            .with_for_update()
            .one_or_none()
        )
        if game_state is None:
            game_state = RockPaperScissorsGameState(room_id=room_id)
        return game_state

    def broadcast_reveal_if_complete(self, event: ChooseEvent):
        """Broadcast the completed round once both participants have chosen."""
        game_state = RockPaperScissorsGameState.query.filter_by(
            room_id=event.room_id
        ).one()
        if not game_state.round_is_complete(event.round):
            return

        this_round = game_state.moves_for_round(event.round)
        pids = sorted(this_round.keys())
        for participant_id in pids:
            snapshot = game_state.reveal_for(participant_id, event.round)
            self.experiment.publish_to_subscribers(
                snapshot.to_json(), channel_name=self.channel
            )


# ---------------------------------------------------------------------------
# PsyNet websocket and control integration
# ---------------------------------------------------------------------------
#
# These classes are the small PsyNet-facing surface of the game module.
# ``EnableRockPaperScissors`` connects validated websocket events to the runtime
# service, while ``RockPaperScissorsControl`` configures the participant-facing
# control and bot fallback. The broader trial/timeline composition remains in
# ``experiment.py``.


class EnableRockPaperScissors(NullElt, WebSocketElt):
    """Timeline element that activates the rock-paper-scissors WebSocket channel.

    Place this directly in the experiment timeline whenever a
    :class:`RockPaperScissorsControl` is used. It is a ``NullElt`` and is
    invisible to participants.
    """

    channel = CHANNEL

    def handle_message(
        self, message, channel_name, participant, node, receive_time, experiment
    ):
        if participant is None:
            logger.warning(
                "Rejected rock-paper-scissors websocket event: missing participant"
            )
            return

        try:
            event = parse_client_event(message)
        except ValidationError as err:
            logger.warning(
                "Rejected rock-paper-scissors websocket event: validation failed "
                "(participant_id=%s, errors=%s)",
                participant.id,
                err.error_count(),
            )
            return
        service = RockPaperScissorsGameService(participant, experiment, self.channel)
        if not service.accepts_event(event):
            return
        event.handle(service)


class RockPaperScissorsControl(Control):
    """Control that renders the rock-paper-scissors board and drives it over a
    WebSocket. The submitted answer is the participant's list of ``n_rounds``
    moves."""

    external_template = "rps-control.html"
    macro = "rps_control"

    def __init__(self, room_id, color, n_rounds=N_ROUNDS, choices=CHOICES):
        # The board advances itself once all rounds are revealed, so we hide the
        # default 'Next' button and submit programmatically from the template.
        super().__init__(show_next_button=False)
        self.room_id = room_id
        self.color = color
        self.n_rounds = n_rounds
        self.choices = choices
        self.channel = EnableRockPaperScissors.channel

    def format_answer(self, raw_answer, **kwargs):
        return raw_answer

    def get_bot_response(self, experiment, bot, page, prompt):
        # Bots cannot use WebSockets, so they simply submit a full set of moves;
        # the authoritative scoring happens server-side in ``score_game``.
        return [random.choice(self.choices) for _ in range(self.n_rounds)]


# ---------------------------------------------------------------------------
# Persistent game state
# ---------------------------------------------------------------------------
#
# SQLAlchemy models are the authoritative database representation of the game.
# ``RockPaperScissorsGameState`` stores mutable aggregate state such as the
# current round, scores, and completion flag. ``RockPaperScissorsMove`` stores
# related per-round choices with a uniqueness constraint so the database also
# enforces "one move per participant per round".


@register_table
class RockPaperScissorsGameState(SQLBase, SQLMixin):
    """Persisted authoritative state for one websocket game room."""

    __tablename__ = "rock_paper_scissors_game_state"
    __table_args__ = (UniqueConstraint("room_id"),)

    room_id = Column(String(128), index=True)
    current_round = Column(Integer)
    scores = Column(PythonDict)
    finished = Column(Boolean)
    moves = relationship(
        lambda: RockPaperScissorsMove,
        back_populates="game_state",
        order_by=lambda: RockPaperScissorsMove.round_number,
    )

    def __init__(self, room_id):
        self.room_id = room_id
        self.current_round = 1
        self.scores = {}
        self.finished = False

    def record_choice(self, round_number: int, participant_id: int, action: Choice):
        """Record a participant choice that has already been validated."""
        rejection_reason = self.rejection_reason_for_choice(
            round_number, participant_id
        )
        if rejection_reason is not None:
            raise ValueError(rejection_reason)

        round_moves = self.moves_for_round(round_number)

        self.moves.append(
            RockPaperScissorsMove(
                room_id=self.room_id,
                round_number=round_number,
                participant_id=participant_id,
                action=action,
            )
        )
        round_moves[participant_id] = action
        if len(round_moves) >= 2:
            self._score_completed_round(round_moves)
        return True

    def rejection_reason_for_choice(self, round_number: int, participant_id: int):
        """Return why a choice would be rejected, or ``None`` if accepted."""
        if self.finished:
            return "game already finished"
        if round_number != self.current_round:
            return (
                f"stale/future round {round_number}; "
                f"current round is {self.current_round}"
            )
        if participant_id in self.moves_for_round(round_number):
            return "participant already moved this round"
        return None

    def round_is_complete(self, round_number: int):
        """Return whether both players have chosen in the given round."""
        return len(self.moves_for_round(round_number)) >= 2

    def _score_completed_round(self, round_moves):
        pids = sorted(round_moves.keys())
        score = score_round(round_moves[pids[0]], round_moves[pids[1]])
        scores = dict(self.scores or {})
        scores.setdefault(pids[0], 0)
        scores.setdefault(pids[1], 0)
        scores[pids[0]] += score
        scores[pids[1]] -= score
        self.scores = scores
        self.finished = self.current_round >= N_ROUNDS
        if not self.finished:
            self.current_round += 1

    def moves_for_round(self, round_number: int):
        """Return submitted moves for a given round."""
        return {
            move.participant_id: move.action
            for move in self.moves
            if move.round_number == round_number
        }

    def score_for(self, participant_id: int):
        """Return a participant's current score."""
        return self.scores.get(participant_id, 0)

    def participant_moves(self, participant_id: int):
        """Return a participant's submitted moves in round order."""
        return [
            move.action for move in self.moves if move.participant_id == participant_id
        ]

    def reveal_for(self, participant_id: int, round_number: int):
        """Return a reveal event from one participant's point of view."""
        round_moves = self.moves_for_round(round_number)
        partner_id = next(pid for pid in round_moves if pid != participant_id)
        delta = score_round(round_moves[participant_id], round_moves[partner_id])
        outcome = (
            "you won the round!"
            if delta > 0
            else "you lost the round."
            if delta < 0
            else "the round was a draw."
        )
        return RevealEvent(
            target=str(participant_id),
            round=round_number + 1,
            result=(
                f"Round {round_number}: you played {round_moves[participant_id]}, "
                f"your partner played {round_moves[partner_id]} — {outcome}"
            ),
            scoreboard=(
                f"Score — you: {self.score_for(participant_id)}, "
                f"partner: {self.score_for(partner_id)}"
            ),
            status=(
                "Game over!"
                if self.finished
                else f"Round {round_number + 1} of {N_ROUNDS}: choose your action."
            ),
            finished=self.finished,
            answer=self.participant_moves(participant_id) if self.finished else None,
        )


@register_table
class RockPaperScissorsMove(SQLBase, SQLMixin):
    """A single move submitted by a participant during one round."""

    __tablename__ = "rock_paper_scissors_move"
    __table_args__ = (
        UniqueConstraint("game_state_id", "round_number", "participant_id"),
    )

    game_state_id = Column(Integer, ForeignKey("rock_paper_scissors_game_state.id"))
    game_state = relationship(
        lambda: RockPaperScissorsGameState, back_populates="moves"
    )
    room_id = Column(String(128), index=True)
    round_number = Column(Integer)
    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    action = Column(String)

    def __init__(self, room_id, round_number, participant_id, action):
        self.room_id = room_id
        self.round_number = round_number
        self.participant_id = participant_id
        self.action = action

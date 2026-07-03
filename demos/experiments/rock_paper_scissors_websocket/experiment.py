"""WebSocket rock-paper-scissors demo.

A minimal real-time rock-paper-scissors experiment. Participants are grouped
into pairs with a :class:`~psynet.sync.SimpleGrouper` and a synchronised trial
maker, then they play five rounds of rock-paper-scissors against each other
inside a single trial. Each round's outcome is revealed to both players the
instant they have both chosen, and a running score is displayed throughout.

The participant-facing interface mirrors ``demos/experiments/rock_paper_scissors``
(a coloured "choose your action" prompt with rock/paper/scissors push buttons),
but the round-by-round coordination is driven entirely over WebSockets rather
than by a page reload per round. The design follows PsyNet's built-in WebSocket
machinery, exactly as the ``ChatRoom`` component does
(see :class:`~psynet.chatroom.EnableChatrooms`):

* :class:`EnableRockPaperScissors` is a :class:`~psynet.timeline.WebSocketElt`
  placed in the timeline. It subscribes the experiment to a Redis channel and
  receives every ``choose`` message. Once both players have submitted a move for
  the current round it scores the round and sends each player a ready-to-render
  snapshot (the result line, scoreboard, and next status) addressed to them.
* :class:`RockPaperScissorsControl` is a :class:`~psynet.modular_page.Control`
  backed by a small custom template that renders the buttons and connects to the
  channel with the same ``ReconnectingWebSocket`` relay (``/chat``) used by the
  chatroom component.

The server is the sole authority for the game state; the browser only sends the
chosen action and drops the server's snapshot text into the page, so there is
almost no game logic in JavaScript. The authoritative live state is persisted in
the ``RockPaperScissorsGameState`` row, while
``RockPaperScissorsMove`` rows provide an auditable action log. The final score
is recomputed from participant submissions inside a :class:`~psynet.sync.GroupBarrier`
on release, so the flow is also fully testable with non-WebSocket bots.
"""

import random
from dataclasses import dataclass
from typing import List, Literal, Optional

from dominate import tags
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

import psynet.experiment
from psynet.bot import BotDriver, advance_past_wait_pages
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict
from psynet.modular_page import Control, ModularPage
from psynet.page import InfoPage
from psynet.participant import Participant
from psynet.sync import GroupBarrier, SimpleGrouper
from psynet.timeline import NullElt, Timeline, WebSocketElt, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.utils import get_logger

logger = get_logger()

GROUP_TYPE = "rock_paper_scissors"
CHANNEL = "rock_paper_scissors"
CHOICES = ["rock", "paper", "scissors"]
N_ROUNDS = 5

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


Choice = Literal["rock", "paper", "scissors"]


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

    def handle(self, context):
        """Apply this event to the running websocket game."""
        if context.record_choice(self):
            context.broadcast_reveal_if_complete(self)


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


def _parse_client_event(message):
    """Parse a raw websocket message into a supported client event."""
    return ChooseEvent.model_validate_json(message)


@dataclass(frozen=True)
class RockPaperScissorsGameContext:
    """Runtime game services available to websocket event handlers."""

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
        rejection_reason = game_state.choice_rejection_reason(
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
        for me, partner in [(pids[0], pids[1]), (pids[1], pids[0])]:
            delta = score_round(this_round[me], this_round[partner])
            outcome = (
                "you won the round!"
                if delta > 0
                else "you lost the round."
                if delta < 0
                else "the round was a draw."
            )
            snapshot = RevealEvent(
                target=str(me),
                round=event.round + 1,
                result=(
                    f"Round {event.round}: you played {this_round[me]}, "
                    f"your partner played {this_round[partner]} — {outcome}"
                ),
                scoreboard=(
                    f"Score — you: {game_state.score_for(me)}, "
                    f"partner: {game_state.score_for(partner)}"
                ),
                status=(
                    "Game over!"
                    if game_state.finished
                    else f"Round {event.round + 1} of {N_ROUNDS}: choose your action."
                ),
                finished=game_state.finished,
                answer=game_state.participant_moves(me)
                if game_state.finished
                else None,
            )
            self.experiment.publish_to_subscribers(
                snapshot.to_json(), channel_name=self.channel
            )


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
        """Record a participant choice in the current round."""
        if self.choice_rejection_reason(round_number, participant_id) is not None:
            return False

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

    def choice_rejection_reason(self, round_number: int, participant_id: int):
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


@register_table
class RockPaperScissorsMove(SQLBase, SQLMixin):
    """A single move submitted by a participant during one round.

    This table is an auditable action log. The real-time source of truth lives
    in ``RockPaperScissorsGameState``.
    """

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
            event = _parse_client_event(message)
        except ValidationError as err:
            logger.warning(
                "Rejected rock-paper-scissors websocket event: validation failed "
                "(participant_id=%s, errors=%s)",
                participant.id,
                err.error_count(),
            )
            return
        context = RockPaperScissorsGameContext(participant, experiment, self.channel)
        if not context.accepts_event(event):
            return
        event.handle(context)


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


class RockPaperScissorsTrialMaker(StaticTrialMaker):
    pass


class RockPaperScissorsTrial(StaticTrial):
    time_estimate = 30

    def show_trial(self, experiment, participant):
        room_id = f"rps_room_{participant.sync_group.id}"
        return join(
            GroupBarrier(
                id_="wait_for_partner",
                group_type=GROUP_TYPE,
                max_wait_time=120,
            ),
            self.play_game(room_id=room_id, color=self.definition["color"]),
            GroupBarrier(
                id_="game_finished",
                group_type=GROUP_TYPE,
                on_release=self.score_game,
                max_wait_time=120,
            ),
        )

    def play_game(self, room_id, color):
        prompt = tags.div()
        with prompt:
            tags.h1("Rock, paper, scissors!")
            tags.p(
                f"Play {N_ROUNDS} rounds against your partner. "
                "Each round is revealed as soon as you have both chosen.",
                style=f"color: {color};",
            )
        return ModularPage(
            "play_game",
            prompt,
            RockPaperScissorsControl(room_id=room_id, color=color),
            time_estimate=30,
            save_answer="rps_moves",
        )

    def score_game(self, participants: List[Participant]):
        assert len(participants) == 2
        players = sorted(participants, key=lambda p: p.id)
        moves = [player.var.rps_moves for player in players]

        totals = [0, 0]
        for round_index in range(len(moves[0])):
            score = score_round(moves[0][round_index], moves[1][round_index])
            totals[0] += score
            totals[1] -= score

        for i, player in enumerate(players):
            j = 1 - i
            player.var.game_result = {
                "my_moves": moves[i],
                "partner_moves": moves[j],
                "my_score": totals[i],
                "partner_score": totals[j],
                "outcome": (
                    "won"
                    if totals[i] > totals[j]
                    else "lost"
                    if totals[i] < totals[j]
                    else "drew"
                ),
            }

    def show_feedback(self, experiment, participant):
        result = participant.var.game_result
        outcome = {
            "won": "You won the match!",
            "lost": "You lost the match.",
            "drew": "The match was a draw.",
        }[result["outcome"]]

        prompt = tags.div()
        with prompt:
            tags.h1("Game over!")
            tags.p(
                f"Final score — you: {result['my_score']}, "
                f"partner: {result['partner_score']}. {outcome}"
            )
            with tags.ol():
                for me, partner in zip(result["my_moves"], result["partner_moves"]):
                    tags.li(f"You played {me}, your partner played {partner}.")

        return InfoPage(prompt, time_estimate=5)


class Exp(psynet.experiment.Experiment):
    label = "Rock paper scissors WebSocket demo"

    timeline = Timeline(
        EnableRockPaperScissors(),
        SimpleGrouper(
            group_type=GROUP_TYPE,
            initial_group_size=2,
            # Allow ample time for a second participant to arrive in the lobby.
            max_wait_time=300,
        ),
        RockPaperScissorsTrialMaker(
            id_="rock_paper_scissors_websocket",
            trial_class=RockPaperScissorsTrial,
            nodes=[
                StaticNode(definition={"color": color})
                for color in ["red", "green", "blue"]
            ],
            expected_trials_per_participant=1,
            max_trials_per_participant=1,
            sync_group_type=GROUP_TYPE,
        ),
        InfoPage("That's the end of the experiment!", time_estimate=5),
    )

    test_n_bots = 2
    test_mode = "serial"

    def test_serial_run_bots(self, bots: List[BotDriver]):
        advance_past_wait_pages(bots)

        # Both players are placed together on the WebSocket game page.
        for bot in bots:
            assert bot.current_page_label == "play_game"

        # Bots submit a full set of moves rather than playing round by round.
        # bots[0] plays rock every round, bots[1] plays scissors, so bots[0]
        # wins all five rounds.
        bots[0].take_page(response=["rock"] * N_ROUNDS)
        bots[1].take_page(response=["scissors"] * N_ROUNDS)

        advance_past_wait_pages(bots)

        assert "Final score — you: 5, partner: -5. You won the match!" in (
            bots[0].current_page_text
        )
        assert "Final score — you: -5, partner: 5. You lost the match." in (
            bots[1].current_page_text
        )

        bots[0].take_page()
        bots[1].take_page()
        advance_past_wait_pages(bots)

        assert "That's the end of the experiment!" in bots[0].current_page_text
        assert "That's the end of the experiment!" in bots[1].current_page_text

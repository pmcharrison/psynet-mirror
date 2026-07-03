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
almost no game logic in JavaScript. Moves are persisted to the
``RockPaperScissorsMove`` table (the raw event log), while the authoritative
overall score is recomputed from the submitted moves inside a
:class:`~psynet.sync.GroupBarrier` on release, so the flow is also fully testable
with non-WebSocket bots.
"""

import random
from dataclasses import dataclass
from typing import List, Literal, Optional

from dominate import tags
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import Column, ForeignKey, Integer, String

import psynet.experiment
from psynet.bot import BotDriver, advance_past_wait_pages
from psynet.data import SQLBase, SQLMixin, register_table
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


class ChooseEvent(BaseModel):
    """A participant's committed choice for one websocket game round."""

    model_config = ConfigDict(extra="ignore", strict=True)

    type: Literal["choose"]
    room_id: str = Field(min_length=1)
    round: int = Field(ge=1, le=N_ROUNDS)
    action: Choice

    def handle(self, context):
        """Apply this event to the running websocket game."""
        if not context.record_choice(self):
            return

        this_round = context.completed_round_moves(self)
        if this_round is not None:
            context.broadcast_reveal(self, this_round)


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
class RockPaperScissorsEventContext:
    """Runtime services available to websocket event handlers."""

    websocket: "EnableRockPaperScissors"
    participant: Optional[Participant]
    experiment: psynet.experiment.Experiment

    def record_choice(self, event: ChooseEvent):
        """Persist a choice unless this participant already moved this round."""
        from dallinger import db

        if self.participant is None:
            return False

        already_moved = RockPaperScissorsMove.query.filter_by(
            room_id=event.room_id,
            round_number=event.round,
            participant_id=self.participant.id,
        ).first()
        if already_moved is not None:
            return False

        db.session.add(
            RockPaperScissorsMove(
                event.room_id, event.round, self.participant.id, event.action
            )
        )
        db.session.commit()
        return True

    @staticmethod
    def completed_round_moves(event: ChooseEvent):
        """Return the round's moves once both participants have chosen."""
        this_round = {
            move.participant_id: move.action
            for move in RockPaperScissorsMove.query.filter_by(
                room_id=event.room_id, round_number=event.round
            ).all()
        }
        return this_round if len(this_round) >= 2 else None

    def broadcast_reveal(self, event: ChooseEvent, this_round):
        """Broadcast the completed round from each participant's point of view."""
        self.websocket._broadcast_reveal(
            self.experiment, event.room_id, event.round, this_round
        )


@register_table
class RockPaperScissorsMove(SQLBase, SQLMixin):
    """A single move submitted by a participant during one round.

    This table is the raw event log and the server-side source of truth used to
    decide when a round is complete and to reveal it in real time.
    """

    __tablename__ = "rock_paper_scissors_move"

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

        try:
            event = _parse_client_event(message)
        except ValidationError:
            return
        event.handle(RockPaperScissorsEventContext(self, participant, experiment))

    def _broadcast_reveal(self, experiment, room_id, round_number, this_round):
        """Send each player a ready-to-render snapshot of the completed round.

        The server owns all game state, so it does the scoring and even builds
        the display strings; the browser just drops them into the page. Each
        snapshot is addressed to one participant (``target``) with their own
        point of view already resolved.
        """
        pids = sorted(this_round.keys())
        totals = self._cumulative_scores(room_id, round_number, pids)
        finished = round_number >= N_ROUNDS
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
                round=round_number + 1,
                result=(
                    f"Round {round_number}: you played {this_round[me]}, "
                    f"your partner played {this_round[partner]} — {outcome}"
                ),
                scoreboard=(f"Score — you: {totals[me]}, partner: {totals[partner]}"),
                status=(
                    "Game over!"
                    if finished
                    else f"Round {round_number + 1} of {N_ROUNDS}: choose your action."
                ),
                finished=finished,
                answer=self._participant_moves(room_id, me) if finished else None,
            )
            experiment.publish_to_subscribers(
                snapshot.to_json(), channel_name=self.channel
            )

    @staticmethod
    def _cumulative_scores(room_id, up_to_round, pids):
        totals = {pids[0]: 0, pids[1]: 0}
        by_round = {}
        for move in RockPaperScissorsMove.query.filter(
            RockPaperScissorsMove.room_id == room_id,
            RockPaperScissorsMove.round_number <= up_to_round,
        ).all():
            by_round.setdefault(move.round_number, {})[move.participant_id] = (
                move.action
            )
        for actions in by_round.values():
            if pids[0] in actions and pids[1] in actions:
                totals[pids[0]] += score_round(actions[pids[0]], actions[pids[1]])
                totals[pids[1]] += score_round(actions[pids[1]], actions[pids[0]])
        return totals

    @staticmethod
    def _participant_moves(room_id, participant_id):
        return [
            move.action
            for move in RockPaperScissorsMove.query.filter_by(
                room_id=room_id, participant_id=participant_id
            )
            .order_by(RockPaperScissorsMove.round_number)
            .all()
        ]


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

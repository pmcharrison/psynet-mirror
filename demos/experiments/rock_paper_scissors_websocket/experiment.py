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
and live-session machinery:

* The experiment defines a direct ``@websocket_handler("choose")`` method that
  receives every browser choice. Once both players have submitted a move for the
  current round it scores the round and stores ready-to-render public snapshots
  in :class:`~psynet.session.LiveSession`.
* :class:`RockPaperScissorsControl` is a :class:`~psynet.modular_page.Control`
  backed by a small custom template that renders the buttons and uses
  ``psynet.websocket`` and ``psynet.session`` for real-time communication
  and refresh/reconnect recovery.

The server is the sole authority for the game state; the browser only sends the
chosen action and drops the server's snapshot text into the page, so there is
almost no game logic in JavaScript. Public recoverable state is persisted in
``LiveSession`` rows, while hidden choices are kept in ``RockPaperScissorsMove``
rows until a round is complete. The final score is recomputed from participant
submissions inside a :class:`~psynet.sync.GroupBarrier` on release, so the flow
is also fully testable with non-WebSocket bots.
"""

import random
from copy import deepcopy
from types import SimpleNamespace
from typing import List, Literal, Optional

from dallinger import db
from dominate import tags
from pydantic import Field, ValidationError
from sqlalchemy import Column, Integer, String, UniqueConstraint

import psynet.experiment
from psynet.bot import BotDriver, advance_past_wait_pages
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.modular_page import ModularPage
from psynet.page import InfoPage
from psynet.participant import Participant
from psynet.session import LiveSession, LiveSessionControl
from psynet.sync import GroupBarrier, SimpleGrouper
from psynet.timeline import Timeline, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.websocket import WebSocketMessage, websocket_handler

GROUP_TYPE = "rock_paper_scissors"
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


def score_match(player_1_moves, player_2_moves):
    """Return total scores for two equal-length move sequences."""
    if len(player_1_moves) != len(player_2_moves):
        raise ValueError("Move sequences must have the same length.")

    player_1_score = 0
    player_2_score = 0
    for player_1_move, player_2_move in zip(player_1_moves, player_2_moves):
        score = score_round(player_1_move, player_2_move)
        player_1_score += score
        player_2_score -= score
    return player_1_score, player_2_score


def room_id_for_sync_group(sync_group_id):
    """Return the websocket room ID for a PsyNet sync group."""
    return f"rps_room_{sync_group_id}"


Choice = Literal["rock", "paper", "scissors"]


class ChooseMessage(WebSocketMessage):
    """A participant's committed choice for one websocket game round."""

    session_id: str = Field(min_length=1)
    round: int = Field(ge=1, le=N_ROUNDS)
    action: Choice


class RevealSnapshot(WebSocketMessage):
    """A participant-specific snapshot for rendering a completed round."""

    target: str
    round: int
    result: str
    scoreboard: str
    status: str
    finished: bool
    answer: Optional[List[str]] = None


def initial_rps_state(participant_ids: list[int]) -> dict:
    """Return the public recoverable state for a new RPS session."""

    ordered_ids = [str(participant_id) for participant_id in sorted(participant_ids)]
    return {
        "current_round": 1,
        "scores": {participant_id: 0 for participant_id in ordered_ids},
        "submitted_participant_ids": [],
        "reveal_history": {participant_id: [] for participant_id in ordered_ids},
        "finished": False,
    }


class RockPaperScissorsSession(LiveSession):
    """Persisted live session for one rock-paper-scissors room."""

    @classmethod
    def build_session_id(cls, participant, group, control):
        """Return the session ID for a rock-paper-scissors sync group."""

        return room_id_for_sync_group(group.id)

    @classmethod
    def build_initial_state(cls, participant_ids, participant, group, control):
        """Return the public recoverable state for a new RPS session."""

        return initial_rps_state(participant_ids)

    @classmethod
    def build_params(cls, participant, group, control):
        """Return browser-facing rock-paper-scissors config."""

        return {
            "color": control.color,
            "n_rounds": control.n_rounds,
            "choices": control.choices,
        }

    def record_choice(self, participant_id: int, message: ChooseMessage):
        """Record a choice and update the public live-session snapshot."""

        participant_id = int(participant_id)
        public_state = deepcopy(self.state or {})
        current_round = int(public_state.get("current_round", 1))
        expected_ids = [int(value) for value in (self.participant_ids or [])]

        if bool(public_state.get("finished")):
            return False
        if message.round != current_round:
            return False
        if participant_id not in expected_ids:
            return False
        if participant_id in moves_for_round(message.session_id, message.round):
            return False

        db.session.add(
            RockPaperScissorsMove(
                room_id=message.session_id,
                round_number=message.round,
                participant_id=participant_id,
                action=message.action,
            )
        )
        db.session.flush()

        round_moves = moves_for_round(message.session_id, message.round)
        submitted = sorted(str(pid) for pid in round_moves)
        public_state["submitted_participant_ids"] = submitted

        if len(round_moves) >= len(expected_ids):
            pids = sorted(round_moves.keys())
            score_1, score_2 = score_match(
                [round_moves[pids[0]]], [round_moves[pids[1]]]
            )
            scores = dict(public_state.get("scores", {}))
            scores.setdefault(str(pids[0]), 0)
            scores.setdefault(str(pids[1]), 0)
            scores[str(pids[0])] += score_1
            scores[str(pids[1])] += score_2
            public_state["scores"] = scores
            public_state["finished"] = message.round >= N_ROUNDS
            public_state["submitted_participant_ids"] = []
            if not public_state["finished"]:
                public_state["current_round"] = message.round + 1

            reveal_history = dict(public_state.get("reveal_history", {}))
            for pid in pids:
                pid_key = str(pid)
                reveal_history.setdefault(pid_key, [])
                reveal = reveal_for(
                    public_state, message.session_id, pid, message.round
                )
                reveal_history[pid_key] = [
                    *reveal_history[pid_key],
                    reveal.model_dump(mode="json", exclude_none=True),
                ]
            public_state["reveal_history"] = reveal_history

        self.state = public_state
        return True


def accepts_choose_message(participant, message: ChooseMessage):
    """Return whether a choice belongs to the participant's current room."""

    sync_group_id = getattr(getattr(participant, "sync_group", None), "id", None)
    return sync_group_id is not None and message.session_id == room_id_for_sync_group(
        sync_group_id
    )


def moves_for_round(room_id: str, round_number: int):
    """Return submitted moves for a given room and round."""

    return {
        move.participant_id: move.action
        for move in RockPaperScissorsMove.query.filter_by(
            room_id=room_id,
            round_number=round_number,
        ).all()
    }


def participant_moves(room_id: str, participant_id: int):
    """Return a participant's submitted moves in round order."""

    return [
        move.action
        for move in RockPaperScissorsMove.query.filter_by(
            room_id=room_id,
            participant_id=participant_id,
        )
        .order_by(RockPaperScissorsMove.round_number)
        .all()
    ]


def reveal_for(
    public_state: dict,
    room_id: str,
    participant_id: int,
    round_number: int,
    *,
    round_moves: dict[int, Choice] | None = None,
    submitted_moves: list[Choice] | None = None,
) -> RevealSnapshot:
    """Return a participant-specific reveal for a completed round."""

    round_moves = round_moves or moves_for_round(room_id, round_number)
    partner_id = next(pid for pid in round_moves if pid != participant_id)
    delta = score_round(round_moves[participant_id], round_moves[partner_id])
    outcome = (
        "you won the round!"
        if delta > 0
        else "you lost the round."
        if delta < 0
        else "the round was a draw."
    )
    scores = public_state.get("scores", {})
    participant_key = str(participant_id)
    partner_key = str(partner_id)
    finished = bool(public_state.get("finished"))
    return RevealSnapshot(
        target=participant_key,
        round=round_number + 1,
        result=(
            f"Round {round_number}: you played {round_moves[participant_id]}, "
            f"your partner played {round_moves[partner_id]} — {outcome}"
        ),
        scoreboard=(
            f"Score — you: {scores.get(participant_key, 0)}, "
            f"partner: {scores.get(partner_key, 0)}"
        ),
        status=(
            "Game over!"
            if finished
            else f"Round {round_number + 1} of {N_ROUNDS}: choose your action."
        ),
        finished=finished,
        answer=(
            submitted_moves
            if submitted_moves is not None
            else participant_moves(room_id, participant_id)
            if finished
            else None
        ),
    )


@register_table
class RockPaperScissorsMove(SQLBase, SQLMixin):
    """A single move submitted by a participant during one round."""

    __tablename__ = "rock_paper_scissors_move"
    __table_args__ = (UniqueConstraint("room_id", "round_number", "participant_id"),)

    room_id = Column(String(128), index=True)
    round_number = Column(Integer)
    participant_id = Column(Integer, index=True)
    action = Column(String)

    def __init__(self, room_id, round_number, participant_id, action):
        self.room_id = room_id
        self.round_number = round_number
        self.participant_id = participant_id
        self.action = action


class RockPaperScissorsControl(LiveSessionControl):
    """Control that renders the rock-paper-scissors board and drives it over a
    WebSocket. The submitted answer is the participant's list of ``n_rounds``
    moves."""

    session_class = RockPaperScissorsSession
    external_template = "rps-control.html"
    macro = "rps_control"

    def __init__(self, participant, color, n_rounds=N_ROUNDS, choices=CHOICES):
        # The board advances itself once all rounds are revealed, so we hide the
        # default 'Next' button and submit programmatically from the template.
        self.color = color
        self.n_rounds = n_rounds
        self.choices = choices
        super().__init__(
            participant=participant,
            group_type=GROUP_TYPE,
            show_next_button=False,
        )

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
        return join(
            GroupBarrier(
                id_="wait_for_partner",
                group_type=GROUP_TYPE,
                max_wait_time=120,
            ),
            self.play_game(participant=participant, color=self.definition["color"]),
            GroupBarrier(
                id_="game_finished",
                group_type=GROUP_TYPE,
                on_release=self.score_game,
                max_wait_time=120,
            ),
        )

    def play_game(self, participant, color):
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
            RockPaperScissorsControl(participant=participant, color=color),
            time_estimate=30,
            save_answer="rps_moves",
        )

    def score_game(self, participants: List[Participant]):
        assert len(participants) == 2
        players = sorted(participants, key=lambda p: p.id)
        moves = [player.var.rps_moves for player in players]
        totals = score_match(moves[0], moves[1])

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

    @websocket_handler("choose", model=ChooseMessage)
    def choose(self, participant, message: ChooseMessage):
        """Handle a browser-submitted rock-paper-scissors choice."""

        if not accepts_choose_message(participant, message):
            return

        live_session = RockPaperScissorsSession.get(message.session_id, for_update=True)
        if live_session is not None and live_session.record_choice(
            participant.id, message
        ):
            live_session.send_snapshot(self)
            if bool((live_session.state or {}).get("finished")):
                live_session.end(self)
            db.session.commit()

    @staticmethod
    def _valid_choose_event():
        return ChooseMessage.model_validate(
            {
                "session_id": room_id_for_sync_group(1),
                "round": 2,
                "action": "paper",
            }
        )

    @staticmethod
    def _assert_payload_rejected(payload):
        try:
            ChooseMessage.model_validate(payload)
        except (ValidationError, ValueError):
            pass
        else:
            raise AssertionError(f"Expected payload to be rejected: {payload}")

    @staticmethod
    def test_websocket_event_parsing():
        """Check websocket event parsing and validation."""
        room_id = room_id_for_sync_group(1)
        event = Exp._valid_choose_event()
        assert event == ChooseMessage(
            session_id=room_id,
            round=2,
            action="paper",
        )

        invalid_payloads = [
            {"round": 1, "action": "rock"},
            {
                "session_id": room_id,
                "round": 1,
                "action": "rock",
                "extra": "unexpected",
            },
            {
                "session_id": "",
                "round": 1,
                "action": "rock",
            },
            {
                "session_id": room_id,
                "round": "1",
                "action": "rock",
            },
            {
                "session_id": room_id,
                "round": 0,
                "action": "rock",
            },
            {
                "session_id": room_id,
                "round": 1,
                "action": "lizard",
            },
        ]
        for payload in invalid_payloads:
            Exp._assert_payload_rejected(payload)

    @staticmethod
    def test_websocket_event_authorization():
        """Check page UUID and room ownership authorization."""
        event = Exp._valid_choose_event()
        participant = SimpleNamespace(
            id=1, page_uuid="current-page", sync_group=SimpleNamespace(id=1)
        )
        assert accepts_choose_message(participant, event)
        assert not accepts_choose_message(
            participant,
            event.model_copy(update={"session_id": room_id_for_sync_group(2)}),
        )

    @staticmethod
    def test_scoring_and_room_helpers():
        """Check shared scoring and room ID helpers."""
        assert room_id_for_sync_group(1) == "rps_room_1"
        assert score_match(["rock", "paper"], ["scissors", "rock"]) == (2, -2)

        try:
            score_match(["rock"], ["scissors", "paper"])
        except ValueError:
            pass
        else:
            raise AssertionError("Expected unequal move sequences to be rejected.")

    @staticmethod
    def test_live_session_initialization():
        """Check the public recoverable live-session shape."""
        state = initial_rps_state([2, 1])
        assert state == {
            "current_round": 1,
            "scores": {"1": 0, "2": 0},
            "submitted_participant_ids": [],
            "reveal_history": {"1": [], "2": []},
            "finished": False,
        }

    @staticmethod
    def test_reveal_serialization():
        """Check outbound reveal serialization."""
        event = RevealSnapshot(
            target="7",
            round=3,
            result="Round 2: you played rock, your partner played scissors - you won!",
            scoreboard="Score - you: 1, partner: -1",
            status="Round 3 of 5: choose your action.",
            finished=False,
        )

        assert event.model_dump(mode="json", exclude_none=True) == {
            "target": "7",
            "round": 3,
            "result": "Round 2: you played rock, your partner played scissors - you won!",
            "scoreboard": "Score - you: 1, partner: -1",
            "status": "Round 3 of 5: choose your action.",
            "finished": False,
        }

    @staticmethod
    def test_reveal_formatting():
        """Check reveal formatting from public LiveSession and hidden move log."""
        room_id = room_id_for_sync_group(1)
        state = initial_rps_state([1, 2])
        state["scores"] = {"1": 1, "2": -1}

        reveal = reveal_for(
            state,
            room_id,
            participant_id=1,
            round_number=1,
            round_moves={1: "rock", 2: "scissors"},
        )

        assert reveal.scoreboard == "Score — you: 1, partner: -1"
        assert reveal.finished is False

    def test_websocket_event_contracts(self):
        """Check websocket event, authorization, state, and reveal contracts."""
        self.test_websocket_event_parsing()
        self.test_websocket_event_authorization()
        self.test_scoring_and_room_helpers()
        self.test_live_session_initialization()
        self.test_reveal_serialization()
        self.test_reveal_formatting()

    def test_serial_run_bots(self, bots: List[BotDriver]):
        self.test_websocket_event_contracts()

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

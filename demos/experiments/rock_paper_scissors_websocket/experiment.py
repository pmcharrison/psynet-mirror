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

import json
import random
from types import SimpleNamespace
from typing import List

from dominate import tags
from pydantic import ValidationError

import psynet.experiment
from psynet.bot import BotDriver, advance_past_wait_pages
from psynet.modular_page import Control, ModularPage
from psynet.page import InfoPage
from psynet.participant import Participant
from psynet.sync import GroupBarrier, SimpleGrouper
from psynet.timeline import NullElt, Timeline, WebSocketElt, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.utils import get_logger

from .game import (
    CHANNEL,
    CHOICES,
    GROUP_TYPE,
    N_ROUNDS,
    ChooseEvent,
    RevealEvent,
    RockPaperScissorsGameService,
    RockPaperScissorsGameState,
    parse_client_event,
    score_round,
)

logger = get_logger()


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

    @staticmethod
    def _valid_choose_event():
        return parse_client_event(
            json.dumps(
                {
                    "type": "choose",
                    "room_id": "rps_room_1",
                    "round": 2,
                    "action": "paper",
                    "page_uuid": "current-page",
                    "sender": "7",
                }
            )
        )

    @staticmethod
    def _assert_payload_rejected(payload):
        try:
            parse_client_event(json.dumps(payload))
        except ValidationError:
            pass
        else:
            raise AssertionError(f"Expected payload to be rejected: {payload}")

    @staticmethod
    def test_websocket_event_parsing():
        """Check websocket event parsing and validation."""
        event = Exp._valid_choose_event()
        assert event == ChooseEvent(
            type="choose",
            room_id="rps_room_1",
            round=2,
            action="paper",
            page_uuid="current-page",
        )

        invalid_payloads = [
            {"type": "reveal", "target": "1"},
            {"type": "choose", "round": 1, "action": "rock"},
            {"type": "choose", "room_id": "rps_room_1", "round": 1, "action": "rock"},
            {
                "type": "choose",
                "room_id": "rps_room_1",
                "round": 1,
                "action": "rock",
                "page_uuid": "",
            },
            {
                "type": "choose",
                "room_id": "",
                "round": 1,
                "action": "rock",
                "page_uuid": "current-page",
            },
            {
                "type": "choose",
                "room_id": "rps_room_1",
                "round": "1",
                "action": "rock",
                "page_uuid": "current-page",
            },
            {
                "type": "choose",
                "room_id": "rps_room_1",
                "round": 0,
                "action": "rock",
                "page_uuid": "current-page",
            },
            {
                "type": "choose",
                "room_id": "rps_room_1",
                "round": 1,
                "action": "lizard",
                "page_uuid": "current-page",
            },
        ]
        for payload in invalid_payloads:
            Exp._assert_payload_rejected(payload)

        try:
            parse_client_event("not JSON")
        except ValidationError:
            pass
        else:
            raise AssertionError("Expected malformed JSON to be rejected.")

    @staticmethod
    def test_websocket_event_authorization():
        """Check page UUID and room ownership authorization."""
        event = Exp._valid_choose_event()
        participant = SimpleNamespace(
            page_uuid="current-page", sync_group=SimpleNamespace(id=1)
        )
        service = RockPaperScissorsGameService(
            participant, SimpleNamespace(), "rock_paper_scissors"
        )
        assert service.accepts_event(event)
        assert not service.accepts_event(
            event.model_copy(update={"page_uuid": "old-page"})
        )
        assert not service.accepts_event(
            event.model_copy(update={"room_id": "rps_room_2"})
        )

    @staticmethod
    def test_game_state_transitions():
        """Check SQLAlchemy game-state transition logic."""
        state = RockPaperScissorsGameState(room_id="rps_room_1")
        assert state.record_choice(1, participant_id=1, action="rock")
        assert (
            state.rejection_reason_for_choice(1, participant_id=1)
            == "participant already moved this round"
        )
        try:
            state.record_choice(1, participant_id=1, action="paper")
        except ValueError:
            pass
        else:
            raise AssertionError("Expected duplicate move to be rejected.")
        assert state.rejection_reason_for_choice(2, participant_id=2) is not None
        assert state.record_choice(1, participant_id=2, action="scissors")
        assert state.current_round == 2
        assert state.score_for(1) == 1
        assert state.score_for(2) == -1
        assert state.participant_moves(1) == ["rock"]
        assert len(state.moves) == 2
        reveal = state.reveal_for(participant_id=1, round_number=1)
        assert reveal.scoreboard == "Score — you: 1, partner: -1"
        assert reveal.finished is False

    @staticmethod
    def test_reveal_serialization():
        """Check outbound reveal serialization."""
        event = RevealEvent(
            target="7",
            round=3,
            result="Round 2: you played rock, your partner played scissors - you won!",
            scoreboard="Score - you: 1, partner: -1",
            status="Round 3 of 5: choose your action.",
            finished=False,
        )

        assert json.loads(event.to_json()) == {
            "type": "reveal",
            "target": "7",
            "round": 3,
            "result": "Round 2: you played rock, your partner played scissors - you won!",
            "scoreboard": "Score - you: 1, partner: -1",
            "status": "Round 3 of 5: choose your action.",
            "finished": False,
        }

    def test_websocket_event_contracts(self):
        """Check websocket event, authorization, state, and reveal contracts."""
        self.test_websocket_event_parsing()
        self.test_websocket_event_authorization()
        self.test_game_state_transitions()
        self.test_reveal_serialization()

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

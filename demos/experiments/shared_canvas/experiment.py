from __future__ import annotations

import json
import math
import os
import random
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from typing import List

from dallinger import db
from dominate import tags
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import Field, ValidationError
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

import psynet.experiment
from psynet.bot import BotDriver, advance_past_wait_pages
from psynet.consent import NoConsent
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.modular_page import Control, ModularPage
from psynet.page import InfoPage, WaitPage
from psynet.participant import Participant
from psynet.session_state import SessionState
from psynet.sync import GroupBarrier, SimpleGrouper
from psynet.timeline import PageMaker, Timeline, join
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.websocket import WebSocketMessage, websocket_handler

GROUP_TYPE = "shared_canvas_group"
CANVAS_SESSION_NAMESPACE = "shared_canvas"
GROUP_SIZE = 2
CANVAS_SIZE = 640
TRIAL_SECONDS = 35
SEND_INTERVAL_MS = 50
DRAW_INTERVAL_MS = 25
PLAYER_RADIUS = 12
COIN_RADIUS = 10
COIN_BONUS = 0.10
COINS_PER_WORLD = 8
N_WORLDS = 3
POSITION_EVENT = "position"
COLLECT_EVENT = "collect"

PLAYER_COLORS = [
    "#1f77b4",
    "#d62728",
    "#2ca02c",
    "#9467bd",
    "#ff7f0e",
    "#17becf",
]


def clamp(value, low, high):
    return max(low, min(high, value))


def generate_world(world_index: int) -> dict:
    seed = 20260706 + world_index * 101
    rng = random.Random(seed)
    margin = 60
    coins = []
    for coin_index in range(COINS_PER_WORLD):
        coins.append(
            {
                "id": f"world-{world_index}-coin-{coin_index + 1}",
                "x": round(rng.uniform(margin, CANVAS_SIZE - margin), 1),
                "y": round(rng.uniform(margin, CANVAS_SIZE - margin), 1),
                "radius": COIN_RADIUS,
            }
        )
    return {
        "world_id": f"world-{world_index}",
        "seed": seed,
        "canvas_size": CANVAS_SIZE,
        "player_radius": PLAYER_RADIUS,
        "coin_radius": COIN_RADIUS,
        "coin_bonus": COIN_BONUS,
        "coins": coins,
    }


WORLD_DEFINITIONS = [generate_world(i + 1) for i in range(N_WORLDS)]


def receive_time_iso(receive_time: datetime):
    return receive_time.isoformat()


@register_table
class CanvasPositionEvent(SQLBase, SQLMixin):
    """Persisted high-frequency position event.

    Position events are recorded for analysis and replay, but they do not mutate
    the authoritative ``SessionState``.
    """

    __tablename__ = "canvas_position_event"

    session_id = Column(String(128), index=True)
    participant_id = Column(Integer, index=True, nullable=True)
    x = Column(Float)
    y = Column(Float)
    vx = Column(Float)
    vy = Column(Float)
    client_time = Column(Float)
    receive_time = Column(DateTime(timezone=True), nullable=False)


@register_table
class CanvasCollectEvent(SQLBase, SQLMixin):
    """Persisted coin-collection attempt."""

    __tablename__ = "canvas_collect_event"

    session_id = Column(String(128), index=True)
    participant_id = Column(Integer, index=True, nullable=True)
    coin_id = Column(String(128), index=True)
    x = Column(Float)
    y = Column(Float)
    client_time = Column(Float)
    accepted = Column(Boolean, nullable=True, index=True)
    rejection_reason = Column(String(128), nullable=True)
    receive_time = Column(DateTime(timezone=True), nullable=False)


def initial_canvas_state(participant_ids: list[int], world: dict) -> dict:
    """Return the initial authoritative canvas state."""

    ordered_ids = [str(p) for p in participant_ids]
    canvas_size = world["canvas_size"]
    players = {}
    for index, participant_id in enumerate(ordered_ids):
        angle = (2 * math.pi * index) / max(1, len(ordered_ids))
        players[participant_id] = {
            "participant_id": participant_id,
            "label": f"Player {index + 1}",
            "color": PLAYER_COLORS[index % len(PLAYER_COLORS)],
            "x": round(canvas_size / 2 + math.cos(angle) * 70, 2),
            "y": round(canvas_size / 2 + math.sin(angle) * 70, 2),
            "vx": 0,
            "vy": 0,
            "client_time": 0,
            "receive_time": None,
        }

    return {
        "params": {
            "participant_ids": ordered_ids,
            "world": deepcopy(world),
            "trial_seconds": TRIAL_SECONDS,
            "send_interval_ms": SEND_INTERVAL_MS,
            "draw_interval_ms": DRAW_INTERVAL_MS,
        },
        "players": players,
        "coins": deepcopy(world["coins"]),
        "collected_coins": [],
        "bonuses": {participant_id: 0.0 for participant_id in ordered_ids},
        "collection_counts": {participant_id: 0 for participant_id in ordered_ids},
    }


def canvas_state_payload(session_state: SessionState) -> dict:
    """Return the canvas-specific snapshot nested inside a generic SessionState."""

    state = session_state.state or {}
    payload = session_state.snapshot_payload()
    payload["state"] = {
        **state,
        "target_participant_ids": [str(p) for p in session_state.participant_ids],
        "session_id": session_state.session_id,
    }
    return payload


def record_collection(
    session_state: SessionState,
    *,
    participant_id: int,
    coin_id: str,
    x: float,
    y: float,
    receive_time,
):
    """Apply a validated collection attempt to authoritative state."""

    state = deepcopy(session_state.state or {})
    participant_id = str(participant_id)
    coin = next((c for c in state.get("coins", []) if c["id"] == coin_id), None)
    if coin is None:
        return False, "already_collected_or_unknown", None

    player = state.get("players", {}).get(participant_id)
    if player is None:
        return False, "unknown_player", None

    distance = math.hypot(float(coin["x"]) - x, float(coin["y"]) - y)
    collect_radius = float(coin.get("radius", COIN_RADIUS)) + PLAYER_RADIUS + 4
    if distance > collect_radius:
        return False, "too_far", None

    state["coins"] = [c for c in state.get("coins", []) if c["id"] != coin_id]
    collected = {
        "coin_id": coin_id,
        "participant_id": participant_id,
        "x": coin["x"],
        "y": coin["y"],
        "bonus": COIN_BONUS,
        "receive_time": receive_time_iso(receive_time),
    }
    state.setdefault("collected_coins", []).append(collected)
    state.setdefault("collection_counts", {}).setdefault(participant_id, 0)
    state["collection_counts"][participant_id] += 1
    state.setdefault("bonuses", {}).setdefault(participant_id, 0.0)
    state["bonuses"][participant_id] = round(
        float(state["bonuses"][participant_id]) + COIN_BONUS,
        2,
    )
    session_state.state = state
    return True, None, collected


def participant_result(session_state: SessionState, participant_id: int) -> dict:
    """Return the final participant result from the authoritative state."""

    state = session_state.state or {}
    participant_id_str = str(participant_id)
    collected_coins = [
        c
        for c in state.get("collected_coins", [])
        if str(c.get("participant_id")) == participant_id_str
    ]
    latest_position = (
        CanvasPositionEvent.query.filter_by(
            session_id=session_state.session_id,
            participant_id=participant_id,
        )
        .order_by(CanvasPositionEvent.id.desc())
        .first()
    )
    final_position = None
    if latest_position is not None:
        final_position = {
            "x": latest_position.x,
            "y": latest_position.y,
            "vx": latest_position.vx,
            "vy": latest_position.vy,
        }
    return {
        "completed_live_canvas": True,
        "participant_id": participant_id,
        "collected_coin_ids": [c["coin_id"] for c in collected_coins],
        "coin_bonus": round(
            float(state.get("bonuses", {}).get(participant_id_str, 0.0)), 2
        ),
        "collection_count": int(
            state.get("collection_counts", {}).get(participant_id_str, 0)
        ),
        "final_position": final_position,
        "world_id": state.get("params", {}).get("world", {}).get("world_id"),
    }


class PositionMessage(WebSocketMessage):
    """High-frequency player position payload."""

    session_id: str = Field(min_length=1)
    label: str | None = None
    color: str | None = None
    x: float = Field(ge=0, le=CANVAS_SIZE)
    y: float = Field(ge=0, le=CANVAS_SIZE)
    vx: float
    vy: float
    client_time: float
    low_latency: bool = True


class CollectMessage(WebSocketMessage):
    """Coin collection attempt payload."""

    session_id: str = Field(min_length=1)
    coin_id: str = Field(min_length=1)
    x: float = Field(ge=0, le=CANVAS_SIZE)
    y: float = Field(ge=0, le=CANVAS_SIZE)
    client_time: float


def position_player_payload(
    participant: Participant, message: PositionMessage, receive_time
):
    """Return a player payload without reading authoritative session state."""

    return {
        "participant_id": str(participant.id),
        "label": message.label,
        "color": message.color,
        "x": round(clamp(message.x, 0, CANVAS_SIZE), 3),
        "y": round(clamp(message.y, 0, CANVAS_SIZE), 3),
        "vx": round(message.vx, 3),
        "vy": round(message.vy, 3),
        "client_time": message.client_time,
        "receive_time": receive_time_iso(receive_time),
    }


def waiting_page(participant: Participant):
    active_barrier = participant.active_barriers.get("canvas_grouper", None)
    if active_barrier:
        waiting = active_barrier.get_waiting_participants()
        content = (
            "Waiting for the shared canvas group. "
            f"{len(waiting)} participant(s) are currently ready."
        )
    else:
        content = "Preparing the shared canvas."
    return WaitPage(content=content, wait_time=2.5)


def instruction_page():
    content = tags.div()
    with content:
        tags.h2("Shared canvas navigation")
        tags.p(
            "You will enter a square canvas with other live participants. "
            "Use the arrow keys to move your avatar."
        )
        tags.p(
            "Your movement has a little inertia: when you release a key, your "
            "avatar slows down smoothly instead of stopping immediately."
        )
        tags.p(
            "Coins are visible to everyone. Move over a coin to collect it. "
            "Each coin you collect adds $0.10 to your bonus."
        )
    return InfoPage(content, time_estimate=20)


def build_session_id(trial, group) -> str:
    return f"shared_canvas:{trial.network.id}:group:{int(group.id)}"


def participant_order(participant: Participant):
    group = participant.active_sync_groups[GROUP_TYPE]
    return sorted(group.participants, key=lambda p: p.id)


def build_bot_answer(bot) -> dict:
    return {
        "completed_live_canvas_browser": True,
        "bot_participant_id": bot.id,
        "note": "PsyNet bot path bypasses browser websocket canvas interaction.",
    }


def build_game_config(trial, participant: Participant) -> dict:
    ordered = participant_order(participant)
    group = participant.active_sync_groups[GROUP_TYPE]
    role_index = [p.id for p in ordered].index(participant.id)
    world = trial.definition["world"]
    session_id = build_session_id(trial, group)
    participant_ids = [p.id for p in ordered]
    SessionState.get_or_create(
        CANVAS_SESSION_NAMESPACE,
        session_id,
        state={
            **initial_canvas_state(participant_ids, world),
            "group_id": int(group.id),
            "network_id": trial.network.id,
            "world_id": world["world_id"],
        },
        participant_ids=participant_ids,
    )
    return {
        "namespace": CANVAS_SESSION_NAMESPACE,
        "session_id": session_id,
        "participant_id": participant.id,
        "role": f"Player {role_index + 1}",
        "world_id": world["world_id"],
        "canvas_size": world["canvas_size"],
        "trial_seconds": TRIAL_SECONDS,
        "send_interval_ms": SEND_INTERVAL_MS,
        "draw_interval_ms": DRAW_INTERVAL_MS,
        "player_radius": PLAYER_RADIUS,
        "coin_radius": world["coin_radius"],
        "coin_bonus": COIN_BONUS,
    }


class SharedCanvasControl(Control):
    """Custom canvas renderer wrapped in PsyNet's modular page API."""

    external_template = "shared_canvas.html"
    macro = "shared_canvas_control"

    def __init__(self, game_config):
        super().__init__(show_next_button=False)
        self.game_config = game_config

    def format_answer(self, raw_answer, **kwargs):
        return raw_answer

    def get_bot_response(self, experiment, bot, page, prompt):
        return build_bot_answer(bot)


class SharedCanvasTrial(StaticTrial):
    time_estimate = TRIAL_SECONDS + 35

    def show_trial(self, experiment, participant):
        return join(
            instruction_page(),
            GroupBarrier(
                id_="canvas_start",
                group_type=GROUP_TYPE,
                max_wait_time=90,
            ),
            self.play_canvas(participant),
            GroupBarrier(
                id_="canvas_finished",
                group_type=GROUP_TYPE,
                on_release=self.score_canvas_game,
                max_wait_time=90,
            ),
        )

    def play_canvas(self, participant):
        prompt = tags.div()
        with prompt:
            tags.p(
                "Use the arrow keys to move. Collect the gold coins before the "
                "session ends."
            )
        return ModularPage(
            "shared_canvas",
            prompt,
            SharedCanvasControl(build_game_config(self, participant)),
            save_answer="shared_canvas_browser_answer",
            time_estimate=TRIAL_SECONDS + 5,
        )

    def score_canvas_game(self, participants: List[Participant]):
        group = participants[0].active_sync_groups[GROUP_TYPE]
        ordered = sorted(participants, key=lambda p: p.id)
        world = self.definition["world"]
        session_state = SessionState.get_or_create(
            CANVAS_SESSION_NAMESPACE,
            build_session_id(self, group),
            state={
                **initial_canvas_state([p.id for p in ordered], world),
                "group_id": int(group.id),
                "network_id": self.network.id,
                "world_id": world["world_id"],
            },
            participant_ids=[p.id for p in ordered],
        )
        for participant in participants:
            participant.var.shared_canvas_result = participant_result(
                session_state, participant.id
            )

    def format_answer(self, raw_answer, **kwargs):
        participant = kwargs.get("participant", self.participant)
        if participant is not None:
            try:
                result = participant.var.shared_canvas_result
            except AttributeError:
                result = None
            if isinstance(result, dict):
                return result
        return {
            "completed_live_canvas": False,
            "world_id": self.definition["world"]["world_id"],
            "coin_bonus": 0.0,
            "raw_answer": raw_answer,
        }

    def score_answer(self, answer, definition):
        if isinstance(answer, dict):
            return int(round(float(answer.get("coin_bonus", 0.0)) / COIN_BONUS))
        return 0

    def compute_performance_reward(self, score):
        return max(0.0, score * COIN_BONUS)

    def show_feedback(self, experiment, participant):
        try:
            answer = participant.var.shared_canvas_result
        except AttributeError:
            answer = self.answer if isinstance(self.answer, dict) else {}
        bonus = float(answer.get("coin_bonus", 0.0))
        content = tags.div()
        with content:
            tags.h2("Navigation complete")
            tags.p(f"Your coin bonus is ${bonus:.2f}.")
            tags.p("Thank you for exploring the shared canvas.")
        return InfoPage(content, time_estimate=5)


class WorldNode(StaticNode):
    def create_definition_from_seed(self, seed, experiment, participant):
        return self.definition


class Exp(psynet.experiment.Experiment):
    label = "Real-time shared canvas navigation"
    variables_initial_values = {
        "group_size": GROUP_SIZE,
        "canvas_size": CANVAS_SIZE,
        "trial_seconds": TRIAL_SECONDS,
        "send_interval_ms": SEND_INTERVAL_MS,
        "draw_interval_ms": DRAW_INTERVAL_MS,
        "coin_bonus": COIN_BONUS,
        "soft_max_experiment_payment": 1000.0,
        "hard_max_experiment_payment": 1100.0,
        "max_participant_payment": 25.0,
        "soft_max_experiment_payment_email_sent": False,
        "hard_max_experiment_payment_email_sent": False,
    }

    timeline = Timeline(
        NoConsent(),
        SimpleGrouper(
            group_type=GROUP_TYPE,
            initial_group_size=GROUP_SIZE,
            batch_size=GROUP_SIZE,
            waiting_logic=PageMaker(waiting_page, time_estimate=5),
            max_wait_time=180,
        ),
        StaticTrialMaker(
            id_="shared_canvas_worlds",
            trial_class=SharedCanvasTrial,
            nodes=[
                WorldNode(definition={"world": world}) for world in WORLD_DEFINITIONS
            ],
            expected_trials_per_participant=1,
            max_trials_per_participant=1,
            sync_group_type=GROUP_TYPE,
            check_performance_at_end=False,
        ),
    )

    test_n_bots = 4
    test_mode = "serial"

    @websocket_handler(POSITION_EVENT, model=PositionMessage)
    def position(self, participant, message: PositionMessage, receive_time):
        """Persist and broadcast a high-frequency position event."""

        target_participant_ids = [p.id for p in participant_order(participant)]
        if int(participant.id) not in [int(p) for p in target_participant_ids]:
            return

        logged_event = CanvasPositionEvent(
            session_id=message.session_id,
            participant_id=participant.id,
            x=message.x,
            y=message.y,
            vx=message.vx,
            vy=message.vy,
            client_time=message.client_time,
            receive_time=receive_time,
        )
        db.session.add(logged_event)
        db.session.flush()
        self.websocket.send(
            target_participant_ids,
            "position_update",
            {
                "event_id": logged_event.id,
                "player": position_player_payload(participant, message, receive_time),
            },
        )
        db.session.commit()

    @websocket_handler(COLLECT_EVENT, model=CollectMessage)
    def collect(self, participant, message: CollectMessage, receive_time):
        """Apply a coin collection attempt to authoritative state."""

        session_state = SessionState.get(
            CANVAS_SESSION_NAMESPACE, message.session_id, for_update=True
        )
        if session_state is None or int(participant.id) not in [
            int(p) for p in session_state.participant_ids
        ]:
            return

        accepted, reason, collection = record_collection(
            session_state,
            participant_id=participant.id,
            coin_id=message.coin_id,
            x=message.x,
            y=message.y,
            receive_time=receive_time,
        )
        db.session.add(
            CanvasCollectEvent(
                session_id=message.session_id,
                participant_id=participant.id,
                coin_id=message.coin_id,
                x=message.x,
                y=message.y,
                client_time=message.client_time,
                accepted=accepted,
                rejection_reason=reason,
                receive_time=receive_time,
            )
        )
        if accepted:
            state = session_state.state or {}
            self.websocket.send(
                session_state.participant_ids,
                "coin_collected",
                {
                    "collection": collection,
                    "coins": state.get("coins", []),
                    "bonuses": state.get("bonuses", {}),
                },
            )
        else:
            self.websocket.send(
                participant,
                "collect_rejected",
                {
                    "coin_id": message.coin_id,
                    "reason": reason,
                },
            )
        db.session.commit()

    @staticmethod
    def _valid_position_event():
        return PositionMessage.model_validate(
            {
                "session_id": "test-session",
                "x": 12.5,
                "y": 13.5,
                "vx": 1.0,
                "vy": -1.0,
                "client_time": 100.0,
            }
        )

    @staticmethod
    def _assert_payload_rejected(payload):
        try:
            PositionMessage.model_validate(payload)
        except (ValidationError, ValueError):
            pass
        else:
            raise AssertionError(f"Expected payload to be rejected: {payload}")

    @staticmethod
    def test_websocket_event_parsing():
        event = Exp._valid_position_event()
        assert event.session_id == "test-session"
        invalid_payloads = [
            {"type": POSITION_EVENT, "session_id": "test-session", "x": 1.0},
            {
                "session_id": "test-session",
                "x": 1.0,
                "vx": 0.0,
                "vy": 0.0,
                "client_time": 1.0,
            },
            {"type": "unknown", "page_uuid": "current-page"},
        ]
        for payload in invalid_payloads:
            Exp._assert_payload_rejected(payload)

        try:
            CollectMessage.model_validate(
                {
                    "session_id": "test-session",
                    "coin_id": "",
                    "x": 1.0,
                    "y": 1.0,
                    "client_time": 1.0,
                }
            )
        except ValidationError:
            pass
        else:
            raise AssertionError("Expected empty coin ID to be rejected.")

    @staticmethod
    def test_canvas_state_transitions():
        world = generate_world(99)
        state = SessionState(
            namespace=CANVAS_SESSION_NAMESPACE,
            session_id="state-transition-test",
            participant_ids=[1],
            state={
                **initial_canvas_state([1], world),
                "group_id": 1,
                "network_id": 1,
                "world_id": world["world_id"],
            },
        )
        coin = state.state["coins"][0]
        event = CollectMessage(
            session_id=state.session_id,
            coin_id=coin["id"],
            x=coin["x"],
            y=coin["y"],
            client_time=1.0,
        )
        receive_time = datetime.now()

        accepted, reason, collection = record_collection(
            state,
            participant_id=1,
            coin_id=event.coin_id,
            x=event.x,
            y=event.y,
            receive_time=receive_time,
        )

        assert accepted is True
        assert reason is None
        assert collection["coin_id"] == coin["id"]
        assert coin["id"] not in [c["id"] for c in state.state["coins"]]
        assert participant_result(state, 1)["coin_bonus"] == COIN_BONUS

        accepted, reason, _ = record_collection(
            state,
            participant_id=1,
            coin_id=event.coin_id,
            x=event.x,
            y=event.y,
            receive_time=receive_time,
        )
        assert accepted is False
        assert reason == "already_collected_or_unknown"

    @staticmethod
    def test_position_event_bypasses_session_state():
        event = Exp._valid_position_event()
        player = position_player_payload(
            SimpleNamespace(id=1),
            event,
            datetime.now(),
        )
        assert player["participant_id"] == "1"
        assert player["x"] == event.x
        assert player["y"] == event.y

    @staticmethod
    def test_server_event_serialization():
        event = {
            "coin_id": "coin-1",
            "reason": "too_far",
        }
        assert json.loads(json.dumps(event)) == {
            "coin_id": "coin-1",
            "reason": "too_far",
        }

    @staticmethod
    def test_canvas_template_config_initialization():
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html"]),
        )
        template = env.get_template("shared_canvas.html")
        config = {
            "namespace": CANVAS_SESSION_NAMESPACE,
            "session_id": "shared_canvas:1:group:1",
            "participant_id": 1,
            "role": "Player 1",
            "world_id": WORLD_DEFINITIONS[0]["world_id"],
            "canvas_size": CANVAS_SIZE,
            "trial_seconds": TRIAL_SECONDS,
            "send_interval_ms": SEND_INTERVAL_MS,
            "draw_interval_ms": DRAW_INTERVAL_MS,
            "player_radius": PLAYER_RADIUS,
            "coin_radius": COIN_RADIUS,
            "coin_bonus": COIN_BONUS,
        }
        html = template.module.shared_canvas_control(
            SimpleNamespace(game_config=config)
        )
        config_line = next(
            line.strip()
            for line in html.splitlines()
            if line.strip().startswith("var cfg =")
        )
        assert config_line.startswith("var cfg = {")
        assert "&#" not in config_line
        assert '"namespace": "shared_canvas"' in config_line
        assert 'tabindex="0"' in html
        assert 'aria-label="Shared canvas arrow-key navigation area"' in html
        assert 'window.addEventListener("keydown", handleArrowKeyDown, true);' in html
        assert 'window.addEventListener("keyup", handleArrowKeyUp, true);' in html
        assert 'canvas.addEventListener("click", focusCanvas);' in html
        assert "psynet.session_state.init" in html
        assert "function wsSend" not in html
        assert 'psynet.websocket.send("position"' in html
        assert "if (!wasPressed) {" in html

    def test_canvas_websocket_contracts(self):
        self.test_websocket_event_parsing()
        self.test_canvas_state_transitions()
        self.test_position_event_bypasses_session_state()
        self.test_server_event_serialization()
        self.test_canvas_template_config_initialization()

    def test_serial_run_bots(self, bots: List[BotDriver]):
        self.test_canvas_websocket_contracts()

        advance_past_wait_pages(bots)

        for bot in bots:
            assert "Shared canvas navigation" in bot.current_page_text
            assert "Each coin you collect adds $0.10" in bot.current_page_text
            bot.take_page()

        advance_past_wait_pages(bots)

        for bot in bots:
            assert bot.current_page_label == "shared_canvas"
            bot.take_page(response=build_bot_answer(bot))

        advance_past_wait_pages(bots)

        answers_by_group = {}
        for bot in bots:
            assert "Navigation complete" in bot.current_page_text
            answer = bot.current_trial.answer
            assert isinstance(answer, dict)
            assert answer["completed_live_canvas"] is True
            assert answer["coin_bonus"] == 0.0
            assert answer["collected_coin_ids"] == []
            assert answer["participant_id"] == bot.id
            participant = Participant.query.get(bot.id)
            group_id = int(participant.active_sync_groups[GROUP_TYPE].id)
            answers_by_group.setdefault(group_id, []).append(answer)

        assert len(answers_by_group) == len(bots) // GROUP_SIZE
        assert all(
            len(group_answers) == GROUP_SIZE
            for group_answers in answers_by_group.values()
        )

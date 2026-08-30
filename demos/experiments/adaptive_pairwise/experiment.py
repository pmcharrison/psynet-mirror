"""Adaptive 2AFC comparisons backed by asynchronous study-model snapshots.

Participants compare pairs from a 100-item manifest. A bootstrap
Bradley--Terry model is deliberately expensive to fit, so a scheduled task
publishes immutable snapshots while participant-facing selection reads only the
newest ready snapshot.
"""

# pylint: disable=unused-argument,abstract-method

from __future__ import annotations

import csv
import hashlib
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
from dallinger import db
from dominate import tags
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import deferred, relationship

import psynet.experiment
from psynet.bot import Bot
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.experiment import scheduled_task
from psynet.field import PythonDict, PythonObject
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage
from psynet.process import WorkerAsyncProcess
from psynet.timeline import Timeline
from psynet.trial.main import Selection, Trial
from psynet.trial.static import StaticNode, StaticTrial, StaticTrialMaker
from psynet.utils import get_logger

if __package__:
    from .adaptive_logic import (
        DEFAULT_BOOTSTRAP_REPLICATES,
        MODEL_VERSION,
        OPTIMIZER_VERSION,
        candidate_pairs,
        fit_model,
        prior_state,
        select_pair,
    )
    from .response_model import MISSPECIFIED, sample_choices
else:
    from adaptive_logic import (
        DEFAULT_BOOTSTRAP_REPLICATES,
        MODEL_VERSION,
        OPTIMIZER_VERSION,
        candidate_pairs,
        fit_model,
        prior_state,
        select_pair,
    )
    from response_model import MISSPECIFIED, sample_choices

logger = get_logger("adaptive_pairwise")
ROOT = Path(__file__).parent
ITEM_BANK_PATH = ROOT / "stimuli" / "item_bank.csv"
CANDIDATE_POOL_VERSION = hashlib.sha256(ITEM_BANK_PATH.read_bytes()).hexdigest()[:16]
N_TRIALS_PER_PARTICIPANT = 20
REFIT_MIN_NEW_OBSERVATIONS = 5


def load_items() -> list[dict]:
    """Load and validate the committed 100-item stimulus manifest."""

    with ITEM_BANK_PATH.open(newline="") as file:
        items = list(csv.DictReader(file))
    if len(items) != 100:
        raise ValueError(f"Expected 100 stimuli, found {len(items)}.")
    if len({item["item_id"] for item in items}) != len(items):
        raise ValueError("Stimulus IDs must be unique.")
    return items


ITEMS = load_items()
ITEM_BY_ID = {item["item_id"]: item for item in ITEMS}
PAIR_DEFINITIONS = candidate_pairs([item["item_id"] for item in ITEMS])
ALL_PAIR_IDS = [pair_id for pair_id, _, _ in PAIR_DEFINITIONS]
SIMULATION_RANKS = np.asarray([float(item["simulation_rank"]) for item in ITEMS])
SIMULATION_UTILITIES = (SIMULATION_RANKS - SIMULATION_RANKS.mean()) / (
    SIMULATION_RANKS.std()
)
SIMULATION_UTILITY_BY_ID = dict(
    zip([item["item_id"] for item in ITEMS], SIMULATION_UTILITIES)
)


def get_nodes() -> list[StaticNode]:
    """Create nodes for the balanced 500-pair comparison graph."""

    return [
        StaticNode(
            definition={
                "pair_id": pair_id,
                "item_a_id": item_a_id,
                "item_b_id": item_b_id,
            }
        )
        for pair_id, item_a_id, item_b_id in PAIR_DEFINITIONS
    ]


@register_table
class StudyModelSnapshot(SQLBase, SQLMixin):
    """Immutable published state for participant-facing pair selection."""

    __tablename__ = "adaptive_pairwise_model_snapshot"

    status = Column(String, index=True)
    model_version = Column(String)
    data_version = Column(Integer, unique=True, index=True)
    observation_count = Column(Integer)
    observation_fingerprint = Column(String)
    state = deferred(Column(PythonObject, nullable=True))
    diagnostics = Column(PythonDict)
    random_seed = Column(Integer, nullable=True)
    error = Column(String, nullable=True)


@register_table
class AdaptiveDecision(SQLBase, SQLMixin):
    """Audit record connecting one assignment to the snapshot that selected it."""

    __tablename__ = "adaptive_pairwise_decision"

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    trial_id = Column(Integer, ForeignKey("info.id"), unique=True, index=True)
    study_fit_id = Column(
        Integer,
        ForeignKey("adaptive_pairwise_model_snapshot.id"),
        index=True,
    )
    selected_candidate_id = Column(String)
    participant_history_count = Column(Integer)
    candidate_pool_version = Column(String)
    selected_utility = Column(Float)
    details = Column(PythonDict)
    trial = relationship(Trial, foreign_keys=[trial_id])


def _latest_ready_snapshot() -> StudyModelSnapshot | None:
    return (
        StudyModelSnapshot.query.filter_by(status="ready")
        .order_by(StudyModelSnapshot.data_version.desc())
        .first()
    )


def _ensure_prior_snapshot() -> StudyModelSnapshot:
    """Publish the cheap zero-data prior if no ready snapshot exists."""

    snapshot = _latest_ready_snapshot()
    if snapshot is not None:
        return snapshot
    try:
        snapshot = StudyModelSnapshot(
            status="ready",
            model_version=MODEL_VERSION,
            data_version=0,
            observation_count=0,
            observation_fingerprint=hashlib.sha256(b"").hexdigest(),
            state=prior_state([item["item_id"] for item in ITEMS]),
            diagnostics={
                "data_loading_seconds": 0.0,
                "fit_seconds": 0.0,
                "bootstrap_replicates": 0,
            },
            random_seed=20260830,
        )
        db.session.add(snapshot)
        db.session.commit()
        return snapshot
    except IntegrityError:
        db.session.rollback()
        snapshot = _latest_ready_snapshot()
        if snapshot is None:
            raise RuntimeError("Failed to initialize the prior model snapshot.")
        return snapshot


def _finalized_observations() -> tuple[list[dict], float]:
    started = time.perf_counter()
    trials = (
        AdaptivePairwiseTrial.query.filter_by(
            finalized=True,
            failed=False,
            is_repeat_trial=False,
        )
        .order_by(AdaptivePairwiseTrial.id)
        .all()
    )
    observations = [
        {
            "trial_id": trial.id,
            "left_item_id": trial.adaptive_left_item_id,
            "right_item_id": trial.adaptive_right_item_id,
            "chosen_left": trial.adaptive_chosen_left,
        }
        for trial in trials
    ]
    return observations, time.perf_counter() - started


def _claim_model_snapshot() -> tuple[int, list[dict], float] | None:
    """Claim the current finalized-data version for one model worker."""

    if StudyModelSnapshot.query.filter_by(status="building").first() is not None:
        return None
    previous = _ensure_prior_snapshot()
    observations, loading_seconds = _finalized_observations()
    data_version = len(observations)
    if data_version - previous.observation_count < REFIT_MIN_NEW_OBSERVATIONS:
        return None

    fingerprint = hashlib.sha256(
        ",".join(str(row["trial_id"]) for row in observations).encode()
    ).hexdigest()
    seed = 20260830 + data_version
    building = StudyModelSnapshot(
        status="building",
        model_version=MODEL_VERSION,
        data_version=data_version,
        observation_count=data_version,
        observation_fingerprint=fingerprint,
        diagnostics={"data_loading_seconds": loading_seconds},
        random_seed=seed,
    )
    try:
        db.session.add(building)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None
    return building.id, observations, loading_seconds


def _fit_claimed_snapshot(
    snapshot_id: int,
    observations: list[dict],
    loading_seconds: float,
    bootstrap_replicates: int | None = None,
) -> int | None:
    """Fit a claimed data version and atomically publish its snapshot."""

    seed = 20260830 + len(observations)
    db.session.remove()
    try:
        fit = fit_model(
            left_item_ids=np.asarray([row["left_item_id"] for row in observations]),
            right_item_ids=np.asarray([row["right_item_id"] for row in observations]),
            chosen_left=np.asarray([row["chosen_left"] for row in observations]),
            item_ids=[item["item_id"] for item in ITEMS],
            rng=np.random.default_rng(seed),
            bootstrap_replicates=(
                bootstrap_replicates
                if bootstrap_replicates is not None
                else int(
                    os.environ.get(
                        "ADAPTIVE_BOOTSTRAP_REPLICATES",
                        DEFAULT_BOOTSTRAP_REPLICATES,
                    )
                )
            ),
        )
    except Exception as error:
        snapshot = db.session.get(StudyModelSnapshot, snapshot_id)
        snapshot.status = "failed"
        snapshot.error = str(error)
        db.session.commit()
        logger.warning("Adaptive model refresh %s failed: %s", snapshot_id, error)
        return None

    snapshot = db.session.get(StudyModelSnapshot, snapshot_id)
    snapshot.state = fit.state
    snapshot.diagnostics = {
        **fit.diagnostics,
        "data_loading_seconds": loading_seconds,
    }
    snapshot.status = "ready"
    db.session.commit()
    logger.info(
        "Published adaptive model snapshot %s from %s observations in %.3f s.",
        snapshot.id,
        len(observations),
        fit.diagnostics["fit_seconds"],
    )
    return snapshot.id


def refresh_model_snapshot(bootstrap_replicates: int | None = None) -> int | None:
    """Synchronously claim, fit, and publish the current data version."""

    claim = _claim_model_snapshot()
    if claim is None:
        return None
    snapshot_id, observations, loading_seconds = claim
    return _fit_claimed_snapshot(
        snapshot_id,
        observations,
        loading_seconds,
        bootstrap_replicates,
    )


class AdaptivePairwiseTrial(StaticTrial):
    """One 2AFC comparison selected from the 100-item candidate bank."""

    time_estimate = 4

    adaptive_pair_id = Column(String, index=True)
    adaptive_item_a_id = Column(String)
    adaptive_item_b_id = Column(String)
    adaptive_left_item_id = Column(String)
    adaptive_right_item_id = Column(String)
    adaptive_chosen_left = Column(Boolean, nullable=True)
    adaptive_snapshot_id = Column(Integer, nullable=True, index=True)

    def finalize_definition(self, definition, experiment, participant):
        position_seed = 100_000 * participant.id + self.node.id
        if np.random.default_rng(position_seed).random() < 0.5:
            left_id, right_id = definition["item_a_id"], definition["item_b_id"]
        else:
            left_id, right_id = definition["item_b_id"], definition["item_a_id"]
        return {
            **definition,
            "left_item_id": left_id,
            "right_item_id": right_id,
        }

    @staticmethod
    def _item_card(item_id: str):
        item = ITEM_BY_ID[item_id]
        return tags.div(
            tags.div(
                style=(
                    "height: 90px; border-radius: 8px; "
                    f"background: hsl({item['hue']} 65% 70%);"
                )
            ),
            tags.h4(item["label"], style="margin-top: 12px;"),
            style="width: 240px; padding: 16px; border: 1px solid #bbb;",
        )

    def show_trial(self, experiment, participant):
        prompt = tags.div(
            tags.h3("Which item do you prefer?"),
            tags.div(
                self._item_card(self.definition["left_item_id"]),
                self._item_card(self.definition["right_item_id"]),
                style=(
                    "display: flex; justify-content: center; gap: 32px; margin: 24px 0;"
                ),
            ),
        )
        return ModularPage(
            "adaptive_pairwise_choice",
            prompt,
            PushButtonControl(
                choices=["Left item", "Right item"],
                arrange_vertically=False,
                bot_response=self.get_bot_response,
            ),
            time_estimate=self.time_estimate,
        )

    def get_bot_response(self, bot: Bot) -> str:
        left_id = self.definition["left_item_id"]
        right_id = self.definition["right_item_id"]
        chosen_left = sample_choices(
            left_utilities=np.asarray([SIMULATION_UTILITY_BY_ID[left_id]]),
            right_utilities=np.asarray([SIMULATION_UTILITY_BY_ID[right_id]]),
            parameters=MISSPECIFIED,
            rng=np.random.default_rng(10_000 * bot.id + self.id),
        )[0]
        return "Left item" if chosen_left else "Right item"


class AdaptivePairwiseTrialMaker(StaticTrialMaker):
    """Select comparisons from cached snapshots and persist decision provenance."""

    def select_node(self, nodes, participant, experiment):
        snapshot = _ensure_prior_snapshot()
        history_count = participant.module_state.n_completed_trials
        eligible_candidate_ids = [node.definition["pair_id"] for node in nodes]
        decision = select_pair(
            pair_ids=eligible_candidate_ids,
            item_a_ids=np.asarray([node.definition["item_a_id"] for node in nodes]),
            item_b_ids=np.asarray([node.definition["item_b_id"] for node in nodes]),
            state=snapshot.state,
            tie_break_seed=100_000 * participant.id + history_count,
        )
        selected_node = nodes[decision["selected_index"]]
        context = {
            **decision,
            "study_fit_id": snapshot.id,
            "posterior_version": snapshot.model_version,
            "data_version": snapshot.data_version,
            "observation_fingerprint": snapshot.observation_fingerprint,
            "participant_history_count": history_count,
            "eligible_candidate_count": len(eligible_candidate_ids),
            "eligible_candidate_ids_sha256": hashlib.sha256(
                "\n".join(eligible_candidate_ids).encode()
            ).hexdigest(),
            "excluded_candidate_ids": sorted(
                set(ALL_PAIR_IDS).difference(eligible_candidate_ids)
            ),
        }
        logger.info(
            "Adaptive selection participant=%s pair=%s snapshot=%s "
            "data_version=%s score_seconds=%.4f",
            participant.id,
            decision["selected_candidate_id"],
            snapshot.id,
            snapshot.data_version,
            decision["scoring_seconds"],
        )
        return Selection(value=selected_node, context=context)

    def on_trial_created(
        self,
        trial,
        experiment,
        participant,
        selection_context=None,
    ):
        if selection_context is None:
            raise RuntimeError("Adaptive trials require selection context.")
        if selection_context["selected_candidate_id"] != trial.definition["pair_id"]:
            raise RuntimeError("Adaptive decision does not match the assigned trial.")

        trial.adaptive_pair_id = trial.definition["pair_id"]
        trial.adaptive_item_a_id = trial.definition["item_a_id"]
        trial.adaptive_item_b_id = trial.definition["item_b_id"]
        trial.adaptive_left_item_id = trial.definition["left_item_id"]
        trial.adaptive_right_item_id = trial.definition["right_item_id"]
        trial.adaptive_snapshot_id = selection_context["study_fit_id"]
        predictive_probability_item_a = selection_context[
            "predictive_probability_item_a"
        ]
        predictive_probability_left = (
            predictive_probability_item_a
            if trial.adaptive_left_item_id == trial.adaptive_item_a_id
            else 1.0 - predictive_probability_item_a
        )
        decision = AdaptiveDecision(
            participant_id=participant.id,
            study_fit_id=selection_context["study_fit_id"],
            selected_candidate_id=selection_context["selected_candidate_id"],
            participant_history_count=selection_context["participant_history_count"],
            candidate_pool_version=CANDIDATE_POOL_VERSION,
            selected_utility=selection_context["selected_utility"],
            details={
                "eligible_candidate_count": selection_context[
                    "eligible_candidate_count"
                ],
                "eligible_candidate_ids_sha256": selection_context[
                    "eligible_candidate_ids_sha256"
                ],
                "excluded_candidate_ids": selection_context["excluded_candidate_ids"],
                "candidate_reconstruction": (
                    "All pair IDs generated from the versioned item-bank manifest "
                    "minus excluded_candidate_ids."
                ),
                "objective_components": selection_context["objective_components"],
                "optimizer_version": OPTIMIZER_VERSION,
                "posterior_version": selection_context["posterior_version"],
                "data_version": selection_context["data_version"],
                "observation_fingerprint": selection_context["observation_fingerprint"],
                "scoring_seconds": selection_context["scoring_seconds"],
                "posterior_predictive": [
                    predictive_probability_left,
                    1.0 - predictive_probability_left,
                ],
            },
        )
        decision.trial = trial
        db.session.add(decision)

    def finalize_trial(self, answer, trial, experiment, participant):
        trial.adaptive_chosen_left = answer == "Left item"
        super().finalize_trial(answer, trial, experiment, participant)


def _practice_page():
    return ModularPage(
        "pairwise_practice",
        tags.div(
            tags.h3("Practice"),
            tags.p(
                "On each trial, compare the two abstract items and choose the one "
                "you prefer. There are no correct answers."
            ),
        ),
        PushButtonControl(
            ["I would choose the left item", "I would choose the right item"],
            arrange_vertically=False,
            bot_response="I would choose the left item",
        ),
        time_estimate=5,
        save_answer="pairwise_practice",
    )


trial_maker = AdaptivePairwiseTrialMaker(
    id_="adaptive_pairwise",
    trial_class=AdaptivePairwiseTrial,
    nodes=get_nodes,
    expected_trials_per_participant=N_TRIALS_PER_PARTICIPANT,
    max_trials_per_participant=N_TRIALS_PER_PARTICIPANT,
    allow_repeated_nodes=False,
    balance_across_nodes=False,
    recruit_mode="n_participants",
    target_n_participants=40,
)


class Exp(psynet.experiment.Experiment):
    """PsyNet experiment entry point."""

    label = "Adaptive pairwise comparison"
    test_n_bots = 4

    timeline = Timeline(
        InfoPage(
            "You will compare abstract items in a series of two-choice trials.",
            time_estimate=4,
        ),
        _practice_page(),
        trial_maker,
        InfoPage("Thank you. You have completed the comparisons.", time_estimate=2),
    )

    @staticmethod
    @scheduled_task("interval", seconds=2, max_instances=1)
    def refresh_adaptive_model():
        from psynet.experiment import is_experiment_launched

        if is_experiment_launched():
            claim = _claim_model_snapshot()
            if claim is None:
                return
            snapshot_id, observations, loading_seconds = claim
            try:
                WorkerAsyncProcess(
                    function=_fit_claimed_snapshot,
                    arguments={
                        "snapshot_id": snapshot_id,
                        "observations": observations,
                        "loading_seconds": loading_seconds,
                    },
                )
                db.session.commit()
            except Exception as error:
                db.session.rollback()
                snapshot = db.session.get(StudyModelSnapshot, snapshot_id)
                snapshot.status = "failed"
                snapshot.error = f"Failed to queue model worker: {error}"
                db.session.commit()
                logger.warning(
                    "Failed to queue adaptive model refresh %s: %s",
                    snapshot_id,
                    error,
                )

    def test_check_bot(self, bot: Bot, **kwargs):
        trials = (
            AdaptivePairwiseTrial.query.filter_by(participant_id=bot.id)
            .order_by(AdaptivePairwiseTrial.id)
            .all()
        )
        assert len(trials) == N_TRIALS_PER_PARTICIPANT
        assert all(trial.adaptive_chosen_left is not None for trial in trials)
        assert all(trial.answer in {"Left item", "Right item"} for trial in trials)
        assert all(trial.adaptive_snapshot_id is not None for trial in trials)
        assert AdaptiveDecision.query.filter_by(participant_id=bot.id).count() == len(
            trials
        )

    @classmethod
    def get_basic_data(cls, context=None, **kwargs):
        trials = [
            {
                "trial_id": trial.id,
                "participant_id": trial.participant_id,
                "pair_id": trial.adaptive_pair_id,
                "item_a_id": trial.adaptive_item_a_id,
                "item_b_id": trial.adaptive_item_b_id,
                "left_item_id": trial.adaptive_left_item_id,
                "right_item_id": trial.adaptive_right_item_id,
                "raw_answer": trial.answer,
                "chosen_left": trial.adaptive_chosen_left,
                "study_fit_id": trial.adaptive_snapshot_id,
            }
            for trial in AdaptivePairwiseTrial.query.all()
        ]
        decisions = [
            {
                "decision_id": decision.id,
                "trial_id": decision.trial_id,
                "participant_id": decision.participant_id,
                "selected_candidate_id": decision.selected_candidate_id,
                "study_fit_id": decision.study_fit_id,
                "participant_history_count": decision.participant_history_count,
                "candidate_pool_version": decision.candidate_pool_version,
                "selected_utility": decision.selected_utility,
                **decision.details,
            }
            for decision in AdaptiveDecision.query.all()
        ]
        snapshots = [
            {
                "study_fit_id": snapshot.id,
                "status": snapshot.status,
                "model_version": snapshot.model_version,
                "data_version": snapshot.data_version,
                "observation_count": snapshot.observation_count,
                "observation_fingerprint": snapshot.observation_fingerprint,
                "diagnostics": snapshot.diagnostics,
                "random_seed": snapshot.random_seed,
                "error": snapshot.error,
            }
            for snapshot in StudyModelSnapshot.query.all()
        ]
        return {
            "trial": pd.DataFrame.from_records(trials),
            "adaptive_decision": pd.DataFrame.from_records(decisions),
            "study_model_snapshot": pd.DataFrame.from_records(snapshots),
        }


if __name__ == "__main__":
    print(f"Loaded {len(ITEMS)} items and {len(get_nodes())} candidate pairs.")

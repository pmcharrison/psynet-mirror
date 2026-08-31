"""Adaptive arithmetic CAT using a 1PL grid posterior and Trial.cue."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from dallinger import db
from dominate import tags
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

import psynet.experiment
from psynet.bot import Bot
from psynet.data import SQLBase, SQLMixin, register_table
from psynet.field import PythonDict
from psynet.modular_page import ModularPage, PushButtonControl
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.participant import Participant
from psynet.timeline import (
    CodeBlock,
    Module,
    PageMaker,
    Timeline,
    for_loop,
    while_loop,
)
from psynet.trial.main import Trial
from psynet.utils import get_logger

from .adaptive_logic import (
    MAX_ITEMS,
    MIN_ITEMS,
    MODEL_VERSION,
    ParticipantFit,
    fit_participant_posterior,
    select_item,
    should_stop_participant,
)
from .response_model.core import ResponseParameters, sample_choice, sample_correct
from .stimuli import load_item_bank

logger = get_logger()

PRACTICE_ITEM_IDS = ("add_sd_01", "sub_sd_01")
ABILITY_PROFILES = (-1.2, 0.3, 1.4)
RESPONSE_PROFILES = ("good", "good", "inattentive")


@register_table
class AdaptiveDecision(SQLBase, SQLMixin):
    """Provenance for one CAT item assignment."""

    __tablename__ = "adaptive_decision"

    participant_id = Column(Integer, ForeignKey("participant.id"), index=True)
    trial_id = Column(
        Integer, ForeignKey("info.id"), nullable=True, unique=True, index=True
    )
    selected_candidate_id = Column(String)
    participant_history_count = Column(Integer, nullable=True)
    candidate_pool_version = Column(String)
    selected_utility = Column(Float, nullable=True)
    details = Column(PythonDict)
    trial = relationship(Trial, foreign_keys=[trial_id])


class IrtTrial(Trial):
    """One arithmetic item, either practice or adaptive."""

    time_estimate = 8
    check_time_credit_received = False

    cat_item_id = Column(String, index=True)
    cat_difficulty = Column(Float)
    cat_phase = Column(String, index=True)
    cat_correct = Column(Float)

    def finalize_definition(self, definition, experiment, participant):
        self.cat_item_id = definition["item_id"]
        self.cat_difficulty = definition["difficulty"]
        self.cat_phase = definition["phase"]
        return definition

    def show_trial(self, experiment, participant):
        prompt = tags.div()
        with prompt:
            tags.p("Choose the correct answer.")
            tags.p(tags.strong(self.definition["prompt"]))
        return ModularPage(
            "arithmetic_item",
            prompt,
            PushButtonControl(
                choices=self.definition["choices"],
                arrange_vertically=True,
                bot_response=self.get_bot_response,
            ),
        )

    def show_feedback(self, experiment, participant):
        if self.definition.get("phase") != "practice":
            return None
        if self.score == 1:
            message = "Correct."
        else:
            message = f"The correct answer was {self.definition['correct_choice']}."
        return InfoPage(message, time_estimate=2)

    def score_answer(self, answer, definition):
        score = float(answer == definition["correct_choice"])
        self.cat_correct = score
        return score

    def get_bot_response(self, experiment, bot, page, prompt):
        profile = bot.var.get("response_profile", "good")
        ability = float(bot.var.get("true_ability", 0.0))
        if profile == "inattentive":
            parameters = ResponseParameters(guessing=0.25, lapse=0.25)
            ability = 0.0
        else:
            parameters = ResponseParameters()
        rng = np.random.default_rng(
            (int(bot.id) * 1_000_003 + abs(hash(self.definition["item_id"]))) % (2**32)
        )
        is_correct = bool(
            sample_correct(
                ability=np.asarray([ability]),
                difficulty=np.asarray([self.definition["difficulty"]]),
                parameters=parameters,
                rng=rng,
            )[0]
        )
        return sample_choice(
            choices=list(self.definition["choices"]),
            correct_choice=self.definition["correct_choice"],
            is_correct=is_correct,
            rng=rng,
        )


def assign_simulation_profile(participant):
    """Give bots a stored ability and response profile for export-visible metadata."""
    index = (participant.id - 1) % len(ABILITY_PROFILES)
    participant.var.true_ability = ABILITY_PROFILES[index]
    participant.var.response_profile = RESPONSE_PROFILES[index]


def _adaptive_trials(participant):
    return [
        trial
        for trial in IrtTrial.query.filter_by(
            participant_id=participant.id, failed=False
        ).all()
        if trial.complete and trial.definition.get("phase") == "adaptive"
    ]


def _seen_item_ids(participant):
    current_id = getattr(participant.current_trial, "id", None)
    return {
        trial.definition["item_id"]
        for trial in IrtTrial.query.filter_by(
            participant_id=participant.id, failed=False
        ).all()
        if trial.complete or trial.id == current_id
    }


def current_participant_fit(participant) -> ParticipantFit:
    """Fit or reuse the from-scratch posterior for this participant."""
    trials = _adaptive_trials(participant)
    n = len(trials)
    cached_n = participant.var.get("fit_n", -1)
    cached = participant.var.get("fit", None)
    if cached_n == n and cached is not None:
        return ParticipantFit(
            log_posterior=np.asarray(cached["log_posterior"]),
            mean=cached["mean"],
            sd=cached["sd"],
            n_observations=n,
        )
    fit = fit_participant_posterior(
        np.asarray([trial.definition["difficulty"] for trial in trials]),
        np.asarray(
            [0.0 if trial.score is None else float(trial.score) for trial in trials]
        ),
    )
    participant.var.fit_n = n
    participant.var.ability_mean = fit.mean
    participant.var.ability_sd = fit.sd
    participant.var.fit = {
        "log_posterior": fit.log_posterior.tolist(),
        "mean": fit.mean,
        "sd": fit.sd,
    }
    return fit


def cat_should_continue(participant):
    """Continue until the shared stopping rule fires or the bank is exhausted."""
    remaining = [
        item
        for item in load_item_bank()
        if item["item_id"] not in _seen_item_ids(participant)
    ]
    if not remaining:
        return False
    fit = current_participant_fit(participant)
    return not should_stop_participant(
        n_administered=fit.n_observations,
        posterior_sd=fit.sd,
    )


def record_decision(trial, participant, creation_context):
    """Write the CAT decision in the same transaction as trial creation."""
    decision = AdaptiveDecision()
    decision.participant_id = participant.id
    decision.selected_candidate_id = creation_context["selected_candidate_id"]
    decision.participant_history_count = creation_context["participant_history_count"]
    decision.candidate_pool_version = creation_context["candidate_pool_version"]
    decision.selected_utility = creation_context["selected_utility"]
    decision.details = creation_context["details"]
    decision.trial = trial
    db.session.add(decision)


def select_and_cue(participant, experiment):
    """Select the next item and cue it on the timeline."""
    t_load = time.perf_counter()
    remaining = [
        item
        for item in load_item_bank()
        if item["item_id"] not in _seen_item_ids(participant)
    ]
    load_seconds = time.perf_counter() - t_load

    t_fit = time.perf_counter()
    fit = current_participant_fit(participant)
    fit_seconds = time.perf_counter() - t_fit

    t_score = time.perf_counter()
    chosen = select_item(
        fit=fit,
        candidate_items=remaining,
        policy="max_information",
    )
    score_seconds = time.perf_counter() - t_score
    logger.info(
        "adaptive_select participant=%s item=%s info=%.3f load=%.4fs fit=%.4fs score=%.4fs",
        participant.id,
        chosen["item_id"],
        chosen["selected_utility"],
        load_seconds,
        fit_seconds,
        score_seconds,
    )
    creation_context = {
        "selected_candidate_id": chosen["item_id"],
        "participant_history_count": fit.n_observations,
        "candidate_pool_version": "stimuli/item_bank.json",
        "selected_utility": chosen["selected_utility"],
        "details": {
            "ability_mean": fit.mean,
            "ability_sd": fit.sd,
            "predictive_p_correct": chosen["predictive_p_correct"],
            "candidate_count": chosen["candidate_count"],
            "model_version": MODEL_VERSION,
            "optimizer_version": chosen["optimizer_version"],
            "load_seconds": load_seconds,
            "fit_seconds": fit_seconds,
            "score_seconds": score_seconds,
        },
    }
    return IrtTrial.cue(
        definition={
            "item_id": chosen["item_id"],
            "prompt": chosen["prompt"],
            "choices": chosen["choices"],
            "correct_choice": chosen["correct_choice"],
            "difficulty": chosen["difficulty"],
            "skill": chosen["skill"],
            "phase": "adaptive",
        },
        on_trial_created=record_decision,
        creation_context=creation_context,
    )


def practice_item_cue(item):
    definition = dict(item)
    definition["phase"] = "practice"
    return IrtTrial.cue(definition)


def practice_items():
    return [
        dict(item) for item in load_item_bank() if item["item_id"] in PRACTICE_ITEM_IDS
    ]


def estimated_ability_page(participant):
    fit = current_participant_fit(participant)
    return InfoPage(
        tags.div(
            tags.p("Thank you. The test is complete."),
            tags.p(
                f"Estimated arithmetic skill: {fit.mean:.2f} "
                f"(posterior SD {fit.sd:.2f}) after {fit.n_observations} scored items."
            ),
        ),
        time_estimate=8,
    )


practice_module = Module(
    "practice",
    InfoPage(
        tags.div(
            tags.p("This is a short practice."),
            tags.p("You will see two easy arithmetic questions with feedback."),
        ),
        time_estimate=8,
    ),
    for_loop(
        label="practice_items",
        iterate_over=practice_items,
        logic=practice_item_cue,
        time_estimate_per_iteration=IrtTrial.time_estimate,
        expected_repetitions=len(PRACTICE_ITEM_IDS),
    ),
)

adaptive_module = Module(
    "adaptive_arithmetic",
    InfoPage(
        "The scored test begins now. Items get easier or harder based on your answers.",
        time_estimate=5,
    ),
    while_loop(
        label="cat",
        condition=cat_should_continue,
        logic=PageMaker(select_and_cue, time_estimate=IrtTrial.time_estimate),
        expected_repetitions=12,
    ),
)


class Exp(psynet.experiment.Experiment):
    label = "Adaptive arithmetic IRT"
    test_n_bots = 3

    timeline = Timeline(
        CodeBlock(assign_simulation_profile),
        InfoPage(
            tags.div(
                tags.h3("Arithmetic skill test"),
                tags.p(
                    "You will answer multiple-choice arithmetic questions. "
                    "The test adapts: after each answer, the next question is "
                    "chosen to be informative about your skill."
                ),
            ),
            time_estimate=12,
        ),
        practice_module,
        adaptive_module,
        PageMaker(estimated_ability_page, time_estimate=8),
        SuccessfulEndPage(),
    )

    def test_check_bot(self, bot: Bot, **kwargs):
        assert not bot.failed
        practice = [
            trial
            for trial in bot.all_trials
            if trial.definition.get("phase") == "practice"
        ]
        adaptive = [
            trial
            for trial in bot.all_trials
            if trial.definition.get("phase") == "adaptive"
        ]
        assert len(practice) == len(PRACTICE_ITEM_IDS)
        assert MIN_ITEMS <= len(adaptive) <= MAX_ITEMS
        assert all(trial.complete and trial.finalized for trial in bot.all_trials)
        item_ids = [trial.definition["item_id"] for trial in adaptive]
        assert len(item_ids) == len(set(item_ids))
        decisions = AdaptiveDecision.query.filter_by(participant_id=bot.id).all()
        assert len(decisions) == len(adaptive)
        assert all(decision.selected_utility is not None for decision in decisions)
        assert bot.var.get("response_profile", None) in RESPONSE_PROFILES

    @classmethod
    def get_basic_data(cls, context=None, **kwargs):
        trials = [
            {
                "id": trial.id,
                "participant_id": trial.participant_id,
                "item_id": trial.definition.get("item_id"),
                "difficulty": trial.definition.get("difficulty"),
                "phase": trial.definition.get("phase"),
                "answer": trial.answer,
                "correct": trial.score,
            }
            for trial in IrtTrial.query.all()
        ]
        participants = [
            {
                "id": participant.id,
                "status": participant.status,
                "true_ability": participant.var.get("true_ability", None),
                "response_profile": participant.var.get("response_profile", None),
                "ability_mean": participant.var.get("ability_mean", None),
                "ability_sd": participant.var.get("ability_sd", None),
            }
            for participant in Participant.query.all()
        ]
        decisions = [
            {
                "id": decision.id,
                "participant_id": decision.participant_id,
                "trial_id": decision.trial_id,
                "selected_candidate_id": decision.selected_candidate_id,
                "participant_history_count": decision.participant_history_count,
                "selected_utility": decision.selected_utility,
                "ability_mean": (decision.details or {}).get("ability_mean"),
                "ability_sd": (decision.details or {}).get("ability_sd"),
                "predictive_p_correct": (decision.details or {}).get(
                    "predictive_p_correct"
                ),
            }
            for decision in AdaptiveDecision.query.all()
        ]
        return {
            "trial": pd.DataFrame.from_records(trials),
            "participant": pd.DataFrame.from_records(participants),
            "adaptive_decision": pd.DataFrame.from_records(decisions),
        }

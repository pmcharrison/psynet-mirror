"""Vectorized 1PL / 3PL response sampling for the arithmetic CAT demo."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.random import Generator


@dataclass(frozen=True)
class ResponseParameters:
    """Parameters of the data-generating response process.

    ``guessing`` is the 3PL lower asymptote. Zero matches the 1PL learner.
    """

    guessing: float = 0.0
    lapse: float = 0.0


def irt_probability(
    ability: np.ndarray,
    difficulty: np.ndarray,
    parameters: ResponseParameters,
) -> np.ndarray:
    """Return P(correct) under a 3PL model with optional lapse."""
    ability = np.asarray(ability, dtype=float)
    difficulty = np.asarray(difficulty, dtype=float)
    logit = np.clip(ability - difficulty, -30.0, 30.0)
    p_1pl = 1.0 / (1.0 + np.exp(-logit))
    guessing = parameters.guessing
    lapse = parameters.lapse
    return guessing + (1.0 - guessing - lapse) * p_1pl


def sample_correct(
    *,
    ability: np.ndarray,
    difficulty: np.ndarray,
    parameters: ResponseParameters,
    rng: Generator,
) -> np.ndarray:
    """Sample binary correctness for each trial."""
    probability = irt_probability(ability, difficulty, parameters)
    return rng.random(size=probability.shape) < probability


def sample_choice(
    *,
    choices: list[str],
    correct_choice: str,
    is_correct: bool,
    rng: Generator,
) -> str:
    """Map a binary outcome onto a multiple-choice string."""
    if is_correct:
        return correct_choice
    distractors = [choice for choice in choices if choice != correct_choice]
    return str(rng.choice(distractors))

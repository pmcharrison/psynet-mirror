"""Scientific response models for synthetic pairwise-comparison participants."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.random import Generator
from scipy.special import expit


@dataclass(frozen=True)
class ResponseParameters:
    """Parameters governing synthetic two-alternative choices."""

    inverse_temperature: float = 1.0
    lapse_rate: float = 0.0
    left_bias: float = 0.0


MATCHING = ResponseParameters()
MISSPECIFIED = ResponseParameters(
    inverse_temperature=0.75,
    lapse_rate=0.08,
    left_bias=0.15,
)


def choice_probabilities(
    *,
    left_utilities: np.ndarray,
    right_utilities: np.ndarray,
    parameters: ResponseParameters,
) -> np.ndarray:
    """Return the probability of choosing the item shown on the left."""

    logits = (
        parameters.inverse_temperature * (left_utilities - right_utilities)
        + parameters.left_bias
    )
    model_probability = expit(logits)
    return (
        parameters.lapse_rate * 0.5 + (1.0 - parameters.lapse_rate) * model_probability
    )


def sample_choices(
    *,
    left_utilities: np.ndarray,
    right_utilities: np.ndarray,
    parameters: ResponseParameters,
    rng: Generator,
) -> np.ndarray:
    """Sample one Boolean left-choice observation per comparison."""

    probabilities = choice_probabilities(
        left_utilities=np.asarray(left_utilities),
        right_utilities=np.asarray(right_utilities),
        parameters=parameters,
    )
    return rng.random(probabilities.shape) < probabilities

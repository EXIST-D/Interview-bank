"""Review intervals: the original doubling schedule, or FSRS (config review.scheduler = "fsrs" or "fsrs6").

FSRS keeps two numbers per card, stability (days until recall drops to 90 %) and difficulty (1-10), and updates
them from each rating and the time since the last review. Ratings map again=1, hard=2, good=3, easy=4.
"fsrs" is FSRS-4.5 with its published default parameters (17 weights, a fixed forgetting curve). "fsrs6" is FSRS-6
(21 weights: the shape of the forgetting curve is the last one, and a review within a day of the previous one has
its own stability rule), following the reference implementation of open-spaced-repetition (py-fsrs, MIT) and
checked against its published test sequences in tests/test_fsrs6.py.
"""
from __future__ import annotations

import math
from typing import Optional

from .errors import ValidationError

W = (0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031, 1.6474, 0.1367, 1.0461,
     2.1072, 0.0793, 0.3246, 1.587, 0.2272, 2.8755)
DECAY = -0.5
FACTOR = 19 / 81  # makes R(S, S) = 0.9
GRADES = {"again": 1, "hard": 2, "good": 3, "easy": 4}
MAX_INTERVAL = 3650


def simple_interval(rating: str, previous: int) -> int:
    """The doubling schedule used since 1.7."""
    return {"again": 1, "hard": max(1, previous), "good": 3 if previous < 3 else min(90, previous * 2),
            "easy": 7 if previous < 7 else min(180, previous * 2)}[rating]


def _clamp_difficulty(value: float) -> float:
    return min(10.0, max(1.0, value))


def _initial_difficulty(grade: int) -> float:
    return _clamp_difficulty(W[4] - (grade - 3) * W[5])


def retrievability(elapsed_days: float, stability: float) -> float:
    return (1 + FACTOR * elapsed_days / stability) ** DECAY


def fsrs_step(rating: str, state: Optional[dict], elapsed_days: float, desired_retention: float = 0.9) -> tuple[int, dict]:
    """(interval in days, new state) after one review. state None means a new (or reworded) card."""
    grade = GRADES[rating]
    if state is None:
        stability, difficulty = W[grade - 1], _initial_difficulty(grade)
    else:
        s, d = state["stability"], state["difficulty"]
        r = retrievability(max(0.0, elapsed_days), s)
        if grade == 1:
            stability = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp(W[14] * (1 - r))
        else:
            bonus = W[15] if grade == 2 else W[16] if grade == 4 else 1.0
            stability = s * (math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp(W[10] * (1 - r)) - 1) * bonus + 1)
        difficulty = _clamp_difficulty(W[7] * _initial_difficulty(3) + (1 - W[7]) * (d - W[6] * (grade - 3)))
    interval = stability / FACTOR * (desired_retention ** (1 / DECAY) - 1)
    days = int(min(MAX_INTERVAL, max(1, round(interval))))
    return days, {"stability": round(stability, 4), "difficulty": round(difficulty, 4)}


# ---------------------------------------------------------------------------------------------------- FSRS-6
W6 = (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483,
      0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542)
# Inclusive bounds of the reference implementation for each weight; weights fitted to a person's own reviews must lie inside.
BOUNDS6 = ((0.001, 100.0), (0.001, 100.0), (0.001, 100.0), (0.001, 100.0), (1.0, 10.0), (0.001, 4.0), (0.001, 4.0), (0.001, 0.75),
           (0.0, 4.5), (0.0, 0.8), (0.001, 3.5), (0.001, 5.0), (0.001, 0.25), (0.001, 0.9), (0.0, 4.0), (0.0, 1.0), (1.0, 6.0),
           (0.0, 2.0), (0.0, 2.0), (0.0, 0.8), (0.1, 0.8))
STABILITY_MIN = 0.001


def fsrs6_parameters(values) -> tuple:
    """The 21 weights as floats, or ValidationError: a wrong count, a non-number or one outside its bounds."""
    if not isinstance(values, (list, tuple)) or len(values) != len(BOUNDS6):
        raise ValidationError(f"config.review.fsrs_parameters: expected {len(BOUNDS6)} numbers")
    for index, (value, (low, high)) in enumerate(zip(values, BOUNDS6)):
        # A comparison with NaN is false, so NaN is refused here too; bool is not a number.
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValidationError(f"config.review.fsrs_parameters[{index}] must be a number from {low} to {high}")
    return tuple(float(value) for value in values)


def _curve(w):
    decay = -w[20]
    return decay, 0.9 ** (1 / decay) - 1


def retrievability6(elapsed_days: float, stability: float, parameters=W6) -> float:
    """Probability of recall after whole elapsed days; 0.9 when the elapsed time equals the stability."""
    decay, factor = _curve(parameters)
    return (1 + factor * max(0, int(elapsed_days)) / stability) ** decay


def fsrs6_step(rating: str, state: Optional[dict], elapsed_days: float, desired_retention: float = 0.9,
               parameters=None) -> tuple[int, dict]:
    """(interval in days, new state) after one review. state None means a new (or reworded) card.

    A review less than a day after the previous one is a same-day review: it follows its own rule and a success never
    lowers stability. Otherwise recall is measured in whole days since the last review. Stability is updated from the old
    difficulty, then difficulty is updated; a first review sets both from the rating alone."""
    w = parameters or W6
    grade = GRADES[rating]
    decay, factor = _curve(w)
    if state is None:
        stability = max(w[grade - 1], STABILITY_MIN)
        difficulty = min(10.0, max(1.0, w[4] - math.exp(w[5] * (grade - 1)) + 1))
    else:
        s, d = state["stability"], state["difficulty"]
        if elapsed_days < 1:
            gain = math.exp(w[17] * (grade - 3 + w[18])) * s ** -w[19]
            stability = s * (max(gain, 1.0) if grade >= 2 else gain)
        else:
            r = (1 + factor * int(elapsed_days) / s) ** decay
            if grade == 1:
                forgotten = w[11] * d ** -w[12] * ((s + 1) ** w[13] - 1) * math.exp((1 - r) * w[14])
                stability = min(forgotten, s / math.exp(w[17] * w[18]))
            else:
                bonus = w[15] if grade == 2 else w[16] if grade == 4 else 1.0
                stability = s * (1 + math.exp(w[8]) * (11 - d) * s ** -w[9] * (math.exp((1 - r) * w[10]) - 1) * bonus)
        stability = max(stability, STABILITY_MIN)
        easiest = w[4] - math.exp(w[5] * 3) + 1  # the first difficulty of an Easy rating, not limited to 1..10
        damped = d + (10.0 - d) * -(w[6] * (grade - 3)) / 9.0
        difficulty = min(10.0, max(1.0, w[7] * easiest + (1 - w[7]) * damped))
    interval = stability / factor * (desired_retention ** (1 / decay) - 1)
    days = int(min(MAX_INTERVAL, max(1, round(interval))))
    return days, {"stability": round(stability, 6), "difficulty": round(difficulty, 6), "algorithm": "fsrs-6"}

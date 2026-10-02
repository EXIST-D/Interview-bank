"""Review intervals: the original doubling schedule, or FSRS (config review.scheduler = "fsrs").

FSRS-4.5 with its published default parameters (open-spaced-repetition). It keeps two numbers per card,
stability (days until recall drops to 90 %) and difficulty (1-10), and updates them from each rating and
the time since the last review. Ratings map again=1, hard=2, good=3, easy=4.
"""
from __future__ import annotations

import math
from typing import Optional

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

"""Small descriptive-statistics helpers with explicit interpretation limits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, median
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ProportionInterval:
    """Observed proportion and Wilson score interval."""

    successes: int
    total: int
    proportion: float | None
    lower: float | None
    upper: float | None


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> ProportionInterval:
    """Calculate a two-sided Wilson interval; this is descriptive, not causal."""

    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes and total must satisfy 0 <= successes <= total")
    if total == 0:
        return ProportionInterval(successes, total, None, None, None)
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2))
        / denominator
    )
    return ProportionInterval(successes, total, proportion, center - margin, center + margin)


def review_score_summary(scores: Iterable[int]) -> dict[str, float | int | None]:
    """Summarize usable review scores without implying delivery caused the score."""

    usable = tuple(score for score in scores if 1 <= score <= 5)
    return {
        "count": len(usable),
        "mean": fmean(usable) if usable else None,
        "median": median(usable) if usable else None,
        "one_or_two_star_count": sum(score <= 2 for score in usable),
        "five_star_count": sum(score == 5 for score in usable),
    }

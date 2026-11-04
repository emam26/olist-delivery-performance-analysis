"""Small descriptive-statistics helpers with explicit interpretation limits."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from statistics import fmean, median


@dataclass(frozen=True, slots=True)
class _LegacyProportionInterval:
    """Observed proportion and Wilson score interval."""

    successes: int
    total: int
    proportion: float | None
    lower: float | None
    upper: float | None


def _legacy_wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> _LegacyProportionInterval:
    """Calculate a two-sided Wilson interval; this is descriptive, not causal."""

    if total < 0 or successes < 0 or successes > total:
        raise ValueError("successes and total must satisfy 0 <= successes <= total")
    if total == 0:
        return _LegacyProportionInterval(successes, total, None, None, None)
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    margin = (
        z * math.sqrt(proportion * (1 - proportion) / total + z**2 / (4 * total**2)) / denominator
    )
    return _LegacyProportionInterval(
        successes,
        total,
        proportion,
        center - margin,
        center + margin,
    )


def _legacy_review_score_summary(scores: Iterable[int]) -> dict[str, float | int | None]:
    """Summarize usable review scores without implying delivery caused the score."""

    usable = tuple(score for score in scores if 1 <= score <= 5)
    return {
        "count": len(usable),
        "mean": fmean(usable) if usable else None,
        "median": median(usable) if usable else None,
        "one_or_two_star_count": sum(score <= 2 for score in usable),
        "five_star_count": sum(score == 5 for score in usable),
    }


@dataclass(frozen=True, slots=True)
class ProportionInterval:
    """Observed proportion and Wilson score interval."""

    successes: int
    trials: int
    proportion: float | None
    lower: float | None
    upper: float | None
    confidence_level: float = 0.95

    @property
    def total(self) -> int:
        """Compatibility name for the denominator."""

        return self.trials


def wilson_interval(
    successes: int,
    trials: int | None = None,
    z: float | None = None,
    *,
    confidence_level: float = 0.95,
    total: int | None = None,
) -> ProportionInterval:
    """Calculate a two-sided Wilson interval; this is descriptive, not causal."""

    if trials is None:
        trials = total
    elif total is not None and total != trials:
        raise ValueError("trials and total must agree")
    if trials is None:
        raise TypeError("trials is required")
    if trials < 0 or successes < 0 or successes > trials:
        raise ValueError("successes and trials must satisfy 0 <= successes <= trials")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be between 0 and 1")
    if z is None:
        z = 1.959963984540054
    if z <= 0 or not math.isfinite(z):
        raise ValueError("z must be positive and finite")
    if trials == 0:
        return ProportionInterval(successes, trials, None, None, None, confidence_level)

    proportion = successes / trials
    denominator = 1 + z**2 / trials
    center = (proportion + z**2 / (2 * trials)) / denominator
    margin = (
        z * math.sqrt(proportion * (1 - proportion) / trials + z**2 / (4 * trials**2)) / denominator
    )
    return ProportionInterval(
        successes,
        trials,
        proportion,
        center - margin,
        center + margin,
        confidence_level,
    )


@dataclass(frozen=True, slots=True)
class ReviewScoreSummary:
    """Review-score group counts with an explicit on-time denominator."""

    reviewed_orders: int
    on_time_orders: int
    on_time_rate: float | None


def review_score_summary(
    records: Iterable[Mapping[str, object]],
) -> dict[int, ReviewScoreSummary]:
    """Summarize valid review scores without hiding missing review records."""

    groups: dict[int, list[bool]] = {}
    for record in records:
        try:
            score = int(str(record.get("review_score") or ""))
        except ValueError:
            continue
        if not 1 <= score <= 5:
            continue
        groups.setdefault(score, []).append(record.get("on_time") is True)
    return {
        score: ReviewScoreSummary(
            reviewed_orders=len(on_time_values),
            on_time_orders=sum(on_time_values),
            on_time_rate=sum(on_time_values) / len(on_time_values) if on_time_values else None,
        )
        for score, on_time_values in sorted(groups.items())
    }

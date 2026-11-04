from __future__ import annotations

import pytest

from olist_delivery.statistics import review_score_summary, wilson_interval


def test_wilson_interval_contains_observed_proportion() -> None:
    interval = wilson_interval(successes=80, trials=100)

    assert interval.lower < 0.8 < interval.upper
    assert interval.confidence_level == 0.95


def test_wilson_interval_rejects_impossible_counts() -> None:
    with pytest.raises(ValueError):
        wilson_interval(successes=3, trials=2)


def test_wilson_interval_uses_requested_confidence_level() -> None:
    interval_90 = wilson_interval(successes=80, trials=100, confidence_level=0.90)
    interval_95 = wilson_interval(successes=80, trials=100, confidence_level=0.95)

    assert interval_90.lower is not None and interval_95.lower is not None
    assert interval_90.upper is not None and interval_95.upper is not None
    assert interval_90.lower > interval_95.lower
    assert interval_90.upper < interval_95.upper


def test_review_score_summary_retains_denominators() -> None:
    summary = review_score_summary(
        [
            {"review_score": 1, "on_time": False},
            {"review_score": 1, "on_time": True},
            {"review_score": 5, "on_time": True},
            {"review_score": None, "on_time": True},
        ]
    )

    assert summary[1].reviewed_orders == 2
    assert summary[1].on_time_orders == 1
    assert summary[1].on_time_rate == 0.5
    assert summary[5].reviewed_orders == 1

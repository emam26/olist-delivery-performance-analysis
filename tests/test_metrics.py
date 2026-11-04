from __future__ import annotations

import math

import pytest

from olist_delivery.metrics import (
    aggregate_delivery_kpis,
    build_order_category_bridge,
    build_order_seller_bridge,
    classify_order,
    percentile_cont,
    select_review_for_order,
)


def _order(**overrides: str | None) -> dict[str, str | None]:
    order: dict[str, str | None] = {
        "order_id": "order-1",
        "order_purchase_timestamp": "2018-01-01 09:00:00",
        "order_delivered_customer_date": "2018-01-10 17:00:00",
        "order_estimated_delivery_date": "2018-01-10 00:00:00",
    }
    order.update(overrides)
    return order


def test_delivery_on_estimated_calendar_date_is_on_time() -> None:
    outcome = classify_order(_order())

    assert outcome.delivery_classification == "On Time"
    assert outcome.delivery_eligible is True
    assert outcome.days_early_or_late == 0
    assert outcome.duration_eligible is True
    assert outcome.delivery_duration_days == pytest.approx(9 + 8 / 24)


def test_delivery_after_estimated_calendar_date_is_late() -> None:
    outcome = classify_order(
        _order(order_delivered_customer_date="2018-01-11 00:00:01")
    )

    assert outcome.delivery_classification == "Late"
    assert outcome.days_early_or_late == 1


def test_missing_estimate_excludes_status_but_not_valid_duration() -> None:
    outcome = classify_order(_order(order_estimated_delivery_date=None))

    assert outcome.delivery_classification == "Excluded"
    assert outcome.delivery_eligible is False
    assert outcome.duration_eligible is True
    assert outcome.delivery_duration_days is not None


def test_negative_duration_is_not_replaced_with_zero() -> None:
    outcome = classify_order(
        _order(order_purchase_timestamp="2018-01-12 09:00:00")
    )

    assert outcome.duration_eligible is False
    assert outcome.delivery_duration_days is None
    assert "negative" in outcome.duration_exclusion_reason.lower()


def test_aggregate_kpis_preserve_independent_denominators() -> None:
    outcomes = [
        classify_order(_order(order_id="on-time")),
        classify_order(
            _order(
                order_id="late",
                order_delivered_customer_date="2018-01-11 17:00:00",
            )
        ),
        classify_order(
            _order(
                order_id="status-excluded",
                order_estimated_delivery_date=None,
            )
        ),
        classify_order(
            _order(
                order_id="duration-excluded",
                order_purchase_timestamp="2018-01-12 09:00:00",
            )
        ),
    ]

    metrics = aggregate_delivery_kpis(outcomes)

    assert metrics.all_orders == 4
    assert metrics.delivery_eligible_orders == 3
    assert metrics.on_time_orders == 2
    assert metrics.late_orders == 1
    assert metrics.on_time_rate == pytest.approx(2 / 3)
    assert metrics.duration_eligible_orders == 3


def test_percentile_cont_uses_linear_interpolation() -> None:
    assert percentile_cont([1.0, 2.0, 3.0, 4.0], 0.5) == 2.5
    assert percentile_cont([1.0, 2.0, 3.0, 4.0], 0.9) == pytest.approx(3.7)
    assert percentile_cont([], 0.5) is None

    with pytest.raises(ValueError):
        percentile_cont([1.0], math.nan)


def test_review_selection_is_deterministic() -> None:
    selected = select_review_for_order(
        [
            {
                "review_id": "older",
                "order_id": "order-1",
                "review_score": "1",
                "review_creation_date": "2018-01-01 00:00:00",
                "review_answer_timestamp": "2018-01-02 00:00:00",
            },
            {
                "review_id": "newer",
                "order_id": "order-1",
                "review_score": "5",
                "review_creation_date": "2018-01-01 00:00:00",
                "review_answer_timestamp": "2018-01-03 00:00:00",
            },
        ]
    )

    assert selected is not None
    assert selected["review_id"] == "newer"


def test_bridges_deduplicate_order_group_pairs() -> None:
    items = [
        {
            "order_id": "order-1",
            "seller_id": "seller-1",
            "product_id": "product-1",
        },
        {
            "order_id": "order-1",
            "seller_id": "seller-1",
            "product_id": "product-2",
        },
    ]
    products = [
        {"product_id": "product-1", "product_category_name": "books"},
        {"product_id": "product-2", "product_category_name": "books"},
    ]

    assert build_order_seller_bridge(items) == {("order-1", "seller-1")}
    assert build_order_category_bridge(items, products) == {("order-1", "books")}

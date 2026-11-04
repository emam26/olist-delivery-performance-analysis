"""Independent Python implementation of the core delivery KPI semantics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, median
from typing import Any, Iterable, Mapping, Sequence


def parse_source_timestamp(value: Any) -> datetime | None:
    """Parse a source timestamp without inventing a timezone."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class OrderDeliveryMetric:
    """One order-level classification independent of item and review joins."""

    order_id: str
    is_delivery_eligible: bool
    is_late: bool | None
    is_duration_eligible: bool
    delivery_duration_hours: float | None
    days_late: int | None
    exclusion_reason: str | None


def classify_order(order: Mapping[str, Any]) -> OrderDeliveryMetric:
    """Apply the documented calendar-date and duration rules to one order."""

    order_id = str(order.get("order_id") or "")
    status = str(order.get("order_status") or "").strip().lower()
    purchase_raw = order.get("order_purchase_timestamp")
    actual_raw = order.get("order_delivered_customer_date")
    estimated_raw = order.get("order_estimated_delivery_date")
    purchase = parse_source_timestamp(purchase_raw)
    actual = parse_source_timestamp(actual_raw)
    estimated = parse_source_timestamp(estimated_raw)

    if status != "delivered":
        eligibility_reason = "status_not_delivered"
    elif actual is None:
        eligibility_reason = "missing_or_invalid_actual_delivery"
    elif estimated is None:
        eligibility_reason = "missing_or_invalid_estimated_delivery"
    else:
        eligibility_reason = None

    is_delivery_eligible = eligibility_reason is None
    is_late = actual.date() > estimated.date() if is_delivery_eligible else None
    days_late = (actual.date() - estimated.date()).days if is_late else None

    duration_hours = None
    is_duration_eligible = False
    duration_reason = None
    if purchase is None:
        duration_reason = "missing_or_invalid_purchase_timestamp"
    elif actual is None:
        duration_reason = "missing_or_invalid_actual_delivery"
    elif actual < purchase:
        duration_reason = "negative_delivery_interval"
    else:
        is_duration_eligible = True
        duration_hours = (actual - purchase).total_seconds() / 3600.0

    exclusion_reason = eligibility_reason or duration_reason
    return OrderDeliveryMetric(
        order_id=order_id,
        is_delivery_eligible=is_delivery_eligible,
        is_late=is_late,
        is_duration_eligible=is_duration_eligible,
        delivery_duration_hours=duration_hours,
        days_late=days_late,
        exclusion_reason=exclusion_reason,
    )


def percentile_cont(values: Sequence[float], percentile: float) -> float | None:
    """Match SQL Server PERCENTILE_CONT linear interpolation for finite values."""

    if not 0 <= percentile <= 1:
        raise ValueError("percentile must be between 0 and 1")
    ordered = sorted(value for value in values if math.isfinite(value))
    if not ordered:
        return None
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    weight = rank - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * weight)


def aggregate_delivery_metrics(orders: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate order-level KPIs with explicit numerators and denominators."""

    classified = tuple(classify_order(order) for order in orders)
    eligible = tuple(item for item in classified if item.is_delivery_eligible)
    late = tuple(item for item in eligible if item.is_late is True)
    on_time = tuple(item for item in eligible if item.is_late is False)
    durations = [
        item.delivery_duration_hours
        for item in classified
        if item.delivery_duration_hours is not None
    ]
    late_days = [float(item.days_late) for item in late if item.days_late is not None]
    denominator = len(eligible)
    return {
        "source_order_count": len(classified),
        "eligible_order_count": denominator,
        "on_time_order_count": len(on_time),
        "late_order_count": len(late),
        "on_time_delivery_rate": len(on_time) / denominator if denominator else None,
        "late_delivery_rate": len(late) / denominator if denominator else None,
        "duration_eligible_order_count": len(durations),
        "average_delivery_hours": fmean(durations) if durations else None,
        "median_delivery_hours": median(durations) if durations else None,
        "p90_delivery_hours": percentile_cont(durations, 0.90),
        "p95_delivery_hours": percentile_cont(durations, 0.95),
        "average_days_late": fmean(late_days) if late_days else None,
    }


def _usable_review_score(review: Mapping[str, Any]) -> int | None:
    try:
        score = int(str(review.get("review_score") or ""))
    except ValueError:
        return None
    return score if 1 <= score <= 5 else None


def select_review(reviews: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Select one usable review using the SQL view's deterministic ordering."""

    usable = [review for review in reviews if _usable_review_score(review) is not None]
    if not usable:
        return None

    def ordering(review: Mapping[str, Any]) -> tuple[datetime, datetime, str, int]:
        answer = parse_source_timestamp(review.get("review_answer_timestamp")) or datetime.min
        created = parse_source_timestamp(review.get("review_creation_date")) or datetime.min
        review_id = str(review.get("review_id") or "")
        source_row = int(review.get("source_row_number") or 0)
        return answer, created, review_id, source_row

    return max(usable, key=ordering)


def select_reviews_by_order(
    reviews: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Return at most one selected usable review for each order."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for review in reviews:
        order_id = str(review.get("order_id") or "")
        grouped.setdefault(order_id, []).append(review)
    return {
        order_id: selected
        for order_id, rows in grouped.items()
        if (selected := select_review(rows)) is not None
    }


def distinct_order_sellers(items: Iterable[Mapping[str, Any]]) -> set[tuple[str, str]]:
    """Build the documented bridge grain without duplicate item multiplication."""

    return {
        (str(item.get("order_id") or ""), str(item.get("seller_id") or ""))
        for item in items
        if item.get("order_id") and item.get("seller_id")
    }


def distinct_order_categories(items: Iterable[Mapping[str, Any]]) -> set[tuple[str, str]]:
    """Build one row per order/category while excluding absent categories."""

    return {
        (str(item.get("order_id") or ""), str(item.get("product_category_name") or ""))
        for item in items
        if item.get("order_id") and item.get("product_category_name")
    }

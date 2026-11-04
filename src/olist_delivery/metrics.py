"""Independent Python implementation of the core delivery KPI semantics."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean, median
from typing import Any


def parse_source_timestamp(value: Any) -> datetime | None:
    """Parse a source timestamp without inventing a timezone."""

    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip())
    except ValueError:
        return None


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
    """Build one row per order/category, retaining absent categories as a label."""

    missing_category = "(Missing category)"
    return {
        (
            str(item.get("order_id") or ""),
            str(item.get("product_category_name") or "").strip() or missing_category,
        )
        for item in items
        if item.get("order_id")
    }


@dataclass(frozen=True, slots=True)
class OrderDeliveryMetric:
    """One order-level delivery outcome with independent eligibility cohorts."""

    order_id: str
    delivered: bool
    delivery_classification: str
    delivery_eligible: bool
    days_early_or_late: int | None
    duration_eligible: bool
    delivery_duration_days: float | None
    duration_exclusion_reason: str | None
    delivery_exclusion_reason: str | None

    @property
    def is_delivery_eligible(self) -> bool:
        """SQL-aligned name for the delivery-status cohort."""

        return self.delivery_eligible

    @property
    def is_late(self) -> bool | None:
        """SQL-aligned lateness flag, undefined for excluded orders."""

        if not self.delivery_eligible:
            return None
        return self.delivery_classification == "Late"

    @property
    def is_duration_eligible(self) -> bool:
        return self.duration_eligible

    @property
    def delivery_duration_hours(self) -> float | None:
        if self.delivery_duration_days is None:
            return None
        return self.delivery_duration_days * 24

    @property
    def days_late(self) -> int | None:
        if self.days_early_or_late is None or self.days_early_or_late <= 0:
            return None
        return self.days_early_or_late

    @property
    def exclusion_reason(self) -> str | None:
        return self.delivery_exclusion_reason or self.duration_exclusion_reason


def classify_order(order: Mapping[str, Any]) -> OrderDeliveryMetric:
    """Apply the SQL contract to one order without conflating KPI cohorts."""

    order_id = str(order.get("order_id") or "")
    status = str(order.get("order_status") or "").strip().lower()
    purchase = parse_source_timestamp(order.get("order_purchase_timestamp"))
    actual = parse_source_timestamp(order.get("order_delivered_customer_date"))
    estimated = parse_source_timestamp(order.get("order_estimated_delivery_date"))

    if status != "delivered":
        delivery_reason = "status_not_delivered"
    elif actual is None:
        delivery_reason = "missing_or_invalid_actual_delivery"
    elif estimated is None:
        delivery_reason = "missing_or_invalid_estimated_delivery"
    else:
        delivery_reason = None

    delivery_eligible = delivery_reason is None
    days_early_or_late = (actual.date() - estimated.date()).days if delivery_eligible else None
    classification = (
        "Excluded"
        if not delivery_eligible
        else "Late"
        if days_early_or_late is not None and days_early_or_late > 0
        else "On Time"
    )

    if purchase is None:
        duration_reason = "missing_or_invalid_purchase_timestamp"
    elif actual is None:
        duration_reason = "missing_or_invalid_actual_delivery"
    elif actual < purchase:
        duration_reason = "negative_delivery_interval"
    else:
        duration_reason = None
    duration_eligible = duration_reason is None
    duration_days = (
        (actual - purchase).total_seconds() / 86_400
        if duration_eligible and actual is not None and purchase is not None
        else None
    )
    return OrderDeliveryMetric(
        order_id=order_id,
        delivered=status == "delivered",
        delivery_classification=classification,
        delivery_eligible=delivery_eligible,
        days_early_or_late=days_early_or_late,
        duration_eligible=duration_eligible,
        delivery_duration_days=duration_days,
        duration_exclusion_reason=duration_reason,
        delivery_exclusion_reason=delivery_reason,
    )


@dataclass(frozen=True, slots=True)
class DeliveryKpis:
    """Aggregated delivery KPIs with explicit denominators."""

    all_orders: int
    delivered_orders: int
    delivery_eligible_orders: int
    on_time_orders: int
    late_orders: int
    on_time_rate: float | None
    late_rate: float | None
    duration_eligible_orders: int
    average_delivery_days: float | None
    median_delivery_days: float | None
    p90_delivery_days: float | None
    p95_delivery_days: float | None
    average_days_late: float | None

    @property
    def source_order_count(self) -> int:
        return self.all_orders

    @property
    def eligible_order_count(self) -> int:
        return self.delivery_eligible_orders

    @property
    def delivery_status_excluded_orders(self) -> int:
        return self.all_orders - self.delivery_eligible_orders

    @property
    def duration_excluded_orders(self) -> int:
        return self.all_orders - self.duration_eligible_orders

    @property
    def on_time_order_count(self) -> int:
        return self.on_time_orders

    @property
    def late_order_count(self) -> int:
        return self.late_orders

    @property
    def duration_eligible_order_count(self) -> int:
        return self.duration_eligible_orders

    @property
    def average_delivery_hours(self) -> float | None:
        return self.average_delivery_days * 24 if self.average_delivery_days is not None else None

    @property
    def median_delivery_hours(self) -> float | None:
        return self.median_delivery_days * 24 if self.median_delivery_days is not None else None

    @property
    def p90_delivery_hours(self) -> float | None:
        return self.p90_delivery_days * 24 if self.p90_delivery_days is not None else None

    @property
    def p95_delivery_hours(self) -> float | None:
        return self.p95_delivery_days * 24 if self.p95_delivery_days is not None else None


def aggregate_delivery_kpis(
    outcomes: Iterable[OrderDeliveryMetric | Mapping[str, Any]],
) -> DeliveryKpis:
    """Aggregate outcomes while keeping delivery and duration denominators separate."""

    materialized = tuple(
        item if isinstance(item, OrderDeliveryMetric) else classify_order(item) for item in outcomes
    )
    eligible = tuple(item for item in materialized if item.delivery_eligible)
    on_time = tuple(item for item in eligible if item.delivery_classification == "On Time")
    late = tuple(item for item in eligible if item.delivery_classification == "Late")
    durations = [
        item.delivery_duration_days
        for item in materialized
        if item.delivery_duration_days is not None
    ]
    late_days = [
        float(item.days_early_or_late) for item in late if item.days_early_or_late is not None
    ]
    denominator = len(eligible)
    return DeliveryKpis(
        all_orders=len(materialized),
        delivered_orders=sum(item.delivered for item in materialized),
        delivery_eligible_orders=denominator,
        on_time_orders=len(on_time),
        late_orders=len(late),
        on_time_rate=len(on_time) / denominator if denominator else None,
        late_rate=len(late) / denominator if denominator else None,
        duration_eligible_orders=len(durations),
        average_delivery_days=fmean(durations) if durations else None,
        median_delivery_days=median(durations) if durations else None,
        p90_delivery_days=percentile_cont(durations, 0.90),
        p95_delivery_days=percentile_cont(durations, 0.95),
        average_days_late=fmean(late_days) if late_days else None,
    )


def aggregate_delivery_metrics(
    orders: Iterable[Mapping[str, Any] | OrderDeliveryMetric],
) -> dict[str, Any]:
    """Return the SQL-facing mapping used by the reconciliation CLI."""

    materialized = tuple(orders)
    outcomes = tuple(
        item if isinstance(item, OrderDeliveryMetric) else classify_order(item)
        for item in materialized
    )
    metrics = aggregate_delivery_kpis(outcomes)
    return {
        "source_order_count": metrics.all_orders,
        "delivered_order_count": metrics.delivered_orders,
        "eligible_order_count": metrics.delivery_eligible_orders,
        "delivery_status_excluded_order_count": metrics.delivery_status_excluded_orders,
        "on_time_order_count": metrics.on_time_orders,
        "late_order_count": metrics.late_orders,
        "on_time_delivery_rate": metrics.on_time_rate,
        "late_delivery_rate": metrics.late_rate,
        "duration_eligible_order_count": metrics.duration_eligible_orders,
        "duration_excluded_order_count": metrics.duration_excluded_orders,
        "average_delivery_hours": (
            metrics.average_delivery_days * 24
            if metrics.average_delivery_days is not None
            else None
        ),
        "median_delivery_hours": (
            metrics.median_delivery_days * 24 if metrics.median_delivery_days is not None else None
        ),
        "p90_delivery_hours": (
            metrics.p90_delivery_days * 24 if metrics.p90_delivery_days is not None else None
        ),
        "p95_delivery_hours": (
            metrics.p95_delivery_days * 24 if metrics.p95_delivery_days is not None else None
        ),
        "average_days_late": metrics.average_days_late,
    }


def select_review_for_order(
    reviews: Iterable[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Select one usable review using the documented deterministic ordering."""

    return select_review(reviews)


def build_order_seller_bridge(
    items: Iterable[Mapping[str, Any]],
) -> set[tuple[str, str]]:
    """Build the distinct order/seller attribution bridge."""

    return distinct_order_sellers(items)


def build_order_category_bridge(
    items: Iterable[Mapping[str, Any]],
    products: Iterable[Mapping[str, Any]],
) -> set[tuple[str, str]]:
    """Build the distinct order/category attribution bridge."""

    missing_category = "(Missing category)"
    categories = {
        str(product.get("product_id")): (
            str(product.get("product_category_name") or "").strip() or missing_category
        )
        for product in products
        if product.get("product_id")
    }
    return {
        (str(item["order_id"]), category)
        for item in items
        if item.get("order_id")
        and str(item.get("product_id") or "").strip()
        and (category := categories.get(str(item.get("product_id")), missing_category))
    }

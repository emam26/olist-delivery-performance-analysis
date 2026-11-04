"""Authoritative source-file and column contracts for the Olist dataset."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """One source CSV contract and its declared business grain."""

    name: str
    filename: str
    columns: tuple[str, ...]
    natural_key: tuple[str, ...]
    timestamp_columns: tuple[str, ...] = ()

    @property
    def key_columns(self) -> tuple[str, ...]:
        """Compatibility name for the declared natural key."""

        return self.natural_key


DATASET_SPECS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        "orders",
        "olist_orders_dataset.csv",
        (
            "order_id",
            "customer_id",
            "order_status",
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
        ("order_id",),
        (
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ),
    ),
    DatasetSpec(
        "order_items",
        "olist_order_items_dataset.csv",
        (
            "order_id",
            "order_item_id",
            "product_id",
            "seller_id",
            "shipping_limit_date",
            "price",
            "freight_value",
        ),
        ("order_id", "order_item_id"),
        ("shipping_limit_date",),
    ),
    DatasetSpec(
        "customers",
        "olist_customers_dataset.csv",
        (
            "customer_id",
            "customer_unique_id",
            "customer_zip_code_prefix",
            "customer_city",
            "customer_state",
        ),
        ("customer_id",),
    ),
    DatasetSpec(
        "sellers",
        "olist_sellers_dataset.csv",
        (
            "seller_id",
            "seller_zip_code_prefix",
            "seller_city",
            "seller_state",
        ),
        ("seller_id",),
    ),
    DatasetSpec(
        "products",
        "olist_products_dataset.csv",
        (
            "product_id",
            "product_category_name",
            "product_name_lenght",
            "product_description_lenght",
            "product_photos_qty",
            "product_weight_g",
            "product_length_cm",
            "product_height_cm",
            "product_width_cm",
        ),
        ("product_id",),
    ),
    DatasetSpec(
        "reviews",
        "olist_order_reviews_dataset.csv",
        (
            "review_id",
            "order_id",
            "review_score",
            "review_comment_title",
            "review_comment_message",
            "review_creation_date",
            "review_answer_timestamp",
        ),
        ("review_id", "order_id"),
        ("review_creation_date", "review_answer_timestamp"),
    ),
)

DATASETS_BY_NAME = {spec.name: spec for spec in DATASET_SPECS}

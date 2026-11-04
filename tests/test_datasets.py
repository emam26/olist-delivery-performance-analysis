import pytest

from olist_delivery.datasets import DATASET_SPECS


def _spec(name: str):
    return next(spec for spec in DATASET_SPECS if spec.name == name)


def test_six_required_source_contracts_are_unique() -> None:
    assert len(DATASET_SPECS) == 6
    assert len({spec.name for spec in DATASET_SPECS}) == 6
    assert len({spec.filename for spec in DATASET_SPECS}) == 6


def test_customer_and_product_source_spellings_are_explicit() -> None:
    customers = _spec("customers")
    products = _spec("products")

    assert customers.natural_key == ("customer_id",)
    assert customers.required_identifiers == ("customer_id",)
    assert _spec("order_items").required_identifiers == (
        "order_id",
        "order_item_id",
        "product_id",
        "seller_id",
    )
    assert "customer_unique_id" in customers.columns
    assert "product_name_lenght" in products.columns
    assert "product_description_lenght" in products.columns


def test_unknown_dataset_is_not_in_the_controlled_contract() -> None:
    with pytest.raises(StopIteration):
        _spec("unknown")

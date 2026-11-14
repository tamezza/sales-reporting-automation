"""End-to-end checks of the full cleaning pipeline on the real raw data.

Run from the project root:  python -m pytest -v
"""
from pathlib import Path

import pytest

from sales_report.cleaning import clean_sales

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cleaned():
    return clean_sales(ROOT / "data/raw/monthly_sales", ROOT / "data/reference")


def test_rows_reconcile(cleaned):
    df, log = cleaned
    assert log.rows_clean == log.rows_raw - log.duplicates_removed
    assert len(df) == log.rows_clean


def test_no_duplicates_left(cleaned):
    df, _ = cleaned
    assert not df.duplicated(subset=["order_id", "product_id", "customer_id"]).any()


def test_no_missing_values_in_key_columns(cleaned):
    df, _ = cleaned
    key = ["order_date", "region", "amount_eur", "qty", "category", "segment"]
    assert df[key].notna().all().all()


def test_imputed_quantity_is_consistent_with_amount(cleaned):
    df, log = cleaned
    imp = df[df["qty_imputed"]]
    assert len(imp) == log.missing_qty_imputed > 0
    rebuilt = imp["qty"] * imp["unit_price"] * (1 - imp["discount"])
    assert (rebuilt - imp["amount_eur"]).abs().max() < 0.05


def test_region_in_order_matches_customer_region(cleaned):
    df, _ = cleaned
    assert (df["region"] == df["customer_region"]).all()
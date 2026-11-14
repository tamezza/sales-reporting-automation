"""Load the raw monthly exports and turn them into one clean, enriched table.

Every correction is counted, so the report can show a data-quality summary
instead of fixing problems silently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

RAW_COLUMNS = {
    "Order ID": "order_id",
    "Order Date": "order_date",
    "Customer ID": "customer_id",
    "Region": "region",
    "Product ID": "product_id",
    "Qty": "qty",
    "Discount": "discount",
    "Amount EUR": "amount_eur",
}


@dataclass
class QualityLog:
    """Counts of every issue found and how it was handled."""

    files_loaded: int = 0
    rows_raw: int = 0
    duplicates_removed: int = 0
    iso_dates_converted: int = 0
    regions_standardised: int = 0
    decimal_commas_fixed: int = 0
    missing_qty_imputed: int = 0
    unknown_products: int = 0
    unknown_customers: int = 0
    rows_clean: int = 0
    notes: list[str] = field(default_factory=list)

    def as_table(self) -> pd.DataFrame:
        labels = {
            "files_loaded": "Monthly files loaded",
            "rows_raw": "Raw rows",
            "duplicates_removed": "Duplicate order lines removed",
            "iso_dates_converted": "Dates in yyyy-mm-dd format converted",
            "regions_standardised": "Region names standardised (spaces / case)",
            "decimal_commas_fixed": "Amounts with decimal comma fixed",
            "missing_qty_imputed": "Missing quantities imputed from amount and price",
            "unknown_products": "Rows with unknown product ID",
            "unknown_customers": "Rows with unknown customer ID",
            "rows_clean": "Clean rows",
        }
        return pd.DataFrame(
            [(labels[k], getattr(self, k)) for k in labels], columns=["Check", "Count"]
        )


def load_raw(folder: str | Path) -> tuple[pd.DataFrame, int]:
    """Read every sales_*.csv file in a folder (all columns as text)."""
    files = sorted(Path(folder).glob("sales_*.csv"))
    if not files:
        raise FileNotFoundError(f"No sales_*.csv files found in {folder}")
    frames = []
    for f in files:
        df = pd.read_csv(f, sep=";", dtype=str, keep_default_na=False)
        df["source_file"] = f.name
        frames.append(df)
    return pd.concat(frames, ignore_index=True), len(files)


def parse_dates(s: pd.Series) -> tuple[pd.Series, int]:
    """Parse a mix of dd/mm/yyyy and yyyy-mm-dd strings."""
    s = s.str.strip()
    iso_mask = s.str.match(r"^\d{4}-\d{2}-\d{2}$")
    out = pd.to_datetime(s.where(~iso_mask), format="%d/%m/%Y", errors="coerce")
    out = out.fillna(pd.to_datetime(s.where(iso_mask), format="%Y-%m-%d", errors="coerce"))
    return out, int(iso_mask.sum())


def standardise_regions(s: pd.Series, valid: list[str]) -> tuple[pd.Series, int]:
    """Trim spaces and map any capitalisation back to the official region name.

    A mapping is used instead of str.title() because title() would turn "UK" into "Uk".
    """
    canonical = {r.casefold(): r for r in valid}
    cleaned = s.str.strip().str.casefold().map(canonical)
    changed = int((cleaned != s).sum())
    return cleaned, changed


def to_amount(s: pd.Series) -> tuple[pd.Series, int]:
    """Convert '12,50' or '12.50' strings to floats."""
    commas = int(s.str.contains(",", regex=False).sum())
    return pd.to_numeric(s.str.replace(",", ".", regex=False)), commas


def clean_sales(raw_folder: str | Path, reference_folder: str | Path) -> tuple[pd.DataFrame, QualityLog]:
    """Full cleaning pipeline. Returns the clean table and the quality log."""
    ref = Path(reference_folder)
    products = pd.read_csv(ref / "products.csv")
    customers = pd.read_csv(ref / "customers.csv")
    log = QualityLog()

    df, log.files_loaded = load_raw(raw_folder)
    log.rows_raw = len(df)
    df = df.rename(columns=RAW_COLUMNS)

    before = len(df)
    df = df.drop_duplicates(subset=list(RAW_COLUMNS.values()))
    log.duplicates_removed = before - len(df)

    df["order_date"], log.iso_dates_converted = parse_dates(df["order_date"])
    df["region"], log.regions_standardised = standardise_regions(
        df["region"], sorted(customers["Region"].unique())
    )
    df["amount_eur"], log.decimal_commas_fixed = to_amount(df["amount_eur"])
    df["discount"] = pd.to_numeric(df["discount"])
    df["qty"] = pd.to_numeric(df["qty"].replace("", pd.NA))

    # Enrich with reference data (the Python equivalent of XLOOKUP / Merge Queries)
    df = df.merge(
        products.rename(columns={"ProductID": "product_id", "ProductName": "product_name",
                                 "Category": "category", "UnitPrice_EUR": "unit_price"}),
        on="product_id", how="left", validate="many_to_one",
    )
    df = df.merge(
        customers.rename(columns={"CustomerID": "customer_id", "CustomerName": "customer_name",
                                  "Region": "customer_region", "Segment": "segment"}),
        on="customer_id", how="left", validate="many_to_one",
    )
    log.unknown_products = int(df["category"].isna().sum())
    log.unknown_customers = int(df["segment"].isna().sum())

    # Missing quantities can be recovered: qty = amount / (unit price x (1 - discount))
    missing = df["qty"].isna()
    df.loc[missing, "qty"] = (
        df.loc[missing, "amount_eur"] / (df.loc[missing, "unit_price"] * (1 - df.loc[missing, "discount"]))
    ).round()
    df["qty_imputed"] = missing
    log.missing_qty_imputed = int(missing.sum())
    df["qty"] = df["qty"].astype(int)

    # helper columns and the final return
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.to_period("M")
    df = df.sort_values(["order_date", "order_id"]).reset_index(drop=True)
    log.rows_clean = len(df)
    return df, log

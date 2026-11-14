"""Load the raw monthly exports and turn them into one clean, enriched table."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

# Raw column names -> clean names used everywhere in the code
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


def load_raw(folder: str | Path) -> tuple[pd.DataFrame, int]:
    """Read every sales_*.csv file in a folder, all columns as text.

    Returns the stacked table (with a source_file column) and the number of files read.
    """
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
    """Parse a mix of dd/mm/yyyy and yyyy-mm-dd strings.

    Each format is parsed explicitly, never guessed. Returns the dates and
    the number of ISO (yyyy-mm-dd) values converted. Invalid dates become NaT.
    """
    s = s.str.strip()
    iso_mask = s.str.match(r"^\d{4}-\d{2}-\d{2}$")
    out = pd.to_datetime(s.where(~iso_mask), format="%d/%m/%Y", errors="coerce")
    out = out.fillna(pd.to_datetime(s.where(iso_mask), format="%Y-%m-%d", errors="coerce"))
    return out, int(iso_mask.sum())

def standardise_regions(s: pd.Series, valid: list[str]) -> tuple[pd.Series, int]:
    """Trim spaces and map any capitalisation back to the official region name.

    A mapping is used instead of str.title() because title() would turn "UK" into "Uk".
    Unknown regions become NaN. Returns the regions and the number of values changed.
    """
    canonical = {r.casefold(): r for r in valid}
    cleaned = s.str.strip().str.casefold().map(canonical)
    changed = int((cleaned != s).sum())
    return cleaned, changed

def to_amount(s: pd.Series) -> tuple[pd.Series, int]:
    """Convert '12,50' or '12.50' strings to floats.

    Returns the amounts and the number of decimal commas fixed.
    Raises an error if a value is still not a number after the fix.
    """
    commas = int(s.str.contains(",", regex=False).sum())
    return pd.to_numeric(s.str.replace(",", ".", regex=False)), commas

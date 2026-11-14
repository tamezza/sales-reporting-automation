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
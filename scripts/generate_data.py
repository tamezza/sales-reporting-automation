"""Generate the synthetic sales dataset used in this project.

The company ("NordFood Distribution") is fictional. Orders are random but follow
realistic patterns (end of year peak (November-December), summer dip (July-August), ~6% growth in 2026), and the monthly
Output is reproducible: a fixed seed (SEED = 42) produces identical files on every run.

Output (relative to the project):
    data/reference/products.csv       30 products in 5 categories
    data/reference/customers.csv      80 customers with region and segment
    data/reference/market_size.csv    market size by year, region and category
    data/raw/monthly_sales/           sales_YYYY_MM.csv, Jan 2025 - Aug 2026
    data/raw/new_month/               sales_2026_09.csv, held back to demo
                                      an automatic report refresh

The monthly exports are ";"-separated and contain deliberate data-quality
issues, like real ERP extracts:

* mixed date formats (dd/mm/yyyy and yyyy-mm-dd)
* region names in capitals or with extra spaces 
* some amounts written with a decimal comma
* a few empty quantities
* duplicated order lines

Usage:
    python scripts/generate_data.py   # writes into data/
"""
from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REF = ROOT / "data" / "reference"

REGIONS = ["France", "Germany", "Italy", "Spain", "Benelux", "UK"]
SEGMENTS = ["Retail", "Wholesale", "Online", "Hospitality"]
CATEGORIES = {"Coffee": 18.0, "Tea": 9.5, "Snacks": 6.0, "Beverages": 4.2, "Dairy": 3.1}
HEADER = ["Order ID", "Order Date", "Customer ID", "Region", "Product ID",
          "Qty", "Discount", "Amount EUR"]


def main() -> None:
    rng = random.Random(SEED)
    for d in (RAW / "monthly_sales", RAW / "new_month", REF):
        d.mkdir(parents=True, exist_ok=True)

    # Reference tables -------------------------------------------------------
    products, pid = [], 100
    for cat, base_price in CATEGORIES.items():
        for i in range(6):
            pid += 1
            price = round(base_price * rng.uniform(0.7, 1.5), 2)
            products.append((f"P{pid}", f"{cat} item {i + 1}", cat, price))
    customers = [(f"C{i:03d}", f"Client {i:03d}", rng.choice(REGIONS), rng.choice(SEGMENTS))
                 for i in range(1, 81)]

    _write(REF / "products.csv", ["ProductID", "ProductName", "Category", "UnitPrice_EUR"], products)
    _write(REF / "customers.csv", ["CustomerID", "CustomerName", "Region", "Segment"], customers)
    market = [(y, r, c, rng.randint(900, 2500) * 1000)
              for y in (2025, 2026) for r in REGIONS for c in CATEGORIES]
    _write(REF / "market_size.csv", ["Year", "Region", "Category", "MarketSize_EUR"], market)

    # Monthly order exports ----------------------------------------------------
    months = [(2025, m) for m in range(1, 13)] + [(2026, m) for m in range(1, 10)]
    order_id = 50000
    for year, month in months:
        season = 1.25 if month in (11, 12) else (0.85 if month in (7, 8) else 1.0)
        growth = 1.0 if year == 2025 else 1.06
        rows = []
        for _ in range(int(rng.randint(260, 320) * season * growth)):
            order_id += 1
            prod, cust = rng.choice(products), rng.choice(customers)
            date = dt.date(year, month, rng.randint(1, 28))
            qty = rng.randint(5, 120)
            disc = rng.choice([0, 0, 0, 0.05, 0.10])
            amount = round(qty * prod[3] * (1 - disc), 2)

            # deliberate data-quality issues
            date_s = date.strftime("%d/%m/%Y") if rng.random() > 0.15 else date.isoformat()
            region, r = cust[2], rng.random()
            if r < 0.05:
                region = region.upper()
            elif r < 0.10:
                region = f" {region} "
            amount_s = f"{amount:.2f}"
            if rng.random() < 0.10:
                amount_s = amount_s.replace(".", ",")
            qty_s = "" if rng.random() < 0.02 else str(qty)
            rows.append([f"O{order_id}", date_s, cust[0], region, prod[0],
                         qty_s, f"{disc:.2f}", amount_s])
        rows += rng.sample(rows, 4)  # duplicated lines
        rng.shuffle(rows)

        # The last month is kept aside to demonstrate an automatic refresh.
        folder = "new_month" if (year, month) == months[-1] else "monthly_sales"
        _write(RAW / folder / f"sales_{year}_{month:02d}.csv", HEADER, rows, delimiter=";")

    print(f"Generated {len(months)} monthly files, {len(products)} products, "
          f"{len(customers)} customers.")


def _write(path: Path, header: list[str], rows, delimiter: str = ",") -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=delimiter)
        writer.writerow(header)
        writer.writerows(rows)


if __name__ == "__main__":
    main()

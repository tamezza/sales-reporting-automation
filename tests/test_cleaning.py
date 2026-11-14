"""Unit tests for the cleaning functions.

Run from the project root:  pytest -v
"""
import pandas as pd
import pytest

from sales_report.cleaning import load_raw, parse_dates, standardise_regions, to_amount

REGIONS = ["Benelux", "France", "Germany", "Italy", "Spain", "UK"]


# ---------- load_raw ----------

def test_load_raw_reads_every_file(tmp_path):
    header = "Order ID;Order Date;Region\n"
    (tmp_path / "sales_2025_01.csv").write_text(header + "O1;02/01/2025;France\n")
    (tmp_path / "sales_2025_02.csv").write_text(header + "O2;03/02/2025;UK\nO3;04/02/2025;Spain\n")

    df, n_files = load_raw(tmp_path)

    assert n_files == 2
    assert len(df) == 3
    assert list(df["source_file"]) == ["sales_2025_01.csv", "sales_2025_02.csv", "sales_2025_02.csv"]


def test_load_raw_empty_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_raw(tmp_path)


# ---------- parse_dates ----------

def test_parse_dates_handles_both_formats():
    raw = pd.Series(["03/02/2026", "2026-02-03", " 28/12/2025 "])

    dates, n_iso = parse_dates(raw)

    assert list(dates.dt.strftime("%Y-%m-%d")) == ["2026-02-03", "2026-02-03", "2025-12-28"]
    assert n_iso == 1


def test_parse_dates_never_swaps_day_and_month():
    dates, _ = parse_dates(pd.Series(["03/02/2026"]))
    assert dates.iloc[0].day == 3 and dates.iloc[0].month == 2


def test_parse_dates_invalid_date_becomes_missing():
    dates, _ = parse_dates(pd.Series(["31/02/2026"]))
    assert dates.isna().all()


# ---------- standardise_regions ----------

def test_regions_keep_official_spelling():
    raw = pd.Series([" france ", "UK", "uk", "GERMANY", "Spain"])

    regions, changed = standardise_regions(raw, REGIONS)

    assert list(regions) == ["France", "UK", "UK", "Germany", "Spain"]
    assert changed == 3


def test_unknown_region_becomes_missing():
    regions, _ = standardise_regions(pd.Series(["Narnia"]), REGIONS)
    assert regions.isna().all()


# ---------- to_amount ----------

def test_to_amount_fixes_decimal_comma():
    amounts, n_commas = to_amount(pd.Series(["12,50", "7.25", "1294,84"]))

    assert list(amounts) == [12.5, 7.25, 1294.84]
    assert n_commas == 2


def test_to_amount_rejects_text():
    with pytest.raises(ValueError):
        to_amount(pd.Series(["twelve"]))
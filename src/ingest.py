"""Supplier data ingestion and standardization module.

Reads raw CSV files from disparate suppliers, maps heterogeneous schemas to a
common staging representation, normalizes currencies and units of measurement,
and parses timestamps into unified UTC ISO format.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from config.settings import (
    CATEGORY_NORMALIZATION_MAP,
    CURRENCY_EXCHANGE_RATES,
    DEFAULT_CATEGORY,
    SUPPLIER_CONFIGS,
    WEIGHT_CONVERSION_TO_KG,
)


def parse_timestamp_safe(ts_series: pd.Series) -> pd.Series:
    """Robustly parse timestamps of varying formats into UTC ISO-8601 strings.

    Returns pd.NaT for unparseable dates.
    """
    try:
        parsed = pd.to_datetime(ts_series, format="mixed", errors="coerce", utc=True)
    except Exception:
        parsed = pd.to_datetime(ts_series, errors="coerce", utc=True)
    return parsed


def normalize_category(cat_val: Optional[str]) -> str:
    """Map arbitrary supplier category strings to canonical taxonomy."""
    if not isinstance(cat_val, str) or not cat_val.strip():
        return DEFAULT_CATEGORY
    cleaned = cat_val.strip().lower()
    return CATEGORY_NORMALIZATION_MAP.get(cleaned, DEFAULT_CATEGORY)


def ingest_supplier_file(supplier_id: str, file_path: Path | str) -> pd.DataFrame:
    """Ingest a single supplier CSV file and normalize into internal staging format."""
    file_path = Path(file_path)
    if supplier_id not in SUPPLIER_CONFIGS:
        raise ValueError(f"Unknown supplier_id: '{supplier_id}'. Must be one of {list(SUPPLIER_CONFIGS.keys())}")

    config = SUPPLIER_CONFIGS[supplier_id]
    cols = config["columns"]
    weight_unit = config["weight_unit"]

    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found for {supplier_id}: {file_path}")

    # Read raw CSV as text to preserve exact values
    raw_df = pd.read_csv(file_path, dtype=str)

    # Capture raw JSON representation per row for audit/lineage/quarantine
    raw_json_records = [json.dumps(row) for row in raw_df.to_dict(orient="records")]

    staging_rows = []
    for idx, row in raw_df.iterrows():
        sku = str(row.get(cols["sku"], "")).strip()
        name = str(row.get(cols["name"], "")).strip()
        category_raw = str(row.get(cols["category"], "")).strip()
        price_raw_str = row.get(cols["price"])
        currency_raw = str(row.get(cols["currency"], "")).strip().upper()
        stock_raw_str = row.get(cols["stock"])
        weight_raw_str = row.get(cols["weight"])
        barcode_raw = str(row.get(cols["barcode"], "")).strip()
        ts_raw = str(row.get(cols["timestamp"], "")).strip()

        staging_rows.append({
            "supplier_id": supplier_id,
            "supplier_name": config["name"],
            "supplier_priority": config["priority"],
            "sku": sku if sku and sku.lower() != "nan" else None,
            "name": name if name and name.lower() != "nan" else None,
            "category_raw": category_raw if category_raw and category_raw.lower() != "nan" else None,
            "category_standardized": normalize_category(category_raw),
            "price_raw": price_raw_str,
            "currency_raw": currency_raw if currency_raw and currency_raw.lower() != "nan" else None,
            "stock_raw": stock_raw_str,
            "weight_raw": weight_raw_str,
            "weight_unit": weight_unit,
            "barcode_raw": barcode_raw if barcode_raw and barcode_raw.lower() != "nan" else None,
            "timestamp_raw": ts_raw if ts_raw and ts_raw.lower() != "nan" else None,
            "raw_json": raw_json_records[idx],
        })

    df = pd.DataFrame(staging_rows)

    # Numeric conversion: Price
    df["price_numeric"] = pd.to_numeric(df["price_raw"], errors="coerce")
    exchange_rates = df["currency_raw"].map(CURRENCY_EXCHANGE_RATES).fillna(np.nan)
    df["price_usd"] = (df["price_numeric"] * exchange_rates).round(2)

    # Numeric conversion: Stock
    df["stock_numeric"] = pd.to_numeric(df["stock_raw"], errors="coerce")

    # Numeric conversion: Weight
    df["weight_numeric"] = pd.to_numeric(df["weight_raw"], errors="coerce")
    weight_factor = WEIGHT_CONVERSION_TO_KG.get(weight_unit, 1.0)
    df["weight_kg"] = (df["weight_numeric"] * weight_factor).round(3)

    # Standardize Timestamps to UTC
    parsed_ts = parse_timestamp_safe(df["timestamp_raw"])
    df["timestamp_utc"] = parsed_ts
    df["timestamp_iso"] = parsed_ts.dt.strftime("%Y-%m-%d %H:%M:%SZ")

    return df


def ingest_all_suppliers(supplier_files: Dict[str, Path]) -> Dict[str, pd.DataFrame]:
    """Ingest multiple supplier CSV files, returning dictionary of standardized DataFrames."""
    results = {}
    for supplier_id, file_path in supplier_files.items():
        results[supplier_id] = ingest_supplier_file(supplier_id, Path(file_path))
    return results

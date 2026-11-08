"""Data validation and quarantine handling module.

Validates incoming supplier records against business rules, data type constraints,
and acceptable value ranges. Segregates clean records for ingestion and routes
defective records to quarantine storage with specific rejection reasons.
"""

from datetime import datetime, timezone
import hashlib
import re
from typing import List, Tuple
import numpy as np
import pandas as pd

from config.settings import VALIDATION_RULES


def is_valid_barcode(barcode_val: any) -> Tuple[bool, str]:
    """Validate GTIN / UPC / EAN barcode format.

    Barcodes must be 8 to 14 numeric digits. Missing barcodes are allowed
    (fallback mapping will be applied), but malformed barcodes must be quarantined.
    """
    if barcode_val is None or pd.isna(barcode_val):
        return True, ""  # Allowed to be missing (mapped to synthetic canonical ID)

    barcode_str = str(barcode_val).strip()
    if not barcode_str or barcode_str.lower() in ("nan", "none", "null"):
        return True, ""

    # Check numeric
    if not barcode_str.isdigit():
        return False, "BARCODE_NON_NUMERIC"

    # Check length (GTIN-8, GTIN-12, GTIN-13, GTIN-14)
    if len(barcode_str) not in (8, 12, 13, 14):
        return False, f"BARCODE_INVALID_LENGTH_{len(barcode_str)}"

    # Check all zeros
    if set(barcode_str) == {"0"}:
        return False, "BARCODE_ALL_ZEROS"

    return True, ""


def validate_records(
    df: pd.DataFrame,
    run_id: str = "",
    source_file: str = "",
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Validate a DataFrame of staged supplier records.

    Returns:
        (valid_df, quarantine_df)
    """
    if df.empty:
        empty_quarantine = pd.DataFrame(columns=[
            "quarantine_id", "run_id", "source_file", "supplier_id", "supplier_sku",
            "rejection_reasons", "raw_data", "failed_at"
        ])
        return df.copy(), empty_quarantine

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    rejection_reasons_list = []
    is_valid_mask = []

    for _, row in df.iterrows():
        reasons = []

        # 1. SKU validation
        sku = row.get("sku")
        if not sku or pd.isna(sku) or not str(sku).strip():
            reasons.append("MISSING_SKU")

        # 2. Product Name validation
        name = row.get("name")
        if not name or pd.isna(name) or not str(name).strip():
            reasons.append("MISSING_PRODUCT_NAME")

        # 3. Price validation
        price_usd = row.get("price_usd")
        if price_usd is None or pd.isna(price_usd):
            reasons.append("INVALID_PRICE_NULL_OR_UNPARSED")
        elif price_usd < VALIDATION_RULES["min_price"]:
            reasons.append("INVALID_PRICE_BELOW_MINIMUM")
        elif price_usd > VALIDATION_RULES["max_price"]:
            reasons.append("INVALID_PRICE_EXCEEDS_MAXIMUM")

        # 4. Currency validation
        curr = row.get("currency_raw")
        if not curr or curr not in VALIDATION_RULES["allowed_currencies"]:
            reasons.append(f"UNSUPPORTED_CURRENCY_{curr}")

        # 5. Stock quantity validation
        stock = row.get("stock_numeric")
        if stock is None or pd.isna(stock):
            reasons.append("INVALID_STOCK_NULL_OR_UNPARSED")
        elif stock < VALIDATION_RULES["min_stock"]:
            reasons.append("INVALID_STOCK_NEGATIVE")
        elif stock > VALIDATION_RULES["max_stock"]:
            reasons.append("INVALID_STOCK_EXCEEDS_MAX")
        elif not float(stock).is_integer():
            reasons.append("INVALID_STOCK_NON_INTEGER")

        # 6. Weight validation
        weight_kg = row.get("weight_kg")
        if weight_kg is not None and not pd.isna(weight_kg):
            if weight_kg < VALIDATION_RULES["min_weight_kg"]:
                reasons.append("INVALID_WEIGHT_BELOW_MIN")
            elif weight_kg > VALIDATION_RULES["max_weight_kg"]:
                reasons.append("INVALID_WEIGHT_EXCEEDS_MAX")

        # 7. Barcode validation
        barcode = row.get("barcode_raw")
        valid_bc, bc_reason = is_valid_barcode(barcode)
        if not valid_bc:
            reasons.append(bc_reason)

        # 8. Timestamp validation
        ts_utc = row.get("timestamp_utc")
        if ts_utc is None or pd.isna(ts_utc):
            reasons.append("INVALID_OR_MISSING_TIMESTAMP")

        if reasons:
            is_valid_mask.append(False)
            rejection_reasons_list.append("; ".join(reasons))
        else:
            is_valid_mask.append(True)
            rejection_reasons_list.append("")

    is_valid_mask = np.array(is_valid_mask)
    valid_df = df[is_valid_mask].copy().reset_index(drop=True)
    invalid_df = df[~is_valid_mask].copy().reset_index(drop=True)

    if not invalid_df.empty:
        invalid_reasons = [r for r, v in zip(rejection_reasons_list, is_valid_mask) if not v]
        quarantine_rows = []
        for i, row in invalid_df.iterrows():
            raw_str = str(row.get("raw_json", "{}"))
            raw_hash = hashlib.md5(raw_str.encode("utf-8")).hexdigest()[:12]
            supp_id = str(row.get("supplier_id") or "unknown")
            supp_sku = str(row.get("sku") or "UNKNOWN")
            file_name = source_file or f"{supp_id}.csv"
            q_id = f"QUAR-{run_id}-{supp_id}-{raw_hash}"

            quarantine_rows.append({
                "quarantine_id": q_id,
                "run_id": run_id,
                "source_file": file_name,
                "supplier_id": supp_id,
                "supplier_sku": supp_sku,
                "rejection_reasons": invalid_reasons[i],
                "raw_data": raw_str,
                "failed_at": now_utc,
            })
        quarantine_df = pd.DataFrame(quarantine_rows)
    else:
        quarantine_df = pd.DataFrame(columns=[
            "quarantine_id", "run_id", "source_file", "supplier_id", "supplier_sku",
            "rejection_reasons", "raw_data", "failed_at"
        ])

    return valid_df, quarantine_df

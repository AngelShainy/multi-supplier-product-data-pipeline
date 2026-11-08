"""Product code mapping and canonical ID generation module.

Resolves heterogeneous supplier SKUs and varied barcode representations
(GTIN-12 UPC, GTIN-13 EAN, GTIN-14) into globally unique, deterministic
Canonical Product IDs. Supports pre-established cross-reference mappings.
"""

import hashlib
from pathlib import Path
import re
from typing import Dict, Optional, Tuple
import pandas as pd


def normalize_gtin(barcode_val: any) -> Optional[str]:
    """Normalize UPC/EAN/GTIN into standard 14-digit GTIN format.

    Pads 8, 12, and 13 digit barcodes with leading zeros.
    Returns None if missing or invalid.
    """
    if barcode_val is None or pd.isna(barcode_val):
        return None

    cleaned = str(barcode_val).strip()
    if not cleaned or not cleaned.isdigit():
        return None

    length = len(cleaned)
    if length in (8, 12, 13, 14):
        return cleaned.zfill(14)

    return None


def generate_fallback_id(name: str, category: str) -> str:
    """Generate deterministic canonical ID from normalized name and category when GTIN is absent."""
    norm_name = re.sub(r"\s+", " ", (name or "").strip().lower())
    norm_cat = re.sub(r"\s+", " ", (category or "").strip().lower())
    token = f"{norm_name}|{norm_cat}"
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:12].upper()
    return f"PROD-NOM-{digest}"


def load_identifier_mapping(mapping_path: Optional[Path] = None) -> Dict[Tuple[str, str], Tuple[str, Optional[str]]]:
    """Load pre-established product identifier cross-reference mapping file."""
    if not mapping_path:
        return {}
    path = Path(mapping_path)
    if not path.exists():
        return {}

    df_map = pd.read_csv(path, dtype=str)
    res = {}
    for _, row in df_map.iterrows():
        s_id = str(row.get("supplier_id", "")).strip()
        sku = str(row.get("supplier_sku", "")).strip()
        cid = str(row.get("canonical_product_id", "")).strip()
        gtin_raw = row.get("gtin")
        gtin_14 = normalize_gtin(gtin_raw) if pd.notna(gtin_raw) else None
        if s_id and sku and cid:
            res[(s_id, sku)] = (cid, gtin_14)
    return res


def map_to_canonical_id(
    row: pd.Series,
    mapping_dict: Optional[Dict[Tuple[str, str], Tuple[str, Optional[str]]]] = None,
) -> Tuple[str, Optional[str]]:
    """Determine canonical product ID and normalized GTIN for a given record.

    Checks explicit cross-reference mapping first; otherwise resolves via GTIN-14 normalization.
    """
    # 1. Check explicit identifier mapping file
    s_id = str(row.get("supplier_id", "")).strip()
    sku = str(row.get("sku", "")).strip()
    if mapping_dict and (s_id, sku) in mapping_dict:
        return mapping_dict[(s_id, sku)]

    # 2. Derive from barcode GTIN
    barcode = row.get("barcode_raw")
    gtin_14 = normalize_gtin(barcode)

    if gtin_14:
        canonical_id = f"PROD-{gtin_14}"
    else:
        name = str(row.get("name", ""))
        cat = str(row.get("category_standardized", ""))
        canonical_id = generate_fallback_id(name, cat)

    return canonical_id, gtin_14


def apply_canonical_mapping(
    df: pd.DataFrame,
    mapping_dict: Optional[Dict[Tuple[str, str], Tuple[str, Optional[str]]]] = None,
) -> pd.DataFrame:
    """Enrich validated DataFrame with canonical_product_id and gtin_14."""
    if df.empty:
        df["canonical_product_id"] = []
        df["gtin_14"] = []
        return df

    mapped = [map_to_canonical_id(row, mapping_dict=mapping_dict) for _, row in df.iterrows()]
    df = df.copy()
    df["canonical_product_id"] = [m[0] for m in mapped]
    df["gtin_14"] = [m[1] for m in mapped]
    return df

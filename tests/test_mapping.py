"""Unit tests for barcode normalization and canonical product ID mapping."""
from pathlib import Path
import pandas as pd
from src.mapping import (
    normalize_gtin,
    generate_fallback_id,
    apply_canonical_mapping,
    load_identifier_mapping,
)


def test_normalize_gtin_pads_to_14_digits():
    """Verify GTIN-12, GTIN-13, and GTIN-14 are unified into standard 14 digits."""
    # 12 digits (UPC)
    assert normalize_gtin("987654321098") == "00987654321098"
    # 13 digits (EAN)
    assert normalize_gtin("0987654321098") == "00987654321098"
    # 14 digits (GTIN-14)
    assert normalize_gtin("00987654321098") == "00987654321098"
    # Invalid
    assert normalize_gtin("ABC123") is None
    assert normalize_gtin(None) is None


def test_cross_supplier_barcode_harmonization():
    """Verify that different barcode formats across suppliers map to identical Canonical ID."""
    df = pd.DataFrame([
        {
            "sku": "APX-002",
            "name": "Apex Ergonomic Mouse",
            "category_standardized": "Electronics",
            "barcode_raw": "0987654321098",  # EAN-13
        },
        {
            "sku": "BCN-501",
            "name": "Beacon Ergonomic Optical Mouse",
            "category_standardized": "Electronics",
            "barcode_raw": "987654321098",   # UPC-12
        },
        {
            "sku": "CR-901",
            "name": "Crest Mouse Ergonomic",
            "category_standardized": "Electronics",
            "barcode_raw": "00987654321098",
        },
    ])

    mapped = apply_canonical_mapping(df)
    # All 3 must yield the exact same canonical_product_id!
    canonical_ids = mapped["canonical_product_id"].unique()
    assert len(canonical_ids) == 1
    assert canonical_ids[0] == "PROD-00987654321098"


def test_fallback_id_generation():
    """Verify deterministic fallback ID is generated when barcode is missing."""
    df = pd.DataFrame([
        {
            "sku": "APX-NO-BC",
            "name": "Custom Unbranded Cable",
            "category_standardized": "Electronics",
            "barcode_raw": None,
        }
    ])
    mapped = apply_canonical_mapping(df)
    cid = mapped.iloc[0]["canonical_product_id"]
    assert cid.startswith("PROD-NOM-")
    assert mapped.iloc[0]["gtin_14"] is None


def test_load_identifier_mapping(temp_dir):
    """Verify loading and applying explicit cross-reference mapping."""
    map_csv = temp_dir / "xref.csv"
    pd.DataFrame([
        {
            "supplier_id": "supplier_a",
            "supplier_sku": "SKU-999",
            "canonical_product_id": "PROD-EXPLICIT-999",
            "gtin": "123456789012",
        }
    ]).to_csv(map_csv, index=False)

    mapping = load_identifier_mapping(map_csv)
    assert ("supplier_a", "SKU-999") in mapping
    cid, gtin14 = mapping[("supplier_a", "SKU-999")]
    assert cid == "PROD-EXPLICIT-999"
    assert gtin14 == "00123456789012"

    df = pd.DataFrame([
        {"supplier_id": "supplier_a", "sku": "SKU-999", "name": "Mapped Item", "barcode_raw": "9999"}
    ])
    mapped_df = apply_canonical_mapping(df, mapping_dict=mapping)
    assert mapped_df.iloc[0]["canonical_product_id"] == "PROD-EXPLICIT-999"

"""Unit tests for intra-supplier deduplication."""
import pandas as pd
from src.deduplication import deduplicate_supplier_records, deduplicate_all_suppliers


def test_intra_supplier_deduplication_keeps_latest():
    """Verify that intra-supplier duplicates keep the row with the most recent timestamp."""
    df = pd.DataFrame([
        {
            "supplier_id": "supplier_a",
            "sku": "APX-001",
            "canonical_product_id": "PROD-0001",
            "name": "Apex Wireless Keyboard Old",
            "price_usd": 49.00,
            "timestamp_utc": pd.to_datetime("2026-10-31T08:00:00Z"),
        },
        {
            "supplier_id": "supplier_a",
            "sku": "APX-001",
            "canonical_product_id": "PROD-0001",
            "name": "Apex Wireless Keyboard New",
            "price_usd": 45.00,
            "timestamp_utc": pd.to_datetime("2026-11-01T10:00:00Z"),
        },
    ])

    deduped, removed_count = deduplicate_supplier_records(df)

    assert len(deduped) == 1
    assert removed_count == 1
    # Latest record must win
    assert deduped.iloc[0]["name"] == "Apex Wireless Keyboard New"
    assert deduped.iloc[0]["price_usd"] == 45.00


def test_deduplicate_all_suppliers():
    """Verify multi-supplier deduplication dictionary stats."""
    dfs = {
        "supplier_a": pd.DataFrame([
            {"supplier_id": "supplier_a", "sku": "A1", "canonical_product_id": "P1", "timestamp_utc": pd.to_datetime("2026-11-01")},
            {"supplier_id": "supplier_a", "sku": "A1", "canonical_product_id": "P1", "timestamp_utc": pd.to_datetime("2026-11-02")},
        ]),
        "supplier_b": pd.DataFrame([
            {"supplier_id": "supplier_b", "sku": "B1", "canonical_product_id": "P2", "timestamp_utc": pd.to_datetime("2026-11-01")},
        ]),
    }

    combined, stats = deduplicate_all_suppliers(dfs)
    assert len(combined) == 2
    assert stats["supplier_a"] == 1
    assert stats["supplier_b"] == 0

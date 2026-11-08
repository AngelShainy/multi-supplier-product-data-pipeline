"""Unit tests for conflict resolution and attribute-level source lineage."""
import json
import pandas as pd
from src.conflict_resolution import resolve_conflicts_for_group, resolve_all_conflicts


def test_conflict_resolution_supplier_priority():
    """Verify that Supplier Priority 1 takes precedence over Priority 2 for master attributes."""
    # Two suppliers supplying the same product:
    # Supplier A: Priority 1, price 30.00 USD, stock 50, name 'Apex Monitor Arm'
    # Supplier B: Priority 2, price 25.00 USD, stock 40, name 'Beacon Arm Mount'
    records = pd.DataFrame([
        {
            "supplier_id": "supplier_a",
            "supplier_priority": 1,
            "sku": "APX-ARM",
            "canonical_product_id": "PROD-12345",
            "gtin_14": "00000000012345",
            "name": "Apex Monitor Arm",
            "category_standardized": "Office Supplies",
            "category_raw": "office",
            "price_usd": 30.00,
            "price_raw": "30.00",
            "currency_raw": "USD",
            "stock_numeric": 50,
            "weight_kg": 2.500,
            "weight_raw": "2.500",
            "weight_unit": "kg",
            "timestamp_utc": pd.to_datetime("2026-11-01T10:00:00Z"),
            "timestamp_iso": "2026-11-01 10:00:00Z",
        },
        {
            "supplier_id": "supplier_b",
            "supplier_priority": 2,
            "sku": "BCN-ARM",
            "canonical_product_id": "PROD-12345",
            "gtin_14": "00000000012345",
            "name": "Beacon Arm Mount",
            "category_standardized": "Office Supplies",
            "category_raw": "Office Products",
            "price_usd": 25.00,  # Lower price!
            "price_raw": "25.00",
            "currency_raw": "USD",
            "stock_numeric": 40,
            "weight_kg": 2.700,
            "weight_raw": "5.95",
            "weight_unit": "lbs",
            "timestamp_utc": pd.to_datetime("2026-11-02T14:00:00Z"),  # Newer timestamp!
            "timestamp_iso": "2026-11-02 14:00:00Z",
        },
    ])

    # Test with default BEST_PRICE and PRIORITY_FIRST
    prod, lineage = resolve_conflicts_for_group("PROD-12345", records, price_strategy="BEST_PRICE")

    # Master attributes (Name, Weight) must come from Priority 1 (Supplier A)
    assert prod["product_name"] == "Apex Monitor Arm"
    assert prod["weight_kg"] == 2.500

    # Price must come from Supplier B (lowest buy price: 25.00)
    assert prod["price_usd"] == 25.00

    # Stock must be aggregated: 50 + 40 = 90 units
    assert prod["stock_quantity"] == 90
    assert prod["supplier_count"] == 2
    assert "supplier_a" in prod["source_suppliers"] and "supplier_b" in prod["source_suppliers"]

    # Verify JSON Lineage
    lineage_data = json.loads(prod["attribute_lineage"])
    assert lineage_data["product_name"]["supplier_id"] == "supplier_a"
    assert lineage_data["product_name"]["resolution_rule"] == "SUPPLIER_PRIORITY"
    assert lineage_data["price_usd"]["supplier_id"] == "supplier_b"
    assert lineage_data["price_usd"]["resolution_rule"] == "LOWEST_PRICE"
    assert lineage_data["stock_quantity"]["resolution_rule"] == "AGGREGATED_SUM"
    assert lineage_data["stock_quantity"]["source_value"] == 90


def test_conflict_resolution_priority_price_strategy():
    """Verify that when price_strategy='PRIORITY', price comes from winning priority supplier."""
    records = pd.DataFrame([
        {
            "supplier_id": "supplier_a",
            "supplier_priority": 1,
            "sku": "APX-01",
            "canonical_product_id": "P1",
            "gtin_14": "0001",
            "name": "Apex Item",
            "category_standardized": "Electronics",
            "category_raw": "elec",
            "price_usd": 30.00,
            "price_raw": "30.00",
            "currency_raw": "USD",
            "stock_numeric": 10,
            "weight_kg": 1.0,
            "weight_raw": "1.0",
            "weight_unit": "kg",
            "timestamp_utc": pd.to_datetime("2026-11-01"),
            "timestamp_iso": "2026-11-01 00:00:00Z",
        },
        {
            "supplier_id": "supplier_b",
            "supplier_priority": 2,
            "sku": "BCN-01",
            "canonical_product_id": "P1",
            "gtin_14": "0001",
            "name": "Beacon Item",
            "category_standardized": "Electronics",
            "category_raw": "Electronics",
            "price_usd": 20.00,
            "price_raw": "20.00",
            "currency_raw": "USD",
            "stock_numeric": 15,
            "weight_kg": 1.0,
            "weight_raw": "2.2",
            "weight_unit": "lbs",
            "timestamp_utc": pd.to_datetime("2026-11-02"),
            "timestamp_iso": "2026-11-02 00:00:00Z",
        },
    ])

    prod, _ = resolve_conflicts_for_group("P1", records, price_strategy="PRIORITY")
    assert prod["price_usd"] == 30.00  # Priority 1 supplier's price


def test_conflict_resolution_timestamp_tiebreaker():
    """Verify that when priorities are equal, the latest timestamp breaks the tie."""
    records = pd.DataFrame([
        {
            "supplier_id": "supp_x",
            "supplier_priority": 1,
            "sku": "X-01",
            "canonical_product_id": "P2",
            "gtin_14": "0002",
            "name": "Older Title",
            "category_standardized": "Electronics",
            "category_raw": "elec",
            "price_usd": 10.0,
            "price_raw": "10.0",
            "currency_raw": "USD",
            "stock_numeric": 5,
            "weight_kg": 1.0,
            "weight_raw": "1.0",
            "weight_unit": "kg",
            "timestamp_utc": pd.to_datetime("2026-11-01T10:00:00Z"),
            "timestamp_iso": "2026-11-01 10:00:00Z",
        },
        {
            "supplier_id": "supp_y",
            "supplier_priority": 1,
            "sku": "Y-01",
            "canonical_product_id": "P2",
            "gtin_14": "0002",
            "name": "Newer Title",
            "category_standardized": "Electronics",
            "category_raw": "elec",
            "price_usd": 10.0,
            "price_raw": "10.0",
            "currency_raw": "USD",
            "stock_numeric": 5,
            "weight_kg": 1.0,
            "weight_raw": "1.0",
            "weight_unit": "kg",
            "timestamp_utc": pd.to_datetime("2026-11-02T10:00:00Z"),
            "timestamp_iso": "2026-11-02 10:00:00Z",
        },
    ])

    prod, _ = resolve_conflicts_for_group("P2", records)
    assert prod["product_name"] == "Newer Title"

"""Pytest fixtures for Multi-Supplier Product Data Pipeline tests."""
from pathlib import Path
import tempfile
import pytest
import pandas as pd
import duckdb

from src.database import DuckDBManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_db(temp_dir):
    """Create a temporary DuckDB instance."""
    db_path = temp_dir / "test_products.duckdb"
    mgr = DuckDBManager(db_path)
    return mgr


@pytest.fixture
def sample_supplier_a_csv(temp_dir):
    """Create a sample Supplier A CSV file."""
    csv_path = temp_dir / "supplier_a_sample.csv"
    data = [
        # Normal row
        {
            "supplier_sku": "APX-001",
            "prod_name": "Apex Wireless Keyboard",
            "cat": "elec",
            "unit_cost": "45.00",
            "curr": "USD",
            "stock_qty": "100",
            "weight_kg": "0.850",
            "barcode_ean": "0123456789012",
            "last_modified": "2026-11-01T10:00:00Z",
        },
        # Overlapping row with Supplier B & C
        {
            "supplier_sku": "APX-002",
            "prod_name": "Apex Ergonomic Mouse",
            "cat": "elec",
            "unit_cost": "25.00",
            "curr": "EUR",  # EUR will be converted to USD (25 * 1.08 = 27.00)
            "stock_qty": "50",
            "weight_kg": "0.200",
            "barcode_ean": "0987654321098",
            "last_modified": "2026-11-01T12:00:00Z",
        },
        # Intra-supplier duplicate of APX-001 with older timestamp
        {
            "supplier_sku": "APX-001",
            "prod_name": "Apex Wireless Keyboard Old",
            "cat": "elec",
            "unit_cost": "49.00",
            "curr": "USD",
            "stock_qty": "10",
            "weight_kg": "0.850",
            "barcode_ean": "0123456789012",
            "last_modified": "2026-10-31T08:00:00Z",
        },
        # Invalid row: negative price (should be quarantined)
        {
            "supplier_sku": "APX-BAD-01",
            "prod_name": "Defective Widget",
            "cat": "home",
            "unit_cost": "-15.00",
            "curr": "USD",
            "stock_qty": "20",
            "weight_kg": "1.0",
            "barcode_ean": "0111111111111",
            "last_modified": "2026-11-01T10:00:00Z",
        },
    ]
    pd.DataFrame(data).to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def sample_supplier_b_csv(temp_dir):
    """Create a sample Supplier B CSV file."""
    csv_path = temp_dir / "supplier_b_sample.csv"
    data = [
        # Overlapping row for APX-002 (same barcode UPC 987654321098)
        # Weight in lbs: 0.44 lbs -> 0.200 kg
        # Price: 20 GBP -> 25.60 USD (lower than Apex EUR price of 27.00 USD)
        {
            "item_code": "BCN-501",
            "title": "Beacon Ergonomic Optical Mouse",
            "department": "Consumer Electronics",
            "wholesale_price": "20.00",
            "currency_code": "GBP",
            "available_inventory": "80",
            "item_weight_lbs": "0.440924",
            "upc_code": "987654321098",
            "updated_at": "2026-11-02 14:00:00",
        },
        # Unique row for Supplier B
        {
            "item_code": "BCN-502",
            "title": "Beacon Standing Desk Mat",
            "department": "Office Products",
            "wholesale_price": "35.00",
            "currency_code": "USD",
            "available_inventory": "40",
            "item_weight_lbs": "3.3",
            "upc_code": "112233445566",
            "updated_at": "2026-11-02 15:30:00",
        },
        # Invalid row: missing SKU (should be quarantined)
        {
            "item_code": "",
            "title": "Nameless Item",
            "department": "General",
            "wholesale_price": "10.00",
            "currency_code": "USD",
            "available_inventory": "5",
            "item_weight_lbs": "1.0",
            "upc_code": "123456789012",
            "updated_at": "2026-11-02 12:00:00",
        },
    ]
    pd.DataFrame(data).to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def sample_supplier_c_csv(temp_dir):
    """Create a sample Supplier C CSV file."""
    csv_path = temp_dir / "supplier_c_sample.csv"
    data = [
        # Overlapping row for APX-002 (same barcode GTIN 000987654321098)
        # Weight in grams: 200g -> 0.200 kg
        # Stock: 60 units
        {
            "vendor_part_no": "CR-901",
            "description": "Crest Mouse Ergonomic",
            "product_category": "Electronics",
            "price": "38.00",
            "iso_currency": "CAD",  # 38 * 0.74 = 28.12 USD
            "quantity_on_hand": "60",
            "package_weight_g": "200.0",
            "gtin": "00987654321098",
            "timestamp": "03/11/2026 10:15:00",
        },
        # Invalid row: negative stock
        {
            "vendor_part_no": "CR-BAD-02",
            "description": "Negative Stock Product",
            "product_category": "Electronics",
            "price": "50.00",
            "iso_currency": "USD",
            "quantity_on_hand": "-10",
            "package_weight_g": "500.0",
            "gtin": "999999999999",
            "timestamp": "03/11/2026 11:00:00",
        },
    ]
    pd.DataFrame(data).to_csv(csv_path, index=False)
    return csv_path

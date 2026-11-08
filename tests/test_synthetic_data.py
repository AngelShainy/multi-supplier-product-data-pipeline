"""Unit tests for synthetic data generation reproducibility and schemas."""
import pandas as pd
from src.data_generator import generate_synthetic_data, create_master_catalog


def test_master_catalog_reproducibility():
    """Verify that same seed generates identical catalog."""
    cat1 = create_master_catalog(100, seed=123)
    cat2 = create_master_catalog(100, seed=123)
    assert cat1 == cat2


def test_synthetic_data_generation(temp_dir):
    """Verify synthetic dataset schema and error injection."""
    files = generate_synthetic_data(
        total_records=500,
        seed=42,
        output_dir=temp_dir,
        error_rate=0.05,
    )

    assert "supplier_a" in files
    assert "supplier_b" in files
    assert "supplier_c" in files

    df_a = pd.read_csv(files["supplier_a"])
    df_b = pd.read_csv(files["supplier_b"])
    df_c = pd.read_csv(files["supplier_c"])

    # Schema verification: Supplier A
    assert "supplier_sku" in df_a.columns
    assert "prod_name" in df_a.columns
    assert "cat" in df_a.columns
    assert "unit_cost" in df_a.columns
    assert "curr" in df_a.columns
    assert "stock_qty" in df_a.columns
    assert "weight_kg" in df_a.columns
    assert "barcode_ean" in df_a.columns
    assert "last_modified" in df_a.columns

    # Schema verification: Supplier B
    assert "item_code" in df_b.columns
    assert "title" in df_b.columns
    assert "department" in df_b.columns
    assert "wholesale_price" in df_b.columns
    assert "currency_code" in df_b.columns
    assert "available_inventory" in df_b.columns
    assert "item_weight_lbs" in df_b.columns
    assert "upc_code" in df_b.columns
    assert "updated_at" in df_b.columns

    # Schema verification: Supplier C
    assert "vendor_part_no" in df_c.columns
    assert "description" in df_c.columns
    assert "product_category" in df_c.columns
    assert "price" in df_c.columns
    assert "iso_currency" in df_c.columns
    assert "quantity_on_hand" in df_c.columns
    assert "package_weight_g" in df_c.columns
    assert "gtin" in df_c.columns
    assert "timestamp" in df_c.columns

    # Check total rows
    total_generated = len(df_a) + len(df_b) + len(df_c)
    assert total_generated == 500

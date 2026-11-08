"""Unit tests for DuckDB database persistence, idempotency, and run tracking."""
from datetime import datetime, timezone
import pandas as pd
from src.database import DuckDBManager


def test_database_initialization(temp_db):
    """Verify all required tables are initialized in DuckDB."""
    with temp_db.get_connection() as con:
        tables = con.execute("SHOW TABLES;").df()["name"].tolist()
        assert "pipeline_runs" in tables
        assert "standardized_products" in tables
        assert "product_attribute_lineage" in tables
        assert "quarantine_records" in tables
        assert "sku_cross_reference" in tables


def test_pipeline_run_tracking(temp_db):
    """Verify run start and finish metrics are accurately recorded in pipeline_runs."""
    run_id = "TEST_RUN_001"
    start_time = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2026, 11, 1, 12, 0, 10, tzinfo=timezone.utc)

    temp_db.record_run_start(run_id=run_id, pipeline_name="TestPipeline")
    temp_db.record_run_finish(
        run_id=run_id,
        start_time=start_time,
        end_time=end_time,
        records_ingested=100,
        records_valid=95,
        records_quarantined=5,
        canonical_products_total=90,
        status="SUCCESS",
    )

    runs_df = temp_db.get_run_history()
    assert len(runs_df) == 1
    run_row = runs_df.iloc[0]
    assert run_row["run_id"] == run_id
    assert run_row["status"] == "SUCCESS"
    assert run_row["records_ingested"] == 100
    assert run_row["records_valid"] == 95
    assert run_row["records_quarantined"] == 5
    assert run_row["duration_seconds"] == 10.0


def test_idempotent_save_standardized_products(temp_db):
    """Verify that rerunning with the same records performs safe upserts without creating duplicates."""
    products_df = pd.DataFrame([
        {
            "canonical_product_id": "PROD-001",
            "gtin": "00000000000001",
            "product_name": "Test Laptop Stand",
            "category": "Office Supplies",
            "price_usd": 29.99,
            "stock_quantity": 50,
            "weight_kg": 0.75,
            "source_suppliers": "supplier_a",
            "supplier_count": 1,
            "attribute_lineage": "{}",
            "last_updated_at": "2026-11-01 10:00:00Z",
        }
    ])
    lineage_df = pd.DataFrame([
        {
            "canonical_product_id": "PROD-001",
            "attribute_name": "price_usd",
            "supplier_id": "supplier_a",
            "source_value": "29.99",
            "source_timestamp": "2026-11-01 10:00:00Z",
            "resolution_rule": "SINGLE_SOURCE",
        }
    ])

    # First write
    temp_db.save_standardized_products(products_df, lineage_df, run_id="RUN_1")
    assert temp_db.get_canonical_products_count() == 1

    # Second write with same primary key but updated price
    updated_products_df = products_df.copy()
    updated_products_df["price_usd"] = 27.99

    temp_db.save_standardized_products(updated_products_df, lineage_df, run_id="RUN_2")

    # Count must remain exactly 1 (Idempotent!)
    assert temp_db.get_canonical_products_count() == 1

    all_prods = temp_db.get_all_canonical_products()
    assert all_prods.iloc[0]["price_usd"] == 27.99
    assert all_prods.iloc[0]["last_run_id"] == "RUN_2"

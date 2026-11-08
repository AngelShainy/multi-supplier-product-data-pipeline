"""End-to-End integration tests for Multi-Supplier Product Data Integration Pipeline."""
import json
import pandas as pd
from src.database import DuckDBManager
from src.pipeline import run_pipeline


def test_pipeline_e2e_execution(
    temp_dir,
    sample_supplier_a_csv,
    sample_supplier_b_csv,
    sample_supplier_c_csv,
):
    """Test full pipeline workflow from raw ingestion to database and reconciliation reporting."""
    db_path = temp_dir / "e2e_products.duckdb"
    out_dir = temp_dir / "output"
    rep_dir = temp_dir / "reports"

    supplier_files = {
        "supplier_a": sample_supplier_a_csv,
        "supplier_b": sample_supplier_b_csv,
        "supplier_c": sample_supplier_c_csv,
    }

    # Execute pipeline
    result = run_pipeline(
        supplier_files=supplier_files,
        db_path=db_path,
        price_strategy="BEST_PRICE",
        priority_strategy="PRIORITY_FIRST",
        output_dir=out_dir,
        reports_dir=rep_dir,
    )

    assert result["status"] == "SUCCESS"
    assert result["records_ingested"] == 9  # 4 + 3 + 2 = 9
    # Quarantined: APX-BAD-01 (neg price), BCN with missing SKU, CR-BAD-02 (neg stock) -> 3 quarantined
    assert result["records_quarantined"] == 3
    assert result["records_valid"] == 6

    # Verify DuckDB contents
    db_mgr = DuckDBManager(db_path)
    prods = db_mgr.get_all_canonical_products()
    # Unique canonical products:
    # 1. Keyboard (APX-001)
    # 2. Mouse (APX-002 + BCN-501 + CR-901 merged!)
    # 3. Desk Mat (BCN-502)
    # Total = 3 canonical products
    assert len(prods) == 3

    # Check the 3-way merged mouse
    # GTIN normalized: 00987654321098
    mouse_row = prods[prods["gtin"] == "00987654321098"].iloc[0]
    assert mouse_row["supplier_count"] == 3
    # Supplier priority 1 (Apex) provides title
    assert "Apex Ergonomic Mouse" in mouse_row["product_name"]
    # Lowest price strategy:
    # Apex EUR 27.00, Beacon GBP 25.60, Crest CAD 28.12 -> Beacon 25.60 is lowest!
    assert mouse_row["price_usd"] == 25.60
    # Stock sum: Apex 50 + Beacon 80 + Crest 60 = 190 units
    assert mouse_row["stock_quantity"] == 190

    # Lineage check
    lineage_data = json.loads(mouse_row["attribute_lineage"])
    assert lineage_data["price_usd"]["supplier_id"] == "supplier_b"
    assert lineage_data["price_usd"]["resolution_rule"] == "LOWEST_PRICE"
    assert lineage_data["product_name"]["supplier_id"] == "supplier_a"
    assert lineage_data["product_name"]["resolution_rule"] == "SUPPLIER_PRIORITY"

    # Verify output files
    assert (out_dir / "canonical_products.csv").exists()
    assert (out_dir / "quarantine_records.csv").exists()
    assert (out_dir / "product_lineage.csv").exists()

    # Verify report files
    assert result["markdown_report"].exists()
    assert result["json_report"].exists()

    report_content = result["markdown_report"].read_text(encoding="utf-8")
    assert "Reconciliation & Data Quality Report" in report_content
    assert "Apex Supplies" in report_content
    assert "LOWEST_PRICE" in report_content


def test_pipeline_safe_rerun_idempotency(
    temp_dir,
    sample_supplier_a_csv,
    sample_supplier_b_csv,
    sample_supplier_c_csv,
):
    """Test that running the pipeline multiple times maintains identical state without duplicate records."""
    db_path = temp_dir / "idempotent_test.duckdb"
    out_dir = temp_dir / "output_idem"
    rep_dir = temp_dir / "reports_idem"

    supplier_files = {
        "supplier_a": sample_supplier_a_csv,
        "supplier_b": sample_supplier_b_csv,
        "supplier_c": sample_supplier_c_csv,
    }

    # Run 1
    res1 = run_pipeline(
        supplier_files=supplier_files,
        db_path=db_path,
        output_dir=out_dir,
        reports_dir=rep_dir,
    )

    db_mgr = DuckDBManager(db_path)
    count1 = db_mgr.get_canonical_products_count()

    # Run 2
    res2 = run_pipeline(
        supplier_files=supplier_files,
        db_path=db_path,
        output_dir=out_dir,
        reports_dir=rep_dir,
    )

    count2 = db_mgr.get_canonical_products_count()

    # The canonical products count must be strictly identical
    assert count1 == count2 == 3

    # Pipeline runs audit must have recorded both runs
    runs = db_mgr.get_run_history()
    assert len(runs) == 2
    assert runs.iloc[0]["status"] == "SUCCESS"
    assert runs.iloc[1]["status"] == "SUCCESS"

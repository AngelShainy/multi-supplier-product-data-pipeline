"""Idempotency and Consistency Audit Script.

Compares database tables, counts, product IDs, attribute values, and lineage
before and after re-running the pipeline on identical input files.
"""

from datetime import datetime
import json
from pathlib import Path
import sys

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import pandas as pd

from config.settings import DUCKDB_PATH, DATA_OUTPUT_DIR
from src.database import DuckDBManager
from src.pipeline import run_pipeline


def inspect_baseline(con: duckdb.DuckDBPyConnection) -> dict:
    """Capture current baseline state from DuckDB."""
    total_prods = con.execute("SELECT COUNT(*) FROM standardized_products;").fetchone()[0]
    total_lineage = con.execute("SELECT COUNT(*) FROM product_attribute_lineage;").fetchone()[0]
    total_quarantine = con.execute("SELECT COUNT(*) FROM quarantine_records;").fetchone()[0]
    total_xref = con.execute("SELECT COUNT(*) FROM sku_cross_reference;").fetchone()[0]
    total_runs = con.execute("SELECT COUNT(*) FROM pipeline_runs;").fetchone()[0]

    # Metrics for latest run
    latest_run = con.execute("SELECT run_id, duration_seconds, records_ingested, records_valid, records_quarantined, canonical_products_total FROM pipeline_runs ORDER BY start_time DESC LIMIT 1;").df().to_dict(orient="records")[0]
    latest_run_id = latest_run["run_id"]

    prods_in_latest = con.execute("SELECT COUNT(*) FROM standardized_products WHERE last_run_id = ?;", [latest_run_id]).fetchone()[0]
    stock_in_latest = con.execute("SELECT SUM(stock_quantity) FROM standardized_products WHERE last_run_id = ?;", [latest_run_id]).fetchone()[0]
    valuation_in_latest = con.execute("SELECT ROUND(SUM(price_usd * stock_quantity), 2) FROM standardized_products WHERE last_run_id = ?;", [latest_run_id]).fetchone()[0]

    return {
        "latest_run_id": latest_run_id,
        "total_prods_table": total_prods,
        "total_lineage_table": total_lineage,
        "total_quarantine_table": total_quarantine,
        "total_xref_table": total_xref,
        "total_runs_logged": total_runs,
        "latest_run_metrics": latest_run,
        "prods_tagged_with_latest_run": prods_in_latest,
        "stock_tagged_with_latest_run": stock_in_latest,
        "valuation_tagged_with_latest_run": valuation_in_latest,
    }


def main():
    con = duckdb.connect(str(DUCKDB_PATH))

    print("=" * 75)
    print("STAGE 1: CAPTURING PRE-RERUN BASELINE (DuckDB Warehouse State)")
    print("=" * 75)
    baseline = inspect_baseline(con)
    for k, v in baseline.items():
        print(f"  {k:35}: {v}")

    # Also capture current CSV output state
    csv_prods_path = DATA_OUTPUT_DIR / "canonical_products.csv"
    csv_lineage_path = DATA_OUTPUT_DIR / "product_lineage.csv"
    csv_prods_before = pd.read_csv(csv_prods_path)
    csv_lineage_before = pd.read_csv(csv_lineage_path)

    print(f"\nCSV Canonical Products Before Rerun: {len(csv_prods_before):,} rows")
    print(f"CSV Attribute Lineage Before Rerun:    {len(csv_lineage_before):,} rows")

    print("\n" + "=" * 75)
    print("STAGE 2: EXECUTING PIPELINE RERUN WITH IDENTICAL INPUTS & CONFIG")
    print("=" * 75)
    rerun_result = run_pipeline(price_strategy="BEST_PRICE", priority_strategy="PRIORITY_FIRST")
    new_run_id = rerun_result["run_id"]
    print(f"Rerun completed. New Run ID: {new_run_id} | Status: {rerun_result['status']}")

    print("\n" + "=" * 75)
    print("STAGE 3: CAPTURING POST-RERUN STATE & COMPARING METRICS")
    print("=" * 75)
    post_state = inspect_baseline(con)
    for k, v in post_state.items():
        print(f"  {k:35}: {v}")

    csv_prods_after = pd.read_csv(csv_prods_path)
    csv_lineage_after = pd.read_csv(csv_lineage_path)

    print("\n" + "=" * 75)
    print("STAGE 4: DEEP CONSISTENCY & VALUE EQUALITY VERIFICATION")
    print("=" * 75)

    # 1. Product row count check
    count_equal = (len(csv_prods_before) == len(csv_prods_after))
    print(f"1. Canonical Product Count Match:        {'PASSED' if count_equal else 'FAILED'} ({len(csv_prods_before):,} == {len(csv_prods_after):,})")

    # 2. Product IDs exact match
    ids_before = set(csv_prods_before["canonical_product_id"])
    ids_after = set(csv_prods_after["canonical_product_id"])
    ids_match = (ids_before == ids_after)
    print(f"2. Exact Canonical Product IDs Match:    {'PASSED' if ids_match else 'FAILED'} (Difference: {len(ids_before ^ ids_after)})")

    # 3. Aggregate Inventory stock match
    stock_before = int(csv_prods_before["stock_quantity"].sum())
    stock_after = int(csv_prods_after["stock_quantity"].sum())
    stock_match = (stock_before == stock_after)
    print(f"3. Aggregate Network Stock Units Match:  {'PASSED' if stock_match else 'FAILED'} ({stock_before:,} == {stock_after:,})")

    # 4. Inventory Valuation match
    val_before = round(float((csv_prods_before["price_usd"] * csv_prods_before["stock_quantity"]).sum()), 2)
    val_after = round(float((csv_prods_after["price_usd"] * csv_prods_after["stock_quantity"]).sum()), 2)
    val_match = (val_before == val_after)
    print(f"4. Aggregate Inventory Valuation Match:  {'PASSED' if val_match else 'FAILED'} (${val_before:,.2f} == ${val_after:,.2f})")

    # 5. Lineage row count match
    lineage_count_match = (len(csv_lineage_before) == len(csv_lineage_after))
    print(f"5. Attribute Lineage Rows Match:         {'PASSED' if lineage_count_match else 'FAILED'} ({len(csv_lineage_before):,} == {len(csv_lineage_after):,})")

    # 6. Check DuckDB table row counts before vs after
    # Did standardized_products table increase in rows, or did it replace?
    # Because all 65,467 products share the exact primary keys, the table row count must NOT increase!
    table_prods_delta = post_state["total_prods_table"] - baseline["total_prods_table"]
    print(f"6. DuckDB standardized_products Delta:   {table_prods_delta} new rows added (Expected: 0)")

    table_lineage_delta = post_state["total_lineage_table"] - baseline["total_lineage_table"]
    print(f"7. DuckDB lineage table Delta:           {table_lineage_delta} new rows added (Expected: 0)")

    # 8. Check that pipeline_runs recorded a new row
    runs_delta = post_state["total_runs_logged"] - baseline["total_runs_logged"]
    print(f"8. DuckDB pipeline_runs Delta:           +{runs_delta} run logged (Expected: +1)")

    # 9. Verify SQL historical run logs
    print("\n" + "=" * 75)
    print("STAGE 5: HISTORICAL PIPELINE RUNS AUDIT TRAIL")
    print("=" * 75)
    runs_df = con.execute("SELECT run_id, start_time, duration_seconds, records_ingested, records_valid, records_quarantined, canonical_products_total, status FROM pipeline_runs ORDER BY start_time ASC;").df()
    print(runs_df.to_string(index=False))

    con.close()


if __name__ == "__main__":
    main()

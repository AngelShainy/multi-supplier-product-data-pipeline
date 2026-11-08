"""Inspect quarantine records, schema, and duplicates."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
from config.settings import DUCKDB_PATH

con = duckdb.connect(str(DUCKDB_PATH))

print("=== 1. QUARANTINE SCHEMA ===")
print(con.execute("PRAGMA table_info(quarantine_records);").df().to_string())

print("\n=== 2. QUARANTINE COUNTS BY RUN ID ===")
print(con.execute("SELECT run_id, COUNT(*) as record_count FROM quarantine_records GROUP BY run_id ORDER BY run_id;").df().to_string())

print("\n=== 3. CHECKING DUPLICATE SKUS WITHIN LATEST RUN ===")
dups = con.execute("""
    SELECT supplier_id, supplier_sku, COUNT(*) as occ_count
    FROM quarantine_records
    WHERE run_id = (SELECT run_id FROM pipeline_runs ORDER BY start_time DESC LIMIT 1)
    GROUP BY supplier_id, supplier_sku
    HAVING COUNT(*) > 1
    ORDER BY occ_count DESC
    LIMIT 10;
""").df()
print(f"Duplicate (supplier_id, supplier_sku) count in latest run: {len(dups)}")
if not dups.empty:
    print(dups.to_string())

print("\n=== 4. CHECKING REJECTION REASONS IN LATEST RUN ===")
reasons = con.execute("""
    SELECT rejection_reasons, COUNT(*) as failure_count
    FROM quarantine_records
    WHERE run_id = (SELECT run_id FROM pipeline_runs ORDER BY start_time DESC LIMIT 1)
    GROUP BY rejection_reasons
    ORDER BY failure_count DESC;
""").df()
print(reasons.to_string())

print("\n=== 5. CHECKING HISTORICAL STANDARDIZED PRODUCTS BY RUN ID ===")
prods_runs = con.execute("""
    SELECT last_run_id, COUNT(*) as product_count,
           ROUND(AVG(price_usd), 2) as avg_price,
           SUM(stock_quantity) as total_units
    FROM standardized_products
    GROUP BY last_run_id
    ORDER BY last_run_id;
""").df()
print(prods_runs.to_string())

con.close()

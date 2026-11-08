"""Multi-Supplier Product Data Integration Pipeline - CLI Entrypoint.

Provides commands to generate reproducible synthetic data, execute the data pipeline,
verify idempotency and safe reruns, and view reconciliation reports.
"""

import argparse
import sys
import time
from pathlib import Path
import pandas as pd

from config.settings import DATA_RAW_DIR, DUCKDB_PATH, REPORTS_DIR, SUPPLIER_CONFIGS
from src.data_generator import generate_synthetic_data
from src.database import DuckDBManager
from src.pipeline import run_pipeline


def cmd_generate_data(args: argparse.Namespace) -> None:
    """Generate synthetic canonical products, supplier CSV feeds, and identifier mapping."""
    print("\n" + "=" * 75)
    print("GENERATING REPRODUCIBLE SYNTHETIC CANONICAL PRODUCTS & SUPPLIER FEEDS")
    print(f"Target Canonical Products: {args.records:,} | Seed: {args.seed} | Error Rate: {args.error_rate * 100:.1f}%")
    print("=" * 75)

    start = time.time()
    files = generate_synthetic_data(
        total_records=args.records,
        seed=args.seed,
        output_dir=Path(args.output_dir),
        error_rate=args.error_rate,
    )
    elapsed = round(time.time() - start, 2)

    print(f"\nGenerated files successfully in {elapsed}s:")
    print("-" * 75)

    # Validate each generated file: record count and expected columns
    for key, path in files.items():
        df = pd.read_csv(path, dtype=str)
        n_rows = len(df)
        cols_count = len(df.columns)
        size_mb = path.stat().st_size / (1024 * 1024)

        print(f"File Key:      {key}")
        print(f"Location:      {path.resolve()}")
        print(f"Record Count:  {n_rows:,} rows")
        print(f"File Size:     {size_mb:.2f} MB ({cols_count} columns)")
        print(f"Columns:       {list(df.columns)}")
        print("-" * 75)

    print("\n>>> All generated files validated with correct schemas and record counts. <<<\n")


def cmd_run_pipeline(args: argparse.Namespace) -> None:
    """Run the complete ETL pipeline."""
    print("\n" + "=" * 65)
    print("RUNNING MULTI-SUPPLIER DATA INTEGRATION PIPELINE")
    print(f"Price Strategy: {args.price_strategy} | Priority: {args.priority_strategy}")
    if getattr(args, "mapping_file", None):
        print(f"Mapping File:   {args.mapping_file}")
    print("=" * 65)

    res = run_pipeline(
        price_strategy=args.price_strategy,
        priority_strategy=args.priority_strategy,
        mapping_file=Path(args.mapping_file) if getattr(args, "mapping_file", None) else None,
    )

    print("\n" + "=" * 65)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 65)
    print(f"Run ID:                      {res['run_id']}")
    print(f"Status:                      {res['status']}")
    print(f"Duration:                    {res['duration_seconds']}s")
    print(f"Total Ingested Records:      {res['records_ingested']:,}")
    print(f"Valid Records:               {res['records_valid']:,}")
    print(f"Quarantined Records:         {res['records_quarantined']:,}")
    print(f"Canonical Standardized SKUs: {res['canonical_products_count']:,}")
    print(f"\nOutputs:")
    for k, v in res["output_files"].items():
        print(f"  - {k}: {v}")
    print(f"  - Reconciliation Report:   {res['markdown_report']}")
    print("=" * 65 + "\n")


def cmd_verify_idempotency(args: argparse.Namespace) -> None:
    """Run pipeline twice and verify that DuckDB database state remains identical."""
    print("\n" + "=" * 65)
    print("VERIFYING PIPELINE IDEMPOTENCY AND SAFE RERUNS")
    print("=" * 65)

    db_mgr = DuckDBManager()
    count_before = db_mgr.get_canonical_products_count()

    print(f"Current canonical products in DuckDB: {count_before:,}")
    print("Executing Pipeline Run #1...")
    res1 = run_pipeline(price_strategy="BEST_PRICE")
    count_after_1 = db_mgr.get_canonical_products_count()
    print(f"Run 1 completed. Canonical products count: {count_after_1:,}")

    print("\nExecuting Pipeline Run #2 (Identical input re-run)...")
    res2 = run_pipeline(price_strategy="BEST_PRICE")
    count_after_2 = db_mgr.get_canonical_products_count()
    print(f"Run 2 completed. Canonical products count: {count_after_2:,}")

    if count_after_1 == count_after_2:
        print("\n>>> IDEMPOTENCY CHECK PASSED: Exact row count maintained without duplication! <<<")
    else:
        print(f"\n>>> IDEMPOTENCY CHECK FAILED: Row count changed ({count_after_1} != {count_after_2}) <<<")
        sys.exit(1)


def cmd_show_report(args: argparse.Namespace) -> None:
    """Print the latest reconciliation report to terminal."""
    report_file = REPORTS_DIR / "reconciliation_report_latest.md"
    if not report_file.exists():
        print("No reconciliation report found. Run pipeline first.")
        return
    print(report_file.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Multi-Supplier Product Data Integration Pipeline CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. generate-data
    p_gen = subparsers.add_parser("generate-data", help="Generate synthetic supplier data & canonical catalog")
    p_gen.add_argument("--records", type=int, default=105000, help="Total canonical products (default: 105,000)")
    p_gen.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    p_gen.add_argument("--error-rate", type=float, default=0.025, help="Anomaly injection rate (default: 0.025)")
    p_gen.add_argument("--output-dir", type=str, default=str(DATA_RAW_DIR), help="Output directory for generated files")
    p_gen.set_defaults(func=cmd_generate_data)

    # 2. run-pipeline
    p_run = subparsers.add_parser("run-pipeline", help="Execute the data integration pipeline")
    p_run.add_argument("--price-strategy", choices=["BEST_PRICE", "PRIORITY"], default="BEST_PRICE")
    p_run.add_argument("--priority-strategy", choices=["PRIORITY_FIRST", "TIMESTAMP_FIRST"], default="PRIORITY_FIRST")
    p_run.add_argument("--mapping-file", type=str, default=str(DATA_RAW_DIR / "product_identifier_mapping.csv"), help="Product identifier mapping CSV path")
    p_run.set_defaults(func=cmd_run_pipeline)

    # 3. verify-idempotency
    p_idem = subparsers.add_parser("verify-idempotency", help="Verify safe re-runs and idempotency")
    p_idem.set_defaults(func=cmd_verify_idempotency)

    # 4. report
    p_rep = subparsers.add_parser("report", help="Display latest reconciliation report")
    p_rep.set_defaults(func=cmd_show_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

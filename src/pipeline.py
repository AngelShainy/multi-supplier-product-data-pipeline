"""End-to-End Orchestrator for Multi-Supplier Product Data Pipeline.

Coordinates ingestion, validation, canonical mapping, deduplication,
conflict resolution, attribute lineage tracking, idempotent DuckDB storage,
and reconciliation reporting.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import uuid
import pandas as pd

from config.settings import (
    DATA_OUTPUT_DIR,
    DATA_RAW_DIR,
    DUCKDB_PATH,
    LOGS_DIR,
    REPORTS_DIR,
    SUPPLIER_CONFIGS,
)
from src.conflict_resolution import resolve_all_conflicts
from src.database import DuckDBManager
from src.deduplication import deduplicate_all_suppliers
from src.ingest import ingest_all_suppliers
from src.mapping import apply_canonical_mapping, load_identifier_mapping
from src.reporter import export_output_csvs, generate_reconciliation_report
from src.validation import validate_records


def setup_pipeline_logging(run_id: str) -> logging.Logger:
    """Set up structured file and console logging for the pipeline run."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(f"Pipeline_{run_id}")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if not logger.handlers:
        file_handler = logging.FileHandler(LOGS_DIR / f"pipeline_{run_id}.log", encoding="utf-8")
        file_fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        file_handler.setFormatter(file_fmt)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_fmt = logging.Formatter("[%(levelname)s] %(message)s")
        console_handler.setFormatter(console_fmt)
        logger.addHandler(console_handler)

    return logger


def run_pipeline(
    supplier_files: Optional[Dict[str, Path]] = None,
    mapping_file: Optional[Path] = None,
    db_path: Path = DUCKDB_PATH,
    price_strategy: str = "BEST_PRICE",
    priority_strategy: str = "PRIORITY_FIRST",
    output_dir: Path = DATA_OUTPUT_DIR,
    reports_dir: Path = REPORTS_DIR,
) -> Dict:
    """Execute the complete Multi-Supplier Data Integration Pipeline."""
    run_timestamp = datetime.now(timezone.utc)
    run_id = f"RUN_{run_timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    logger = setup_pipeline_logging(run_id)

    logger.info("=" * 70)
    logger.info(f"Starting Multi-Supplier Product Data Pipeline: {run_id}")
    logger.info(f"Price Strategy: {price_strategy} | Priority Strategy: {priority_strategy}")
    logger.info("=" * 70)

    # Resolve default input files if not provided
    if supplier_files is None:
        supplier_files = {
            s_id: DATA_RAW_DIR / cfg["filename"]
            for s_id, cfg in SUPPLIER_CONFIGS.items()
        }

    # Resolve default identifier mapping file if present
    if mapping_file is None:
        default_map = DATA_RAW_DIR / "product_identifier_mapping.csv"
        if default_map.exists():
            mapping_file = default_map

    db_mgr = DuckDBManager(db_path)
    config_summary = json.dumps({
        "price_strategy": price_strategy,
        "priority_strategy": priority_strategy,
        "suppliers": list(supplier_files.keys()),
    })
    db_mgr.record_run_start(run_id=run_id, pipeline_name="MultiSupplierETL", config_summary=config_summary)

    try:
        # 1. Ingestion
        logger.info("[1/7] Ingesting supplier CSV files...")
        raw_dfs = ingest_all_suppliers(supplier_files)

        # 2. Validation & Quarantine
        logger.info("[2/7] Validating data schemas and quarantining invalid records...")
        valid_dfs = {}
        quarantine_dfs = []
        ingestion_stats = {}

        for s_id, raw_df in raw_dfs.items():
            valid_df, quaran_df = validate_records(raw_df, run_id=run_id)
            valid_dfs[s_id] = valid_df
            quarantine_dfs.append(quaran_df)
            ingestion_stats[s_id] = {
                "name": SUPPLIER_CONFIGS[s_id]["name"],
                "ingested": len(raw_df),
                "valid": len(valid_df),
                "quarantined": len(quaran_df),
            }
            logger.info(
                f"  -> {s_id} ({SUPPLIER_CONFIGS[s_id]['name']}): "
                f"{len(raw_df):,} ingested | {len(valid_df):,} valid | {len(quaran_df):,} quarantined"
            )

        all_quarantine_df = pd.concat(quarantine_dfs, ignore_index=True) if quarantine_dfs else pd.DataFrame()

        # 3. Canonical Mapping
        mapping_dict = load_identifier_mapping(mapping_file)
        if mapping_dict:
            logger.info(f"[3/7] Loaded {len(mapping_dict):,} product identifier mappings from {mapping_file.name}...")
        else:
            logger.info("[3/7] Mapping supplier SKUs and normalizing GTIN barcodes to Canonical IDs...")

        mapped_dfs = {}
        for s_id, v_df in valid_dfs.items():
            mapped_dfs[s_id] = apply_canonical_mapping(v_df, mapping_dict=mapping_dict)

        # 4. Intra-Supplier Deduplication
        logger.info("[4/7] Performing intra-supplier deduplication...")
        combined_clean_df, dedup_stats = deduplicate_all_suppliers(mapped_dfs)
        for s_id, pruned in dedup_stats.items():
            logger.info(f"  -> {s_id}: {pruned:,} duplicate records pruned")

        # 5. Cross-Supplier Conflict Resolution & Lineage Tracking
        logger.info("[5/7] Harmonizing cross-supplier records and building attribute-level lineage...")
        canonical_products_df, lineage_df = resolve_all_conflicts(
            combined_clean_df,
            price_strategy=price_strategy,
            priority_strategy=priority_strategy,
        )
        logger.info(f"  -> Harmonized into {len(canonical_products_df):,} canonical product SKUs")
        logger.info(f"  -> Generated {len(lineage_df):,} attribute-level lineage records")

        # 6. Idempotent DuckDB Persistence
        logger.info("[6/7] Persisting to DuckDB warehouse with idempotent staging merge...")
        db_mgr.save_sku_cross_reference(combined_clean_df, run_id=run_id)
        db_mgr.save_quarantine_records(all_quarantine_df)
        db_mgr.save_standardized_products(canonical_products_df, lineage_df, run_id=run_id)

        # 7. Outputs & Reconciliation Reports
        logger.info("[7/7] Generating downstream CSV exports and reconciliation reports...")
        output_files = export_output_csvs(
            canonical_products_df, lineage_df, all_quarantine_df, output_dir=output_dir
        )

        end_timestamp = datetime.now(timezone.utc)
        md_report, json_report = generate_reconciliation_report(
            run_id=run_id,
            start_time=run_timestamp,
            end_time=end_timestamp,
            ingestion_stats=ingestion_stats,
            quarantine_df=all_quarantine_df,
            dedup_stats=dedup_stats,
            products_df=canonical_products_df,
            lineage_df=lineage_df,
            reports_dir=reports_dir,
        )

        # Finalize run status in DuckDB
        total_ingested = sum(s["ingested"] for s in ingestion_stats.values())
        total_valid = sum(s["valid"] for s in ingestion_stats.values())
        total_quarantined = len(all_quarantine_df)
        total_canonical = len(canonical_products_df)

        db_mgr.record_run_finish(
            run_id=run_id,
            start_time=run_timestamp,
            end_time=end_timestamp,
            records_ingested=total_ingested,
            records_valid=total_valid,
            records_quarantined=total_quarantined,
            canonical_products_total=total_canonical,
            status="SUCCESS",
            error_message=None,
        )

        duration = round((end_timestamp - run_timestamp).total_seconds(), 2)
        logger.info(f"Pipeline {run_id} completed successfully in {duration}s!")
        logger.info(f"Canonical catalog export: {output_files['canonical_products']}")
        logger.info(f"Reconciliation report: {md_report}")

        return {
            "run_id": run_id,
            "status": "SUCCESS",
            "duration_seconds": duration,
            "records_ingested": total_ingested,
            "records_valid": total_valid,
            "records_quarantined": total_quarantined,
            "canonical_products_count": total_canonical,
            "output_files": output_files,
            "markdown_report": md_report,
            "json_report": json_report,
        }

    except Exception as exc:
        end_timestamp = datetime.now(timezone.utc)
        logger.exception(f"Pipeline {run_id} failed with error: {exc}")
        db_mgr.record_run_finish(
            run_id=run_id,
            start_time=run_timestamp,
            end_time=end_timestamp,
            records_ingested=0,
            records_valid=0,
            records_quarantined=0,
            canonical_products_total=0,
            status="FAILED",
            error_message=str(exc),
        )
        raise exc

"""DuckDB database management and idempotent storage engine.

Handles table creation, transactional operations, upserts, run auditing,
quarantine logging, and attribute lineage queries.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import duckdb
import pandas as pd

from config.settings import DUCKDB_PATH


class DuckDBManager:
    """Manages connections, schema initialization, and transactional persistence in DuckDB."""

    def __init__(self, db_path: Path = DUCKDB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Create and return a new DuckDB connection."""
        return duckdb.connect(str(self.db_path))

    def _init_schema(self) -> None:
        """Initialize tables and indexes if they do not exist."""
        with self.get_connection() as con:
            # 1. Pipeline Execution Runs table
            con.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    run_id VARCHAR PRIMARY KEY,
                    pipeline_name VARCHAR,
                    start_time VARCHAR,
                    end_time VARCHAR,
                    duration_seconds DOUBLE,
                    records_ingested BIGINT,
                    records_valid BIGINT,
                    records_quarantined BIGINT,
                    canonical_products_total BIGINT,
                    status VARCHAR,
                    error_message VARCHAR,
                    config_summary VARCHAR
                );
            """)

            # 2. Standardized Canonical Products table
            con.execute("""
                CREATE TABLE IF NOT EXISTS standardized_products (
                    canonical_product_id VARCHAR PRIMARY KEY,
                    gtin VARCHAR,
                    product_name VARCHAR,
                    category VARCHAR,
                    price_usd DOUBLE,
                    stock_quantity BIGINT,
                    weight_kg DOUBLE,
                    source_suppliers VARCHAR,
                    supplier_count INTEGER,
                    attribute_lineage VARCHAR,
                    last_updated_at VARCHAR,
                    last_run_id VARCHAR
                );
            """)

            # 3. Product Attribute Source Lineage table
            con.execute("""
                CREATE TABLE IF NOT EXISTS product_attribute_lineage (
                    canonical_product_id VARCHAR,
                    attribute_name VARCHAR,
                    supplier_id VARCHAR,
                    source_value VARCHAR,
                    source_timestamp VARCHAR,
                    resolution_rule VARCHAR,
                    run_id VARCHAR,
                    PRIMARY KEY (canonical_product_id, attribute_name)
                );
            """)

            # 4. Quarantine Records table
            con.execute("""
                CREATE TABLE IF NOT EXISTS quarantine_records (
                    quarantine_id VARCHAR PRIMARY KEY,
                    run_id VARCHAR,
                    supplier_id VARCHAR,
                    supplier_sku VARCHAR,
                    rejection_reasons VARCHAR,
                    raw_data VARCHAR,
                    failed_at VARCHAR
                );
            """)

            # 5. SKU Cross-Reference mapping table
            con.execute("""
                CREATE TABLE IF NOT EXISTS sku_cross_reference (
                    supplier_id VARCHAR,
                    supplier_sku VARCHAR,
                    canonical_product_id VARCHAR,
                    gtin VARCHAR,
                    last_seen_at VARCHAR,
                    run_id VARCHAR,
                    PRIMARY KEY (supplier_id, supplier_sku)
                );
            """)

    def record_run_start(self, run_id: str, pipeline_name: str = "MultiSupplierETL", config_summary: str = "") -> None:
        """Log pipeline execution commencement."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        with self.get_connection() as con:
            con.execute("""
                INSERT OR REPLACE INTO pipeline_runs (
                    run_id, pipeline_name, start_time, status, config_summary
                ) VALUES (?, ?, ?, 'RUNNING', ?);
            """, [run_id, pipeline_name, now_utc, config_summary])

    def record_run_finish(
        self,
        run_id: str,
        start_time: datetime,
        end_time: datetime,
        records_ingested: int,
        records_valid: int,
        records_quarantined: int,
        canonical_products_total: int,
        status: str = "SUCCESS",
        error_message: Optional[str] = None,
    ) -> None:
        """Finalize pipeline execution metrics in pipeline_runs."""
        duration_sec = round((end_time - start_time).total_seconds(), 2)
        end_time_str = end_time.strftime("%Y-%m-%d %H:%M:%SZ")
        with self.get_connection() as con:
            con.execute("""
                UPDATE pipeline_runs SET
                    end_time = ?,
                    duration_seconds = ?,
                    records_ingested = ?,
                    records_valid = ?,
                    records_quarantined = ?,
                    canonical_products_total = ?,
                    status = ?,
                    error_message = ?
                WHERE run_id = ?;
            """, [
                end_time_str,
                duration_sec,
                records_ingested,
                records_valid,
                records_quarantined,
                canonical_products_total,
                status,
                error_message,
                run_id,
            ])

    def save_quarantine_records(self, quarantine_df: pd.DataFrame) -> None:
        """Persist quarantined records into DuckDB."""
        if quarantine_df.empty:
            return

        cols = ["quarantine_id", "run_id", "supplier_id", "supplier_sku", "rejection_reasons", "raw_data", "failed_at"]
        df_to_save = quarantine_df[cols]

        with self.get_connection() as con:
            con.register("df_quarantine_temp", df_to_save)
            con.execute("""
                INSERT OR REPLACE INTO quarantine_records
                SELECT * FROM df_quarantine_temp;
            """)
            con.unregister("df_quarantine_temp")

    def save_sku_cross_reference(self, clean_staged_df: pd.DataFrame, run_id: str) -> None:
        """Update the supplier SKU -> canonical_product_id cross-reference table."""
        if clean_staged_df.empty:
            return

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        xref_df = clean_staged_df[["supplier_id", "sku", "canonical_product_id", "gtin_14"]].drop_duplicates(
            subset=["supplier_id", "sku"]
        ).copy()
        xref_df.rename(columns={"sku": "supplier_sku", "gtin_14": "gtin"}, inplace=True)
        xref_df["last_seen_at"] = now_utc
        xref_df["run_id"] = run_id

        with self.get_connection() as con:
            con.register("df_xref_temp", xref_df)
            con.execute("""
                INSERT OR REPLACE INTO sku_cross_reference
                SELECT supplier_id, supplier_sku, canonical_product_id, gtin, last_seen_at, run_id
                FROM df_xref_temp;
            """)
            con.unregister("df_xref_temp")

    def save_standardized_products(
        self,
        products_df: pd.DataFrame,
        lineage_df: pd.DataFrame,
        run_id: str,
    ) -> None:
        """Idempotently save standardized canonical products and attribute lineage.

        Uses transactional staging replacement to ensure complete idempotency
        and safe reruns without duplication or partial states.
        """
        if products_df.empty:
            return

        df_prods = products_df.copy()
        df_prods["last_run_id"] = run_id

        cols = [
            "canonical_product_id", "gtin", "product_name", "category",
            "price_usd", "stock_quantity", "weight_kg", "source_suppliers",
            "supplier_count", "attribute_lineage", "last_updated_at", "last_run_id"
        ]
        df_prods = df_prods[cols]

        df_lineage = lineage_df.copy() if not lineage_df.empty else pd.DataFrame(columns=[
            "canonical_product_id", "attribute_name", "supplier_id",
            "source_value", "source_timestamp", "resolution_rule"
        ])
        df_lineage["run_id"] = run_id

        lineage_cols = [
            "canonical_product_id", "attribute_name", "supplier_id",
            "source_value", "source_timestamp", "resolution_rule", "run_id"
        ]
        df_lineage = df_lineage[lineage_cols]

        with self.get_connection() as con:
            con.execute("BEGIN TRANSACTION;")
            try:
                # 1. Upsert Products
                con.register("temp_prods", df_prods)
                con.execute("""
                    INSERT OR REPLACE INTO standardized_products
                    SELECT * FROM temp_prods;
                """)
                con.unregister("temp_prods")

                # 2. Upsert Lineage
                con.register("temp_lineage", df_lineage)
                con.execute("""
                    INSERT OR REPLACE INTO product_attribute_lineage
                    SELECT * FROM temp_lineage;
                """)
                con.unregister("temp_lineage")

                con.execute("COMMIT;")
            except Exception as e:
                con.execute("ROLLBACK;")
                raise e

    def get_run_history(self) -> pd.DataFrame:
        """Retrieve all pipeline execution logs."""
        with self.get_connection() as con:
            return con.execute("SELECT * FROM pipeline_runs ORDER BY start_time DESC;").df()

    def get_canonical_products_count(self) -> int:
        """Get total count of standardized products in warehouse."""
        with self.get_connection() as con:
            res = con.execute("SELECT COUNT(*) FROM standardized_products;").fetchone()
            return res[0] if res else 0

    def get_all_canonical_products(self) -> pd.DataFrame:
        """Fetch all standardized products as a DataFrame."""
        with self.get_connection() as con:
            return con.execute("SELECT * FROM standardized_products ORDER BY canonical_product_id;").df()

    def get_all_lineage(self) -> pd.DataFrame:
        """Fetch all attribute lineages."""
        with self.get_connection() as con:
            return con.execute("SELECT * FROM product_attribute_lineage ORDER BY canonical_product_id, attribute_name;").df()

    def get_all_quarantine(self, run_id: Optional[str] = None) -> pd.DataFrame:
        """Fetch quarantined records, optionally filtered by run_id."""
        with self.get_connection() as con:
            if run_id:
                return con.execute("SELECT * FROM quarantine_records WHERE run_id = ? ORDER BY failed_at DESC;", [run_id]).df()
            return con.execute("SELECT * FROM quarantine_records ORDER BY failed_at DESC;").df()

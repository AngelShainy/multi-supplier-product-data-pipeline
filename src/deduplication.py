"""Deduplication module for supplier product records.

Handles intra-supplier duplicates by selecting the latest valid record
based on timestamps, ensuring only clean and current records participate in
cross-supplier reconciliation.
"""

from typing import Dict, Tuple
import pandas as pd


def deduplicate_supplier_records(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Deduplicate records within a single supplier.

    Prioritizes the most recent record based on timestamp_utc.
    Deduplicates primarily by supplier SKU. If same canonical_product_id appears
    with different SKUs in the same supplier feed, selects the most recent one.

    Returns:
        (deduplicated_df, duplicates_removed_count)
    """
    if df.empty:
        return df.copy(), 0

    initial_count = len(df)

    # Sort so that latest timestamp comes first
    # Missing timestamps go last
    sorted_df = df.sort_values(
        by=["supplier_id", "sku", "timestamp_utc"],
        ascending=[True, True, False],
        na_position="last",
    )

    # Deduplicate by supplier_id and SKU first
    dedup_sku = sorted_df.drop_duplicates(subset=["supplier_id", "sku"], keep="first")

    # Also deduplicate by supplier_id and canonical_product_id to ensure
    # each supplier contributes at most one active record per canonical product
    dedup_product = dedup_sku.sort_values(
        by=["supplier_id", "canonical_product_id", "timestamp_utc"],
        ascending=[True, True, False],
        na_position="last",
    ).drop_duplicates(subset=["supplier_id", "canonical_product_id"], keep="first")

    duplicates_removed = initial_count - len(dedup_product)
    return dedup_product.reset_index(drop=True), duplicates_removed


def deduplicate_all_suppliers(
    supplier_dfs: Dict[str, pd.DataFrame]
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Deduplicate each supplier's records individually and combine into a single pool."""
    deduped_frames = []
    stats = {}

    for supplier_id, df in supplier_dfs.items():
        deduped, removed_count = deduplicate_supplier_records(df)
        deduped_frames.append(deduped)
        stats[supplier_id] = removed_count

    combined_df = (
        pd.concat(deduped_frames, ignore_index=True)
        if deduped_frames
        else pd.DataFrame()
    )
    return combined_df, stats

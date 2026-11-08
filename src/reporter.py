"""Reconciliation reporting and CSV export module.

Generates comprehensive data engineering audit reports in both Markdown and
JSON formats, along with clean downstream CSV outputs for catalog, quarantine,
and attribute-level source lineage.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

from config.settings import DATA_OUTPUT_DIR, REPORTS_DIR


def export_output_csvs(
    products_df: pd.DataFrame,
    lineage_df: pd.DataFrame,
    quarantine_df: pd.DataFrame,
    output_dir: Path = DATA_OUTPUT_DIR,
) -> Dict[str, Path]:
    """Export standardized canonical products, lineage, and quarantine records to CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)

    products_file = output_dir / "canonical_products.csv"
    lineage_file = output_dir / "product_lineage.csv"
    quarantine_file = output_dir / "quarantine_records.csv"

    products_df.to_csv(products_file, index=False)
    lineage_df.to_csv(lineage_file, index=False)
    quarantine_df.to_csv(quarantine_file, index=False)

    return {
        "canonical_products": products_file,
        "product_lineage": lineage_file,
        "quarantine_records": quarantine_file,
    }


def generate_reconciliation_report(
    run_id: str,
    start_time: datetime,
    end_time: datetime,
    ingestion_stats: Dict[str, Dict[str, int]],
    quarantine_df: pd.DataFrame,
    dedup_stats: Dict[str, int],
    products_df: pd.DataFrame,
    lineage_df: pd.DataFrame,
    reports_dir: Path = REPORTS_DIR,
) -> Tuple[Path, Path]:
    """Generate detailed Markdown and JSON reconciliation reports.

    Returns:
        (markdown_report_path, json_report_path)
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    duration_sec = round((end_time - start_time).total_seconds(), 2)

    total_ingested = sum(s["ingested"] for s in ingestion_stats.values())
    total_valid = sum(s["valid"] for s in ingestion_stats.values())
    total_quarantined = len(quarantine_df)
    total_dedup_removed = sum(dedup_stats.values())
    total_canonical_products = len(products_df)

    # Rejection reasons breakdown
    rejection_breakdown = {}
    if not quarantine_df.empty and "rejection_reasons" in quarantine_df.columns:
        all_reasons = []
        for r_str in quarantine_df["rejection_reasons"].dropna():
            for r in str(r_str).split("; "):
                cleaned = r.strip()
                if cleaned:
                    all_reasons.append(cleaned)
        reason_counts = pd.Series(all_reasons).value_counts()
        rejection_breakdown = reason_counts.to_dict()

    # Overlap metrics
    overlap_counts = {1: 0, 2: 0, 3: 0}
    if not products_df.empty and "supplier_count" in products_df.columns:
        counts = products_df["supplier_count"].value_counts().to_dict()
        for k, v in counts.items():
            if k in overlap_counts:
                overlap_counts[k] = v

    # Lineage resolution rules breakdown
    resolution_rules_breakdown = {}
    if not lineage_df.empty and "resolution_rule" in lineage_df.columns:
        resolution_rules_breakdown = lineage_df["resolution_rule"].value_counts().to_dict()

    # Financial and Inventory KPIs
    total_units = int(products_df["stock_quantity"].sum()) if not products_df.empty else 0
    total_inventory_value = (
        round(float((products_df["price_usd"] * products_df["stock_quantity"]).sum()), 2)
        if not products_df.empty
        else 0.0
    )
    avg_price = round(float(products_df["price_usd"].mean()), 2) if not products_df.empty else 0.0
    min_price = round(float(products_df["price_usd"].min()), 2) if not products_df.empty else 0.0
    max_price = round(float(products_df["price_usd"].max()), 2) if not products_df.empty else 0.0

    report_data = {
        "run_id": run_id,
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%SZ"),
        "end_time": end_time.strftime("%Y-%m-%d %H:%M:%SZ"),
        "duration_seconds": duration_sec,
        "summary": {
            "total_ingested": total_ingested,
            "total_valid": total_valid,
            "total_quarantined": total_quarantined,
            "quarantine_rate_percent": round((total_quarantined / total_ingested * 100), 2) if total_ingested else 0.0,
            "intra_supplier_duplicates_pruned": total_dedup_removed,
            "canonical_products_created": total_canonical_products,
        },
        "supplier_funnel": ingestion_stats,
        "intra_supplier_dedup": dedup_stats,
        "rejection_breakdown": rejection_breakdown,
        "overlap_metrics": overlap_counts,
        "resolution_rules": resolution_rules_breakdown,
        "financial_kpis": {
            "total_canonical_products": total_canonical_products,
            "total_inventory_units": total_units,
            "total_inventory_value_usd": total_inventory_value,
            "average_price_usd": avg_price,
            "min_price_usd": min_price,
            "max_price_usd": max_price,
        },
    }

    # Write JSON report
    json_path = reports_dir / f"reconciliation_report_{run_id}.json"
    latest_json_path = reports_dir / "reconciliation_report_latest.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    with open(latest_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    # Executive summary percentages
    valid_pct = (report_data['summary']['total_valid'] / total_ingested * 100) if total_ingested > 0 else 0.0
    quarantine_pct = (total_quarantined / total_ingested * 100) if total_ingested > 0 else 0.0

    # Overlap percentages
    s_pct = (overlap_counts[1] / total_canonical_products * 100) if total_canonical_products > 0 else 0.0
    d_pct = (overlap_counts[2] / total_canonical_products * 100) if total_canonical_products > 0 else 0.0
    t_pct = (overlap_counts[3] / total_canonical_products * 100) if total_canonical_products > 0 else 0.0

    # Build Markdown Report
    md_lines = [
        f"# Reconciliation & Data Quality Report",
        f"",
        f"**Pipeline Run ID**: `{run_id}`  ",
        f"**Execution Timestamp**: {report_data['start_time']} to {report_data['end_time']}  ",
        f"**Processing Duration**: {duration_sec} seconds  ",
        f"**Overall Status**: **SUCCESS**  ",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"| Metric | Count | Percentage |",
        f"| :--- | :--- | :--- |",
        f"| **Total Ingested Records** | {total_ingested:,} | 100.0% |",
        f"| **Clean / Valid Records** | {total_valid:,} | {valid_pct:.2f}% |",
        f"| **Quarantined Records** | {total_quarantined:,} | {quarantine_pct:.2f}% |",
        f"| **Intra-Supplier Duplicates Pruned** | {total_dedup_removed:,} | - |",
        f"| **Consolidated Canonical Products** | {total_canonical_products:,} | - |",
        f"",
        f"---",
        f"",
        f"## 2. Supplier Ingestion Funnel",
        f"",
        f"| Supplier ID | Supplier Name | Rows Ingested | Valid Rows | Quarantined | Duplicates Pruned | Quarantine Rate |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for supp_id, s in ingestion_stats.items():
        q_rate = (s["quarantined"] / s["ingested"] * 100) if s["ingested"] else 0.0
        dedup_cnt = dedup_stats.get(supp_id, 0)
        md_lines.append(
            f"| `{supp_id}` | {s.get('name', supp_id)} | {s['ingested']:,} | {s['valid']:,} | {s['quarantined']:,} | {dedup_cnt:,} | {q_rate:.2f}% |"
        )

    md_lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Data Quality & Quarantine Analysis",
        f"",
        f"Defective records were quarantined without halting pipeline operations. Root cause distribution:",
        f"",
        f"| Rejection Reason | Record Count | Share of Failures |",
        f"| :--- | :--- | :--- |",
    ])

    total_failures = sum(rejection_breakdown.values()) if rejection_breakdown else 1
    for reason, count in rejection_breakdown.items():
        share = count / total_failures * 100
        md_lines.append(f"| `{reason}` | {count:,} | {share:.1f}% |")

    md_lines.extend([
        f"",
        f"---",
        f"",
        f"## 4. Cross-Supplier Overlap & Harmonization",
        f"",
        f"Physical items identified across distinct supplier catalogs using universal GTIN normalization and deterministic matching:",
        f"",
        f"| Overlap Degree | Product Count | Share of Catalog |",
        f"| :--- | :--- | :--- |",
        f"| **Single Supplier Only** | {overlap_counts[1]:,} | {s_pct:.1f}% |",
        f"| **Dual-Supplied (2 Suppliers)** | {overlap_counts[2]:,} | {d_pct:.1f}% |",
        f"| **Triple-Supplied (All 3 Suppliers)** | {overlap_counts[3]:,} | {t_pct:.1f}% |",
        f"",
        f"---",
        f"",
        f"## 5. Conflict Resolution Rules Applied",
        f"",
        f"| Resolution Rule | Attribute Applications | Description |",
        f"| :--- | :--- | :--- |",
    ])

    rule_descriptions = {
        "SUPPLIER_PRIORITY": "Resolved by supplier precedence (Apex Supplies > Beacon Retail > Crest Wholesale)",
        "LOWEST_PRICE": "Selected lowest wholesale purchase price across suppliers to maximize retailer margin",
        "AGGREGATED_SUM": "Summed inventory quantities across all active supplier warehouses",
        "SINGLE_SOURCE": "Attribute provided by the sole supplier of this product",
        "LATEST_TIMESTAMP": "Resolved by most recent update timestamp",
    }

    for rule, count in resolution_rules_breakdown.items():
        desc = rule_descriptions.get(rule, "Custom resolution rule")
        md_lines.append(f"| `{rule}` | {count:,} | {desc} |")

    md_lines.extend([
        f"",
        f"---",
        f"",
        f"## 6. Catalog Financial & Inventory KPIs",
        f"",
        f"- **Total Standardized Products**: {total_canonical_products:,} SKUs",
        f"- **Total Network Stock Quantity**: {total_units:,} units",
        f"- **Total Network Inventory Valuation**: ${total_inventory_value:,.2f} USD",
        f"- **Average Unit Wholesale Price**: ${avg_price:,.2f} USD",
        f"- **Price Range**: ${min_price:,.2f} USD to ${max_price:,.2f} USD",
        f"",
        f"---",
        f"",
        f"## 7. Sample Multi-Supplier Lineage Provenance",
        f"",
    ])

    # Show a multi-supplier product example if available
    multi_supp_prods = products_df[products_df["supplier_count"] > 1] if not products_df.empty else pd.DataFrame()
    if not multi_supp_prods.empty:
        sample_prod = multi_supp_prods.iloc[0]
        lineage_dict = json.loads(sample_prod["attribute_lineage"])
        md_lines.extend([
            f"**Canonical ID**: `{sample_prod['canonical_product_id']}`  ",
            f"**GTIN**: `{sample_prod['gtin']}`  ",
            f"**Consolidated Name**: `{sample_prod['product_name']}`  ",
            f"**Contributing Suppliers**: `{sample_prod['source_suppliers']}`  ",
            f"",
            f"```json",
            json.dumps(lineage_dict, indent=2),
            f"```",
        ])

    md_path = reports_dir / f"reconciliation_report_{run_id}.md"
    latest_md_path = reports_dir / "reconciliation_report_latest.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    with open(latest_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    return md_path, json_path

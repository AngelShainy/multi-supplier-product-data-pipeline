# Reconciliation & Data Quality Report

**Pipeline Run ID**: `RUN_20261108_142436_ecb09b`  
**Execution Timestamp**: 2026-11-08 14:24:36Z to 2026-11-08 14:34:44Z  
**Processing Duration**: 607.91 seconds  
**Overall Status**: **SUCCESS**  

---

## 1. Executive Summary

| Metric | Count | Percentage |
| :--- | :--- | :--- |
| **Total Ingested Records** | 105,000 | 100.0% |
| **Clean / Valid Records** | 102,376 | 97.50% |
| **Quarantined Records** | 2,624 | 2.50% |
| **Intra-Supplier Duplicates Pruned** | 15,156 | - |
| **Consolidated Canonical Products** | 65,467 | - |

---

## 2. Supplier Ingestion Funnel

| Supplier ID | Supplier Name | Rows Ingested | Valid Rows | Quarantined | Duplicates Pruned | Quarantine Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `supplier_a` | Apex Supplies | 39,900 | 38,903 | 997 | 6,424 | 2.50% |
| `supplier_b` | Beacon Retail | 33,600 | 32,760 | 840 | 4,633 | 2.50% |
| `supplier_c` | Crest Wholesale | 31,500 | 30,713 | 787 | 4,099 | 2.50% |

---

## 3. Data Quality & Quarantine Analysis

Defective records were quarantined without halting pipeline operations. Root cause distribution:

| Rejection Reason | Record Count | Share of Failures |
| :--- | :--- | :--- |
| `INVALID_PRICE_BELOW_MINIMUM` | 618 | 23.6% |
| `INVALID_OR_MISSING_TIMESTAMP` | 370 | 14.1% |
| `MISSING_SKU` | 360 | 13.7% |
| `MISSING_PRODUCT_NAME` | 336 | 12.8% |
| `INVALID_WEIGHT_BELOW_MIN` | 326 | 12.4% |
| `INVALID_STOCK_NEGATIVE` | 313 | 11.9% |
| `BARCODE_NON_NUMERIC` | 301 | 11.5% |

---

## 4. Cross-Supplier Overlap & Harmonization

Physical items identified across distinct supplier catalogs using universal GTIN normalization and deterministic matching:

| Overlap Degree | Product Count | Share of Catalog |
| :--- | :--- | :--- |
| **Single Supplier Only** | 45,961 | 70.2% |
| **Dual-Supplied (2 Suppliers)** | 17,259 | 26.4% |
| **Triple-Supplied (All 3 Suppliers)** | 2,247 | 3.4% |

---

## 5. Conflict Resolution Rules Applied

| Resolution Rule | Attribute Applications | Description |
| :--- | :--- | :--- |
| `SINGLE_SOURCE` | 229,805 | Attribute provided by the sole supplier of this product |
| `SUPPLIER_PRIORITY` | 58,518 | Resolved by supplier precedence (Apex Supplies > Beacon Retail > Crest Wholesale) |
| `LOWEST_PRICE` | 19,506 | Selected lowest wholesale purchase price across suppliers to maximize retailer margin |
| `AGGREGATED_SUM` | 19,506 | Summed inventory quantities across all active supplier warehouses |

---

## 6. Catalog Financial & Inventory KPIs

- **Total Standardized Products**: 65,467 SKUs
- **Total Network Stock Quantity**: 32,081,165 units
- **Total Network Inventory Valuation**: $8,044,001,460.16 USD
- **Average Unit Wholesale Price**: $252.17 USD
- **Price Range**: $9.38 USD to $547.79 USD

---

## 7. Sample Multi-Supplier Lineage Provenance

**Canonical ID**: `PROD-00100093709310`  
**GTIN**: `00100093709310`  
**Consolidated Name**: `Quantum Socket Wrench Set (Model Ultra-393)`  
**Contributing Suppliers**: `supplier_a, supplier_c`  

```json
{
  "product_name": {
    "supplier_id": "supplier_a",
    "source_value": "Quantum Socket Wrench Set (Model Ultra-393)",
    "source_timestamp": "2026-11-06 18:17:00Z",
    "resolution_rule": "SUPPLIER_PRIORITY"
  },
  "category": {
    "supplier_id": "supplier_a",
    "source_value": "Tools & Hardware",
    "raw_category": "tools",
    "source_timestamp": "2026-11-06 18:17:00Z",
    "resolution_rule": "SUPPLIER_PRIORITY"
  },
  "price_usd": {
    "supplier_id": "supplier_a",
    "source_value": 94.38,
    "raw_price": "94.38",
    "raw_currency": "USD",
    "source_timestamp": "2026-11-06 18:17:00Z",
    "resolution_rule": "LOWEST_PRICE"
  },
  "stock_quantity": {
    "supplier_id": "supplier_a, supplier_c",
    "source_value": 1382,
    "supplier_breakdown": {
      "supplier_a": 408,
      "supplier_c": 974
    },
    "source_timestamp": "2026-11-06 18:17:00Z",
    "resolution_rule": "AGGREGATED_SUM"
  },
  "weight_kg": {
    "supplier_id": "supplier_a",
    "source_value": 5.265,
    "raw_weight": "5.265",
    "raw_unit": "kg",
    "source_timestamp": "2026-11-06 18:17:00Z",
    "resolution_rule": "SUPPLIER_PRIORITY"
  }
}
```
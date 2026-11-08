# Multi-Supplier Product Data Integration Pipeline: Data Dictionary

## 1. Overview

This document provides a comprehensive specification of all data schemas across the pipeline lifecycle:
- **Raw Supplier Feeds**: Heterogeneous schemas provided by external suppliers.
- **Unified Staging Layer**: Standardized internal representations with unit and currency normalization.
- **Canonical Warehouse Catalog**: Harmonized master products stored in DuckDB.
- **Attribute Lineage**: Relational and JSON provenance audit trail.
- **Quarantine**: Storage for defective records failing data quality checks.
- **Pipeline Execution Audits**: Metadata tracking execution metrics and status.

---

## 2. Raw Ingestion Schemas

### 2.1 Supplier A: Apex Supplies (`supplier_a.csv`)
- **Precedence**: Priority 1 (Highest)
- **Primary Market**: European & Global Tech Distribution

| Raw Column | Data Type | Nullable | Example | Description |
| :--- | :--- | :--- | :--- | :--- |
| `supplier_sku` | String | No | `APX-010482` | Supplier's internal stock keeping unit |
| `prod_name` | String | No | `ApexPro Wireless Headphones (Model Pro-401)` | Product title |
| `cat` | String | Yes | `elec` | Abbreviated category code |
| `unit_cost` | Float | No | `45.00` | Wholesale cost |
| `curr` | String | No | `EUR`, `USD` | ISO 4217 currency code |
| `stock_qty` | Integer | No | `250` | Warehouse inventory level |
| `weight_kg` | Float | Yes | `0.450` | Net weight in kilograms |
| `barcode_ean` | String | Yes | `0123456789012` | 13-digit EAN barcode |
| `last_modified`| String | No | `2026-11-01T10:30:00Z` | ISO 8601 UTC timestamp |

### 2.2 Supplier B: Beacon Retail (`supplier_b.csv`)
- **Precedence**: Priority 2
- **Primary Market**: North American & UK Retail

| Raw Column | Data Type | Nullable | Example | Description |
| :--- | :--- | :--- | :--- | :--- |
| `item_code` | String | No | `BCN-010482` | Beacon item code |
| `title` | String | No | `APEXPRO WIRELESS HEADPHONES` | Product title (often capitalized) |
| `department` | String | Yes | `Consumer Electronics` | Department classification |
| `wholesale_price` | Float | No | `38.50` | Wholesale purchase price |
| `currency_code` | String | No | `GBP`, `USD` | ISO 4217 currency code |
| `available_inventory` | Integer | No | `180` | Available stock in warehouse |
| `item_weight_lbs` | Float | Yes | `0.992` | Item weight in pounds (lbs) |
| `upc_code` | String | Yes | `123456789012` | 12-digit UPC barcode |
| `updated_at` | String | No | `2026-11-02 14:15:22` | Datetime format |

### 2.3 Supplier C: Crest Wholesale (`supplier_c.csv`)
- **Precedence**: Priority 3
- **Primary Market**: Canadian & Regional Wholesalers

| Raw Column | Data Type | Nullable | Example | Description |
| :--- | :--- | :--- | :--- | :--- |
| `vendor_part_no` | String | No | `CR-010482` | Vendor part reference |
| `description` | String | No | `apexpro wireless headphones` | Product description |
| `product_category` | String | Yes | `Electronics` | Full category description |
| `price` | Float | No | `58.20` | Unit price |
| `iso_currency` | String | No | `CAD`, `USD` | ISO 4217 currency code |
| `quantity_on_hand` | Integer | No | `420` | Stock on hand |
| `package_weight_g` | Float | Yes | `450.0` | Packaged weight in grams (g) |
| `gtin` | String | Yes | `00012345678901`| 14-digit GTIN barcode |
| `timestamp` | String | No | `03/11/2026 09:45:00` | Regional timestamp format |

---

## 3. Warehouse Database Tables (DuckDB)

### 3.1 Table: `standardized_products`
Harmonized master catalog representation storing the single source of truth for all products across suppliers.

| Column | DuckDB Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `canonical_product_id` | `VARCHAR` | `PRIMARY KEY` | Globally unique ID (`PROD-{gtin14}` or `PROD-NOM-{hash}`) |
| `gtin` | `VARCHAR` | Index | Standard 14-digit GTIN / UPC / EAN |
| `product_name` | `VARCHAR` | NOT NULL | Master product title (resolved by supplier precedence) |
| `category` | `VARCHAR` | NOT NULL | Standardized category taxonomy |
| `price_usd` | `DOUBLE` | NOT NULL | Consolidated unit price in USD (lowest cost or priority) |
| `stock_quantity` | `BIGINT` | NOT NULL | Aggregated total network inventory across all suppliers |
| `weight_kg` | `DOUBLE` | NOT NULL | Normalized product weight in kilograms |
| `source_suppliers` | `VARCHAR` | NOT NULL | Comma-delimited list of contributing supplier IDs |
| `supplier_count` | `INTEGER` | NOT NULL | Total distinct suppliers offering this product (1, 2, or 3) |
| `attribute_lineage` | `VARCHAR` | JSON | Complete JSON map documenting attribute-level provenance |
| `last_updated_at` | `VARCHAR` | ISO-8601 | Maximum timestamp of all contributing supplier records |
| `last_run_id` | `VARCHAR` | FK -> runs | Identifier of the pipeline execution run that wrote this row |

### 3.2 Table: `product_attribute_lineage`
Relational lineage records allowing SQL queries on attribute provenance.

| Column | DuckDB Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `canonical_product_id` | `VARCHAR` | Composite PK | Reference to canonical product |
| `attribute_name` | `VARCHAR` | Composite PK | Attribute name (`product_name`, `price_usd`, etc.) |
| `supplier_id` | `VARCHAR` | NOT NULL | Supplier ID providing the attribute value |
| `source_value` | `VARCHAR` | NOT NULL | Exact value used in canonical record |
| `source_timestamp` | `VARCHAR` | NOT NULL | Origin timestamp from source supplier |
| `resolution_rule` | `VARCHAR` | NOT NULL | Business rule used (`SUPPLIER_PRIORITY`, `LOWEST_PRICE`, `AGGREGATED_SUM`, `SINGLE_SOURCE`) |
| `run_id` | `VARCHAR` | NOT NULL | Pipeline execution ID |

### 3.3 Table: `quarantine_records`
Stores rejected records failing validation rules, ensuring pipeline resilience.

| Column | DuckDB Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `quarantine_id` | `VARCHAR` | `PRIMARY KEY` | Unique UUID for quarantine record |
| `run_id` | `VARCHAR` | NOT NULL | Pipeline execution run ID |
| `supplier_id` | `VARCHAR` | NOT NULL | Source supplier identifier |
| `supplier_sku` | `VARCHAR` | NOT NULL | Supplier's SKU (or 'UNKNOWN' if missing) |
| `rejection_reasons` | `VARCHAR` | NOT NULL | Semicolon-delimited list of violated data quality rules |
| `raw_data` | `VARCHAR` | JSON | Original row raw contents serialized as JSON |
| `failed_at` | `VARCHAR` | ISO-8601 | UTC timestamp of validation rejection |

### 3.4 Table: `sku_cross_reference`
Cross-reference mapping between supplier-specific SKUs and canonical IDs.

| Column | DuckDB Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `supplier_id` | `VARCHAR` | Composite PK | Supplier ID (`supplier_a`, `supplier_b`, `supplier_c`) |
| `supplier_sku` | `VARCHAR` | Composite PK | Supplier's SKU code |
| `canonical_product_id` | `VARCHAR` | NOT NULL | Resolved canonical product ID |
| `gtin` | `VARCHAR` | Nullable | Normalized 14-digit GTIN |
| `last_seen_at` | `VARCHAR` | NOT NULL | Timestamp when mapping was last confirmed |
| `run_id` | `VARCHAR` | NOT NULL | Pipeline run ID |

### 3.5 Table: `pipeline_runs`
Execution audit log tracking every pipeline run.

| Column | DuckDB Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `run_id` | `VARCHAR` | `PRIMARY KEY` | Unique run identifier (`RUN_YYYYMMDD_HHMMSS_xxxxxx`) |
| `pipeline_name` | `VARCHAR` | NOT NULL | Pipeline name (`MultiSupplierETL`) |
| `start_time` | `VARCHAR` | NOT NULL | UTC execution start time |
| `end_time` | `VARCHAR` | Nullable | UTC execution end time |
| `duration_seconds` | `DOUBLE` | Nullable | Elapsed execution duration in seconds |
| `records_ingested` | `BIGINT` | NOT NULL | Total rows ingested across all suppliers |
| `records_valid` | `BIGINT` | NOT NULL | Total clean rows passing validation |
| `records_quarantined` | `BIGINT` | NOT NULL | Total defective rows quarantined |
| `canonical_products_total` | `BIGINT` | NOT NULL | Total standardized canonical products produced |
| `status` | `VARCHAR` | NOT NULL | Execution status (`RUNNING`, `SUCCESS`, `FAILED`) |
| `error_message` | `VARCHAR` | Nullable | Error traceback if status is `FAILED` |
| `config_summary` | `VARCHAR` | JSON | Serialized run configuration (strategies, suppliers) |

---

## 4. Standardization Rules & Reference Codes

### 4.1 Currency Exchange Rates (to USD)
| Currency Code | ISO | Conversion Rate |
| :--- | :--- | :--- |
| US Dollar | `USD` | 1.000 |
| Euro | `EUR` | 1.080 |
| British Pound | `GBP` | 1.280 |
| Canadian Dollar | `CAD` | 0.740 |

### 4.2 Weight Conversion (to Kilograms)
| Input Unit | Conversion Factor to kg | Formula |
| :--- | :--- | :--- |
| `kg` | 1.000000 | `kg = kg` |
| `lbs` | 0.453592 | `kg = lbs * 0.45359237` |
| `g` | 0.001000 | `kg = g / 1000.0` |

### 4.3 Category Taxonomy Mapping
All supplier departments and categories normalize to 7 core taxonomies:
- `Electronics`
- `Home & Kitchen`
- `Office Supplies`
- `Sports & Outdoors`
- `Beauty & Health`
- `Tools & Hardware`
- `Other`

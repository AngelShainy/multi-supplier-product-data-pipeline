# Architecture & Design Specification: Multi-Supplier Product Data Pipeline

## 1. System Architecture

The Multi-Supplier Product Data Pipeline is designed following a layered, functional data engineering architecture. It addresses the challenge of integrating heterogeneous, dirty, and conflicting product catalogs into a unified, clean, and deduplicated master catalog.

```mermaid
flowchart TD
    subgraph S1["Supplier Ingestion Layer"]
        SA["Supplier A: Apex Supplies\n(EUR/USD, kg, EAN)"] --> INGEST["Schema Ingest & Unit Normalizer"]
        SB["Supplier B: Beacon Retail\n(GBP/USD, lbs, UPC)"] --> INGEST
        SC["Supplier C: Crest Wholesale\n(CAD/USD, g, GTIN)"] --> INGEST
    end

    subgraph S2["Validation & Quarantine"]
        INGEST --> VAL["Quality Rules Engine"]
        VAL -->|"Defective (Negative Price, Bad Barcode, etc.)"| QUARANTINE["Quarantine Storage\n(quarantine_records)"]
        VAL -->|"Clean Records"| MAPPING["Canonical Identifier Mapping\n(GTIN-14 Pad & Fallback SHA)"]
    end

    subgraph S3["Deduplication & Harmonization"]
        MAPPING --> DEDUP["Intra-Supplier Deduplication\n(Latest Timestamp Wins)"]
        DEDUP --> HARMONIZE["Cross-Supplier Conflict Resolver"]
        HARMONIZE --> LINEAGE["Attribute Lineage Generator"]
    end

    subgraph S4["Persistence & Storage (DuckDB)"]
        HARMONIZE --> DUCKDB[("DuckDB Warehouse\n(products.duckdb)")]
        LINEAGE --> DUCKDB
        QUARANTINE --> DUCKDB
    end

    subgraph S5["Downstream Delivery & Reporting"]
        DUCKDB --> OUT_PROD["canonical_products.csv"]
        DUCKDB --> OUT_LINEAGE["product_lineage.csv"]
        DUCKDB --> OUT_QUAR["quarantine_records.csv"]
        DUCKDB --> REPORT["Reconciliation Report\n(Markdown & JSON)"]
    end
```

---

## 2. Architectural Decision Records (ADRs)

### ADR-001: Embedded DuckDB for Analytical Storage
- **Context**: The pipeline requires high-performance analytical storage, ACID transaction support, fast columnar processing, and zero external infrastructure dependencies for local evaluation and submission.
- **Decision**: Selected **DuckDB**.
- **Rationale**: DuckDB is an in-process, columnar OLAP database engine. It supports full SQL-92, transactional ACID commits, vectorized execution, direct zero-copy pandas/parquet integration, and creates a single persistent `.duckdb` file.
- **Trade-offs**: Single-writer model (concurrency managed via serial pipeline execution).

### ADR-002: Universal GTIN-14 Barcode Normalization
- **Context**: Different suppliers encode the same physical items under varying barcode formats: UPC-12 (North America), EAN-13 (Europe), and GTIN-14 (Global Logistics).
- **Decision**: Standardize all numeric barcodes by left-padding with leading zeros to 14 digits (GTIN-14 specification).
- **Rationale**: A North American UPC `987654321098` pads to `00987654321098`. An EAN `0987654321098` pads to `00987654321098`. This guarantees deterministic identity across international boundaries.
- **Fallback**: Missing barcodes use deterministic SHA-256 digests over normalized `(product_name, category)`.

### ADR-003: Attribute-Level Source Lineage Model
- **Context**: When resolving conflicts across suppliers, data consumers must know exactly who supplied each field, why that supplier was chosen, and the original source value.
- **Decision**: Implemented a **Dual Lineage Strategy**:
  1. **Embedded JSON Column** (`standardized_products.attribute_lineage`): Enables downstream applications and microservices to retrieve complete product provenance in a single lookup without joining.
  2. **Relational Table** (`product_attribute_lineage`): Normalized table `(canonical_product_id, attribute_name, supplier_id, source_value, timestamp, resolution_rule)` for SQL auditing and supplier quality scorecards.

### ADR-004: Transactional Idempotency & Safe Reruns
- **Context**: Data pipelines frequently experience network retries or batch re-executions. Re-running the pipeline must never result in duplicate rows, phantom inventory, or corrupted states.
- **Decision**:
  - Encapsulate all database mutations inside atomic transactions (`BEGIN TRANSACTION ... COMMIT`).
  - Use `INSERT OR REPLACE` semantics keyed on `canonical_product_id` for products and `(supplier_id, supplier_sku)` for cross-references.
  - Lineage records are updated atomically with the current run ID.
  - Safe Rerun Guarantee: Re-running with identical inputs produces the exact same database row count and canonical states.

---

## 3. Conflict Resolution Matrix

When multiple suppliers provide records for the same physical product, attribute values are resolved according to defined business policies:

| Attribute | Default Resolution Policy | Rationale | Tie-Breaker |
| :--- | :--- | :--- | :--- |
| **Product Name** | `SUPPLIER_PRIORITY` | Supplier A (Apex) has the highest catalog metadata quality standards | Latest Timestamp |
| **Category** | `SUPPLIER_PRIORITY` | Standardized category taxonomy driven by primary catalog vendor | Latest Timestamp |
| **Weight (kg)** | `SUPPLIER_PRIORITY` | Converted to kg; primary vendor provides standardized specification | Latest Timestamp |
| **Price (USD)** | `LOWEST_PRICE` | Maximizes retailer gross margin by purchasing at best available wholesale cost | Supplier Priority |
| **Stock Quantity** | `AGGREGATED_SUM` | Total available network inventory is the sum of stock across all supplier warehouses | N/A |
| **Last Updated** | `MAX_TIMESTAMP` | Reflects the freshest data event among all contributing feeds | N/A |

---

## 4. Data Quality Rules & Quarantine Matrix

The data quality engine evaluates all staged records against 8 strict validation gates:

| Gate | Rule Code | Condition | Failure Action |
| :--- | :--- | :--- | :--- |
| 1 | `MISSING_SKU` | SKU is null, empty string, or `'nan'` | Route to Quarantine |
| 2 | `MISSING_PRODUCT_NAME` | Product name is null or whitespace | Route to Quarantine |
| 3 | `INVALID_PRICE_BELOW_MINIMUM` | Price <= 0 or null | Route to Quarantine |
| 4 | `INVALID_PRICE_EXCEEDS_MAXIMUM` | Price > \$50,000 | Route to Quarantine |
| 5 | `UNSUPPORTED_CURRENCY` | Currency not in `[USD, EUR, GBP, CAD]` | Route to Quarantine |
| 6 | `INVALID_STOCK_NEGATIVE` | Stock < 0 or non-integer | Route to Quarantine |
| 7 | `BARCODE_NON_NUMERIC` | Barcode contains non-digit characters | Route to Quarantine |
| 8 | `INVALID_OR_MISSING_TIMESTAMP` | Unparseable timestamp | Route to Quarantine |

**Quarantine Guarantee**: Defective records are tagged with all violated rules and written to `quarantine_records` without stopping pipeline execution.

---

## 5. Performance & Scalability Considerations

- **Chunked / Vectorized Processing**: Ingestion and validation use NumPy and Pandas vector expressions rather than nested Python loops.
- **Memory Footprint**: Ingesting 105,000+ records executes within under 1 GB RAM.
- **Benchmark**:
  - Synthetic Data Generation (105,000 rows): **~2.2 seconds**
  - Full End-to-End Pipeline Execution: **~15-25 seconds**
  - DuckDB Database Storage: **~8-12 MB**
- **Future Scale**: For 100M+ records, the architecture maps cleanly to PySpark or Polars using the identical stage-and-harmonize pattern.

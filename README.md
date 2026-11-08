# Multi-Supplier Product Data Integration Pipeline

An enterprise-grade, idempotent data engineering pipeline built with **Python**, **Pandas**, **DuckDB**, **Pytest**, and **Faker**. 

The pipeline ingests heterogeneous product catalog feeds from multiple suppliers, normalizes schema discrepancies and unit systems (currencies, weights, barcodes), resolves attribute collisions using supplier precedence and timestamps, enforces rigorous data quality validation with quarantine isolation, persists standardized records to a local DuckDB analytical warehouse, and provides attribute-level source lineage.

---

## 1. Business Requirements Matrix

| # | Business Requirement | Pipeline Implementation & Module | Status |
| :-: | :--- | :--- | :-: |
| **1** | Ingest three supplier CSV files with different schemas | Heterogeneous ingestion engine with column mapping and type parsing (`src/ingest.py`) | Verified |
| **2** | Standardize product attributes and column names | Unit conversion (lbs/g -> kg), currency exchange (EUR/GBP/CAD -> USD), taxonomy normalization (`src/ingest.py`, `config/settings.py`) | Verified |
| **3** | Map supplier codes to canonical product IDs | Universal GTIN-14 normalization and deterministic SHA-256 fallback mapping (`src/mapping.py`) | Verified |
| **4** | Handle duplicate records | Intra-supplier deduplication prioritizing latest UTC timestamp (`src/deduplication.py`) | Verified |
| **5** | Resolve conflicting attributes | Configurable precedence (Supplier A > B > C), timestamp tie-breaker, optimal purchase pricing (`src/conflict_resolution.py`) | Verified |
| **6** | Maintain attribute-level source lineage | Dual lineage tracking (relational SQL table + embedded JSON payload) recording provider, source timestamp, and resolution rule (`src/conflict_resolution.py`, `src/database.py`) | Verified |
| **7** | Validate data and quarantine invalid records | 8-gate data quality validator isolating defective records to `quarantine_records` without halting execution (`src/validation.py`) | Verified |
| **8** | Store standardized products in DuckDB | Columnar DuckDB warehouse (`products.duckdb`) with schema DDL, indexed queries, and relational joins (`src/database.py`) | Verified |
| **9** | Implement idempotency and safe reruns | Transactional `INSERT OR REPLACE` staging merge pattern guaranteeing identical state upon re-execution (`src/database.py`) | Verified |
| **10** | Track run IDs, row counts, timestamps, status | Execution metadata audit logging table `pipeline_runs` (`src/database.py`) | Verified |
| **11** | Output CSVs and reconciliation reports | Downstream CSV catalog export, JSON report, and formatted Markdown reconciliation audit (`src/reporter.py`) | Verified |
| **12** | Reproducible synthetic data for 100,000+ records | Vectorized Faker + NumPy generator with seed reproducibility and controlled defect injection (`src/data_generator.py`) | Verified |
| **13** | Automated tests for normal & negative scenarios | 25 automated tests with Pytest covering edge cases, invalid inputs, and E2E workflows (`tests/`) | Verified |
| **14** | Complete README, data dictionary & design docs | Detailed documentation in `README.md`, `docs/DATA_DICTIONARY.md`, and `docs/DESIGN.md` | Verified |

---

## 2. Tech Stack

- **Core Engine**: Python 3.10+
- **Data Transformation & Wrangling**: Pandas (v2.3+)
- **Analytical Storage & Data Warehouse**: DuckDB (v2.0+)
- **Testing & Quality Assurance**: Pytest (v9.2+)
- **Synthetic Data Generation**: Faker (v40.4+) & NumPy

---

## 3. Project Structure

```
Multi-Supplier Product Data Pipeline/
├── config/
│   ├── __init__.py
│   └── settings.py              # System paths, supplier configurations, exchange rates, validation rules
├── data/
│   ├── raw/                     # Ingested CSV files from Supplier A, B, C
│   ├── warehouse/               # DuckDB warehouse file (products.duckdb)
│   ├── output/                  # Downstream CSV exports (canonical products, lineage, quarantine)
│   └── quarantine/              # Quarantined CSV records
├── docs/
│   ├── DATA_DICTIONARY.md       # Comprehensive field descriptions, data types, constraints
│   └── DESIGN.md                # System architecture, ADRs, conflict resolution matrix
├── logs/                        # Structured execution run logs
├── reports/                     # Reconciliation reports (Markdown & JSON)
├── src/
│   ├── __init__.py
│   ├── conflict_resolution.py   # Multi-supplier attribute resolution & lineage generator
│   ├── data_generator.py        # Reproducible 100,000+ record synthetic data generator
│   ├── database.py              # DuckDB database manager (transactions, upserts, run audits)
│   ├── deduplication.py         # Intra-supplier deduplication engine
│   ├── ingest.py                # Heterogeneous CSV ingestion, unit and currency normalization
│   ├── mapping.py               # GTIN-14 barcode normalization and canonical ID resolver
│   ├── pipeline.py              # End-to-end pipeline orchestrator
│   ├── reporter.py              # Reconciliation report generator and CSV exporter
│   └── validation.py            # 8-gate data quality validation engine
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures and mock datasets
│   ├── test_conflict_resolution.py # Precedence, timestamps, and lineage tests
│   ├── test_database.py         # DuckDB storage, runs tracking, and idempotency tests
│   ├── test_deduplication.py    # Intra-supplier deduplication tests
│   ├── test_ingest.py           # Schema normalization, currency, and weight tests
│   ├── test_mapping.py          # Barcode harmonization and canonical ID tests
│   ├── test_pipeline_e2e.py     # End-to-end integration and safe rerun tests
│   ├── test_synthetic_data.py   # Data generation reproducibility and schema tests
│   └── test_validation.py       # Normal and negative quarantine scenario tests
├── main.py                      # CLI entrypoint for pipeline operations
├── requirements.txt             # Project dependencies
└── README.md                    # Project documentation
```

---

Note: Large synthetic input datasets and the DuckDB
warehouse are generated locally during execution and
are excluded from Git version control. Small sample
supplier datasets are included in data/sample/.

## 4. Quick Start & Setup

### 4.1 Prerequisites
- Python 3.10, 3.11, 3.12, or 3.13 installed.

### 4.2 Installation
```bash
# Clone the repository and navigate to root
cd "Multi-Supplier Product Data Pipeline"

# Install required dependencies
pip install -r requirements.txt
```

---

## 5. Usage & CLI Commands

The project includes an intuitive command-line interface via `main.py`:

### 5.1 Generate 100,000+ Reproducible Synthetic Records
Generates 105,000 records partitioned across Supplier A, B, and C with realistic schema variances, catalog overlaps, and intentional defect edge cases:
```bash
python main.py generate-data --records 105000 --seed 42 --error-rate 0.025
```

### 5.2 Execute the Data Integration Pipeline
Runs the end-to-end pipeline: ingestion $\rightarrow$ validation $\rightarrow$ canonical mapping $\rightarrow$ deduplication $\rightarrow$ conflict resolution $\rightarrow$ DuckDB persistence $\rightarrow$ CSV export and reporting:
```bash
python main.py run-pipeline --price-strategy BEST_PRICE --priority-strategy PRIORITY_FIRST
```

### 5.3 Verify Safe Reruns & Idempotency
Executes the pipeline twice back-to-back on identical inputs to verify that zero duplicate records are created and row counts remain strictly invariant:
```bash
python main.py verify-idempotency
```

### 5.4 Display Latest Reconciliation Report
Prints the latest markdown reconciliation summary directly to the terminal:
```bash
python main.py report
```

### 5.5 Run Automated Test Suite
Runs the complete suite of 25 unit and integration tests with verbose reporting:
```bash
pytest -v
```

---

## 6. Architecture & Business Logic

### 6.1 Supplier Schema Heterogeneity
| Dimension | Supplier A (Apex Supplies) | Supplier B (Beacon Retail) | Supplier C (Crest Wholesale) |
| :--- | :--- | :--- | :--- |
| **Precedence** | Priority 1 (Highest) | Priority 2 | Priority 3 |
| **SKU Column** | `supplier_sku` | `item_code` | `vendor_part_no` |
| **Title Column** | `prod_name` | `title` | `description` |
| **Category Column** | `cat` (e.g. `elec`) | `department` (e.g. `Consumer Electronics`) | `product_category` (e.g. `Electronics`) |
| **Price / Currency** | `unit_cost` / `curr` (EUR, USD) | `wholesale_price` / `currency_code` (GBP, USD) | `price` / `iso_currency` (CAD, USD) |
| **Stock Column** | `stock_qty` | `available_inventory` | `quantity_on_hand` |
| **Weight** | `weight_kg` (kg) | `item_weight_lbs` (lbs $\rightarrow$ kg) | `package_weight_g` (g $\rightarrow$ kg) |
| **Barcode** | `barcode_ean` (13-digit EAN) | `upc_code` (12-digit UPC) | `gtin` (14-digit GTIN) |
| **Timestamp** | `last_modified` (ISO-8601 UTC) | `updated_at` (`YYYY-MM-DD HH:MM:SS`) | `timestamp` (`DD/MM/YYYY HH:MM:SS`) |

### 6.2 Canonical Mapping & Barcode Harmonization
- **GTIN-14 Standard**: All numeric barcodes are left-padded with zeros to 14 digits.
  - UPC-12 `987654321098` $\rightarrow$ `00987654321098`
  - EAN-13 `0987654321098` $\rightarrow$ `00987654321098`
  - Canonical ID: `PROD-00987654321098`
- **Fallback**: Products without universal barcodes receive a deterministic canonical ID computed via SHA-256 hash of normalized `(product_name, category)`.

### 6.3 Conflict Resolution Rules
When multiple suppliers supply the same physical product:
1. **Catalog Master Data (`product_name`, `category`, `weight_kg`)**: Sourced from the highest priority supplier (Apex Supplies > Beacon Retail > Crest Wholesale).
2. **Wholesale Price (`price_usd`)**: Sourced via `LOWEST_PRICE` across suppliers to optimize retailer purchase margin.
3. **Available Stock (`stock_quantity`)**: Aggregated across all active warehouses (`AGGREGATED_SUM`).
4. **Timestamp Tie-Breaker**: When supplier priority is tied, the most recent update wins.

### 6.4 Attribute-Level Source Lineage
Every attribute in `standardized_products` maintains complete provenance:
```json
{
  "product_name": {
    "supplier_id": "supplier_a",
    "source_value": "ApexPro Wireless Headphones (Model Pro-401)",
    "source_timestamp": "2026-11-01 10:30:00Z",
    "resolution_rule": "SUPPLIER_PRIORITY"
  },
  "price_usd": {
    "supplier_id": "supplier_b",
    "source_value": 38.5,
    "raw_price": "30.08",
    "raw_currency": "GBP",
    "source_timestamp": "2026-11-02 14:15:22Z",
    "resolution_rule": "LOWEST_PRICE"
  },
  "stock_quantity": {
    "supplier_id": "supplier_a, supplier_b, supplier_c",
    "source_value": 850,
    "resolution_rule": "AGGREGATED_SUM"
  }
}
```

### 6.5 Data Validation & Quarantine Engine
Records failing any of the 8 validation rules (e.g. negative price, negative stock, missing SKU/name, invalid barcode length, corrupt timestamp) are segregated to `quarantine_records` with failure reasons and raw payloads, ensuring the pipeline never crashes on dirty data.

---

## 7. Testing & Quality Assurance

The test suite covers:
- **Unit Tests**:
  - `test_ingest.py`: Unit conversion, currency rates, category taxonomy normalization, timestamp parsing, missing files.
  - `test_validation.py`: Normal records, negative prices, negative stock, bad barcodes, missing fields.
  - `test_mapping.py`: GTIN-12/13/14 normalization, fallback SHA IDs.
  - `test_deduplication.py`: Intra-supplier latest-timestamp selection.
  - `test_conflict_resolution.py`: Supplier precedence, lowest-price selection, aggregated stock, lineage integrity.
  - `test_database.py`: DuckDB table initialization, run tracking, idempotent upserts.
  - `test_synthetic_data.py`: Seed reproducibility, error rate injection.
- **Integration Tests**:
  - `test_pipeline_e2e.py`: End-to-end execution, database persistence, CSV export, reconciliation reporting, and safe rerun verification.

Execute tests via:
```bash
pytest -v
```
Output:
```
tests/test_conflict_resolution.py::test_conflict_resolution_supplier_priority PASSED
tests/test_conflict_resolution.py::test_conflict_resolution_priority_price_strategy PASSED
tests/test_conflict_resolution.py::test_conflict_resolution_timestamp_tiebreaker PASSED
tests/test_database.py::test_database_initialization PASSED
tests/test_database.py::test_pipeline_run_tracking PASSED
tests/test_database.py::test_idempotent_save_standardized_products PASSED
tests/test_deduplication.py::test_intra_supplier_deduplication_keeps_latest PASSED
tests/test_deduplication.py::test_deduplicate_all_suppliers PASSED
tests/test_ingest.py::test_ingest_supplier_a PASSED
tests/test_ingest.py::test_ingest_supplier_b PASSED
tests/test_ingest.py::test_ingest_supplier_c PASSED
tests/test_ingest.py::test_category_normalization PASSED
tests/test_ingest.py::test_timestamp_parsing PASSED
tests/test_ingest.py::test_ingest_nonexistent_file PASSED
tests/test_ingest.py::test_ingest_invalid_supplier PASSED
tests/test_mapping.py::test_normalize_gtin_pads_to_14_digits PASSED
tests/test_mapping.py::test_cross_supplier_barcode_harmonization PASSED
tests/test_mapping.py::test_fallback_id_generation PASSED
tests/test_pipeline_e2e.py::test_pipeline_e2e_execution PASSED
tests/test_pipeline_e2e.py::test_pipeline_safe_rerun_idempotency PASSED
tests/test_synthetic_data.py::test_master_catalog_reproducibility PASSED
tests/test_synthetic_data.py::test_synthetic_data_generation PASSED
tests/test_validation.py::test_validation_quarantines_defective_records PASSED
tests/test_validation.py::test_barcode_validation PASSED
tests/test_validation.py::test_quarantine_empty_input PASSED
============================= 25 passed in 3.92s ==============================
```

---

## 8. License

Open-source project developed for academic submission and enterprise data engineering reference.

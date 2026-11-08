"""Pipeline configuration, supplier definitions, and schema mappings."""
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_WAREHOUSE_DIR = DATA_DIR / "warehouse"
DATA_OUTPUT_DIR = DATA_DIR / "output"
DATA_QUARANTINE_DIR = DATA_DIR / "quarantine"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
DOCS_DIR = BASE_DIR / "docs"

# Warehouse path
DUCKDB_PATH = DATA_WAREHOUSE_DIR / "products.duckdb"

# Supplier Configurations
# Priorities: Lower number = higher precedence (1 is highest priority)
SUPPLIER_CONFIGS = {
    "supplier_a": {
        "id": "supplier_a",
        "name": "Apex Supplies",
        "priority": 1,
        "filename": "supplier_a.csv",
        "weight_unit": "kg",
        "columns": {
            "sku": "supplier_sku",
            "name": "prod_name",
            "category": "cat",
            "price": "unit_cost",
            "currency": "curr",
            "stock": "stock_qty",
            "weight": "weight_kg",
            "barcode": "barcode_ean",
            "timestamp": "last_modified",
        },
    },
    "supplier_b": {
        "id": "supplier_b",
        "name": "Beacon Retail",
        "priority": 2,
        "filename": "supplier_b.csv",
        "weight_unit": "lbs",
        "columns": {
            "sku": "item_code",
            "name": "title",
            "category": "department",
            "price": "wholesale_price",
            "currency": "currency_code",
            "stock": "available_inventory",
            "weight": "item_weight_lbs",
            "barcode": "upc_code",
            "timestamp": "updated_at",
        },
    },
    "supplier_c": {
        "id": "supplier_c",
        "name": "Crest Wholesale",
        "priority": 3,
        "filename": "supplier_c.csv",
        "weight_unit": "g",
        "columns": {
            "sku": "vendor_part_no",
            "name": "description",
            "category": "product_category",
            "price": "price",
            "currency": "iso_currency",
            "stock": "quantity_on_hand",
            "weight": "package_weight_g",
            "barcode": "gtin",
            "timestamp": "timestamp",
        },
    },
}

# Unit conversions
WEIGHT_CONVERSION_TO_KG = {
    "kg": 1.0,
    "lbs": 0.45359237,
    "g": 0.001,
}

# Currency Exchange Rates to USD
CURRENCY_EXCHANGE_RATES = {
    "USD": 1.00,
    "EUR": 1.08,
    "GBP": 1.28,
    "CAD": 0.74,
}

# Standard Category Taxonomy Mapping
CATEGORY_NORMALIZATION_MAP = {
    # Electronics
    "elec": "Electronics",
    "electronics": "Electronics",
    "consumer electronics": "Electronics",
    "gadgets": "Electronics",
    "audio & video": "Electronics",
    # Home & Kitchen
    "home": "Home & Kitchen",
    "kitchen": "Home & Kitchen",
    "kitchen & dining": "Home & Kitchen",
    "home & kitchen": "Home & Kitchen",
    "appliances": "Home & Kitchen",
    "housewares": "Home & Kitchen",
    # Office Supplies
    "office": "Office Supplies",
    "office supplies": "Office Supplies",
    "office products": "Office Supplies",
    "stationery": "Office Supplies",
    "business": "Office Supplies",
    # Sports & Outdoors
    "sports": "Sports & Outdoors",
    "outdoors": "Sports & Outdoors",
    "sports & outdoors": "Sports & Outdoors",
    "fitness": "Sports & Outdoors",
    "fitness & outdoors": "Sports & Outdoors",
    # Beauty & Health
    "beauty": "Beauty & Health",
    "health": "Beauty & Health",
    "health & personal care": "Beauty & Health",
    "personal care": "Beauty & Health",
    "beauty & personal care": "Beauty & Health",
    # Tools & Hardware
    "tools": "Tools & Hardware",
    "hardware": "Tools & Hardware",
    "hardware & tools": "Tools & Hardware",
    "diy": "Tools & Hardware",
}

DEFAULT_CATEGORY = "Other"

# Validation thresholds
VALIDATION_RULES = {
    "min_price": 0.01,
    "max_price": 50000.0,
    "min_stock": 0,
    "max_stock": 1000000,
    "min_weight_kg": 0.001,
    "max_weight_kg": 2000.0,
    "allowed_currencies": set(CURRENCY_EXCHANGE_RATES.keys()),
}

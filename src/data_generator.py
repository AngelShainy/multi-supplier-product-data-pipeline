"""Synthetic data generator for Multi-Supplier Product Data Pipeline.

Generates reproducible synthetic datasets (105,000 canonical products and supplier feeds)
with differing schemas, intentional cross-supplier overlaps, and edge cases
(corrupt data, invalid prices, bad barcodes) to test data validation and quarantine.
Also outputs the canonical master catalog and product identifier cross-reference mapping.
"""

from datetime import datetime, timedelta
from pathlib import Path
import random
from typing import Dict, List, Optional, Tuple
from faker import Faker
import numpy as np
import pandas as pd

from config.settings import DATA_RAW_DIR, SUPPLIER_CONFIGS
from src.mapping import normalize_gtin


def generate_gtin(random_state: random.Random) -> str:
    """Generate a valid 12, 13, or 14-digit GTIN / UPC / EAN string."""
    length = random_state.choice([12, 13, 14])
    digits = [str(random_state.randint(0, 9)) for _ in range(length)]
    if digits[0] == "0":
        digits[0] = str(random_state.randint(1, 9))
    return "".join(digits)


def create_master_catalog(total_base_products: int, seed: int = 42) -> List[Dict]:
    """Create a master pool of base products used to generate cross-supplier catalog overlap."""
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    categories = [
        ("Electronics", ["Wireless Headphones", "Mechanical Keyboard", "USB-C Hub", "4K Webcam", "Smart Watch", "Portable Power Bank"]),
        ("Home & Kitchen", ["Espresso Machine", "Air Fryer", "Stainless Steel Knife Set", "Blender 1000W", "Robot Vacuum", "Nonstick Cookware"]),
        ("Office Supplies", ["Ergonomic Desk Chair", "Adjustable Monitor Arm", "Desk Mat Large", "Gel Pen Set 24pk", "Stapler Heavy Duty"]),
        ("Sports & Outdoors", ["Yoga Mat Extra Thick", "Resistance Bands Set", "Insulated Water Bottle", "Camping Tent 4-Person", "Hiking Backpack"]),
        ("Beauty & Health", ["Sonic Electric Toothbrush", "Facial Cleansing Device", "Hair Dryer Ionic", "Massage Gun Deep Tissue"]),
        ("Tools & Hardware", ["Cordless Drill 20V", "Socket Wrench Set", "Digital Caliper", "Laser Measuring Tool"]),
    ]

    brands = ["ApexPro", "Vanguard", "NovaTech", "AeroCraft", "Titan", "Zenith", "Quantum", "Echo", "Prism", "Lumina"]

    master_products = []
    for i in range(total_base_products):
        cat_name, item_templates = rng.choice(categories)
        brand = rng.choice(brands)
        item_base = rng.choice(item_templates)
        model_suffix = f"Model {rng.choice(['X', 'Pro', 'Ultra', 'Plus', 'Air', 'Max'])}-{rng.randint(100, 999)}"
        name = f"{brand} {item_base} ({model_suffix})"

        base_price = round(rng.uniform(9.99, 499.99), 2)
        base_weight_kg = round(rng.uniform(0.1, 15.0), 3)
        gtin = generate_gtin(rng)
        gtin_14 = normalize_gtin(gtin)
        canonical_id = f"PROD-{gtin_14}" if gtin_14 else f"PROD-BASE-{i:06d}"

        master_products.append({
            "canonical_product_id": canonical_id,
            "product_name": name,
            "category": cat_name,
            "base_price_usd": base_price,
            "base_weight_kg": base_weight_kg,
            "gtin": gtin,
        })

    return master_products


def generate_synthetic_data(
    total_records: int = 105000,
    seed: int = 42,
    output_dir: Path = DATA_RAW_DIR,
    error_rate: float = 0.025,
    canonical_products_count: Optional[int] = None,
) -> Dict[str, Path]:
    """Generate synthetic canonical master catalog, 3 supplier CSV feeds, and identifier mapping.

    Args:
        total_records: Total supplier records across the 3 feeds (default: 105,000).
        seed: Random seed for exact reproducibility.
        output_dir: Target directory.
        error_rate: Rate of realistic edge-case defects.
        canonical_products_count: Total unique canonical products to generate (defaults to total_records).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)

    # Canonical products pool size
    n_canonical = canonical_products_count if canonical_products_count is not None else total_records
    master_catalog = create_master_catalog(n_canonical, seed=seed)

    # 1. Save Canonical Products Master Catalog
    df_canonical = pd.DataFrame(master_catalog)
    file_canonical = output_dir / "canonical_products_master.csv"
    df_canonical.to_csv(file_canonical, index=False)

    # Partition supplier counts so sum(counts) == total_records exactly
    count_a = int(total_records * 0.38)
    count_b = int(total_records * 0.32)
    count_c = total_records - count_a - count_b

    base_time = datetime(2026, 11, 1, 0, 0, 0)
    mapping_records = []

    # -------------------------------------------------------------
    # 2. Supplier A: Apex Supplies (count_a rows)
    # Schema: supplier_sku, prod_name, cat, unit_cost, curr, stock_qty, weight_kg, barcode_ean, last_modified
    # -------------------------------------------------------------
    indices_a = rng.choices(range(len(master_catalog)), k=count_a)
    rows_a = []
    cat_abbr = {"Electronics": "elec", "Home & Kitchen": "home", "Office Supplies": "office",
                "Sports & Outdoors": "sports", "Beauty & Health": "beauty", "Tools & Hardware": "tools"}

    for master_idx in indices_a:
        base_item = master_catalog[master_idx]
        sku = f"APX-{master_idx:06d}"
        name = base_item["product_name"]
        cat = cat_abbr.get(base_item["category"], "other")
        curr = rng.choice(["USD", "EUR"])
        rate = 1.0 if curr == "USD" else 0.92
        price = round(base_item["base_price_usd"] * rate * rng.uniform(0.95, 1.05), 2)
        stock = rng.randint(0, 500)
        weight = base_item["base_weight_kg"]
        barcode = base_item["gtin"]
        ts = (base_time + timedelta(hours=rng.randint(0, 168), minutes=rng.randint(0, 59))).isoformat() + "Z"

        rows_a.append({
            "supplier_sku": sku,
            "prod_name": name,
            "cat": cat,
            "unit_cost": price,
            "curr": curr,
            "stock_qty": stock,
            "weight_kg": weight,
            "barcode_ean": barcode,
            "last_modified": ts,
        })
        mapping_records.append({
            "supplier_id": "supplier_a",
            "supplier_sku": sku,
            "canonical_product_id": base_item["canonical_product_id"],
            "gtin": barcode,
        })

    df_a = pd.DataFrame(rows_a)
    _inject_anomalies(df_a, rng, error_rate, sku_col="supplier_sku", name_col="prod_name",
                      price_col="unit_cost", stock_col="stock_qty", barcode_col="barcode_ean",
                      ts_col="last_modified", weight_col="weight_kg")

    file_a = output_dir / SUPPLIER_CONFIGS["supplier_a"]["filename"]
    df_a.to_csv(file_a, index=False)

    # -------------------------------------------------------------
    # 3. Supplier B: Beacon Retail (count_b rows)
    # Schema: item_code, title, department, wholesale_price, currency_code, available_inventory, item_weight_lbs, upc_code, updated_at
    # -------------------------------------------------------------
    indices_b = rng.choices(range(len(master_catalog)), k=count_b)
    rows_b = []
    dept_map = {"Electronics": "Consumer Electronics", "Home & Kitchen": "Kitchen & Dining",
                "Office Supplies": "Office Products", "Sports & Outdoors": "Fitness & Outdoors",
                "Beauty & Health": "Health & Personal Care", "Tools & Hardware": "Hardware & Tools"}

    for master_idx in indices_b:
        base_item = master_catalog[master_idx]
        sku = f"BCN-{master_idx:06d}"
        name = base_item["product_name"].upper() if rng.random() < 0.2 else base_item["product_name"]
        dept = dept_map.get(base_item["category"], "General")
        curr = rng.choice(["USD", "GBP"])
        rate = 1.0 if curr == "USD" else 0.78
        price = round(base_item["base_price_usd"] * rate * rng.uniform(0.92, 1.08), 2)
        stock = rng.randint(0, 750)
        weight_lbs = round(base_item["base_weight_kg"] / 0.45359237, 2)
        barcode = base_item["gtin"]
        ts = (base_time + timedelta(hours=rng.randint(24, 192), minutes=rng.randint(0, 59))).strftime("%Y-%m-%d %H:%M:%S")

        rows_b.append({
            "item_code": sku,
            "title": name,
            "department": dept,
            "wholesale_price": price,
            "currency_code": curr,
            "available_inventory": stock,
            "item_weight_lbs": weight_lbs,
            "upc_code": barcode,
            "updated_at": ts,
        })
        mapping_records.append({
            "supplier_id": "supplier_b",
            "supplier_sku": sku,
            "canonical_product_id": base_item["canonical_product_id"],
            "gtin": barcode,
        })

    df_b = pd.DataFrame(rows_b)
    _inject_anomalies(df_b, rng, error_rate, sku_col="item_code", name_col="title",
                      price_col="wholesale_price", stock_col="available_inventory", barcode_col="upc_code",
                      ts_col="updated_at", weight_col="item_weight_lbs")

    file_b = output_dir / SUPPLIER_CONFIGS["supplier_b"]["filename"]
    df_b.to_csv(file_b, index=False)

    # -------------------------------------------------------------
    # 4. Supplier C: Crest Wholesale (count_c rows)
    # Schema: vendor_part_no, description, product_category, price, iso_currency, quantity_on_hand, package_weight_g, gtin, timestamp
    # -------------------------------------------------------------
    indices_c = rng.choices(range(len(master_catalog)), k=count_c)
    rows_c = []
    for master_idx in indices_c:
        base_item = master_catalog[master_idx]
        sku = f"CR-{master_idx:06d}"
        name = base_item["product_name"].lower() if rng.random() < 0.15 else base_item["product_name"]
        cat = base_item["category"]
        curr = rng.choice(["USD", "CAD"])
        rate = 1.0 if curr == "USD" else 1.35
        price = round(base_item["base_price_usd"] * rate * rng.uniform(0.90, 1.10), 2)
        stock = rng.randint(0, 1000)
        weight_g = round(base_item["base_weight_kg"] * 1000.0, 1)
        barcode = base_item["gtin"]
        dt_c = base_time + timedelta(hours=rng.randint(48, 240), minutes=rng.randint(0, 59))
        ts = dt_c.strftime("%d/%m/%Y %H:%M:%S")

        rows_c.append({
            "vendor_part_no": sku,
            "description": name,
            "product_category": cat,
            "price": price,
            "iso_currency": curr,
            "quantity_on_hand": stock,
            "package_weight_g": weight_g,
            "gtin": barcode,
            "timestamp": ts,
        })
        mapping_records.append({
            "supplier_id": "supplier_c",
            "supplier_sku": sku,
            "canonical_product_id": base_item["canonical_product_id"],
            "gtin": barcode,
        })

    df_c = pd.DataFrame(rows_c)
    _inject_anomalies(df_c, rng, error_rate, sku_col="vendor_part_no", name_col="description",
                      price_col="price", stock_col="quantity_on_hand", barcode_col="gtin",
                      ts_col="timestamp", weight_col="package_weight_g")

    file_c = output_dir / SUPPLIER_CONFIGS["supplier_c"]["filename"]
    df_c.to_csv(file_c, index=False)

    # -------------------------------------------------------------
    # 5. Product Identifier Mapping Cross-Reference
    # -------------------------------------------------------------
    df_mapping = pd.DataFrame(mapping_records).drop_duplicates(subset=["supplier_id", "supplier_sku"])
    file_mapping = output_dir / "product_identifier_mapping.csv"
    df_mapping.to_csv(file_mapping, index=False)

    return {
        "canonical_products_master": file_canonical,
        "supplier_a": file_a,
        "supplier_b": file_b,
        "supplier_c": file_c,
        "product_identifier_mapping": file_mapping,
    }


def _inject_anomalies(
    df: pd.DataFrame,
    rng: random.Random,
    error_rate: float,
    sku_col: str,
    name_col: str,
    price_col: str,
    stock_col: str,
    barcode_col: str,
    ts_col: str,
    weight_col: str,
) -> None:
    """Inject intentional real-world defects to test validation and quarantine pipeline."""
    n_rows = len(df)
    error_count = int(n_rows * error_rate)
    error_indices = rng.sample(range(n_rows), min(error_count, n_rows))

    for idx in error_indices:
        anomaly_type = rng.choice([
            "missing_sku",
            "missing_name",
            "negative_price",
            "zero_price",
            "negative_stock",
            "corrupt_barcode",
            "invalid_timestamp",
            "negative_weight",
        ])

        if anomaly_type == "missing_sku":
            df.at[idx, sku_col] = np.nan
        elif anomaly_type == "missing_name":
            df.at[idx, name_col] = ""
        elif anomaly_type == "negative_price":
            df.at[idx, price_col] = -round(abs(float(df.at[idx, price_col])), 2)
        elif anomaly_type == "zero_price":
            df.at[idx, price_col] = 0.0
        elif anomaly_type == "negative_stock":
            df.at[idx, stock_col] = -rng.randint(1, 50)
        elif anomaly_type == "corrupt_barcode":
            df.at[idx, barcode_col] = "INVALID_GTIN_#@"
        elif anomaly_type == "invalid_timestamp":
            df.at[idx, ts_col] = "CORRUPT_TIMESTAMP_NOT_A_DATE"
        elif anomaly_type == "negative_weight":
            df.at[idx, weight_col] = -5.0

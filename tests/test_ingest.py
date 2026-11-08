"""Unit tests for ingestion and schema standardization."""
import pytest
import pandas as pd
from src.ingest import ingest_supplier_file, parse_timestamp_safe, normalize_category


def test_ingest_supplier_a(sample_supplier_a_csv):
    """Test Supplier A ingestion: EUR to USD conversion, kg weight, column mapping."""
    df = ingest_supplier_file("supplier_a", sample_supplier_a_csv)

    assert len(df) == 4
    assert "sku" in df.columns
    assert "price_usd" in df.columns
    assert "weight_kg" in df.columns

    # Verify APX-001 mapping
    row_001 = df[df["sku"] == "APX-001"].iloc[0]
    assert row_001["name"] == "Apex Wireless Keyboard"
    assert row_001["price_usd"] == 45.00
    assert row_001["weight_kg"] == 0.850
    assert row_001["category_standardized"] == "Electronics"

    # Verify APX-002 EUR conversion (25 EUR * 1.08 = 27.00 USD)
    row_002 = df[df["sku"] == "APX-002"].iloc[0]
    assert row_002["price_usd"] == 27.00
    assert row_002["weight_kg"] == 0.200


def test_ingest_supplier_b(sample_supplier_b_csv):
    """Test Supplier B ingestion: lbs to kg conversion, GBP to USD conversion."""
    df = ingest_supplier_file("supplier_b", sample_supplier_b_csv)

    assert len(df) == 3
    # Check BCN-501: 20 GBP * 1.28 = 25.60 USD
    row_501 = df[df["sku"] == "BCN-501"].iloc[0]
    assert row_501["price_usd"] == 25.60
    # 0.440924 lbs * 0.45359237 = ~0.200 kg
    assert abs(row_501["weight_kg"] - 0.200) < 0.005
    assert row_501["category_standardized"] == "Electronics"


def test_ingest_supplier_c(sample_supplier_c_csv):
    """Test Supplier C ingestion: grams to kg conversion, CAD to USD conversion."""
    df = ingest_supplier_file("supplier_c", sample_supplier_c_csv)

    assert len(df) == 2
    # Check CR-901: 38 CAD * 0.74 = 28.12 USD
    row_901 = df[df["sku"] == "CR-901"].iloc[0]
    assert row_901["price_usd"] == 28.12
    # 200g -> 0.200 kg
    assert row_901["weight_kg"] == 0.200
    assert row_901["category_standardized"] == "Electronics"


def test_category_normalization():
    """Verify various synonyms map to canonical category taxonomy."""
    assert normalize_category("elec") == "Electronics"
    assert normalize_category("Consumer Electronics") == "Electronics"
    assert normalize_category("Kitchen") == "Home & Kitchen"
    assert normalize_category("Office Products") == "Office Supplies"
    assert normalize_category("Unknown XYZ") == "Other"
    assert normalize_category(None) == "Other"


def test_timestamp_parsing():
    """Verify robust parsing of various ISO and datetime formats."""
    series = pd.Series([
        "2026-11-01T10:00:00Z",
        "2026-11-02 14:00:00",
        "03/11/2026 10:15:00",
        "NOT_A_DATE",
    ])
    parsed = parse_timestamp_safe(series)
    assert pd.notna(parsed[0])
    assert pd.notna(parsed[1])
    assert pd.notna(parsed[2])
    assert pd.isna(parsed[3])


def test_ingest_nonexistent_file(temp_dir):
    """Negative test: Ingesting missing file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        ingest_supplier_file("supplier_a", temp_dir / "nonexistent.csv")


def test_ingest_invalid_supplier(temp_dir):
    """Negative test: Invalid supplier identifier raises ValueError."""
    dummy_csv = temp_dir / "dummy.csv"
    dummy_csv.write_text("a,b\n1,2", encoding="utf-8")
    with pytest.raises(ValueError):
        ingest_supplier_file("supplier_unknown", dummy_csv)

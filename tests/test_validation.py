"""Unit tests for data validation and quarantine handling."""
import pandas as pd
from src.ingest import ingest_supplier_file
from src.validation import validate_records, is_valid_barcode


def test_validation_quarantines_defective_records(sample_supplier_a_csv, sample_supplier_b_csv, sample_supplier_c_csv):
    """Test that defective records are cleanly separated into quarantine with specific reasons."""
    df_a = ingest_supplier_file("supplier_a", sample_supplier_a_csv)
    valid_a, quaran_a = validate_records(df_a, run_id="TEST_RUN")

    # APX-BAD-01 has negative price (-15.00)
    assert len(valid_a) == 3
    assert len(quaran_a) == 1
    assert quaran_a.iloc[0]["supplier_sku"] == "APX-BAD-01"
    assert "INVALID_PRICE_BELOW_MINIMUM" in quaran_a.iloc[0]["rejection_reasons"]
    assert quaran_a.iloc[0]["run_id"] == "TEST_RUN"

    # Supplier B: item with missing SKU
    df_b = ingest_supplier_file("supplier_b", sample_supplier_b_csv)
    valid_b, quaran_b = validate_records(df_b, run_id="TEST_RUN")
    assert len(valid_b) == 2
    assert len(quaran_b) == 1
    assert "MISSING_SKU" in quaran_b.iloc[0]["rejection_reasons"]

    # Supplier C: item with negative stock
    df_c = ingest_supplier_file("supplier_c", sample_supplier_c_csv)
    valid_c, quaran_c = validate_records(df_c, run_id="TEST_RUN")
    assert len(valid_c) == 1
    assert len(quaran_c) == 1
    assert "INVALID_STOCK_NEGATIVE" in quaran_c.iloc[0]["rejection_reasons"]


def test_barcode_validation():
    """Verify barcode validity checking logic."""
    # Valid lengths: 8, 12, 13, 14 numeric
    assert is_valid_barcode("12345678")[0] is True
    assert is_valid_barcode("123456789012")[0] is True
    assert is_valid_barcode("1234567890123")[0] is True
    assert is_valid_barcode("12345678901234")[0] is True

    # Missing is allowed (will use fallback mapping)
    assert is_valid_barcode(None)[0] is True
    assert is_valid_barcode("")[0] is True

    # Corrupt / non-numeric
    ok, reason = is_valid_barcode("BAD_BARCODE")
    assert ok is False
    assert reason == "BARCODE_NON_NUMERIC"

    # Invalid length (e.g. 5 digits)
    ok, reason = is_valid_barcode("12345")
    assert ok is False
    assert "BARCODE_INVALID_LENGTH" in reason

    # All zeros
    ok, reason = is_valid_barcode("000000000000")
    assert ok is False
    assert reason == "BARCODE_ALL_ZEROS"


def test_quarantine_empty_input():
    """Verify validate_records handles empty DataFrame without errors."""
    empty_df = pd.DataFrame()
    valid_df, quaran_df = validate_records(empty_df, run_id="TEST_EMPTY")
    assert valid_df.empty
    assert quaran_df.empty
    assert "quarantine_id" in quaran_df.columns

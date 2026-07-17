"""Tests pour DataProcessor (chargement, validation, nettoyage)."""

from pathlib import Path

import pytest

from src.utils.data_processor import DataLoadError, DataProcessor

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_sales.csv"


def test_load_csv():
    processor = DataProcessor()
    df = processor.load(str(FIXTURE_CSV))
    assert df.shape[0] == 10
    assert "region" in df.columns


def test_load_unsupported_extension():
    processor = DataProcessor()
    with pytest.raises(DataLoadError):
        processor.load("data.txt")


def test_validate_detects_missing_and_duplicates():
    processor = DataProcessor()
    processor.load(str(FIXTURE_CSV))
    report = processor.validate()

    assert report.n_rows == 10
    assert report.duplicate_rows == 1
    assert report.missing_values["units_sold"] == 1
    assert report.missing_values["customer_satisfaction"] == 1
    assert report.is_valid()


def test_clean_removes_duplicates_and_fills_na():
    processor = DataProcessor()
    processor.load(str(FIXTURE_CSV))
    clean_df = processor.clean()

    assert clean_df.duplicated().sum() == 0
    assert clean_df["units_sold"].isna().sum() == 0
    assert clean_df["customer_satisfaction"].isna().sum() == 0


def test_get_summary_returns_expected_keys():
    processor = DataProcessor()
    processor.load(str(FIXTURE_CSV))
    processor.clean()
    summary = processor.get_summary()

    assert summary["n_columns"] == 6
    assert "units_sold" in summary["numeric_columns"]
    assert "region" in summary["categorical_columns"]
    assert "numeric_stats" in summary
    assert "categorical_top_values" in summary

"""Tests pour src/utils/report_generator.py (aucun appel API)."""

from pathlib import Path

import pandas as pd
import pytest

from src.utils.report_generator import generate_excel_report, generate_pdf_report
from src.utils.visualization import render_chart, to_png_bytes

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_sales.csv"

SAMPLE_REPORT = {
    "summary": "Les ventes sont concentrees sur la region Nord et le produit Widget A.",
    "insights": [
        {
            "category": "tendance",
            "title": "Widget A domine les ventes",
            "description": "Widget A represente la plus grande part des unites vendues.",
            "importance": 4,
        },
        {
            "category": "qualite_donnees",
            "title": "Valeurs manquantes",
            "description": "Deux colonnes contiennent des valeurs manquantes.",
            "importance": 2,
        },
    ],
    "recommendations": [
        {
            "title": "Completer les valeurs manquantes",
            "description": "Mettre en place une validation a la saisie.",
            "priority": 3,
        },
    ],
}


@pytest.fixture
def sample_df():
    return pd.read_csv(FIXTURE_CSV)


def test_generate_pdf_report_returns_valid_pdf_bytes(sample_df):
    pdf_bytes = generate_pdf_report(sample_df, SAMPLE_REPORT, source_name="sample_sales.csv")
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_generate_pdf_report_with_empty_report(sample_df):
    pdf_bytes = generate_pdf_report(sample_df, {}, source_name="sample_sales.csv")
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_pdf_report_with_chart_images(sample_df):
    fig = render_chart(sample_df, "bar", ["region", "units_sold"], title="Ventes par region")
    png_bytes = to_png_bytes(fig, width=400, height=250)
    pdf_bytes = generate_pdf_report(
        sample_df,
        SAMPLE_REPORT,
        source_name="sample_sales.csv",
        chart_images=[("Ventes par region", png_bytes)],
    )
    assert pdf_bytes.startswith(b"%PDF")


def test_generate_excel_report_returns_valid_xlsx_bytes(sample_df):
    xlsx_bytes = generate_excel_report(sample_df, SAMPLE_REPORT, source_name="sample_sales.csv")
    assert xlsx_bytes[:2] == b"PK"
    assert len(xlsx_bytes) > 500


def test_generate_excel_report_with_empty_report(sample_df):
    xlsx_bytes = generate_excel_report(sample_df, {}, source_name="sample_sales.csv")
    assert xlsx_bytes[:2] == b"PK"

"""Tests pour les outils LangChain de src/agent/tools.py.

Ces tests n'appellent aucun modele: ils verifient uniquement la logique
pandas exposee via les outils.
"""

import json
from pathlib import Path

import pandas as pd

from src.agent.tools import build_data_tools

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_sales.csv"


def load_tools():
    df = pd.read_csv(FIXTURE_CSV)
    tools = build_data_tools(df)
    return {t.name: t for t in tools}


def test_get_dataset_shape():
    tools = load_tools()
    result = json.loads(tools["get_dataset_shape"].invoke({}))
    assert result == {"n_rows": 10, "n_columns": 6}


def test_list_columns():
    tools = load_tools()
    result = json.loads(tools["list_columns"].invoke({}))
    assert "region" in result
    assert result["region"]["dtype"] == "object"


def test_get_numeric_summary():
    tools = load_tools()
    result = json.loads(tools["get_numeric_summary"].invoke({"columns": ["units_sold"]}))
    assert "units_sold" in result


def test_get_correlations_reports_error_when_not_enough_columns():
    tools = load_tools()
    result = json.loads(tools["get_correlations"].invoke({"threshold": 0.99}))
    assert "pairs" in result


def test_detect_outliers_invalid_column():
    tools = load_tools()
    result = json.loads(tools["detect_outliers"].invoke({"column": "region"}))
    assert "error" in result


def test_get_missing_values():
    tools = load_tools()
    result = json.loads(tools["get_missing_values"].invoke({}))
    assert result["units_sold"]["count"] == 1
    assert result["customer_satisfaction"]["count"] == 1


def test_group_by_aggregate():
    tools = load_tools()
    result = json.loads(
        tools["group_by_aggregate"].invoke(
            {"group_column": "region", "value_column": "units_sold", "agg": "sum"}
        )
    )
    assert "North" in result


def test_group_by_aggregate_invalid_agg():
    tools = load_tools()
    result = json.loads(
        tools["group_by_aggregate"].invoke(
            {"group_column": "region", "value_column": "units_sold", "agg": "not_a_valid_agg"}
        )
    )
    assert "error" in result

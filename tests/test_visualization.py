"""Tests pour src/utils/visualization.py (aucun appel API)."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import pytest

from src.utils.visualization import ChartError, render_chart

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_sales.csv"


@pytest.fixture
def sample_df():
    return pd.read_csv(FIXTURE_CSV)


def test_bar_chart(sample_df):
    fig = render_chart(sample_df, "bar", ["region", "units_sold"], title="Ventes par region")
    assert isinstance(fig, go.Figure)


def test_bar_chart_value_counts_only(sample_df):
    fig = render_chart(sample_df, "bar", ["region"])
    assert isinstance(fig, go.Figure)


def test_line_chart(sample_df):
    fig = render_chart(sample_df, "line", ["date", "units_sold"])
    assert isinstance(fig, go.Figure)


def test_pie_chart(sample_df):
    fig = render_chart(sample_df, "pie", ["product"])
    assert isinstance(fig, go.Figure)


def test_scatter_chart(sample_df):
    fig = render_chart(sample_df, "scatter", ["units_sold", "unit_price"])
    assert isinstance(fig, go.Figure)


def test_histogram(sample_df):
    fig = render_chart(sample_df, "histogram", ["units_sold"])
    assert isinstance(fig, go.Figure)


def test_box_plot(sample_df):
    fig = render_chart(sample_df, "box", ["units_sold", "region"])
    assert isinstance(fig, go.Figure)


def test_heatmap(sample_df):
    fig = render_chart(sample_df, "heatmap", ["units_sold", "unit_price", "customer_satisfaction"])
    assert isinstance(fig, go.Figure)


def test_unknown_chart_type_raises(sample_df):
    with pytest.raises(ChartError):
        render_chart(sample_df, "not_a_chart", ["region"])


def test_unknown_column_raises(sample_df):
    with pytest.raises(ChartError):
        render_chart(sample_df, "bar", ["does_not_exist"])


def test_heatmap_needs_two_numeric_columns(sample_df):
    with pytest.raises(ChartError):
        render_chart(sample_df, "heatmap", ["units_sold"])

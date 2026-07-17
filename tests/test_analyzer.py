"""Tests d'integration pour DataAnalyzerAgent (src/agent/analyzer.py).

Ces tests appellent reellement l'API OpenAI: ils sont ignores automatiquement
si OPENAI_API_KEY n'est pas definie (voir .env.example), pour ne pas casser
la suite de tests sans cle ni engendrer de cout a chaque execution.
"""

import os
from pathlib import Path

import pandas as pd
import pytest
from dotenv import load_dotenv

from src.agent.analyzer import AgentRunResult, AnalysisReport, DataAnalyzerAgent, InsightCategory
from src.utils.visualization import SUPPORTED_CHART_TYPES

load_dotenv()

FIXTURE_CSV = Path(__file__).parent / "fixtures" / "sample_sales.csv"

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY absent: tests d'integration de l'agent ignores (voir .env.example).",
)


@pytest.fixture(scope="module")
def sample_df():
    return pd.read_csv(FIXTURE_CSV)


@pytest.fixture(scope="module")
def analysis_result(sample_df):
    agent = DataAnalyzerAgent()
    return agent.analyze(sample_df)


def test_analyze_returns_agent_run_result(analysis_result):
    assert isinstance(analysis_result, AgentRunResult)
    assert isinstance(analysis_result.report, AnalysisReport)


def test_analyze_produces_at_least_five_insights(analysis_result):
    assert len(analysis_result.report.insights) >= 5


def test_analyze_insight_categories_and_importance_are_valid(analysis_result):
    for insight in analysis_result.report.insights:
        assert insight.category in InsightCategory
        assert 1 <= insight.importance <= 5


def test_analyze_produces_recommendations(analysis_result):
    assert len(analysis_result.report.recommendations) >= 1
    for rec in analysis_result.report.recommendations:
        assert 1 <= rec.priority <= 5


def test_analyze_trace_contains_real_tool_calls(analysis_result):
    assert len(analysis_result.trace) >= 1
    for step in analysis_result.trace:
        assert step.tool
        assert step.output


def test_analyze_suggested_visualizations_use_supported_types(analysis_result):
    for viz in analysis_result.report.suggested_visualizations:
        assert viz.chart_type.lower() in SUPPORTED_CHART_TYPES
        assert viz.columns


def test_ask_answers_a_followup_question(sample_df):
    agent = DataAnalyzerAgent()
    answer, trace = agent.ask(sample_df, "Combien y a-t-il de lignes dans ce jeu de donnees ?")
    assert isinstance(answer, str) and answer
    assert len(trace) >= 1


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        DataAnalyzerAgent()

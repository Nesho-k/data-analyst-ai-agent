"""Agent principal: explore un DataFrame via des outils, puis produit un
rapport d'analyse structure (insights, recommandations, visualisations)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agent.prompts import CHAT_SYSTEM_PROMPT, EXPLORATION_SYSTEM_PROMPT, SYNTHESIS_PROMPT_TEMPLATE
from src.agent.tools import build_data_tools

load_dotenv()


class InsightCategory(str, Enum):
    TENDANCE = "tendance"
    ANOMALIE = "anomalie"
    CORRELATION = "correlation"
    DISTRIBUTION = "distribution"
    QUALITE_DONNEES = "qualite_donnees"
    SEGMENTATION = "segmentation"


class Insight(BaseModel):
    category: InsightCategory
    title: str
    description: str
    importance: int = Field(ge=1, le=5, description="1 = mineur, 5 = critique")


class Recommendation(BaseModel):
    title: str
    description: str
    priority: int = Field(ge=1, le=5, description="1 = faible, 5 = urgente")


class SuggestedVisualization(BaseModel):
    chart_type: str = Field(description="bar, line, pie, scatter, histogram, box ou heatmap")
    title: str
    columns: list[str]
    rationale: str


class AnalysisReport(BaseModel):
    summary: str
    insights: list[Insight]
    recommendations: list[Recommendation]
    suggested_visualizations: list[SuggestedVisualization]


class ExplorationStep(BaseModel):
    """Un appel d'outil effectue par l'agent, conserve pour la tracabilite."""

    tool: str
    tool_input: Any
    output: str


@dataclass
class AgentRunResult:
    report: AnalysisReport
    trace: list[ExplorationStep] = field(default_factory=list)


@dataclass
class AnalyzerConfig:
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    temperature: float = 0.2
    max_exploration_steps: int = 8


class DataAnalyzerAgent:
    """Agent d'analyse de donnees base sur LangChain et un modele OpenAI."""

    def __init__(self, config: AnalyzerConfig | None = None):
        self.config = config or AnalyzerConfig()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY manquant. Definissez-le dans un fichier .env "
                "a la racine du projet (voir .env.example)."
            )
        self.llm = ChatOpenAI(
            model=self.config.model,
            temperature=self.config.temperature,
            api_key=api_key,
        )

    def analyze(self, df: pd.DataFrame, user_question: str | None = None) -> AgentRunResult:
        """Explore `df` avec les outils disponibles puis retourne un rapport
        d'analyse structure et valide (Pydantic), accompagne de la trace des
        outils utilises pour y parvenir."""
        exploration_summary, trace = self._explore(df, user_question)
        report = self._synthesize(df, exploration_summary)
        return AgentRunResult(report=report, trace=trace)

    def ask(
        self,
        df: pd.DataFrame,
        question: str,
        chat_history: list[dict[str, str]] | None = None,
    ) -> tuple[str, list[ExplorationStep]]:
        """Repond a une question de suivi sur `df` en reutilisant les memes
        outils que l'exploration initiale, avec l'historique de la
        conversation pour le contexte. Retourne la reponse et la trace des
        outils utilises."""
        executor = self._build_executor(df, CHAT_SYSTEM_PROMPT)
        messages = _to_langchain_messages(chat_history or [])
        result = executor.invoke({"input": question, "chat_history": messages})
        return result["output"], _extract_trace(result)

    def _build_executor(self, df: pd.DataFrame, system_prompt: str) -> AgentExecutor:
        tools = build_data_tools(df)
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder("chat_history", optional=True),
                ("human", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=self.config.max_exploration_steps,
            verbose=False,
            return_intermediate_steps=True,
        )

    def _explore(
        self, df: pd.DataFrame, user_question: str | None
    ) -> tuple[str, list[ExplorationStep]]:
        executor = self._build_executor(df, EXPLORATION_SYSTEM_PROMPT)

        exploration_input = user_question or (
            "Explore ce jeu de donnees en profondeur en utilisant les outils "
            "disponibles, puis resume tes observations les plus importantes."
        )
        result = executor.invoke({"input": exploration_input, "chat_history": []})
        return result["output"], _extract_trace(result)

    def _synthesize(self, df: pd.DataFrame, exploration_summary: str) -> AnalysisReport:
        structured_llm = self.llm.with_structured_output(AnalysisReport)
        synthesis_prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
            exploration_summary=exploration_summary,
            n_rows=df.shape[0],
            n_columns=df.shape[1],
            columns=", ".join(str(c) for c in df.columns),
        )
        return structured_llm.invoke(synthesis_prompt)


def _extract_trace(executor_result: dict[str, Any]) -> list[ExplorationStep]:
    steps = []
    for action, output in executor_result.get("intermediate_steps", []):
        steps.append(ExplorationStep(tool=action.tool, tool_input=action.tool_input, output=str(output)))
    return steps


def _to_langchain_messages(chat_history: list[dict[str, str]]) -> list[BaseMessage]:
    messages: list[BaseMessage] = []
    for turn in chat_history:
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=turn.get("content", "")))
        else:
            messages.append(AIMessage(content=turn.get("content", "")))
    return messages

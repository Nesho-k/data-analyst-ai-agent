"""Interface Streamlit du Data Analyst Agent."""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.agent.analyzer import AnalysisReport, DataAnalyzerAgent, ExplorationStep
from src.utils.data_processor import DataLoadError, DataProcessor
from src.utils.report_generator import generate_excel_report, generate_pdf_report
from src.utils.visualization import ChartError, render_chart, to_png_bytes

load_dotenv()

st.set_page_config(page_title="Data Analyst Agent", layout="wide")

SESSION_DEFAULTS = {
    "processor": None,
    "raw_df": None,
    "clean_df": None,
    "validation_report": None,
    "analysis_report": None,
    "exploration_trace": [],
    "agent": None,
    "chat_history": [],
    "source_name": None,
    "figures": [],
    "pdf_bytes": None,
    "xlsx_bytes": None,
}


def init_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session_state() -> None:
    for key, value in SESSION_DEFAULTS.items():
        st.session_state[key] = value


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Data Analyst Agent")
        st.caption("Chargez un fichier, laissez l'agent l'analyser, exportez un rapport.")

        api_key = os.getenv("OPENAI_API_KEY")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if api_key:
            st.success(f"Cle OpenAI detectee (modele: {model})")
        else:
            st.warning("OPENAI_API_KEY absent. Ajoutez-le dans un fichier .env (voir .env.example).")

        if st.button("Nouveau fichier"):
            reset_session_state()
            st.rerun()

        render_export_section()


def render_upload_section() -> None:
    st.header("1. Charger les donnees")
    uploaded_file = st.file_uploader("Fichier CSV ou Excel", type=["csv", "xlsx", "xls"])
    if uploaded_file is None:
        return

    if st.session_state["source_name"] != uploaded_file.name:
        processor = DataProcessor()
        try:
            raw_df = processor.load(uploaded_file, filename=uploaded_file.name)
        except DataLoadError as exc:
            st.error(str(exc))
            return

        st.session_state["processor"] = processor
        st.session_state["raw_df"] = raw_df
        st.session_state["source_name"] = uploaded_file.name
        st.session_state["validation_report"] = processor.validate()
        st.session_state["clean_df"] = None
        st.session_state["analysis_report"] = None
        st.session_state["exploration_trace"] = []
        st.session_state["agent"] = None
        st.session_state["chat_history"] = []
        st.session_state["figures"] = []
        st.session_state["pdf_bytes"] = None
        st.session_state["xlsx_bytes"] = None

    raw_df = st.session_state["raw_df"]
    validation = st.session_state["validation_report"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Lignes", validation.n_rows)
    col2.metric("Colonnes", validation.n_columns)
    col3.metric("Doublons", validation.duplicate_rows)

    for warning in validation.warnings:
        st.warning(warning)

    st.dataframe(raw_df.head(20), use_container_width=True)


def render_cleaning_section() -> None:
    if st.session_state["raw_df"] is None:
        return

    st.header("2. Nettoyer les donnees")
    with st.form("cleaning_form"):
        col1, col2 = st.columns(2)
        drop_duplicates = col1.checkbox("Supprimer les doublons", value=True)
        drop_constant_columns = col2.checkbox("Supprimer les colonnes constantes", value=False)
        fill_numeric_na = col1.selectbox(
            "Valeurs manquantes numeriques", ["median", "mean", "zero", "none"]
        )
        fill_categorical_na = col2.selectbox(
            "Valeurs manquantes categorielles", ["mode", "unknown", "none"]
        )
        submitted = st.form_submit_button("Nettoyer les donnees")

    if submitted:
        processor: DataProcessor = st.session_state["processor"]
        clean_df = processor.clean(
            drop_duplicates=drop_duplicates,
            drop_constant_columns=drop_constant_columns,
            fill_numeric_na=fill_numeric_na,
            fill_categorical_na=fill_categorical_na,
        )
        st.session_state["clean_df"] = clean_df
        st.session_state["analysis_report"] = None
        st.session_state["exploration_trace"] = []
        st.session_state["agent"] = None
        st.session_state["chat_history"] = []
        st.session_state["figures"] = []
        st.session_state["pdf_bytes"] = None
        st.session_state["xlsx_bytes"] = None

    if st.session_state["clean_df"] is not None:
        st.success(f"Donnees nettoyees: {st.session_state['clean_df'].shape[0]} lignes restantes.")
        st.dataframe(st.session_state["clean_df"].head(20), use_container_width=True)


def render_trace(trace: list[ExplorationStep]) -> None:
    """Affiche la sequence d'outils appeles par l'agent, pour que les
    chiffres avances puissent etre verifies plutot que pris pour acquis."""
    for i, step in enumerate(trace, start=1):
        st.markdown(f"**{i}. {step.tool}**")
        st.code(str(step.tool_input), language="json")
        output = step.output if len(step.output) <= 1000 else step.output[:1000] + "..."
        st.text(output)


def render_analysis_section() -> None:
    clean_df = st.session_state["clean_df"]
    if clean_df is None:
        return

    st.header("3. Analyse automatique")

    if not os.getenv("OPENAI_API_KEY"):
        st.info("Definissez OPENAI_API_KEY dans un fichier .env pour activer l'analyse par l'agent.")
        return

    question = st.text_input("Question optionnelle pour orienter l'analyse", value="")

    if st.button("Lancer l'analyse"):
        with st.spinner("Analyse en cours..."):
            try:
                agent = DataAnalyzerAgent()
                result = agent.analyze(clean_df, user_question=question or None)
            except Exception as exc:
                st.error(f"Erreur lors de l'analyse: {exc}")
                return
        st.session_state["agent"] = agent
        st.session_state["analysis_report"] = result.report
        st.session_state["exploration_trace"] = result.trace
        st.session_state["chat_history"] = []
        st.session_state["figures"] = []
        st.session_state["pdf_bytes"] = None
        st.session_state["xlsx_bytes"] = None

    report: AnalysisReport | None = st.session_state["analysis_report"]
    if report is None:
        return

    st.subheader("Resume")
    st.write(report.summary)

    st.subheader("Insights")
    insights_df = pd.DataFrame([i.model_dump() for i in report.insights])
    st.dataframe(insights_df, use_container_width=True)

    st.subheader("Recommandations")
    recommendations_df = pd.DataFrame([r.model_dump() for r in report.recommendations])
    st.dataframe(recommendations_df, use_container_width=True)

    if st.session_state["exploration_trace"]:
        with st.expander("Comment l'agent a obtenu ces resultats"):
            render_trace(st.session_state["exploration_trace"])


def render_visualization_section() -> None:
    report = st.session_state["analysis_report"]
    clean_df = st.session_state["clean_df"]
    if report is None or clean_df is None:
        return

    st.header("4. Visualisations")
    if not report.suggested_visualizations:
        st.info("Aucune visualisation suggeree par l'agent.")
        return

    figures = []
    for suggestion in report.suggested_visualizations:
        try:
            fig = render_chart(clean_df, suggestion.chart_type, suggestion.columns, title=suggestion.title)
        except ChartError as exc:
            st.warning(f"Impossible de generer '{suggestion.title}': {exc}")
            continue
        st.plotly_chart(fig, use_container_width=True)
        st.caption(suggestion.rationale)
        figures.append((suggestion.title, fig))

    st.session_state["figures"] = figures


def render_chat_section() -> None:
    report = st.session_state["analysis_report"]
    clean_df = st.session_state["clean_df"]
    agent: DataAnalyzerAgent | None = st.session_state["agent"]
    if report is None or clean_df is None or agent is None:
        return

    st.header("5. Poser une question sur les donnees")
    st.caption(
        "L'agent reutilise les memes outils que l'analyse automatique pour repondre, "
        "en s'appuyant sur les donnees reelles plutot que sur des suppositions."
    )

    for turn in st.session_state["chat_history"]:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    question = st.chat_input("Ex: quelle region a le plus faible taux de completion ?")
    if not question:
        return

    st.session_state["chat_history"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Reflexion en cours..."):
            try:
                answer, trace = agent.ask(
                    clean_df, question, chat_history=st.session_state["chat_history"][:-1]
                )
            except Exception as exc:
                answer, trace = f"Erreur lors de la reponse: {exc}", []
        st.write(answer)
        if trace:
            with st.expander("Outils utilises pour cette reponse"):
                render_trace(trace)

    st.session_state["chat_history"].append({"role": "assistant", "content": answer})


def render_export_section() -> None:
    """Affiche dans la barre laterale (visible en permanence, contrairement
    au chat qui reste fixe en bas de la colonne principale)."""
    clean_df = st.session_state["clean_df"]
    if clean_df is None:
        return

    st.divider()
    st.subheader("Export du rapport")
    report = st.session_state["analysis_report"]
    report_dict = report.model_dump(mode="json") if report else {}
    source_name = st.session_state["source_name"]

    if st.button("Generer le PDF", use_container_width=True):
        with st.spinner("Generation du PDF..."):
            chart_images = [(title, to_png_bytes(fig)) for title, fig in st.session_state["figures"]]
            st.session_state["pdf_bytes"] = generate_pdf_report(
                clean_df, report_dict, source_name=source_name, chart_images=chart_images
            )
    if st.session_state["pdf_bytes"]:
        st.download_button(
            "Telecharger le PDF",
            data=st.session_state["pdf_bytes"],
            file_name="rapport_analyse.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    if st.button("Generer l'Excel", use_container_width=True):
        with st.spinner("Generation de l'Excel..."):
            st.session_state["xlsx_bytes"] = generate_excel_report(
                clean_df, report_dict, source_name=source_name
            )
    if st.session_state["xlsx_bytes"]:
        st.download_button(
            "Telecharger l'Excel",
            data=st.session_state["xlsx_bytes"],
            file_name="rapport_analyse.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def main() -> None:
    init_session_state()
    render_sidebar()
    st.title("Data Analyst Agent")

    render_upload_section()
    render_cleaning_section()
    render_analysis_section()
    render_visualization_section()
    render_chat_section()


if __name__ == "__main__":
    main()

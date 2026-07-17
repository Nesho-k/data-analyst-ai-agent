"""Generation de rapports PDF et Excel a partir des donnees analysees.

Le parametre `report` attendu par ces fonctions est un dict JSON-serialisable
(typiquement obtenu via `AnalysisReport.model_dump(mode="json")` cote agent),
afin que ce module reste independant du module agent.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PRIMARY_COLOR = colors.HexColor("#2a78d6")
MUTED_COLOR = colors.HexColor("#898781")
GRID_COLOR = colors.HexColor("#e1e0d9")
ROW_ALT_COLOR = colors.HexColor("#f9f9f7")

CATEGORY_LABELS = {
    "tendance": "Tendance",
    "anomalie": "Anomalie",
    "correlation": "Correlation",
    "distribution": "Distribution",
    "qualite_donnees": "Qualite des donnees",
    "segmentation": "Segmentation",
}


def generate_pdf_report(
    df: pd.DataFrame,
    report: dict[str, Any],
    source_name: str | None = None,
    chart_images: list[tuple[str, bytes]] | None = None,
) -> bytes:
    """Construit un rapport PDF (resume, insights, recommandations,
    visualisations) et retourne son contenu binaire.

    `chart_images` est une liste de tuples (titre, image_png_bytes), par
    exemple produits via `visualization.to_png_bytes`.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], textColor=PRIMARY_COLOR)
    heading_style = ParagraphStyle(
        "HeadingCustom", parent=styles["Heading2"], textColor=PRIMARY_COLOR, spaceBefore=16
    )
    body_style = styles["BodyText"]
    muted_style = ParagraphStyle("Muted", parent=styles["BodyText"], textColor=MUTED_COLOR)

    story: list[Any] = [Paragraph("Rapport d'analyse de donnees", title_style)]
    meta = (
        f"Source: {source_name or 'inconnue'} | {df.shape[0]} lignes x {df.shape[1]} colonnes "
        f"| genere le {datetime.now():%d/%m/%Y a %H:%M}"
    )
    story.append(Paragraph(meta, muted_style))
    story.append(Spacer(1, 0.5 * cm))

    if report.get("summary"):
        story.append(Paragraph("Resume", heading_style))
        story.append(Paragraph(report["summary"], body_style))

    insights = report.get("insights") or []
    if insights:
        story.append(Paragraph("Insights", heading_style))
        rows = [["Categorie", "Insight", "Importance"]]
        for insight in sorted(insights, key=lambda i: i.get("importance", 0), reverse=True):
            category = CATEGORY_LABELS.get(insight.get("category"), str(insight.get("category", "")))
            text = f"<b>{insight.get('title', '')}</b><br/>{insight.get('description', '')}"
            rows.append([category, Paragraph(text, body_style), str(insight.get("importance", ""))])
        story.append(_make_table(rows, col_widths=[3 * cm, 10.5 * cm, 2.5 * cm]))

    recommendations = report.get("recommendations") or []
    if recommendations:
        story.append(Paragraph("Recommandations", heading_style))
        rows = [["Priorite", "Recommandation"]]
        for rec in sorted(recommendations, key=lambda r: r.get("priority", 0), reverse=True):
            text = f"<b>{rec.get('title', '')}</b><br/>{rec.get('description', '')}"
            rows.append([str(rec.get("priority", "")), Paragraph(text, body_style)])
        story.append(_make_table(rows, col_widths=[2.5 * cm, 13.5 * cm]))

    if chart_images:
        story.append(PageBreak())
        story.append(Paragraph("Visualisations", heading_style))
        for chart_title, image_bytes in chart_images:
            story.append(Paragraph(chart_title, styles["Heading3"]))
            story.append(Image(io.BytesIO(image_bytes), width=16 * cm, height=9 * cm))
            story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
    return buffer.getvalue()


def _make_table(rows: list[list[Any]], col_widths: list[float]) -> Table:
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, GRID_COLOR),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROW_ALT_COLOR]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def generate_excel_report(
    df: pd.DataFrame,
    report: dict[str, Any],
    source_name: str | None = None,
) -> bytes:
    """Construit un classeur Excel (donnees, resume, insights, recommandations,
    statistiques) et retourne son contenu binaire."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {"bold": True, "bg_color": "#2a78d6", "font_color": "white", "border": 1}
        )
        wrap_format = workbook.add_format({"text_wrap": True, "valign": "top"})

        df.to_excel(writer, sheet_name="Donnees", index=False)
        _format_sheet(writer.sheets["Donnees"], df, header_format)

        summary_df = pd.DataFrame(
            [
                ["Source", source_name or "inconnue"],
                ["Lignes", df.shape[0]],
                ["Colonnes", df.shape[1]],
                ["Genere le", datetime.now().strftime("%d/%m/%Y %H:%M")],
                ["Resume", report.get("summary", "")],
            ],
            columns=["Champ", "Valeur"],
        )
        summary_df.to_excel(writer, sheet_name="Resume", index=False)
        _format_sheet(
            writer.sheets["Resume"], summary_df, header_format, wrap_format=wrap_format, wrap_columns=[1]
        )

        insights = report.get("insights") or []
        if insights:
            insights_df = pd.DataFrame(insights)
            if "category" in insights_df.columns:
                insights_df["category"] = insights_df["category"].map(
                    lambda c: CATEGORY_LABELS.get(c, c)
                )
            insights_df = insights_df.rename(
                columns={
                    "category": "Categorie",
                    "title": "Titre",
                    "description": "Description",
                    "importance": "Importance",
                }
            )
            insights_df.to_excel(writer, sheet_name="Insights", index=False)
            description_col = (
                [insights_df.columns.get_loc("Description")] if "Description" in insights_df.columns else []
            )
            _format_sheet(
                writer.sheets["Insights"],
                insights_df,
                header_format,
                wrap_format=wrap_format,
                wrap_columns=description_col,
            )

        recommendations = report.get("recommendations") or []
        if recommendations:
            rec_df = pd.DataFrame(recommendations).rename(
                columns={"title": "Titre", "description": "Description", "priority": "Priorite"}
            )
            rec_df.to_excel(writer, sheet_name="Recommandations", index=False)
            description_col = (
                [rec_df.columns.get_loc("Description")] if "Description" in rec_df.columns else []
            )
            _format_sheet(
                writer.sheets["Recommandations"],
                rec_df,
                header_format,
                wrap_format=wrap_format,
                wrap_columns=description_col,
            )

        numeric_df = df.select_dtypes(include="number")
        if not numeric_df.empty:
            stats_df = numeric_df.describe().round(3).reset_index().rename(columns={"index": "Statistique"})
            stats_df.to_excel(writer, sheet_name="Statistiques", index=False)
            _format_sheet(writer.sheets["Statistiques"], stats_df, header_format)

    return buffer.getvalue()


def _format_sheet(
    worksheet,
    data: pd.DataFrame,
    header_format,
    wrap_format=None,
    wrap_columns: list[int] | None = None,
) -> None:
    wrap_columns = wrap_columns or []
    for col_idx, col_name in enumerate(data.columns):
        worksheet.write(0, col_idx, col_name, header_format)
        if len(data):
            max_len = max(len(str(col_name)), data[col_name].astype(str).str.len().max())
        else:
            max_len = len(str(col_name))
        width = min(max(int(max_len) + 2, 10), 60)
        if col_idx in wrap_columns and wrap_format is not None:
            worksheet.set_column(col_idx, col_idx, min(width, 50), wrap_format)
        else:
            worksheet.set_column(col_idx, col_idx, width)
    worksheet.freeze_panes(1, 0)

"""Construction de visualisations Plotly a partir d'un DataFrame.

Palette et regles de mise en forme: ordre categoriel fixe (jamais recycle),
une seule teinte pour l'encodage sequentiel, une paire divergente bleu/rouge
avec point neutre gris, un seul axe Y par graphique, legende systematique
des qu'il y a plusieurs series.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

CATEGORICAL_COLORS = [
    "#2a78d6",  # bleu
    "#1baf7a",  # aqua
    "#eda100",  # jaune
    "#008300",  # vert
    "#4a3aa7",  # violet
    "#e34948",  # rouge
    "#e87ba4",  # magenta
    "#eb6834",  # orange
]

SEQUENTIAL_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

DIVERGING_BLUE_RED = [
    [0.0, "#0d366b"],
    [0.25, "#3987e5"],
    [0.5, "#f0efec"],
    [0.75, "#e34948"],
    [1.0, "#7a1f1f"],
]

CHART_SURFACE = "#fcfcfb"
GRID_COLOR = "#e1e0d9"
AXIS_COLOR = "#c3c2b7"
TEXT_PRIMARY = "#0b0b0b"
TEXT_MUTED = "#898781"

MAX_CATEGORIES = 8
OTHER_LABEL = "Autres"

SUPPORTED_CHART_TYPES = {"bar", "line", "pie", "scatter", "histogram", "box", "heatmap"}


class ChartError(Exception):
    """Erreur levee quand un graphique ne peut pas etre construit."""


def _base_layout(fig: go.Figure, title: str | None = None) -> go.Figure:
    fig.update_layout(
        title=title,
        plot_bgcolor=CHART_SURFACE,
        paper_bgcolor=CHART_SURFACE,
        font=dict(color=TEXT_PRIMARY, family="system-ui, -apple-system, Segoe UI, sans-serif"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=40, r=20, t=50 if title else 20, b=40),
        hovermode="x unified",
    )
    fig.update_xaxes(gridcolor=GRID_COLOR, linecolor=AXIS_COLOR, tickfont=dict(color=TEXT_MUTED))
    fig.update_yaxes(gridcolor=GRID_COLOR, linecolor=AXIS_COLOR, tickfont=dict(color=TEXT_MUTED))
    return fig


def _group_small_categories(
    df: pd.DataFrame, category_col: str, value_col: str, max_categories: int = MAX_CATEGORIES
) -> pd.DataFrame:
    """Regroupe les categories au-dela de max_categories dans 'Autres' pour ne
    jamais depasser la palette categorielle a 8 teintes."""
    if df[category_col].nunique(dropna=True) <= max_categories:
        return df
    ordered = df.sort_values(value_col, ascending=False)
    top = ordered.iloc[: max_categories - 1]
    rest = ordered.iloc[max_categories - 1 :]
    other_row = pd.DataFrame({category_col: [OTHER_LABEL], value_col: [rest[value_col].sum()]})
    return pd.concat([top, other_row], ignore_index=True)


def bar_chart(
    df: pd.DataFrame,
    category_column: str,
    value_column: str | None = None,
    title: str | None = None,
    orientation: str = "v",
) -> go.Figure:
    """Graphique en barres. Si value_column est absent, compte les occurrences
    de chaque categorie."""
    if value_column is None:
        counts = df[category_column].value_counts(dropna=True).reset_index()
        counts.columns = [category_column, "count"]
        value_column = "count"
        data = counts
    else:
        data = df[[category_column, value_column]].dropna()

    data = _group_small_categories(data, category_column, value_column)
    data = data.sort_values(value_column, ascending=orientation == "h")

    x, y = (value_column, category_column) if orientation == "h" else (category_column, value_column)
    fig = px.bar(data, x=x, y=y, orientation=orientation, color_discrete_sequence=[CATEGORICAL_COLORS[0]])
    return _base_layout(fig, title)


def line_chart(
    df: pd.DataFrame,
    x_column: str,
    y_columns: str | list[str],
    title: str | None = None,
) -> go.Figure:
    """Graphique en lignes, une ou plusieurs series sur un seul axe Y."""
    if isinstance(y_columns, str):
        y_columns = [y_columns]

    data = df.sort_values(x_column)
    fig = go.Figure()
    for i, col in enumerate(y_columns):
        color = CATEGORICAL_COLORS[i % len(CATEGORICAL_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=data[x_column],
                y=data[col],
                mode="lines+markers",
                name=col,
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color),
            )
        )
    fig.update_layout(showlegend=len(y_columns) > 1)
    return _base_layout(fig, title)


def pie_chart(
    df: pd.DataFrame,
    category_column: str,
    value_column: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Diagramme circulaire (donut). Regroupe les categories excedentaires
    dans 'Autres' pour rester dans la palette a 8 teintes."""
    if value_column is None:
        counts = df[category_column].value_counts(dropna=True).reset_index()
        counts.columns = [category_column, "count"]
        value_column = "count"
        data = counts
    else:
        data = df[[category_column, value_column]].dropna()

    data = _group_small_categories(data, category_column, value_column)

    fig = go.Figure(
        data=[
            go.Pie(
                labels=data[category_column],
                values=data[value_column],
                hole=0.45,
                marker=dict(colors=CATEGORICAL_COLORS[: len(data)]),
                textinfo="percent",
                textposition="inside",
            )
        ]
    )
    return _base_layout(fig, title)


def scatter_chart(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    color_column: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Nuage de points, avec encodage categoriel optionnel par couleur."""
    data = df[[x_column, y_column] + ([color_column] if color_column else [])].dropna()

    if color_column:
        fig = px.scatter(
            data,
            x=x_column,
            y=y_column,
            color=color_column,
            color_discrete_sequence=CATEGORICAL_COLORS,
        )
        fig.update_layout(showlegend=True)
    else:
        fig = px.scatter(data, x=x_column, y=y_column, color_discrete_sequence=[CATEGORICAL_COLORS[0]])
    fig.update_traces(marker=dict(size=8, line=dict(width=1, color=CHART_SURFACE)))
    return _base_layout(fig, title)


def histogram(
    df: pd.DataFrame,
    column: str,
    title: str | None = None,
    nbins: int | None = None,
) -> go.Figure:
    """Histogramme de distribution pour une colonne numerique (encodage
    sequentiel, une seule teinte)."""
    data = df[[column]].dropna()
    fig = px.histogram(data, x=column, nbins=nbins, color_discrete_sequence=[SEQUENTIAL_BLUE[3]])
    fig.update_layout(showlegend=False)
    return _base_layout(fig, title)


def box_plot(
    df: pd.DataFrame,
    value_column: str,
    category_column: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Boite a moustaches pour reperer la distribution et les valeurs
    aberrantes, globalement ou par categorie."""
    if category_column:
        fig = px.box(
            df.dropna(subset=[value_column]),
            x=category_column,
            y=value_column,
            color=category_column,
            color_discrete_sequence=CATEGORICAL_COLORS,
        )
        fig.update_layout(showlegend=False)
    else:
        fig = px.box(df.dropna(subset=[value_column]), y=value_column, color_discrete_sequence=[CATEGORICAL_COLORS[0]])
    return _base_layout(fig, title)


def correlation_heatmap(
    df: pd.DataFrame,
    columns: list[str] | None = None,
    title: str | None = None,
) -> go.Figure:
    """Matrice de correlation (encodage divergent: bleu/rouge, point neutre gris)."""
    numeric_df = df.select_dtypes(include="number")
    if columns:
        missing = [c for c in columns if c not in numeric_df.columns]
        if missing:
            raise ChartError(f"Colonnes numeriques introuvables pour la heatmap: {missing}")
        numeric_df = numeric_df[columns]

    if numeric_df.shape[1] < 2:
        raise ChartError("Il faut au moins deux colonnes numeriques pour une matrice de correlation.")

    corr = numeric_df.corr(numeric_only=True).round(2)
    fig = go.Figure(
        data=go.Heatmap(
            z=corr.values,
            x=list(corr.columns),
            y=list(corr.columns),
            colorscale=DIVERGING_BLUE_RED,
            zmid=0,
            zmin=-1,
            zmax=1,
            text=corr.values,
            texttemplate="%{text}",
            textfont=dict(color=TEXT_PRIMARY),
            colorbar=dict(title="correlation"),
        )
    )
    return _base_layout(fig, title)


def render_chart(
    df: pd.DataFrame,
    chart_type: str,
    columns: list[str],
    title: str | None = None,
) -> go.Figure:
    """Point d'entree unique pour transformer une suggestion de visualisation
    (type + colonnes, ex. issue de l'agent) en figure Plotly.

    Cette fonction ne depend d'aucun type de l'agent: elle prend des
    primitives (str/list) pour rester reutilisable independamment du module
    agent.
    """
    chart_type = chart_type.strip().lower()
    if chart_type not in SUPPORTED_CHART_TYPES:
        raise ChartError(f"Type de graphique non supporte: '{chart_type}'.")

    unknown = [c for c in columns if c not in df.columns]
    if unknown:
        raise ChartError(f"Colonne(s) introuvable(s): {unknown}")

    numeric_columns = set(df.select_dtypes(include="number").columns)

    if chart_type == "bar":
        if len(columns) >= 2:
            return bar_chart(df, columns[0], columns[1], title=title)
        return bar_chart(df, columns[0], title=title)

    if chart_type == "line":
        if len(columns) < 2:
            raise ChartError("Un graphique en ligne necessite une colonne x et au moins une colonne y.")
        return line_chart(df, columns[0], columns[1:], title=title)

    if chart_type == "pie":
        if len(columns) >= 2:
            return pie_chart(df, columns[0], columns[1], title=title)
        return pie_chart(df, columns[0], title=title)

    if chart_type == "scatter":
        if len(columns) < 2:
            raise ChartError("Un nuage de points necessite au moins deux colonnes.")
        color_column = columns[2] if len(columns) >= 3 else None
        return scatter_chart(df, columns[0], columns[1], color_column=color_column, title=title)

    if chart_type == "histogram":
        column = next((c for c in columns if c in numeric_columns), columns[0] if columns else None)
        if not column:
            raise ChartError("Un histogramme necessite une colonne numerique.")
        return histogram(df, column, title=title)

    if chart_type == "box":
        value_column = next((c for c in columns if c in numeric_columns), None)
        if not value_column:
            raise ChartError("Une boite a moustaches necessite une colonne numerique.")
        category_column = next((c for c in columns if c != value_column), None)
        return box_plot(df, value_column, category_column=category_column, title=title)

    if chart_type == "heatmap":
        chosen = [c for c in columns if c in numeric_columns] or None
        return correlation_heatmap(df, columns=chosen, title=title)

    raise ChartError(f"Type de graphique non supporte: '{chart_type}'.")


def to_png_bytes(fig: go.Figure, width: int = 1200, height: int = 675, scale: int = 2) -> bytes:
    """Exporte une figure Plotly en image PNG (utilise pour l'inclure dans un
    rapport PDF). Necessite le paquet kaleido."""
    return fig.to_image(format="png", width=width, height=height, scale=scale)

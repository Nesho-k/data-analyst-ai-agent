"""Outils LangChain permettant a l'agent d'explorer un DataFrame pandas."""

from __future__ import annotations

import json

import pandas as pd
from langchain_core.tools import BaseTool, tool


def build_data_tools(df: pd.DataFrame) -> list[BaseTool]:
    """Cree la liste des outils LangChain lies a ce DataFrame precis.

    Chaque outil capture `df` par fermeture, ce qui evite de faire transiter
    des donnees potentiellement volumineuses dans le contexte du modele.
    """

    @tool
    def get_dataset_shape() -> str:
        """Retourne le nombre total de lignes et de colonnes du jeu de donnees."""
        return json.dumps({"n_rows": int(df.shape[0]), "n_columns": int(df.shape[1])})

    @tool
    def list_columns() -> str:
        """Liste les colonnes du jeu de donnees avec leur type, leur nombre de
        valeurs non nulles et leur nombre de valeurs distinctes."""
        info = {
            col: {
                "dtype": str(df[col].dtype),
                "non_null_count": int(df[col].notna().sum()),
                "unique_count": int(df[col].nunique(dropna=True)),
            }
            for col in df.columns
        }
        return json.dumps(info, ensure_ascii=False)

    @tool
    def get_numeric_summary(columns: list[str] | None = None) -> str:
        """Retourne les statistiques descriptives (moyenne, ecart-type, min, max,
        quartiles) pour les colonnes numeriques indiquees, ou toutes si aucune
        n'est precisee."""
        numeric_df = df.select_dtypes(include="number")
        if columns:
            missing = [c for c in columns if c not in numeric_df.columns]
            if missing:
                return json.dumps({"error": f"Colonnes numeriques introuvables: {missing}"})
            numeric_df = numeric_df[columns]
        if numeric_df.empty:
            return json.dumps({"error": "Aucune colonne numerique disponible."})
        return numeric_df.describe().round(3).to_json()

    @tool
    def get_categorical_summary(column: str, top_n: int = 10) -> str:
        """Retourne les valeurs les plus frequentes d'une colonne categorielle
        donnee, avec leur nombre d'occurrences."""
        if column not in df.columns:
            return json.dumps({"error": f"Colonne '{column}' introuvable."})
        counts = df[column].value_counts(dropna=True).head(top_n)
        return counts.to_json()

    @tool
    def get_correlations(threshold: float = 0.5) -> str:
        """Retourne les paires de colonnes numeriques dont la correlation absolue
        depasse le seuil indique (0.5 par defaut)."""
        numeric_df = df.select_dtypes(include="number")
        if numeric_df.shape[1] < 2:
            return json.dumps({"error": "Pas assez de colonnes numeriques pour calculer une correlation."})
        corr = numeric_df.corr(numeric_only=True)
        columns = list(corr.columns)
        pairs = []
        for i in range(len(columns)):
            for j in range(i + 1, len(columns)):
                value = corr.iloc[i, j]
                if pd.notna(value) and abs(value) >= threshold:
                    pairs.append(
                        {
                            "column_a": columns[i],
                            "column_b": columns[j],
                            "correlation": round(float(value), 3),
                        }
                    )
        pairs.sort(key=lambda p: abs(p["correlation"]), reverse=True)
        return json.dumps({"pairs": pairs}, ensure_ascii=False)

    @tool
    def detect_outliers(column: str) -> str:
        """Detecte les valeurs aberrantes d'une colonne numerique avec la methode
        IQR (ecart interquartile) et retourne leur nombre, seuils et exemples."""
        if column not in df.select_dtypes(include="number").columns:
            return json.dumps({"error": f"'{column}' n'est pas une colonne numerique valide."})
        series = df[column].dropna()
        if series.empty:
            return json.dumps({"error": f"Colonne '{column}' vide."})
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = series[(series < lower) | (series > upper)]
        return json.dumps(
            {
                "column": column,
                "lower_bound": round(float(lower), 3),
                "upper_bound": round(float(upper), 3),
                "outlier_count": int(outliers.shape[0]),
                "outlier_percent": round(outliers.shape[0] / series.shape[0] * 100, 2),
                "sample_values": outliers.head(10).tolist(),
            },
            ensure_ascii=False,
        )

    @tool
    def get_missing_values() -> str:
        """Retourne le nombre et le pourcentage de valeurs manquantes par colonne."""
        n_rows = df.shape[0]
        missing = {
            col: {
                "count": int(df[col].isna().sum()),
                "percent": round(float(df[col].isna().sum()) / n_rows * 100, 2) if n_rows else 0,
            }
            for col in df.columns
        }
        return json.dumps(missing, ensure_ascii=False)

    @tool
    def group_by_aggregate(group_column: str, value_column: str, agg: str = "mean") -> str:
        """Agrege une colonne numerique par groupe d'une colonne categorielle.
        agg doit etre l'un de: mean, sum, median, count, min, max."""
        allowed = {"mean", "sum", "median", "count", "min", "max"}
        if agg not in allowed:
            return json.dumps({"error": f"agg doit etre parmi {sorted(allowed)}"})
        if group_column not in df.columns:
            return json.dumps({"error": f"Colonne '{group_column}' introuvable."})
        if value_column not in df.select_dtypes(include="number").columns:
            return json.dumps({"error": f"'{value_column}' n'est pas une colonne numerique valide."})
        result = df.groupby(group_column)[value_column].agg(agg).sort_values(ascending=False)
        return result.round(3).to_json()

    return [
        get_dataset_shape,
        list_columns,
        get_numeric_summary,
        get_categorical_summary,
        get_correlations,
        detect_outliers,
        get_missing_values,
        group_by_aggregate,
    ]

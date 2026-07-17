"""Chargement, validation et nettoyage des donnees CSV/Excel."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


class DataLoadError(Exception):
    """Erreur levee quand un fichier ne peut pas etre charge."""


@dataclass
class ValidationReport:
    """Resultat de la validation d'un DataFrame."""

    n_rows: int
    n_columns: int
    missing_values: dict[str, int]
    missing_percent: dict[str, float]
    duplicate_rows: int
    constant_columns: list[str]
    dtypes: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def is_valid(self) -> bool:
        return self.n_rows > 0 and self.n_columns > 0


class DataProcessor:
    """Charge, valide et nettoie un fichier CSV ou Excel."""

    SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}

    def __init__(self) -> None:
        self.raw_df: pd.DataFrame | None = None
        self.clean_df: pd.DataFrame | None = None
        self.source_name: str | None = None

    def load(self, file: Any, filename: str | None = None) -> pd.DataFrame:
        """Charge un fichier CSV/Excel depuis un chemin ou un objet fichier
        (ex: retourne par st.file_uploader)."""
        name = filename or getattr(file, "name", None) or str(file)
        extension = Path(name).suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise DataLoadError(
                f"Format non supporte: '{extension}'. "
                f"Formats acceptes: {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}"
            )

        try:
            if extension == ".csv":
                df = self._load_csv(file)
            else:
                df = pd.read_excel(file)
        except DataLoadError:
            raise
        except Exception as exc:
            raise DataLoadError(f"Impossible de lire le fichier '{name}': {exc}") from exc

        if df.empty:
            raise DataLoadError(f"Le fichier '{name}' est vide.")

        self.raw_df = df
        self.source_name = name
        return df

    @staticmethod
    def _load_csv(file: Any) -> pd.DataFrame:
        """Essaie plusieurs separateurs/encodages courants pour un CSV."""
        separators = [",", ";", "\t", "|"]
        encodings = ["utf-8", "latin-1"]

        last_error: Exception | None = None
        for encoding in encodings:
            for sep in separators:
                try:
                    if hasattr(file, "seek"):
                        file.seek(0)
                    df = pd.read_csv(file, sep=sep, encoding=encoding)
                    if df.shape[1] > 1:
                        return df
                except Exception as exc:
                    last_error = exc
                    continue

        if hasattr(file, "seek"):
            file.seek(0)
        try:
            return pd.read_csv(file)
        except Exception as exc:
            raise DataLoadError(
                f"Aucun separateur/encodage compatible trouve pour ce CSV: {last_error or exc}"
            ) from exc

    def validate(self, df: pd.DataFrame | None = None) -> ValidationReport:
        """Analyse la qualite des donnees: valeurs manquantes, doublons,
        colonnes constantes, types."""
        data = df if df is not None else self.raw_df
        if data is None:
            raise DataLoadError("Aucune donnee chargee. Appelez load() d'abord.")

        n_rows, n_columns = data.shape
        missing_values = data.isna().sum().to_dict()
        missing_percent = {
            col: round(count / n_rows * 100, 2) if n_rows else 0.0
            for col, count in missing_values.items()
        }
        duplicate_rows = int(data.duplicated().sum())
        constant_columns = [col for col in data.columns if data[col].nunique(dropna=True) <= 1]
        dtypes = {col: str(dtype) for col, dtype in data.dtypes.items()}

        warnings: list[str] = []
        if duplicate_rows > 0:
            warnings.append(f"{duplicate_rows} ligne(s) dupliquee(s) detectee(s).")
        if constant_columns:
            warnings.append(f"Colonne(s) constante(s): {', '.join(constant_columns)}.")
        high_missing = [col for col, pct in missing_percent.items() if pct > 50]
        if high_missing:
            warnings.append(f"Colonne(s) avec plus de 50% de valeurs manquantes: {', '.join(high_missing)}.")

        return ValidationReport(
            n_rows=n_rows,
            n_columns=n_columns,
            missing_values=missing_values,
            missing_percent=missing_percent,
            duplicate_rows=duplicate_rows,
            constant_columns=constant_columns,
            dtypes=dtypes,
            warnings=warnings,
        )

    def clean(
        self,
        df: pd.DataFrame | None = None,
        drop_duplicates: bool = True,
        drop_constant_columns: bool = False,
        fill_numeric_na: str = "median",
        fill_categorical_na: str = "mode",
    ) -> pd.DataFrame:
        """Nettoie le DataFrame: doublons, valeurs manquantes, colonnes vides.

        fill_numeric_na: 'median', 'mean', 'zero' ou 'none' (ne rien faire).
        fill_categorical_na: 'mode', 'unknown' ou 'none' (ne rien faire).
        """
        data = df if df is not None else self.raw_df
        if data is None:
            raise DataLoadError("Aucune donnee chargee. Appelez load() d'abord.")

        data = data.copy()
        data.columns = [str(col).strip() for col in data.columns]

        data = data.dropna(axis=1, how="all")

        if drop_duplicates:
            data = data.drop_duplicates()

        if drop_constant_columns:
            constant_columns = [col for col in data.columns if data[col].nunique(dropna=True) <= 1]
            data = data.drop(columns=constant_columns)

        numeric_columns = data.select_dtypes(include="number").columns
        categorical_columns = data.select_dtypes(exclude="number").columns

        if fill_numeric_na == "median":
            for col in numeric_columns:
                data[col] = data[col].fillna(data[col].median())
        elif fill_numeric_na == "mean":
            for col in numeric_columns:
                data[col] = data[col].fillna(data[col].mean())
        elif fill_numeric_na == "zero":
            data[numeric_columns] = data[numeric_columns].fillna(0)

        if fill_categorical_na == "mode":
            for col in categorical_columns:
                mode = data[col].mode(dropna=True)
                if not mode.empty:
                    data[col] = data[col].fillna(mode.iloc[0])
        elif fill_categorical_na == "unknown":
            data[categorical_columns] = data[categorical_columns].fillna("Inconnu")

        data = data.reset_index(drop=True)
        self.clean_df = data
        return data

    def get_summary(self, df: pd.DataFrame | None = None) -> dict[str, Any]:
        """Retourne un resume statistique pret a etre utilise par l'agent
        ou affiche dans l'interface."""
        data = df if df is not None else (self.clean_df if self.clean_df is not None else self.raw_df)
        if data is None:
            raise DataLoadError("Aucune donnee chargee. Appelez load() d'abord.")

        numeric_columns = list(data.select_dtypes(include="number").columns)
        categorical_columns = list(data.select_dtypes(exclude="number").columns)

        summary: dict[str, Any] = {
            "source_name": self.source_name,
            "n_rows": int(data.shape[0]),
            "n_columns": int(data.shape[1]),
            "columns": list(data.columns),
            "numeric_columns": numeric_columns,
            "categorical_columns": categorical_columns,
            "memory_usage_kb": round(data.memory_usage(deep=True).sum() / 1024, 2),
        }

        if numeric_columns:
            summary["numeric_stats"] = data[numeric_columns].describe().round(3).to_dict()

        if categorical_columns:
            summary["categorical_top_values"] = {
                col: data[col].value_counts(dropna=True).head(5).to_dict()
                for col in categorical_columns
            }

        return summary

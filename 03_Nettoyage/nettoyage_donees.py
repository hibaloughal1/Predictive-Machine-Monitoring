#!/usr/bin/env python3
"""
export_clean_metrics.py
-----------------------
Nettoie la table `system_metrics` de metrics.db et exporte le résultat
en CSV pour la couche ML du pipeline.

La base SQLite est ouverte explicitement en lecture seule.
Toutes les transformations sont réalisées en mémoire.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd


INPUT_DB = Path("data/metrics_db_fusionnees.db")
TABLE_NAME = "system_metrics"
OUTPUT_FILE = Path("data/exports/cleaned_metrics.csv")

REQUIRED_METRICS_COLUMNS = {
    "run_id",
    "machine_id",
    "timestamp",
    "missed_deadline",
    "sensor_errors_json",
}

REQUIRED_RUN_COLUMNS = {
    "run_id",
    "machine_id",
    "status",
    "ended_at_utc",
}


def validate_table_name(table_name: str) -> None:
    """Empêche l'utilisation accidentelle d'un nom de table invalide."""
    if not table_name.replace("_", "").isalnum():
        raise ValueError(f"Nom de table invalide : {table_name!r}")


def validate_columns(
    df: pd.DataFrame,
    required_columns: set[str],
    dataframe_name: str,
) -> None:
    """Vérifie que les colonnes indispensables sont présentes."""
    missing = required_columns - set(df.columns)

    if missing:
        raise ValueError(
            f"Colonnes manquantes dans {dataframe_name} : "
            f"{', '.join(sorted(missing))}"
        )


def load_table(
    db_path: Path,
    table_name: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Charge system_metrics et runs depuis SQLite en lecture seule."""
    validate_table_name(table_name)

    db_uri = db_path.resolve().as_uri() + "?mode=ro"

    try:
        with sqlite3.connect(db_uri, uri=True) as conn:
            metrics = pd.read_sql_query(
                f'SELECT * FROM "{table_name}"',
                conn,
            )

            runs = pd.read_sql_query(
                """
                SELECT
                    run_id,
                    machine_id AS run_machine_id,
                    status,
                    ended_at_utc
                FROM runs
                """,
                conn,
            )
    except sqlite3.Error as exc:
        raise RuntimeError(
            f"Erreur lors de la lecture de la base SQLite : {exc}"
        ) from exc

    validate_columns(metrics, REQUIRED_METRICS_COLUMNS, table_name)

    required_loaded_run_columns = {
        "run_id",
        "run_machine_id",
        "status",
        "ended_at_utc",
    }
    validate_columns(runs, required_loaded_run_columns, "runs")

    return metrics, runs


def fix_machine_id(
    df: pd.DataFrame,
    runs: pd.DataFrame,
) -> pd.DataFrame:
    """Aligne machine_id sur la table runs, considérée comme source de vérité."""
    result = df.merge(
        runs[["run_id", "run_machine_id"]],
        on="run_id",
        how="left",
        validate="many_to_one",
    )

    valid_reference = result["run_machine_id"].notna()

    mismatch_mask = (
        valid_reference
        & result["machine_id"]
        .fillna("")
        .astype(str)
        .ne(result["run_machine_id"].fillna("").astype(str))
    )

    mismatch_count = int(mismatch_mask.sum())
    missing_reference_count = int((~valid_reference).sum())

    if mismatch_count:
        print(
            f"[machine_id] {mismatch_count} lignes corrigées "
            "(ancien hostname vers identifiant anonymisé)"
        )

    if missing_reference_count:
        print(
            f"[machine_id] Attention : {missing_reference_count} lignes "
            "ne possèdent pas de run correspondant dans la table runs"
        )

    result["machine_id"] = result["run_machine_id"].combine_first(
        result["machine_id"]
    )

    return result.drop(columns=["run_machine_id"])


def normalize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Convertit les timestamps vers un datetime UTC homogène."""
    result = df.copy()

    result["timestamp"] = pd.to_datetime(
        result["timestamp"],
        utc=True,
        format="mixed",
        errors="coerce",
    )

    invalid_count = int(result["timestamp"].isna().sum())

    if invalid_count:
        print(
            f"[timestamp] Attention : {invalid_count} timestamps invalides "
            "convertis en NaT"
        )

    return result


def contains_sensor_error(raw_json: object) -> bool:
    """Retourne True si le JSON contient une erreur ou s'il est invalide."""
    if raw_json is None or pd.isna(raw_json):
        return False

    if isinstance(raw_json, dict):
        return bool(raw_json)

    text = str(raw_json).strip()

    if text in {"", "{}", "null", "None"}:
        return False

    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return True

    if isinstance(parsed, dict):
        return bool(parsed)

    if isinstance(parsed, list):
        return bool(parsed)

    return parsed not in (None, False, 0, "")


def flag_reliability(
    df: pd.DataFrame,
    runs: pd.DataFrame,
) -> pd.DataFrame:
    """Ajoute des indicateurs de fiabilité sans supprimer les observations."""
    result = df.copy()

    missed_deadline = (
        pd.to_numeric(result["missed_deadline"], errors="coerce")
        .fillna(0)
        .ne(0)
    )

    sensor_error = result["sensor_errors_json"].apply(
        contains_sensor_error
    )

    invalid_timestamp = result["timestamp"].isna()
    missing_run_id = result["run_id"].isna()

    result["sample_reliable"] = (
        ~(
            missed_deadline
            | sensor_error
            | invalid_timestamp
            | missing_run_id
        )
    ).astype("int8")

    unreliable_count = int(result["sample_reliable"].eq(0).sum())
    total_count = len(result)
    unreliable_ratio = (
        unreliable_count / total_count if total_count else 0
    )

    print(
        f"[flags] {unreliable_count}/{total_count} lignes marquées "
        f"sample_reliable=0 ({unreliable_ratio:.1%})"
    )

    run_status = runs[
        ["run_id", "status", "ended_at_utc"]
    ].drop_duplicates(subset=["run_id"])

    result = result.merge(
        run_status,
        on="run_id",
        how="left",
        validate="many_to_one",
        suffixes=("", "_run"),
    )

    normalized_status = (
        result["status"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    ended_at = pd.to_datetime(
        result["ended_at_utc"],
        utc=True,
        errors="coerce",
    )

    successful_statuses = {
        "completed",
        "complete",
        "finished",
        "success",
        "succeeded",
    }

    result["run_complete"] = (
        normalized_status.isin(successful_statuses)
        & ended_at.notna()
    ).astype("int8")

    return result


def drop_duplicate_samples(df: pd.DataFrame) -> pd.DataFrame:
    """
    Supprime les mesures partageant le même run_id et timestamp.

    Une mesure fiable est conservée en priorité. En cas d'égalité,
    la ligne contenant le moins de valeurs manquantes est conservée.
    """
    if df.empty:
        return df

    result = df.copy()
    result["_missing_value_count"] = result.isna().sum(axis=1)

    result = result.sort_values(
        by=[
            "run_id",
            "timestamp",
            "sample_reliable",
            "_missing_value_count",
        ],
        ascending=[True, True, False, True],
        na_position="last",
    )

    before = len(result)

    result = result.drop_duplicates(
        subset=["run_id", "timestamp"],
        keep="first",
    )

    removed = before - len(result)

    if removed:
        print(f"[duplicates] {removed} échantillons dupliqués supprimés")

    return result.drop(columns=["_missing_value_count"])


def export_csv(df: pd.DataFrame, output_file: Path) -> None:
    """Exporte le dataset nettoyé sans écraser silencieusement le dossier."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    df.to_csv(
        output_file,
        index=False,
        encoding="utf-8",
        na_rep="",
        date_format="%Y-%m-%dT%H:%M:%S.%fZ",
    )


def main() -> None:
    if not INPUT_DB.exists():
        raise SystemExit(f"Fichier introuvable : {INPUT_DB}")

    df, runs = load_table(INPUT_DB, TABLE_NAME)

    print(f"Lignes chargées depuis {TABLE_NAME} : {len(df)}")
    print(f"Runs chargés : {len(runs)}")

    if df.empty:
        print("[warning] La table system_metrics est vide.")
        export_csv(df, OUTPUT_FILE)
        return

    df = fix_machine_id(df, runs)
    df = normalize_timestamps(df)
    df = flag_reliability(df, runs)
    df = drop_duplicate_samples(df)

    df = df.sort_values(
        ["machine_id", "run_id", "timestamp"],
        na_position="last",
    ).reset_index(drop=True)

    export_csv(df, OUTPUT_FILE)

    print(
        f"\nExport terminé : {OUTPUT_FILE} "
        f"({len(df)} lignes, {len(df.columns)} colonnes)"
    )


if __name__ == "__main__":
    main()
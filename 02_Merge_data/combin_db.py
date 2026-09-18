#!/usr/bin/env python3
"""Fusion des bases SQLite (.db) -> génère un .csv (system_metrics) ET un .db fusionnés (toutes les tables)."""
from pathlib import Path
import sqlite3
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

OUTPUT_CSV = DATA_DIR / "metrics_db_fusionnees.csv"
OUTPUT_DB = DATA_DIR / "metrics_db_fusionnees.db"
# Ordre de fusion : runs d'abord (référencée par les autres via FK run_id)
TABLE_ORDER = ["schema_meta", "runs", "events", "capabilities", "system_metrics"]

# clé de dédoublonnage par table (basée sur le schéma réel de metrics.db)
DEDUP_KEYS = {
    "schema_meta": ["key"],
    "runs": ["run_id"],
    "events": ["run_id", "timestamp_utc", "event_type", "message"],
    "capabilities": ["run_id", "metric_name"],
    "system_metrics": ["machine_id", "run_id", "timestamp"],
}

# colonnes id auto-incrémentées à régénérer après fusion (sinon collisions entre fichiers sources)
AUTOINCREMENT_COLS = {
    "events": "id",
    "system_metrics": "id",
}


def get_table_names(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    return [row[0] for row in cur.fetchall()]


def main():
    db_files = sorted(DATA_DIR.glob("*.db"))
    db_files = [f for f in db_files if f.resolve() != OUTPUT_DB.resolve()]

    if not db_files:
        raise SystemExit("Aucune base SQLite trouvée.")

    tables_data = {}  # table_name -> liste de DataFrames

    for db_file in db_files:
        try:
            db_uri = db_file.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(db_uri, uri=True) as conn:
                table_names = get_table_names(conn)
                for table_name in table_names:
                    df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
                    if not df.empty:
                        tables_data.setdefault(table_name, []).append(df)
            print(f"✓ {db_file.name} : tables {table_names}")
        except Exception as e:
            print(f"Erreur avec {db_file.name} : {e}")

    if not tables_data:
        raise SystemExit("Aucune base valide.")

    if OUTPUT_DB.exists():
        OUTPUT_DB.unlink()

    conn = sqlite3.connect(OUTPUT_DB)
    merged_tables = {}

    try:
        # on respecte l'ordre pour que runs soit créée avant les tables qui la référencent
        ordered_names = [t for t in TABLE_ORDER if t in tables_data]
        ordered_names += [t for t in tables_data if t not in ordered_names]  # tables imprévues

        for table_name in ordered_names:
            dfs = tables_data[table_name]
            merged_df = pd.concat(dfs, ignore_index=True)
            before = len(merged_df)

            dedup_cols = DEDUP_KEYS.get(table_name)
            if dedup_cols and set(dedup_cols).issubset(merged_df.columns):
                merged_df.drop_duplicates(subset=dedup_cols, inplace=True)
            else:
                merged_df.drop_duplicates(inplace=True)

            removed = before - len(merged_df)

            sort_cols = [c for c in (dedup_cols or []) if c in merged_df.columns]
            if sort_cols:
                merged_df = merged_df.sort_values(sort_cols)

            merged_df.reset_index(drop=True, inplace=True)

            # régénère les id auto-incrémentés pour éviter les collisions entre fichiers sources
            id_col = AUTOINCREMENT_COLS.get(table_name)
            if id_col and id_col in merged_df.columns:
                merged_df[id_col] = range(1, len(merged_df) + 1)

            merged_tables[table_name] = merged_df
            merged_df.to_sql(table_name, conn, index=False, if_exists="replace")

            print(f"  - {table_name}: {len(merged_df)} lignes (doublons supprimés: {removed})")

        cur = conn.cursor()
        if "system_metrics" in merged_tables:
            cols = merged_tables["system_metrics"].columns
            if {"machine_id", "timestamp"}.issubset(cols):
                cur.execute(
                    'CREATE INDEX IF NOT EXISTS idx_machine_ts '
                    'ON "system_metrics" (machine_id, timestamp)'
                )
        if "events" in merged_tables and "run_id" in merged_tables["events"].columns:
            cur.execute('CREATE INDEX IF NOT EXISTS idx_events_run ON "events" (run_id)')
        if "capabilities" in merged_tables and "run_id" in merged_tables["capabilities"].columns:
            cur.execute('CREATE INDEX IF NOT EXISTS idx_capabilities_run ON "capabilities" (run_id)')

        conn.commit()
    except Exception as e:
        conn.close()
        if OUTPUT_DB.exists():
            OUTPUT_DB.unlink()
        raise SystemExit(f"Erreur lors de l'écriture du .db : {e}")
    else:
        conn.close()

    # --- Export CSV (uniquement system_metrics, comme avant) ---
    if "system_metrics" in merged_tables:
        merged_tables["system_metrics"].to_csv(OUTPUT_CSV, index=False)

    print("\nFusion terminée")
    print(f"Bases fusionnées : {len(db_files)}")
    print(f"Tables fusionnées : {list(merged_tables.keys())}")
    print(f"CSV -> {OUTPUT_CSV}")
    print(f"DB  -> {OUTPUT_DB}")


if __name__ == "__main__":
    main()
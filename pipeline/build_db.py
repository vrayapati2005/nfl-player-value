"""Load the raw Parquet files from data/raw/ into data/nfl.duckdb, one table each.

Run from the project root after ingest.py:
    python pipeline/build_db.py
"""

from pathlib import Path

import duckdb

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "nfl.duckdb"

# Table name in DuckDB -> Parquet file written by ingest.py
TABLES = {
    "pbp": "pbp.parquet",
    "player_stats": "player_stats.parquet",
    "snap_counts": "snap_counts.parquet",
    "rosters": "rosters.parquet",
    "contracts": "contracts.parquet",
}


def load_table(con: duckdb.DuckDBPyConnection, table: str, filename: str) -> None:
    """(Re)create a table from a Parquet file. Rerunning gives the same result."""
    path = RAW_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run pipeline/ingest.py first")
    con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet(?)", [str(path)])


def print_row_counts(con: duckdb.DuckDBPyConnection) -> None:
    """Print the row count of every table, straight from the database."""
    print(f"\nRow counts in {DB_PATH.name}:")
    for table in TABLES:
        (n,) = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        print(f"  {table:<14} {n:>9,}")


def main() -> None:
    with duckdb.connect(str(DB_PATH)) as con:
        for table, filename in TABLES.items():
            load_table(con, table, filename)
            print(f"loaded {table}")
        print_row_counts(con)


if __name__ == "__main__":
    main()

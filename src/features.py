"""Build the feature tables by running every sql/*.sql file, in filename order,
against data/nfl.duckdb.

Run from the project root after pipeline/build_db.py:
    python -m src.features
"""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DB_PATH = ROOT / "data" / "nfl.duckdb"


def sql_files() -> list[Path]:
    """The SQL files to run. The numeric prefix (01_, 02_, ...) sets the order."""
    return sorted(SQL_DIR.glob("*.sql"))


def table_name(path: Path) -> str:
    """'03_player_plays.sql' -> 'player_plays' (each file builds the table it's named after)."""
    return path.stem.split("_", 1)[1]


def build_features(con: duckdb.DuckDBPyConnection) -> None:
    """Run each SQL file and print the row count of the table it built."""
    for path in sql_files():
        con.execute(path.read_text())
        (n,) = con.execute(f"SELECT COUNT(*) FROM {table_name(path)}").fetchall()[0]
        print(f"  {path.name:<28} -> {table_name(path):<18} {n:>9,} rows")


def main() -> None:
    with duckdb.connect(str(DB_PATH)) as con:
        build_features(con)


if __name__ == "__main__":
    main()

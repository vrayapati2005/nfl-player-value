"""Download raw nflverse data and save each dataset as Parquet in data/raw/.

Run from the project root:
    python pipeline/ingest.py
"""

from pathlib import Path

import nflreadpy as nfl
import polars as pl

SEASONS = list(range(2019, 2026))  # 2019–2025 inclusive
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def save(df: pl.DataFrame, name: str) -> None:
    """Write a DataFrame to data/raw/<name>.parquet and report its size."""
    path = RAW_DIR / f"{name}.parquet"
    df.write_parquet(path)
    print(f"  saved {name:<14} {df.height:>9,} rows x {df.width:>3} cols -> {path.name}")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading seasons {SEASONS[0]}–{SEASONS[-1]} into {RAW_DIR}")

    # One row per play. The largest dataset; source of EPA, success, CPOE, air yards.
    save(nfl.load_pbp(SEASONS), "pbp")

    # One row per player per week (regular season + playoffs).
    save(nfl.load_player_stats(SEASONS, summary_level="week"), "player_stats")

    # One row per player per game: offensive/defensive/special-teams snaps and %.
    save(nfl.load_snap_counts(SEASONS), "snap_counts")

    # One row per player per team per season: position, birth date, IDs.
    save(nfl.load_rosters(SEASONS), "rosters")

    # One row per contract (OverTheCap). Has no season filter, so we keep all
    # history and select the contract active in each season later, in SQL.
    save(nfl.load_contracts(), "contracts")

    print("Done.")


if __name__ == "__main__":
    main()

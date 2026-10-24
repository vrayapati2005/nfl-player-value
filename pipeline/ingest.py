"""Download raw nflverse data and save each dataset as Parquet in data/raw/.

Run from the project root:
    python pipeline/ingest.py                # download every dataset
    python pipeline/ingest.py players        # download only the named dataset(s)
"""

import sys
from pathlib import Path

import nflreadpy as nfl
import polars as pl

SEASONS = list(range(2019, 2026))  # 2019–2025 inclusive
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# Dataset name -> function that downloads it.
DATASETS = {
    # One row per play. The largest dataset; source of EPA, success, CPOE, air yards.
    "pbp": lambda: nfl.load_pbp(SEASONS),
    # One row per player per week (regular season + playoffs).
    "player_stats": lambda: nfl.load_player_stats(SEASONS, summary_level="week"),
    # One row per player per game: offensive/defensive/special-teams snaps and %.
    "snap_counts": lambda: nfl.load_snap_counts(SEASONS),
    # One row per player per team per season: position, birth date, IDs.
    "rosters": lambda: nfl.load_rosters(SEASONS),
    # One row per contract (OverTheCap). Has no season filter, so we keep all
    # history and select the contract active in each season later, in SQL.
    "contracts": lambda: nfl.load_contracts(),
    # One row per player (all eras): nflverse's master ID crosswalk, linking
    # gsis_id to pfr_id (snap counts) and otc_id (contracts).
    "players": lambda: nfl.load_players(),
}


def save(df: pl.DataFrame, name: str) -> None:
    """Write a DataFrame to data/raw/<name>.parquet and report its size."""
    path = RAW_DIR / f"{name}.parquet"
    df.write_parquet(path)
    print(f"  saved {name:<14} {df.height:>9,} rows x {df.width:>3} cols -> {path.name}")


def main(names: list[str]) -> None:
    unknown = set(names) - DATASETS.keys()
    if unknown:
        sys.exit(f"Unknown dataset(s): {sorted(unknown)}. Choose from {list(DATASETS)}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading seasons {SEASONS[0]}–{SEASONS[-1]} into {RAW_DIR}")
    for name in names or DATASETS:
        save(DATASETS[name](), name)
    print("Done.")


if __name__ == "__main__":
    main(sys.argv[1:])

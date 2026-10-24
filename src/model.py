"""Shared modeling code: feature matrix, season-based CV folds, and evaluation.

Used by notebooks/02_model.ipynb (training) and notebooks/03_value.ipynb (scoring).
"""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nfl.duckdb"

POSITIONS = ["QB", "RB", "WR", "TE"]
TARGET = "apy_cap_pct"

# On-field production only. Deliberately excluded:
#   - contract columns (apy, contract_year_signed, contract_years, contract_type):
#     they are the answer, or derived from it -> leakage
#   - plays: it is exactly dropbacks + rushes + targets, so it adds nothing
#   - team, player name/ID: we want "what does this production earn", not "who is it"
NUMERIC_FEATURES = [
    "age",
    "games_played",
    "offense_snaps",
    "snap_pct",
    "dropbacks",
    "rushes",
    "targets",
    "receptions",
    "total_epa",
    "epa_per_play",
    "success_rate",
    "cpoe",
    "target_share",
    "air_yards_share",
    "air_yards",
    "yards_after_catch",
]


def load_player_season() -> pd.DataFrame:
    """Read the player_season table built by sql/05_player_season.sql."""
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.sql("SELECT * FROM player_season").df()


def build_features(df: pd.DataFrame, drop_first: bool = False) -> pd.DataFrame:
    """Model inputs: numeric features plus one-hot position columns.

    drop_first=True drops position_QB, so QB becomes the reference category. The linear
    model needs this: with all four dummies plus an intercept the columns are perfectly
    collinear. Tree models don't care, and all four columns read better in SHAP plots.
    """
    X = df[NUMERIC_FEATURES].astype(float).copy()
    # Missing means "not applicable" here, not "unknown":
    #   cpoe is QB-only (0 = league average), receiving columns are empty with no catches.
    X = X.fillna({"cpoe": 0.0, "receptions": 0.0, "air_yards": 0.0, "yards_after_catch": 0.0})

    positions = pd.Categorical(df["position"], categories=POSITIONS)  # fixed column order
    dummies = pd.get_dummies(positions, prefix="position", dtype=float)
    dummies.index = df.index
    if drop_first:
        dummies = dummies.drop(columns="position_QB")
    return pd.concat([dummies, X], axis=1)


def season_cv_splits(seasons: pd.Series, first_val_season: int) -> list[tuple[np.ndarray, np.ndarray]]:
    """Expanding-window folds: train on every season before S, validate on season S.

    e.g. seasons 2019–2023 with first_val_season=2021 gives
        train 2019–2020 -> validate 2021
        train 2019–2021 -> validate 2022
        train 2019–2022 -> validate 2023
    so, like the real test, each fold only ever predicts a season the model hasn't seen.
    """
    seasons = seasons.to_numpy()
    folds = []
    for val_season in range(first_val_season, seasons.max() + 1):
        train_idx = np.flatnonzero(seasons < val_season)
        val_idx = np.flatnonzero(seasons == val_season)
        folds.append((train_idx, val_idx))
    return folds


def evaluate(y_true: pd.Series, y_pred: np.ndarray, positions: pd.Series) -> pd.DataFrame:
    """R² and MAE overall and within each position. MAE is in percentage points of cap."""
    y_pred = pd.Series(y_pred, index=y_true.index)
    groups = [("all", y_true.index)] + [(p, y_true.index[positions == p]) for p in POSITIONS]
    rows = []
    for name, idx in groups:
        rows.append({
            "group": name,
            "n": len(idx),
            "R2": r2_score(y_true[idx], y_pred[idx]),
            "MAE_pct_of_cap": 100 * mean_absolute_error(y_true[idx], y_pred[idx]),
        })
    return pd.DataFrame(rows).set_index("group")

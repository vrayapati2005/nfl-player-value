"""Shared modeling code: feature matrices, season-based CV folds, evaluation and labeling.

v1 (season totals): notebooks/02_model.ipynb (training), notebooks/03_value.ipynb (scoring).
"""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score
from xgboost import XGBRegressor

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "nfl.duckdb"

POSITIONS = ["QB", "RB", "WR", "TE"]
TARGET = "apy_cap_pct"
TRAIN_SEASONS = range(2019, 2024)

# Chosen by season-based CV in notebooks/02_model.ipynb.
BEST_PARAMS = {
    "learning_rate": 0.03,
    "max_depth": 4,
    "min_child_weight": 5,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
}

# Labeling thresholds
TAIL_PCT = 0.15         # top / bottom 15% of the gap within position x pay tier
MIN_GAP_MUSD = 2.5      # ...and at least $2.5M away from the prediction
MIN_GAMES = 10          # v1 only: fewer games -> "Injury-shortened" / "Limited sample"

# Manual corrections to the contract attached to a player-season, keyed by (gsis_id, season).
# Each one documents why the SQL rule ("latest contract signed on or before the season") got it wrong.
CONTRACT_OVERRIDES = {
    ("00-0035710", 2024): {  # Daniel Jones
        "contract_year_signed": 2023,
        "contract_type": "UFA",
        "apy": 40.0,
        "apy_cap_pct": 0.178,
        "reason": "Played all 10 games for NYG on his 2023 Giants deal (4 yrs, $40M APY); the 2024 Vikings "
                  "deal (0.4% of cap) was signed after NYG released him in November.",
    },
}

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
    """Read the player_season table built by sql/05_player_season.sql.

    Sorted, because SQL tables have no guaranteed row order and XGBoost's row subsampling
    depends on it: without a fixed order, rebuilding the database changes the model.
    """
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.sql("SELECT * FROM player_season ORDER BY season, gsis_id").df()


def apply_contract_overrides(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with CONTRACT_OVERRIDES applied and an `override_reason` column."""
    df = df.copy()
    df["override_reason"] = None
    for (gsis_id, season), fix in CONTRACT_OVERRIDES.items():
        rows = (df["gsis_id"] == gsis_id) & (df["season"] == season)
        for col, value in fix.items():
            df.loc[rows, "override_reason" if col == "reason" else col] = value
    return df


def implied_salary_cap(years: list[int]) -> pd.Series:
    """Salary cap in $M per year, backed out of the contract data: median of APY / APY-%-of-cap
    over contracts signed that year with at least 5% of cap (bigger deals = less rounding error)."""
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        cap = con.execute(
            """
            SELECT year_signed AS year, median(apy / apy_cap_pct) AS cap_musd
            FROM contracts
            WHERE apy_cap_pct >= 0.05 AND list_contains(?, year_signed)
            GROUP BY 1 ORDER BY 1
            """,
            [list(years)],
        ).df()
    return cap.set_index("year")["cap_musd"]


def train_model(df: pd.DataFrame) -> XGBRegressor:
    """Fit the final XGBoost model on veteran contracts from the training seasons."""
    train = df[~df["is_rookie_contract"] & df["season"].isin(TRAIN_SEASONS)]
    model = XGBRegressor(objective="reg:squarederror", random_state=42, n_jobs=4, **BEST_PARAMS)
    return model.fit(build_features(train), train[TARGET])


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


# ---------------------------------------------------------------------------
# Labeling
# ---------------------------------------------------------------------------

def pay_tiers(df: pd.DataFrame) -> pd.Series:
    """'low' / 'mid' / 'high': thirds of actual pay among veterans at the same position.
    Rookie-contract rows get NaN (they aren't labeled)."""
    vet = ~df["is_rookie_contract"]
    tiers = df[vet].groupby("position")[TARGET].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["low", "mid", "high"]))
    return tiers.astype(str).reindex(df.index)


def assign_labels(df: pd.DataFrame, gap_pp: str, gap_musd: str, group_cols: list[str],
                  min_games: int | None = None, min_games_for_underpaid: bool = False):
    """Label veterans by where their gap ranks within `group_cols`.

    Overpaid  = top TAIL_PCT of the gap in the group and at least MIN_GAP_MUSD above the prediction.
    Underpaid = bottom TAIL_PCT and at least MIN_GAP_MUSD below. Everyone else is Fair.
    If min_games is set (v1): Overpaid with fewer games -> "Injury-shortened", and, when
    min_games_for_underpaid, Underpaid with fewer games -> "Limited sample".
    Returns (labels, percentile of the gap within the group).
    """
    is_vet = ~df["is_rookie_contract"]
    pct = df[is_vet].groupby(group_cols)[gap_pp].rank(pct=True).reindex(df.index)
    over = is_vet & (pct > 1 - TAIL_PCT) & (df[gap_musd] >= MIN_GAP_MUSD)
    under = is_vet & (pct <= TAIL_PCT) & (df[gap_musd] <= -MIN_GAP_MUSD)
    few = df["games_played"] < min_games if min_games else pd.Series(False, index=df.index)
    limited = under & few if min_games_for_underpaid else pd.Series(False, index=df.index)
    labels = np.select(
        [~is_vet, over & few, limited, over, under],
        ["Rookie contract", "Injury-shortened", "Limited sample", "Overpaid", "Underpaid"],
        default="Fair",
    )
    return pd.Series(labels, index=df.index), pct

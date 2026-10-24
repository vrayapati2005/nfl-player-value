"""Shared modeling code: feature matrices, season-based CV folds, evaluation and labeling.

v1 (season totals): notebooks/02_model.ipynb (training), notebooks/03_value.ipynb (scoring).
v2 (per-game production): notebooks/04_value_v2.ipynb.
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

# ---- v2 production score: edit these to re-weight ----
# Weights on within-position percentiles (position and season). Each set must sum to 1.
PRODUCTION_WEIGHTS = {
    "QB": {
        "epa_pg": 0.30,          # EPA per game
        "pass_yds_pg": 0.25,     # passing yards per game
        "pass_td_pg": 0.20,      # passing TDs per game
        "cpoe": 0.15,            # completion % over expected
        "rush_yds_pg": 0.10,     # rushing yards per game
    },
    "RB/WR/TE": {
        "yds_pg": 0.35,           # yards per game: receiving (WR/TE) or scrimmage (RB)
        "rec_pg": 0.20,           # receptions per game
        "good_game_share": 0.125, # consistency (25% total): half share of games over the threshold...
        "floor_yards": 0.125,     # ...half the 25th-percentile weekly yards
        "epa_pg": 0.20,           # EPA per game
    },
}

# Nobody can be paid less than the league minimum, so fair value is floored here. 0.3% of cap is the
# 1st percentile of veteran pay in the 2019–2023 training data (only practice-squad deals sit below it).
# Needed for v2: with monotone constraints, very poor per-game production can extrapolate below zero.
PAY_FLOOR = 0.003

# Labeling thresholds (v1 and v2)
TAIL_PCT = 0.15         # top / bottom 15% of the gap within position x pay tier
MIN_GAP_MUSD = 2.5      # ...and at least $2.5M away from the prediction
MIN_GAMES = 10          # v1 only: fewer games -> "Injury-shortened" / "Limited sample"
V2_MIN_GAMES = 6        # v2 season label only: fewer games -> "Limited sample" (sample size, not an injury penalty)

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
# Labeling (shared by v1 and v2)
# ---------------------------------------------------------------------------

def pay_tiers(df: pd.DataFrame) -> pd.Series:
    """'low' / 'mid' / 'high': thirds of actual pay among veterans at the same position.
    Rookie-contract rows get NaN (they aren't labeled)."""
    vet = ~df["is_rookie_contract"]
    tiers = df[vet].groupby("position")[TARGET].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["low", "mid", "high"]))
    return tiers.astype(str).reindex(df.index)


def assign_labels(df: pd.DataFrame, gap_pp: str, gap_musd: str, group_cols: list[str],
                  min_games: int | None = None, min_games_for_underpaid: bool = False,
                  limited_sample_games: int | None = None):
    """Label veterans by where their gap ranks within `group_cols`.

    Overpaid  = top TAIL_PCT of the gap in the group and at least MIN_GAP_MUSD above the prediction.
    Underpaid = bottom TAIL_PCT and at least MIN_GAP_MUSD below. Everyone else is Fair.
    If min_games is set (v1): Overpaid with fewer games -> "Injury-shortened", and, when
    min_games_for_underpaid, Underpaid with fewer games -> "Limited sample".
    If limited_sample_games is set (v2 season label): Overpaid or Underpaid with fewer games ->
    "Limited sample". Percentiles are still ranked over all veterans; only the label changes.
    Returns (labels, percentile of the gap within the group).
    """
    is_vet = ~df["is_rookie_contract"]
    pct = df[is_vet].groupby(group_cols)[gap_pp].rank(pct=True).reindex(df.index)
    over = is_vet & (pct > 1 - TAIL_PCT) & (df[gap_musd] >= MIN_GAP_MUSD)
    under = is_vet & (pct <= TAIL_PCT) & (df[gap_musd] <= -MIN_GAP_MUSD)
    few = df["games_played"] < min_games if min_games else pd.Series(False, index=df.index)
    limited = under & few if min_games_for_underpaid else pd.Series(False, index=df.index)
    if limited_sample_games:
        limited |= (over | under) & (df["games_played"] < limited_sample_games)
    labels = np.select(
        [~is_vet, over & few, limited, over, under],
        ["Rookie contract", "Injury-shortened", "Limited sample", "Overpaid", "Underpaid"],
        default="Fair",
    )
    return pd.Series(labels, index=df.index), pct


# ---------------------------------------------------------------------------
# v2: per-game production model
# ---------------------------------------------------------------------------

# 2-season weighted per-game features (sql/07_player_season_pergame.sql) plus the production score.
# Monotone constraint: predicted pay may only go UP as any of these goes up.
V2_PRODUCTION_FEATURES = [
    "w_pass_yds_pg",
    "w_pass_td_pg",
    "w_cpoe",
    "w_rush_yds_pg",
    "w_carries_pg",
    "w_rec_yds_pg",
    "w_rec_pg",
    "w_targets_pg",
    "w_epa_pg",
    "w_success_rate",
    "w_epa_per_play",
    "w_good_game_share",
    "w_floor_yards",
    "production_score",
]
# Not production, so unconstrained. No games_played, snaps or snap %: missing games must not lower value.
V2_OTHER_FEATURES = ["age"]

# Percentile inputs to the production score: score component -> weighted column
SCORE_COMPONENTS = {
    "epa_pg": "w_epa_pg",
    "pass_yds_pg": "w_pass_yds_pg",
    "pass_td_pg": "w_pass_td_pg",
    "cpoe": "w_cpoe",
    "rush_yds_pg": "w_rush_yds_pg",
    "yds_pg": "w_yds_pg",
    "rec_pg": "w_rec_pg",
    "good_game_share": "w_good_game_share",
    "floor_yards": "w_floor_yards",
}


def load_player_season_v2() -> pd.DataFrame:
    """player_season joined to per-game production (sql/07) and availability (sql/08)."""
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        return con.sql("""
            SELECT
                ps.*,
                pg.* EXCLUDE (gsis_id, season, position, games, success_rate, epa_per_play, cpoe),
                a.availability, a.availability_3yr, a.games_3yr, a.possible_games_3yr,
                a.seasons_in_window, a.low_availability_seasons, a.durability_concern
            FROM player_season AS ps
            JOIN player_season_pergame AS pg USING (gsis_id, season)
            JOIN player_availability AS a USING (gsis_id, season)
            ORDER BY season, gsis_id  -- fixed order: XGBoost's subsampling depends on it
        """).df()


def add_production_score(df: pd.DataFrame) -> pd.DataFrame:
    """Add within-position percentiles (pct_*) and the 0–100 production score.

    Percentiles are taken within position and season, so a season is only compared with
    its own season (no information from other seasons, including test seasons).
    """
    for weights in PRODUCTION_WEIGHTS.values():
        assert abs(sum(weights.values()) - 1) < 1e-9, "production weights must sum to 1"

    df = df.copy()
    df["w_yds_pg"] = np.where(df["position"] == "RB", df["w_scrim_yds_pg"], df["w_rec_yds_pg"])
    for name, col in SCORE_COMPONENTS.items():
        df[f"pct_{name}"] = df.groupby(["position", "season"])[col].rank(pct=True)

    score = pd.Series(np.nan, index=df.index)
    for group, weights in PRODUCTION_WEIGHTS.items():
        rows = df["position"] == "QB" if group == "QB" else df["position"] != "QB"
        score[rows] = sum(w * df.loc[rows, f"pct_{name}"] for name, w in weights.items())
    df["production_score"] = 100 * score
    return df


def build_features_v2(df: pd.DataFrame, drop_first: bool = False) -> pd.DataFrame:
    """v2 inputs: one-hot position, age, and per-game production features."""
    X = df[V2_OTHER_FEATURES + V2_PRODUCTION_FEATURES].astype(float).copy()
    # Not applicable -> 0: CPOE for non-QBs, consistency for QBs
    X = X.fillna({"w_cpoe": 0.0, "w_good_game_share": 0.0, "w_floor_yards": 0.0})
    # Stats that belong to another position are noise (a QB catching his own deflected pass for -3 yards,
    # a WR's trick-play throw), and the trees split on them because nearly everyone else has exactly 0.
    is_qb = (df["position"] == "QB").to_numpy()
    X.loc[is_qb, ["w_rec_yds_pg", "w_rec_pg", "w_targets_pg"]] = 0.0
    X.loc[~is_qb, ["w_pass_yds_pg", "w_pass_td_pg"]] = 0.0
    positions = pd.Categorical(df["position"], categories=POSITIONS)
    dummies = pd.get_dummies(positions, prefix="position", dtype=float)
    dummies.index = df.index
    if drop_first:
        dummies = dummies.drop(columns="position_QB")
    return pd.concat([dummies, X], axis=1)


def monotone_constraints(columns: list[str]) -> tuple[int, ...]:
    """XGBoost constraint per column: +1 (pay can only rise) for production features, else 0."""
    return tuple(1 if c in V2_PRODUCTION_FEATURES else 0 for c in columns)


# Plain-English names for SHAP reasons
FEATURE_NAMES = {
    "position_QB": "Playing QB", "position_RB": "Playing RB", "position_WR": "Playing WR", "position_TE": "Playing TE",
    "age": "Age",
    "w_pass_yds_pg": "Passing yards per game", "w_pass_td_pg": "Passing TDs per game", "w_cpoe": "CPOE",
    "w_rush_yds_pg": "Rushing yards per game", "w_carries_pg": "Carries per game",
    "w_rec_yds_pg": "Receiving yards per game", "w_rec_pg": "Receptions per game", "w_targets_pg": "Targets per game",
    "w_epa_pg": "EPA per game", "w_success_rate": "Success rate", "w_epa_per_play": "EPA per play",
    "w_good_game_share": "Share of good games", "w_floor_yards": "Weekly yardage floor",
    "production_score": "Production score",
}


def shap_reasons(shap_values: np.ndarray, X: pd.DataFrame, n: int = 3) -> list[str]:
    """For each row, the n biggest SHAP contributions as plain English.
    shap_values must be in percentage points of cap, aligned with X's rows and columns."""
    reasons = []
    for row_vals, (_, x) in zip(shap_values, X.iterrows()):
        top = np.argsort(-np.abs(row_vals))[:n]
        parts = []
        for j in top:
            col, s = X.columns[j], row_vals[j]
            name = FEATURE_NAMES.get(col, col)
            if col.startswith("position_"):
                text = name
            elif col in ("w_success_rate", "w_good_game_share"):
                text = f"{name} {x[col]:.0%}"
            else:
                text = f"{name} {x[col]:.1f}"
            parts.append(f"{text} ({'+' if s >= 0 else '−'}{abs(s):.1f} pts of cap)")
        reasons.append("; ".join(parts))
    return reasons

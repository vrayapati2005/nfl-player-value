# Results

Every number on this page comes from code that was actually run. Each section names the
script or notebook that produced it, so any figure can be traced and reproduced.

_Nothing recorded yet. Sections are filled in as each phase finishes._

## Data (Phase 1)
Source: `pipeline/ingest.py` then `pipeline/build_db.py` (run 2026-10-21, nflreadpy 0.1.5).
Seasons 2019–2025, regular season + playoffs. Contracts are all OverTheCap history (no season filter).

| Table | Rows | Grain (one row per…) |
|---|---:|---|
| pbp | 342,249 | play |
| player_stats | 129,812 | player per week |
| snap_counts | 181,478 | player per game |
| rosters | 21,720 | player per team per season |
| contracts | 53,349 | contract |

## Features (Phase 2)
Source: `python -m src.features` (runs `sql/01`–`05`) and `notebooks/01_eda.ipynb` (run 2026-10-24).
Filters: regular season only, QB/RB/WR/TE, at least 200 offensive snaps.

**`player_season`: 2,402 player-seasons, 817 distinct players, 29 columns.** No duplicate (player, season) keys.

| Position | Player-seasons | Median EPA/play | Median plays | % on rookie contract | Median cap % (rookie / veteran) |
|---|---:|---:|---:|---:|---|
| QB | 317 | +0.021 | 457 | 34.1% | 2.6% / 13.7% |
| RB | 505 | −0.041 | 168 | 43.0% | 0.6% / 1.4% |
| WR | 1,003 | +0.224 | 60 | 41.6% | 0.7% / 1.7% |
| TE | 577 | +0.204 | 34 | 38.5% | 0.5% / 1.7% |

Per season: 2019 327 · 2020 344 · 2021 348 · 2022 341 · 2023 346 · 2024 347 · 2025 349. 67 rows are players traded mid-season.

**Join coverage**
- Snap counts → gsis_id: 4,673 PFR IDs matched (4,662 via the nflverse players table, 11 via exact name + team + season). Only skill players never matched had ≤165 snaps in a season.
- Contracts: 100% of the 2,402 player-seasons have a contract (99.6% before adding the name + date-of-birth fallback).

**Validation against nflverse's official weekly stats** (player-seasons with 20+ touches)
- Targets: exact match for 2,332 of 2,354 (99.1%); within 2 for 2,352.
- RB carries: within 2 for 665 of 665; rushing EPA correlation 0.999. (QB carries differ by design: scrambles are counted as dropbacks here.)

**Pay vs production (Spearman correlation, cap % vs total EPA)**: QB 0.423, WR 0.323, TE 0.257, RB −0.069. Veteran contracts only: QB 0.521, WR 0.424, TE 0.391, RB −0.050.

## Model (Phase 3)
Source: `notebooks/02_model.ipynb` (run 2026-10-24), shared code in `src/model.py`.
Target: `apy_cap_pct`. Veteran (non-rookie) contracts only. Train: 2019–2023 (1,025 rows). Test: 2024–2025 (413 rows).
20 features: 4 one-hot position columns + 16 production/usage features (age, games, snaps, snap %, dropbacks, rushes,
targets, receptions, total EPA, EPA/play, success rate, CPOE, target share, air-yards share, air yards, YAC).

XGBoost settings, chosen by season-based CV on 2019–2023 (folds validate 2021, 2022, 2023):
`max_depth=4, learning_rate=0.03, n_estimators=500, min_child_weight=5, subsample=0.8, colsample_bytree=0.8`.

**Test set (2024–2025): R² and MAE in percentage points of cap**

| Model | R² | MAE (pp) | MAE at 2024 cap |
|---|---:|---:|---:|
| Position average | 0.342 | 3.61 | — |
| Linear regression | 0.647 | 2.32 | $5.9M |
| **XGBoost** | **0.674** | **2.07** | **$5.3M** |

**Per position (test)**

| Position | n | Linear R² | Linear MAE | XGBoost R² | XGBoost MAE |
|---|---:|---:|---:|---:|---:|
| QB | 63 | 0.339 | 6.44 | 0.366 | 5.71 |
| RB | 86 | 0.348 | 1.13 | 0.359 | 1.08 |
| WR | 163 | 0.624 | 2.12 | 0.705 | 1.76 |
| TE | 101 | 0.537 | 1.08 | 0.507 | 1.13 |

**Stricter test: contracts never seen in training** (343 of 413 rows; the other 70 share a multi-year contract with a training row):
linear R² 0.614 / MAE 2.02 pp; **XGBoost R² 0.621 / MAE 1.85 pp**.

**Overfitting check (MAE, pp of cap)**: linear 1.98 train / 2.15 CV / 2.32 test; XGBoost 0.85 train / 1.93 CV / 2.07 test.
CV and test agree. Widening the grid (depth up to 6, up to 1,000 trees) improved CV MAE from 1.926 to 1.918 pp, a negligible gain.

**Regression toward the mean (test, XGBoost)**: contracts under 2% of cap average 0.82% actual vs 1.98% predicted;
contracts at 15%+ of cap average 21.46% actual vs 14.73% predicted.

**SHAP (mean |SHAP|, pp of cap)**: snap % 1.61, dropbacks 0.90, target share 0.70, age 0.36, rushes 0.31,
games played 0.25, total EPA 0.25, air-yards share 0.20; EPA/play 0.12, success rate 0.12.
Figures: `docs/figures/shap_summary.png`, `shap_waterfall_*_2024.png`, `pred_vs_actual.png`.

Implied salary cap (median APY ÷ APY % of cap, contracts signed that year with ≥5% of cap): 2024 $255.4M, 2025 $278.8M.

## Value (Phase 4)
<!-- Most underpaid / overpaid players, how "value" is defined. Source: notebooks/03_value.ipynb -->

## Limitations
- **Same-year contracts from another team (29 player-seasons, 1.2%).** OverTheCap has no signing dates, so a contract
  signed later in the same year with a different team can be chosen as "the contract in force". Nearly all are
  minimum deals. The material case: **Daniel Jones 2024** shows 0.4% of cap (Vikings, after his release) instead of
  his 17.8% Giants contract. A blanket rule was rejected because OverTheCap sometimes labels a contract with its current
  team (e.g. DK Metcalf's 2022 Seattle extension is labeled "Steelers").
- **APY is measured at signing**, not the actual cap hit in each season.
- **The model compresses extreme salaries** (see Phase 3), so raw residuals favor cheap players and penalize stars.
- **SHAP shows association, not causation:** usage (snap %, target share) is partly a consequence of pay.

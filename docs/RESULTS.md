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
<!-- Train seasons / test seasons, test-set metrics (e.g. MAE, R²) vs. a baseline. Source: notebooks/02_model.ipynb -->

## Value (Phase 4)
<!-- Most underpaid / overpaid players, how "value" is defined. Source: notebooks/03_value.ipynb -->

## Limitations
<!-- Known caveats: sample sizes, ID matching, what EPA doesn't capture, etc. -->

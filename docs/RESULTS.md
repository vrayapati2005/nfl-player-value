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
<!-- Number of player-seasons, by position. Source: sql/ + notebooks/01_eda.ipynb -->

## Model (Phase 3)
<!-- Train seasons / test seasons, test-set metrics (e.g. MAE, R²) vs. a baseline. Source: notebooks/02_model.ipynb -->

## Value (Phase 4)
<!-- Most underpaid / overpaid players, how "value" is defined. Source: notebooks/03_value.ipynb -->

## Limitations
<!-- Known caveats: sample sizes, ID matching, what EPA doesn't capture, etc. -->

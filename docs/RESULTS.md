# Results

Every number on this page comes from code that was actually run. Each section names the
script or notebook that produced it, so any figure can be traced and reproduced.

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
Source: `notebooks/02_model.ipynb` (re-run 2026-10-24 with a fixed row order, see *Reproducibility* below),
shared code in `src/model.py`.
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
| **XGBoost** | **0.679** | **2.04** | **$5.2M** |

**Seed stability:** retraining XGBoost with 5 random seeds gives test MAE 2.05–2.10 pp, so differences under about
0.05 pp between models are noise.

**Per position (test)**

| Position | n | Linear R² | Linear MAE | XGBoost R² | XGBoost MAE |
|---|---:|---:|---:|---:|---:|
| QB | 63 | 0.339 | 6.44 | 0.371 | 5.66 |
| RB | 86 | 0.348 | 1.13 | 0.440 | 1.01 |
| WR | 163 | 0.624 | 2.12 | 0.712 | 1.75 |
| TE | 101 | 0.537 | 1.08 | 0.508 | 1.12 |

**Stricter test: contracts never seen in training** (343 of 413 rows; the other 70 share a multi-year contract with a training row):
linear R² 0.614 / MAE 2.02 pp; **XGBoost R² 0.631 / MAE 1.82 pp**.

**Overfitting check (MAE, pp of cap)**: linear 1.98 train / 2.15 CV / 2.32 test; XGBoost 0.83 train / 1.94 CV / 2.04 test.
CV and test agree. Widening the grid (depth up to 6, up to 1,000 trees) improved CV MAE from 1.940 to 1.924 pp,
less than the seed-to-seed variation.

**Regression toward the mean (test, XGBoost)**: contracts under 2% of cap average 0.82% actual vs 1.95% predicted;
contracts at 15%+ of cap average 21.46% actual vs 14.87% predicted.

**SHAP (mean |SHAP|, pp of cap)**: snap % 1.51, dropbacks 0.97, target share 0.73, age 0.38, rushes 0.32,
games played 0.25, air-yards share 0.22, offense snaps 0.21, total EPA 0.20; success rate 0.12, EPA/play 0.12.
Figures: `docs/figures/shap_summary.png`, `shap_waterfall_*_2024.png`, `pred_vs_actual.png`.

Implied salary cap (median APY ÷ APY % of cap, contracts signed that year with ≥5% of cap): 2024 $255.4M, 2025 $278.8M.

## Value (Phase 4, model v1)
Source: `notebooks/03_value.ipynb` (re-run 2026-10-24). Model refit from `src/model.py` (`BEST_PARAMS`).
Exports: `exports/v1/`.

**Definition.** Contract gap = actual APY % of cap − predicted APY % of cap (positive = paid more than the production
earns), converted to $M with the season's implied cap (2024 $255.4M, 2025 $278.8M).
696 player-seasons scored: 413 veteran, 283 rookie-contract.

**Labels (veterans).** The gap is ranked within **position × pay tier** (thirds of veteran pay at that position).
- Overpaid = top 15% **and** gap ≥ +$2.5M
- Underpaid = bottom 15% **and** gap ≤ −$2.5M
- Fewer than 10 games → "Injury-shortened" (instead of Overpaid) or "Limited sample" (instead of Underpaid)

The first attempt, ranking within position only (as specified), flagged 36.2% of top-pay-tier veterans as Overpaid vs 0%
of the bottom tier, including Josh Allen's 2024 MVP season. With pay tiers: 12.5% (middle) and 14.5% (top).

| Label | QB | RB | WR | TE | Total |
|---|---:|---:|---:|---:|---:|
| Overpaid | 6 | 6 | 14 | 11 | 37 |
| Injury-shortened | 3 | 0 | 2 | 0 | 5 |
| Fair | 48 | 68 | 128 | 76 | 320 |
| Limited sample | 1 | 0 | 4 | 1 | 6 |
| Underpaid | 5 | 12 | 15 | 13 | 45 |
| Rookie contract | 30 | 58 | 124 | 71 | 283 |

**Most overpaid veterans ($M above prediction):** Lamar Jackson 2025 (38.3), Trevor Lawrence 2024 (35.1),
Kirk Cousins 2025 (34.0), Jaylen Waddle 2024 (19.7), Josh Allen 2025 (19.4)\*, Christian Kirk 2025 (17.3),
Matthew Stafford 2024 (17.2).

**Most underpaid veterans ($M below prediction):** Russell Wilson 2024 (45.3)\*, Aaron Rodgers 2025 (31.5),
Sam Darnold 2024 (31.4), Baker Mayfield 2024 (17.0), Daniel Jones 2025 (12.6), Jauan Jennings 2025 (12.5).

**Largest rookie-contract surplus ($M):** Bo Nix 2025 (50.9), Drake Maye 2025 (42.8), Brock Purdy 2024 (40.2),
Bo Nix 2024 (32.3), Michael Penix Jr. 2025 (31.0), Bryce Young 2025 (28.4)\*.

**Injury-shortened:** Joe Burrow 2025 (8 games, +$48.1M), Deshaun Watson 2024 (7, +$36.0M),
Brandon Aiyuk 2024, Calvin Ridley 2025, Russell Wilson 2025.

**Team net value, 2024+2025** (underpaid surplus + rookie surplus − overpaid, QB/RB/WR/TE only):
best DEN +$100.6M, PIT +$88.0M, SF +$78.4M, NO +$75.0M, TB +$73.4M;
worst BAL −$17.4M, JAX −$13.2M, BUF −$8.4M, PHI −$0.2M, DET +$3.3M.

**SHAP on overpaid players** (vs. peers at the same position paid within ±25%):
- Lamar Jackson 2025: 366 dropbacks vs 524 and 30 total EPA vs 66, over 13 games
- Jaylen Waddle 2024: target share 0.16 vs 0.24
- David Njoku 2025: −3.6 total EPA vs +21.7; target share 0.12 vs 0.20

\*Known artifacts, explained in the notebook:
- Allen 2025 sits at the top edge of the QB middle pay tier; in the top tier his gap would rank Fair.
- Efficient but lower-volume players (Amon-Ra St. Brown 2024, Mark Andrews 2024) are flagged because the model
  under-rewards per-play efficiency.
- Starting QBs in weak seasons (Russell Wilson 2024, Bryce Young 2025) look underpaid or high-surplus because the
  model prices role and volume.

## Value model v2: per-game production (Phase 5)
Source: `notebooks/04_value_v2.ipynb` (run 2026-10-24); SQL `sql/06`–`08`; code and weights in `src/model.py`.
Exports: `exports/player_value.csv` (696 rows, 77 columns), `exports/team_value.csv` (64 team-seasons),
`exports/shap_importance.csv` (95 rows). v1's exports moved to `exports/v1/`.

**What changed from v1**
- **Per-game features only**, as a 2-season weighted average (2/3 current, 1/3 prior; the prior season counts only with 4+ games).
  - QB: passing yards, passing TDs, EPA, rushing yards per game, plus CPOE.
  - RB/WR/TE: receiving and rushing yards, receptions, targets, carries and EPA per game, plus success rate and EPA/play.
  - Removed: games played, snaps and snap %.
- **Stats that belong to another position are set to 0** (QB receiving, non-QB passing).
- **Consistency (RB/WR/TE):** the share of games over 50 receiving yards (WR/TE) or 60 scrimmage yards (RB), and the
  25th-percentile weekly yards (the "floor").
- **Production score (0–100):** a weighted average of within-position, within-season percentiles.
  - QB: EPA/game 30%, passing yards/game 25%, passing TDs/game 20%, CPOE 15%, rushing yards/game 10%.
  - RB/WR/TE: yards/game 35%, receptions/game 20%, consistency 25% (half good-game share, half floor), EPA/game 20%.
- **Monotone constraints:** predicted pay can only rise with the production score and every production feature
  (checked: bumping any of them by 1 SD never lowers a prediction).
- **Fair value is floored at 0.3% of cap**, the 1st percentile of veteran pay in training (about the veteran minimum).

New tables: `player_game_box` 69,354 rows · `player_season_pergame` 4,407 · `player_availability` 15,661.

**v1 vs v2: test set 2024–2025, 413 veteran player-seasons.** Same rows, the same contract correction and the
same floor for every model.

| Model | R² | MAE (pp) | R², unseen contracts | MAE, unseen contracts (pp) | MAE over 5 seeds (pp) |
|---|---:|---:|---:|---:|---|
| Position average | 0.353 | 3.60 | 0.242 | 3.28 | – |
| Linear v2 | 0.702 | 2.07 | 0.690 | 1.75 | – |
| XGBoost v1 | 0.705 | 1.99 | 0.670 | 1.77 | 2.002–2.052 |
| **XGBoost v2** | **0.753** | **1.79** | **0.692** | **1.63** | **1.785–1.808** |

At the 2024 cap, v2's MAE is about $4.6M (v1: $5.1M).

| Position | v1 R² / MAE | v2 R² / MAE |
|---|---|---|
| QB | 0.417 / 5.38 | **0.516 / 4.77** |
| RB | **0.440 / 1.01** | 0.366 / 1.07 |
| WR | 0.712 / 1.74 | **0.762 / 1.56** |
| TE | 0.508 / 1.12 | **0.640 / 0.94** |

v2 train / CV / test MAE: 1.20 / 1.74 / 1.79 pp. v1 was 0.83 / 1.94 / 2.04, so v2 overfits less.
v2 settings: `max_depth=4, learning_rate=0.03, n_estimators=500, min_child_weight=1`.

**SHAP (mean |SHAP|, test set, pp of cap):** passing yards/game 1.10, passing TDs/game 1.06, production score 0.66,
targets/game 0.64, carries/game 0.50, age 0.47, receiving yards/game 0.40.

**Labels.** Both are ranked within position × pay tier: top/bottom 15% and at least $2.5M.
- Season label (per-game fair value): 47 Overpaid, 313 Fair, 52 Underpaid, 1 Limited sample. A veteran with fewer than
  6 games gets "Limited sample" instead of Overpaid/Underpaid: a sample-size rule, not an injury penalty (the fair
  value still ignores missed games). 7 veterans played under 6 games; only Carson Wentz 2025 (5 games, would have been
  Underpaid by $29.9M) changed label.
- 3-year label (fair value × availability over the current and two prior seasons): 48 Overpaid, 317 Fair, 48 Underpaid.
  No game-count rule here; availability already accounts for missed games.
- Durability concern (availability under 75% in 2+ of the last 3 seasons): 96 veteran player-seasons.

**Eye test, v1 → v2 (season / 3-year)**
- Amon-Ra St. Brown 2024: Overpaid → Fair / Fair
- Lamar Jackson 2025: Overpaid → Fair / Fair
- Josh Allen 2024: Fair → Fair / Fair
- Josh Allen 2025: Overpaid → Fair / Fair
- Justin Jefferson 2024: Fair → Fair / Fair
- Saquon Barkley 2024: Fair → Fair / Fair
- Nico Collins 2024 (durability flag): Fair → Fair / Fair
- Kyler Murray 2025 (durability flag, 5 games): Fair → Fair / **Overpaid**

**Standouts (season label, $M gap)**
- Overpaid: Deshaun Watson 2024 (+47.6), Trevor Lawrence 2024 (+39.4), Kirk Cousins 2025 (+33.5),
  Tua Tagovailoa 2025 (+27.4), Dak Prescott 2024 (+21.8).
- Underpaid: Russell Wilson 2024 (−48.8), Joe Flacco 2024 (−37.1), Daniel Jones 2025 (−19.3),
  Baker Mayfield 2024 (−16.6), Aaron Rodgers 2025 (−15.3).
- Rookie surplus: Brock Purdy 2024 ($53.7M), Drake Maye 2025 ($51.2M), Bo Nix 2025 ($49.9M),
  Jayden Daniels 2024 ($40.2M), Puka Nacua 2025 ($31.1M).

**Teams, 2024+2025 net value (season label)**
- Best: DEN +$116.9M, PIT +$108.7M, IND +$100.5M, NO +$93.8M, TB +$79.6M.
- Worst: CLE −$41.1M, MIA −$14.0M, PHI −$10.2M, JAX −$3.8M, CAR +$4.1M.
- On the 3-year label, teams with injured starters drop: NYJ +7.7 → −35.0, IND +100.5 → +41.3, ARI +35.4 → −8.4.

**Known weaknesses**
- RB accuracy dropped compared with v1.
- Top-of-market contracts are still compressed (Jefferson 2024 worth 9.5% vs paid 13.7%; Goff 2025 14.0% vs 20.8%).
- The season label treats short QB stints as full per-game value: Flacco 2024 (8 games) is still Underpaid. The 6-game
  rule only catches very short stints like Wentz 2025; the 3-year label tempers the rest.

## Limitations
- **Reproducibility fix (found in Phase 5).** XGBoost's row subsampling depends on row order, and SQL tables have no
  guaranteed order, so rebuilding the database changed the model (test MAE moved between about 2.04 and 2.08 pp).
  The loaders now sort rows (`ORDER BY season, gsis_id`), and Phases 3–4 were re-run; the numbers above are from that run.
- **Same-year contracts from another team (29 player-seasons, 1.2%).** OverTheCap has no signing dates, so a contract
  signed later in the same year with a different team can be chosen as "the contract in force". Nearly all are
  minimum deals. The material case: **Daniel Jones 2024** shows 0.4% of cap (Vikings, after his release) instead of
  his 17.8% Giants contract. A blanket rule was rejected because OverTheCap sometimes labels a contract with its current
  team (e.g. DK Metcalf's 2022 Seattle extension is labeled "Steelers").
- **Daniel Jones 2024 is corrected in Phase 4** via `CONTRACT_OVERRIDES` in `src/model.py` (Giants 2023 deal, 17.8%).
  The Phase 3 test metrics include his uncorrected row (1 of 413); excluding it, test MAE is 2.00 pp.
- **Availability counts games played, not injuries:** a healthy backup who is active but doesn't play counts as
  unavailable. Seasons on a practice squad, cut or out of the league don't count.
- **Team totals cover only QB/RB/WR/TE with 200+ snaps**, and a traded player counts for the team he played the most snaps for.
- **APY is measured at signing**, not the actual cap hit in each season.
- **The model compresses extreme salaries** (see Phase 3), so raw residuals favor cheap players and penalize stars.
- **SHAP shows association, not causation:** usage (snap %, target share) is partly a consequence of pay.

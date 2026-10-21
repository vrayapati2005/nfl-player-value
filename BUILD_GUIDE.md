# NFL Player Value Model: Build Guide

Do the phases in order, about one per day. Each phase has:
1. **Paste into Claude Code:** the prompt to give it.
2. **You check:** what to look at before moving on.
3. **Understand it:** questions you should be able to answer in an interview. Ask Claude Code to quiz you on them.
4. **Commit:** commit with your own message. Short, normal messages are fine.

---

## Phase 0: Setup (30 min)

In Terminal:
```bash
mkdir nfl-player-value && cd nfl-player-value
git init
code .
```
Copy `CLAUDE.md` into the folder. Create an empty **public** repo on GitHub called `nfl-player-value` and connect it (GitHub shows the two commands after you create it). Then start Claude Code in the folder with `claude`.

**Paste into Claude Code:**
> Read CLAUDE.md. Set up the project: create the folder structure, a Python virtual environment, requirements.txt (nflreadpy, duckdb, pandas, polars, pyarrow, scikit-learn, xgboost, shap, matplotlib, jupyter), and a .gitignore that excludes data/ and the venv. Install everything and confirm nflreadpy imports. Create docs/LEARNING.md and docs/RESULTS.md as empty templates. Explain what each piece is for.

**You check:** `python -c "import nflreadpy, xgboost, shap"` runs without errors.
**Commit:** `project setup`

---

## Phase 1: Ingest the data (Day 1)

**Paste into Claude Code:**
> Write pipeline/ingest.py using nflreadpy to download, for seasons 2019–2025: play-by-play, weekly player stats, snap counts, rosters, and contracts (OverTheCap data). Check the actual nflreadpy function names in its docs before using them. Save each as Parquet in data/raw/. Then write pipeline/build_db.py that loads them into data/nfl.duckdb as tables. Print row counts for every table. Explain what each dataset contains and the key columns we'll use (especially epa, success, cpoe, air_yards, and the contract fields like apy and apy_cap_pct).

**You check:** the row counts print. Play-by-play should be several hundred thousand rows. Write the counts down.
**Understand it:**
- What is EPA (expected points added), and why is it better than yards?
- Why store the data in DuckDB instead of CSVs?
- What does `apy_cap_pct` mean, and why use % of cap instead of dollars? (The salary cap grows every year.)

**Commit:** `ingest nflverse data into duckdb`

---

## Phase 2: Build features with SQL (Day 2)

**Paste into Claude Code:**
> In sql/, write SQL that builds a player_season table (one row per player per season, QB/RB/WR/TE only, minimum snap threshold so tiny samples are excluded) with: total EPA, EPA per play, success rate, CPOE (QBs), targets, target share, air-yards share, yards after catch, snap count and snap %, games played, age, position, and team. Join each player-season to the contract active that season (APY and APY as % of cap), plus a flag for rookie-scale contracts. Run it, show 10 sample rows and summary stats, and do a quick EDA notebook (01_eda.ipynb): distributions of EPA/play by position, and APY % vs EPA scatter by position. Explain any join or data-quality issues you hit (e.g. player ID matching, traded players).

**You check:** the sample rows look sane. Patrick Mahomes and Josh Allen should have high EPA and high cap %. Write down how many player-seasons are in the table.
**Understand it:**
- How did you match contracts to player-seasons? What went wrong, and how did you fix it?
- Why set a minimum snap threshold?
- Why flag rookie contracts? (Rookie pay is set by draft slot, not performance.)

**Commit:** `player-season features in sql`

---

## Phase 3: The ML model (Day 3)

**Paste into Claude Code:**
> In notebooks/02_model.ipynb: predict APY % of cap from on-field production, trained only on veteran (non-rookie) contracts. Use a time-based split: train on seasons 2019–2023, test on 2024–2025. First fit a linear regression baseline, then an XGBoost regressor (tune a few hyperparameters with cross-validation on the training set only). Report R² and MAE (in % of cap) for both on the test set. Then use SHAP: a summary plot of which features drive valuations, and a waterfall plot for 2–3 well-known players. Save the plots to docs/. Write the real metrics into docs/RESULTS.md. Explain every choice: why a time-based split, why a baseline, and what SHAP shows.

**You check:** XGBoost beats the baseline. If it doesn't, ask Claude Code why and what to try. Write down both R² and MAE values. Look at the SHAP plot and make sure the features make football sense.
**Understand it:**
- Why train only on veteran contracts?
- Why split by season instead of randomly? (So the model is tested the way it would actually be used, on future seasons.)
- What is R²? What does MAE = X% of cap mean in dollars?
- What is SHAP, and what did it say drives contract value?
- Why XGBoost over linear regression? (Hint: nonlinear effects and interactions, like age × production.)

**Commit:** `xgboost contract value model + shap`

---

## Phase 4: Find the undervalued players (Day 4)

**Paste into Claude Code:**
> In notebooks/03_value.ipynb, use the trained model to predict fair contract value for every player-season in 2024–2025, including rookie-contract players. Compute surplus value = predicted fair value − actual APY % (and in dollars using that season's cap). List the top 15 most underpaid veterans and the top 15 rookie-contract surplus players, and the team-level total surplus. Write the key findings (counts, top examples, team rankings) into docs/RESULTS.md. Export clean CSVs to exports/ for Tableau: player_value.csv, team_value.csv, shap_importance.csv.

**You check:** the lists pass the eye test. Cheap stars on rookie deals should top the surplus list. Write down how many veterans you flagged as underpaid (use a clear threshold, e.g. more than 2% of cap below predicted) and 1–2 standout names.
**Understand it:**
- How did you define "undervalued," and why that threshold?
- What's one limitation? For example: offensive line and defense aren't in the model, injuries, and contract structure (guarantees, not just APY).

**Commit:** `surplus value analysis + tableau exports`

---

## Phase 5: Tableau Public dashboard (Day 5, built by you)

Download Tableau Public (free, Mac). Connect to the CSVs in `exports/`. Build one dashboard with:
1. **Value scatter:** predicted vs. actual cap %, colored by position, with labels on the biggest outliers.
2. **Team bar chart:** total surplus value by team.
3. **Player drill-down:** filter by player to see production stats and their top SHAP drivers.
4. Filters for season and position.

Publish it to Tableau Public and copy the link.

**Understand it:** why each chart exists, and what one insight a GM would take from the dashboard.

---

## Phase 6: README and wrap-up

**Paste into Claude Code:**
> Write README.md: the question, data sources (nflverse/OverTheCap), approach (pipeline → SQL features → XGBoost + SHAP → surplus value), results using ONLY the numbers in docs/RESULTS.md, the SHAP plot and a dashboard screenshot, the Tableau Public link [I'll paste it], limitations, and how to run it.

**Commit:** `readme + results`

Pin the repo on your GitHub profile. Add it to LinkedIn Projects with the Tableau link.

---

## Numbers to bring back for the resume

Give these to the tailor-resume skill. It will switch the project to finished bullets.
- [ ] Play-by-play rows ingested, and the number of player-seasons in the final table
- [ ] Linear baseline R² and MAE; XGBoost R² and MAE (test seasons 2024–2025)
- [ ] Top SHAP driver(s)
- [ ] Number of underpaid veterans flagged (and the threshold), plus 1–2 standout names
- [ ] GitHub repo URL and Tableau Public URL

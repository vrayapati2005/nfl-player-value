# Learning Log

Plain-English notes on every concept used in this project, added as we go.
Each entry: what it is, why we use it here, and how I'd explain it in an interview.

<!--
Template for new entries:

## <Concept name>
**Phase:** <phase number / step>
**What it is:** <one or two sentences, no jargon>
**Why we use it here:** <how it helps answer "who produces more than they're paid?">
**Interview version:** <a 1–2 sentence answer I could say out loud>
-->

## Python virtual environment (venv)
**Phase:** 0 – Setup
**What it is:** A private folder (`.venv/`) holding its own copy of Python and its own installed packages, separate from the rest of the computer.
**Why we use it here:** This machine also has Anaconda. A venv keeps this project's package versions isolated, so installing something for another project (or in conda's `base`) can't break this one, and `requirements.txt` lets anyone recreate the same setup.
**Interview version:** "I isolated dependencies in a venv built from a standalone Python 3.11 and listed them in requirements.txt, so the project is reproducible on any machine."

## .gitignore
**Phase:** 0 – Setup
**What it is:** A list of files and folders Git should never track.
**Why we use it here:** Raw NFL data and the DuckDB file are large and can be re-downloaded by `pipeline/ingest.py`, and the venv can be rebuilt from `requirements.txt`. Git should hold code and docs, not generated artifacts.
**Interview version:** "I commit code, not data. The pipeline regenerates the data from source."

## Parquet
**Phase:** 1 – Ingest
**What it is:** A file format that stores data by column instead of row, compressed, with column types saved inside the file.
**Why we use it here:** Seven seasons of play-by-play (342k plays x 372 columns) is 96 MB as Parquet; as CSV it would be several times bigger and lose types (dates, numbers, nested lists). Reading only a few columns is also fast, because each column is stored separately.
**Interview version:** "I stored raw data as Parquet: compressed, typed and columnar, so analytic queries only read the columns they need."

## DuckDB
**Phase:** 1 – Ingest
**What it is:** A SQL database that runs inside Python as a single file (`data/nfl.duckdb`), with no server to set up. It's built for analytics (big scans, GROUP BYs, joins).
**Why we use it here:** All feature building is done in SQL, joining hundreds of thousands of plays to players and contracts. DuckDB does this in seconds on a laptop, and the SQL stays visible in `sql/`.
**Interview version:** "DuckDB is like SQLite for analytics: an embedded columnar database, so I could write real SQL joins and aggregations without running a database server."

## Idempotent pipeline
**Phase:** 1 – Ingest
**What it is:** A step you can rerun any number of times and get the same result, with no duplicates.
**Why we use it here:** `build_db.py` uses `CREATE OR REPLACE TABLE`, so rerunning it rebuilds each table instead of appending to it. I ran it twice and got identical row counts.
**Interview version:** "My load step is idempotent: rerunning it replaces tables rather than duplicating rows."

## EPA (Expected Points Added)
**Phase:** 1 – Ingest (column `epa` in pbp)
**What it is:** Before every play, a model estimates how many points the offense should expect from that situation (down, distance, field position, time). EPA = expected points after the play minus expected points before it.
**Why we use it here:** Yards treat every yard the same. EPA knows that 4 yards on 3rd-and-3 (a first down) is worth far more than 4 yards on 3rd-and-10. It's our main measure of on-field production. League average is about 0 by design (2019–2025 seasons averaged -0.03 to +0.02 per play).
**Interview version:** "EPA measures how much a play changed the offense's expected points, so it credits context, not just yardage."

## Success rate
**Phase:** 1 – Ingest (column `success` in pbp)
**What it is:** A play is a "success" (1) if its EPA is greater than 0, otherwise 0. Success rate is the share of a player's plays that were successful.
**Why we use it here:** EPA can be dominated by a few huge plays. Success rate measures consistency: how often a player keeps the offense "on schedule." (League-wide, about 40–45% of plays.)
**Interview version:** "EPA tells you how much value, success rate tells you how often. One long touchdown can't inflate success rate."

## CPOE (Completion Percentage Over Expected)
**Phase:** 1 – Ingest (column `cpoe` in pbp, QBs only)
**What it is:** For each pass, a model estimates the chance it's completed (based on throw depth, receiver separation, field position, etc.). CPOE = actual completion (0 or 1, as %) minus that probability, averaged over passes.
**Why we use it here:** Raw completion % rewards QBs who throw lots of short, easy passes. CPOE measures accuracy after adjusting for difficulty. Only filled on pass attempts.
**Interview version:** "CPOE adjusts completion percentage for throw difficulty, so a QB isn't rewarded just for dumping the ball off."

## Air yards
**Phase:** 1 – Ingest (column `air_yards` in pbp)
**What it is:** How far the ball travels in the air past the line of scrimmage, whether or not it's caught. Yards after catch (YAC) is what the receiver adds after catching it.
**Why we use it here:** It separates the QB's/route's depth from the receiver's running. Summed per receiver and divided by team totals, it becomes air-yards share: how much of the downfield passing game a player commands. That's a strong sign of a receiver's role.
**Interview version:** "Air yards measure intended depth of target; air-yards share shows how central a receiver is to the passing offense, even on incompletions."

## APY and APY as % of cap
**Phase:** 1 – Ingest (columns `apy`, `apy_cap_pct` in contracts)
**What it is:** APY = average per year = total contract value / years, in **millions of dollars**. `apy_cap_pct` = APY divided by the salary cap in the year the contract was signed, stored as a **fraction** (0.227 = 22.7%).
**Why we use it here:** The salary cap grows almost every year, so $40M in 2019 was a bigger share of a team's budget than $40M in 2025. % of cap makes contracts from different years comparable. It's the "cost" side of our value question.
**Interview version:** "I measured pay as a share of the salary cap at signing, not raw dollars, because the cap keeps rising and teams budget against the cap."

## Grain (of a table)
**Phase:** 2 – Features
**What it is:** What one row represents: "one play", "one player per game", "one player per season". Every SQL file in `sql/` states its grain at the top.
**Why we use it here:** Most join bugs are grain bugs. If you join a one-row-per-contract table to a one-row-per-season table without picking one contract per season, rows multiply silently. I checked `COUNT(*) = COUNT(DISTINCT (gsis_id, season))` after building `player_season`.
**Interview version:** "Before writing a join I define each table's grain, and afterwards I assert the key is still unique."

## ID crosswalk (entity resolution)
**Phase:** 2 – Features
**What it is:** A lookup table that translates one system's player ID into another's. Snap counts come from Pro Football Reference (`pfr_id`), while everything else uses the NFL's `gsis_id`.
**Why we use it here:** Without it, snap counts can't be attached to anyone. I matched in steps from most to least reliable: the nflverse players table (an official 1:1 mapping), then exact name + team + season, accepting a name match only if it pointed to exactly one player. I didn't use the rosters table's `pfr_id` because it had wrong IDs (Tyler Conklin carried Ryan Izzo's). Contracts got the same treatment: own `gsis_id` → OverTheCap ID → name + date of birth.
**Interview version:** "Different sources use different player IDs, so I built a crosswalk: trusted ID mappings first, then strict fallback matches that are only accepted when unambiguous, and I measured the match rate at each step."

## ASOF join
**Phase:** 2 – Features (`sql/05_player_season.sql`)
**What it is:** A join that matches each row to the most recent row on the other side at or before a point in time, instead of requiring an exact match. DuckDB supports it directly: `ASOF LEFT JOIN contracts ON player = player AND season >= year_signed`.
**Why we use it here:** A contract signed in 2020 is still the one in force in 2023 unless a newer one replaced it. "Latest contract signed on or before this season" handles extensions automatically. I didn't filter on expiry (`year_signed + years`) because OverTheCap's `years` for an extension counts only the *new* years, so that formula wrongly marked valid contracts as expired.
**Interview version:** "I used an as-of join to attach the contract in force each season: the latest one signed on or before that season."

## Share metrics and their denominator
**Phase:** 2 – Features
**What it is:** Target share = player's targets / team's targets; air-yards share = player's air yards / team's air yards; snap % = player's snaps / team's snaps.
**Why we use it here:** The denominator decides the meaning. I used only the games the player appeared in, for the team he played for that day, so a player traded mid-season or injured for six games isn't penalized for games he wasn't there. Share then means "how big is his role when he plays."
**Interview version:** "I computed shares over the games the player actually played, which handles trades and injuries cleanly."

## Validating against a reference
**Phase:** 2 – Features
**What it is:** Rebuilding a number yourself, then checking it against an independent published source.
**Why we use it here:** I built targets and carries from raw play-by-play, so I compared them with nflverse's official weekly stats: targets matched exactly for 99% of player-seasons and RB rushing EPA correlated at 0.999. The one mismatch (QB carries) was explained by a deliberate choice: scrambles count as QB dropbacks.
**Interview version:** "I reconciled my play-level aggregates with the official stats. They matched, and the one difference was a documented design choice."

## Spearman (rank) correlation
**Phase:** 2 – EDA
**What it is:** A correlation computed on ranks instead of raw values: "do the higher-paid players also tend to rank higher in EPA?" Ranges from −1 to +1.
**Why we use it here:** Pay is very skewed (a few QBs earn 20%+ of the cap, most players under 2%). Ordinary (Pearson) correlation would be dominated by those few points; Spearman isn't.
**Interview version:** "Because salaries are heavily skewed, I used rank correlation so a few star contracts don't drive the result."

## Small multiples
**Phase:** 2 – EDA
**What it is:** The same chart repeated in a grid, one panel per group, instead of one crowded chart with many colors.
**Why we use it here:** QB, RB, WR and TE have very different scales (QBs earn up to ~25% of the cap, RBs ~8%), so one panel per position keeps each readable, and color is saved for one comparison: rookie vs veteran contract.
**Interview version:** "I faceted by position because the scales differ by an order of magnitude, and used color only for the one comparison that mattered."

## Train only on veteran contracts
**Phase:** 3 – Model
**What it is:** Rookie contracts are set by a fixed pay scale based on draft slot, not negotiated on performance.
**Why we use it here:** We want the model to learn what the *market* pays for production. If rookie deals were in the training data, the model would learn "elite production can cost 1% of the cap", which is a rule of the league's labor agreement, not a market price. We learn the market rate from veterans, then apply it to everyone in Phase 4.
**Interview version:** "Rookie pay is fixed by the CBA, so I trained only on negotiated veteran deals to learn the market rate for production."

## Time-based train/test split
**Phase:** 3 – Model
**What it is:** Train on earlier seasons (2019–2023), test on later ones (2024–2025), instead of shuffling rows at random.
**Why we use it here:** The model will be used on future seasons, so it should be tested that way. A random split would put a player's 2022 season in training and his near-identical 2023 season (same contract!) in test, making the score look better than it is.
**Interview version:** "I split by season so the test mimics real use: predicting seasons the model has never seen."

## Time-aware cross-validation (expanding window)
**Phase:** 3 – Model
**What it is:** To tune settings without touching the test set, the training seasons are split into folds that respect time: train 2019–20 → check on 2021; train 2019–21 → check on 2022; train 2019–22 → check on 2023.
**Why we use it here:** Ordinary k-fold CV shuffles seasons together and would leak the future into the past. Our CV error (1.93 pp) ended up close to the real test error (2.07 pp), which shows the CV setup was a faithful rehearsal.
**Interview version:** "I tuned hyperparameters with expanding-window CV on training seasons only; the test set was used once, at the end."

## Baseline model
**Phase:** 3 – Model
**What it is:** The simplest reasonable model, used as a yardstick. We used two: "predict the position's average pay" and a linear regression.
**Why we use it here:** A score like R² 0.67 means nothing alone. Position average alone already gets 0.34, so position explains a big chunk "for free". XGBoost has to beat both baselines to justify its complexity.
**Interview version:** "I always fit baselines first: they show how much the fancy model actually adds."

## One-hot encoding
**Phase:** 3 – Model
**What it is:** Turning a category like position into separate 0/1 columns (position_QB, position_RB, ...).
**Why we use it here:** Models need numbers, and "QB = 1, RB = 2" would invent a fake order. For linear regression we drop one column (QB becomes the reference), because all four columns plus an intercept are perfectly redundant.
**Interview version:** "I one-hot encoded position, dropping a reference level for the linear model to avoid perfect collinearity."

## R² and MAE
**Phase:** 3 – Model
**What it is:** MAE (mean absolute error) is the average size of a miss, here in percentage points of cap. R² is the share of the variation in pay the model explains (1 = perfect, 0 = no better than predicting the average, negative = worse).
**Why we use it here:** MAE is easy to explain: 2.07 pp of a $255.4M cap is about $5.3M per player. R² is useful for comparing, but overall R² is inflated when groups differ a lot (QBs vs everyone), so we also report R² within each position.
**Interview version:** "MAE is my headline because it converts to dollars: the model misses by about $5.3M on average."

## XGBoost (gradient-boosted trees)
**Phase:** 3 – Model
**What it is:** Many small decision trees built one after another, each one correcting the mistakes of the ones before it.
**Why we use it here:** Pay isn't a straight line in production. It jumps for starters, and the same stat means different things by position and age. Trees capture these thresholds and interactions automatically; linear regression can't.
**Interview version:** "XGBoost handles non-linear effects and interactions, like EPA mattering more for a QB, that a linear model can't."

## Overfitting
**Phase:** 3 – Model
**What it is:** A model that fits its training data much better than new data has partly memorized noise.
**Why we use it here:** XGBoost's training error (0.85 pp) is far below its test error (2.07 pp), so it memorizes training rows, helped by multi-year contracts repeating across seasons. The reassuring part: CV error and test error agree, so the error we report is honest.
**Interview version:** "The gap between train and test error shows memorization, but CV and test errors agreed, so the reported performance is trustworthy."

## Leakage
**Phase:** 3 – Model
**What it is:** When information about the answer sneaks into the model's inputs or into the test set, making results look better than they'd be in real use.
**Why we use it here:** Two checks. (1) No contract fields are features. (2) 17% of test rows share a contract with training rows, so I also scored only unseen contracts: XGBoost MAE 1.85 pp, R² 0.621. Reporting both numbers is the honest way to handle it.
**Interview version:** "I checked for leakage in features and in the split itself, and reported a stricter score on contracts the model had never seen."

## Regression toward the mean
**Phase:** 3 – Model
**What it is:** Models trained to minimize average error pull extreme predictions toward the middle.
**Why we use it here:** Our model predicts 14.7% on average for players actually paid 15%+ of the cap, and 2.0% for players paid under 2%. So in Phase 4, stars will look overpaid and minimum-salary players underpaid partly *because of the model*, not reality. We'll need to compare players within pay tiers or positions.
**Interview version:** "The model compresses the extremes, so I didn't read raw residuals at face value; I compared like with like."

## SHAP values
**Phase:** 3 – Model
**What it is:** A method that splits one prediction into contributions from each feature, starting from the average prediction. The contributions add up exactly to the prediction. The summary (beeswarm) plot shows every player's contributions for every feature; a waterfall shows one player's breakdown.
**Why we use it here:** It shows *why* the model values a player. Ours says the market pays for role and volume (snap %, being the starting QB, target share) far more than per-play efficiency. It also exposed a quirk: very high EPA/play slightly lowers predicted pay, because in the data extreme rates mostly come from low-volume backups.
**Interview version:** "SHAP showed the model values role and volume over efficiency, which matches how NFL teams actually pay. But SHAP explains the model, not causation: usage is partly a consequence of pay."

## Contract gap (a residual)
**Phase:** 4 – Value
**What it is:** Actual pay minus the model's predicted pay for the same production. In modeling terms it's the residual: the part of pay the production doesn't explain.
**Why we use it here:** It's the project's answer. Positive = paid more than the market rate for that production (overpaid); negative = paid less (underpaid). Converted to dollars with each season's salary cap so it's easy to read.
**Interview version:** "Value is the residual: what a player is paid minus what the market typically pays for his production."

## Comparing within groups (position × pay tier)
**Phase:** 4 – Value
**What it is:** Ranking a number only against similar cases (same position, similar salary) instead of against everyone.
**Why we use it here:** Regression residuals always correlate with the actual value: the highest-paid players will always have the most positive gaps, just because of how regression works. Ranking within position alone still flagged 35% of the highest-paid third (including Josh Allen's MVP season) and 0% of the lowest third. Ranking within pay tiers asks "among players paid like him, whose production falls shortest?" and evened the flag rates out (13% and 15% in the middle and top tiers). I also tried a boundary-free version (compare to the 15 nearest-paid players) and it did worse, so I kept the tiers and documented their edge case (Allen 2025).
**Interview version:** "Raw residuals are biased by the target itself, so I compared players to others paid similarly, and checked the fix with flag rates by pay tier."

## Surplus value of rookie contracts
**Phase:** 4 – Value
**What it is:** Predicted market value minus actual pay, for players on rookie deals.
**Why we use it here:** Rookie pay is fixed by draft slot, so "underpaid" isn't a meaningful label for them. Surplus measures how much cheap production the rookie scale gives a team. Bo Nix's 2025 season was worth about $50M more than his rookie deal.
**Interview version:** "For rookie deals I report surplus value, the market value of the production minus the fixed salary, instead of calling them underpaid."

## Documented manual overrides
**Phase:** 4 – Value
**What it is:** Correcting a known data error by hand, in one visible place, with the reason written next to it.
**Why we use it here:** Daniel Jones 2024 was matched to a Vikings deal signed after the Giants released him. A blanket rule would have broken other correct rows, so I corrected the one material case in `CONTRACT_OVERRIDES`. Anyone reading the code sees exactly what changed and why, and the Tableau export carries an `override_reason` column.
**Interview version:** "When a rule can't be fixed generally, I fix the specific case transparently: one dictionary, with the reason, and flagged in the output."

## The eye test (sanity-checking results)
**Phase:** 4 – Value
**What it is:** Reading the output lists and asking "does this make sense to someone who knows football?" before trusting them.
**Why we use it here:** The first version labeled the 2024 MVP as overpaid and a QB with 5 games and −19.5 EPA as underpaid by $18M. Both pointed to real method problems (residual bias, small samples), which I fixed and measured. The remaining oddities are explained by the model itself: it prices role and volume more than efficiency.
**Interview version:** "I check results against domain knowledge. When a list fails the eye test, I trace it to a cause and either fix the method or document the limitation."

## Per-game normalization
**Phase:** 5 – Value model v2
**What it is:** Dividing production by games played (yards per game, EPA per game) instead of using season totals.
**Why we use it here:** Season totals mix two things: how good a player is when he plays, and how often he plays. v1 learned from totals and snap %, so an injury looked like bad production. Per-game stats measure quality on its own, and availability is handled separately and on purpose (the 3-year label). I also blend in the prior season (2/3 current, 1/3 prior) to steady small samples. The prior season only counts with 4+ games, because Aaron Rodgers' 1-game 2023 season was dragging his average down.
**Interview version:** "I separated how good a player is per game from how often he's available, so injuries don't masquerade as poor play."

## Consistency metrics
**Phase:** 5 – Value model v2
**What it is:** Two ways to describe how reliable a player's weekly output is. The *share of good games* is the fraction of games over a threshold (50 receiving yards for WR/TE, 60 scrimmage yards for RB). The *floor* is the 25th-percentile weekly yards, roughly "a bad week for him".
**Why we use it here:** Two receivers with 70 yards per game can be very different: one gets 70 every week, the other alternates 140 and 0. Teams value the steady one more. I counted games with no box-score line as zero, so quiet games couldn't vanish and inflate consistency.
**Interview version:** "Averages hide volatility, so I added a hit rate and a 25th-percentile floor to capture how dependable a player is week to week."

## Composite production score
**Phase:** 5 – Value model v2
**What it is:** A 0–100 score built by converting each stat to a percentile within the player's position and season, then taking a weighted average. QB: EPA/game 30%, passing yards/game 25%, passing TDs/game 20%, CPOE 15%, rushing yards/game 10%. RB/WR/TE: yards/game 35%, receptions/game 20%, consistency 25%, EPA/game 20%. The weights are constants in `src/model.py`, so they're easy to change.
**Why we use it here:** Percentiles put very different stats (yards, TDs, CPOE) on one scale. Computing them within a season means a season is only compared with its own season, so no information leaks from other years. The score gives the model and the dashboard one readable number.
**Interview version:** "I built a transparent, position-specific production index from within-season percentiles, with weights anyone can change."

## Monotone constraints
**Phase:** 5 – Value model v2
**What it is:** A setting in XGBoost that forces predictions to only move in one direction as a feature increases. Here: more production can never lower predicted pay.
**Why we use it here:** v1 learned a quirk where very high EPA per play *lowered* predicted pay, because extreme rates came from low-volume backups. That makes no football sense. The constraint rules it out, and acts as regularization: v2's train/test gap shrank (1.20 → 1.79 pp vs v1's 0.83 → 2.04). One side effect: very poor production could extrapolate below zero, so fair value is floored at 0.3% of cap (about the veteran minimum).
**Interview version:** "I added domain knowledge as a constraint, so pay can only increase with production. It removed a nonsense pattern and reduced overfitting."

## Availability adjustment
**Phase:** 5 – Value model v2
**What it is:** Availability = games played ÷ games possible. The 3-year value multiplies a player's per-game fair value by his availability over the current and two prior seasons. A "durability concern" flag marks players under 75% availability in at least 2 of those seasons.
**Why we use it here:** There are two honest questions. *How good is he when he plays?* That's the season label, where injury has no effect. *What does a team actually get for the money?* That's the 3-year label. Kyler Murray 2025 shows the difference: Fair per game, but Overpaid once five games played and his injury history are counted. Seasons out of the league or on a practice squad aren't counted, because they say nothing about health.
**Interview version:** "I kept quality and availability separate, then combined them explicitly: per-game value times a 3-year availability rate, plus a durability flag."

## Reproducibility and random seeds
**Phase:** 5 – Value model v2
**What it is:** Making sure re-running the code gives the same numbers, and knowing how much results move when only the randomness changes.
**Why we use it here:** XGBoost samples rows, so its results depend on row order, and SQL tables have no guaranteed order. Rebuilding the database changed v1's labels. I fixed it by sorting when loading, re-ran every phase, and confirmed v1's export is identical after a full rebuild. Retraining with 5 seeds showed test MAE varies by about 0.05 pp, so v2's 0.2 pp improvement over v1 is real, not luck.
**Interview version:** "I pinned the data order so results are reproducible, and used seed variation to tell a real improvement from noise."

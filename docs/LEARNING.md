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

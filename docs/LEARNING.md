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

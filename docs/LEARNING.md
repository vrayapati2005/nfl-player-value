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

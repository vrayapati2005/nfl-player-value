# NFL Player Value Model

## Goal
Answer one question: **which NFL players produce more on the field than their contracts pay for?**
This is a portfolio project for data analyst / data science roles. Every step must be explainable in an interview.

## Stack
- Python 3.11+, nflreadpy (nflverse data), pandas/polars, DuckDB (SQL), scikit-learn, XGBoost, SHAP, matplotlib
- Dashboard: Tableau Public (built manually from CSVs in `exports/`)

## Scope
- Seasons: 2019–2025 (seven complete seasons)
- Positions: QB, RB, WR, TE (EPA-based stats are strongest for these)
- Unit of analysis: one row per player per season

## Repo layout
```
pipeline/     ingest.py (download raw data), build_db.py (load into DuckDB)
sql/          feature queries (one .sql file per table)
notebooks/    01_eda.ipynb, 02_model.ipynb, 03_value.ipynb
src/          reusable Python (features.py, model.py)
exports/      CSVs for Tableau
data/         raw + duckdb file (gitignored)
docs/         LEARNING.md, RESULTS.md
```

## Working rules for Claude Code
- Work in small steps. After each step, explain what you did and why in plain English (2–5 sentences), as if teaching a student.
- Append a short entry to `docs/LEARNING.md` for every concept used (e.g. EPA, train/test split by season, SHAP), in simple language.
- Write all transformation logic as SQL in `sql/` where reasonable, so the SQL skills are visible.
- Never invent numbers. Every metric in `docs/RESULTS.md` must come from code that was actually run.
- Use a time-based split (train on earlier seasons, test on later ones). Never test on data the model trained on.
- Keep code readable: clear names, short functions, comments on non-obvious lines.
- Don't commit large data files; keep `data/` in `.gitignore`.
- Stop after each phase and wait for me before starting the next one.

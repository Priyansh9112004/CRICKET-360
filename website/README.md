# CRICKET 360 website — first working version

This is an initial read-only player and historical-match explorer, with format/opponent breakdowns and match batting/bowling totals. It intentionally does not claim to show live matches, upcoming series, news, or social posts until permitted data sources are connected. Player photos are withheld until identity checks and public-use rights are resolved. The match summary combines innings for multi-innings formats and is not a conventional innings-by-innings scorecard.

## Run with the GitHub samples

From the repository root:

```bash
python -m venv .venv
python -m pip install -r website/requirements.txt
python website/import_data.py --data-dir data/sample
python -m uvicorn website.app:app --reload
```

Open <http://127.0.0.1:8000>. For production CSVs, run the importer with `--data-dir DATA/processed` instead. The importer requires `dim_player.csv`, `matches.csv`, `player_match_batting.csv` and `player_match_bowling.csv`. When available it also imports `match_summary.csv` (the complete 22,818-match list and team innings totals) and `player_summary.csv` (career batting numbers). It builds a local SQLite database atomically and leaves the source CSVs unchanged. Do not commit the generated database or source CSVs to GitHub.

The next steps are full-data validation, profile analytics, photo review, licensed live/upcoming match feed, historical expansion, news/social feeds, and deployment. Browser and Android app can share the later API.

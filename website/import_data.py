"""Import the existing CRICKET 360 CSVs into a small website database.

Usage: python website/import_data.py --data-dir DATA/processed
For a local demo: python website/import_data.py --data-dir data/sample
"""

import argparse
import csv
import sqlite3
from pathlib import Path


TABLES = {
    "players": "dim_player",
    "matches": "matches",
    "batting": "player_match_batting",
    "bowling": "player_match_bowling",
}


def import_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        columns = reader.fieldnames
        if not columns or any(not name or not name.replace("_", "").isalnum() for name in columns):
            raise ValueError(f"Invalid header in {path}")
        fields = ", ".join(f'"{name}" TEXT' for name in columns)
        conn.execute(f'CREATE TABLE "{table}" ({fields})')
        field_names = ", ".join(f'"{name}"' for name in columns)
        placeholders = ", ".join("?" for _ in columns)
        query = f'INSERT INTO "{table}" ({field_names}) VALUES ({placeholders})'
        count = 0
        for batch in iter(lambda: [row for _, row in zip(range(2000), reader)], []):
            conn.executemany(query, ([row[name] for name in columns] for row in batch))
            count += len(batch)
        return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--database", type=Path, default=Path(__file__).with_name("cricket360.sqlite3"))
    args = parser.parse_args()
    args.database.parent.mkdir(parents=True, exist_ok=True)
    temp_path = args.database.with_suffix(".sqlite3.tmp")
    temp_path.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temp_path) as conn:
            for table, stem in TABLES.items():
                path = args.data_dir / f"{stem}.csv"
                if not path.exists():
                    path = args.data_dir / f"{stem}_sample.csv"
                if not path.exists():
                    raise FileNotFoundError(f"Missing {stem}.csv in {args.data_dir}")
                print(f"{table}: {import_csv(conn, table, path):,} rows")
            summary_path = args.data_dir / "match_summary.csv"
            if summary_path.exists():
                print(f"match_summary: {import_csv(conn, 'match_summary', summary_path):,} rows")
            else:
                # Repository samples do not ship the production match summary.
                conn.execute(
                    "CREATE TABLE match_summary AS SELECT match_id, match_date, format, gender, "
                    "season, team1, team2, NULL AS Team1_Runs, NULL AS Team2_Runs, "
                    "NULL AS Team1_Wickets, NULL AS Team2_Wickets FROM matches"
                )
            player_summary_path = args.data_dir / "player_summary.csv"
            if player_summary_path.exists():
                print(f"player_summary: {import_csv(conn, 'player_summary', player_summary_path):,} rows")
            else:
                conn.execute(
                    "CREATE TABLE player_summary (player_id TEXT, Matches TEXT, Runs TEXT, "
                    "Batting_Average TEXT, Strike_Rate TEXT)"
                )
            conn.execute("CREATE INDEX idx_player_name ON players(display_name)")
            conn.execute("CREATE INDEX idx_batting_player ON batting(player_id)")
            conn.execute("CREATE INDEX idx_bowling_player ON bowling(player_id)")
            conn.execute("CREATE INDEX idx_match_date ON matches(match_date)")
            conn.execute("CREATE INDEX idx_summary_date ON match_summary(match_date)")
            conn.execute("CREATE INDEX idx_summary_match ON match_summary(match_id)")
            conn.execute("CREATE INDEX idx_player_summary ON player_summary(player_id)")
        temp_path.replace(args.database)
        print(f"Database: {args.database}")
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

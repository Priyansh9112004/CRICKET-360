"""Read-only first version of the CRICKET 360 website API."""

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse


ROOT = Path(__file__).parent
DATABASE = Path(os.environ.get("CRICKET360_DATABASE", ROOT / "cricket360.sqlite3"))
app = FastAPI(title="CRICKET 360", version="0.1.0")


def connect() -> sqlite3.Connection:
    if not DATABASE.is_file():
        raise HTTPException(503, "Data not imported. Run website/import_data.py first.")
    conn = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
def home():
    return FileResponse(ROOT / "index.html")


@app.get("/api/players")
def players(q: str = "", limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT player_id, display_name, full_name, country, role, photo_source "
            "FROM players WHERE display_name LIKE ? OR full_name LIKE ? "
            "ORDER BY display_name LIMIT ? OFFSET ?",
            (f"%{q}%", f"%{q}%", limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/players/{player_id}")
def player(player_id: int):
    with connect() as conn:
        person = conn.execute("SELECT * FROM players WHERE player_id = ?", (str(player_id),)).fetchone()
        if person is None:
            raise HTTPException(404, "Player not found")
        batting = conn.execute(
            "SELECT b.match_id, b.match_date, b.format, b.opponent_team, b.Runs, b.Balls_Faced, b.Fours, b.Sixes "
            "FROM batting b WHERE b.player_id = ? ORDER BY b.match_date DESC LIMIT 10",
            (str(player_id),),
        ).fetchall()
        bowling = conn.execute(
            "SELECT b.match_id, m.match_date, m.format, b.opponent_team, b.wickets, b.runs_conceded, b.legal_balls "
            "FROM bowling b LEFT JOIN match_summary m ON m.match_id = b.match_id "
            "WHERE b.player_id = ? ORDER BY m.match_date DESC LIMIT 10",
            (str(player_id),),
        ).fetchall()
        summary = conn.execute(
            "SELECT Matches, Runs, Batting_Average, Strike_Rate FROM player_summary WHERE player_id = ?",
            (str(player_id),),
        ).fetchone()
        formats = conn.execute(
            "SELECT format, COUNT(DISTINCT match_id) AS matches, "
            "SUM(CAST(Runs AS INTEGER)) AS runs, SUM(CAST(Balls_Faced AS INTEGER)) AS balls, "
            "SUM(CAST(Dismissals AS INTEGER)) AS dismissals "
            "FROM batting WHERE player_id = ? GROUP BY format ORDER BY matches DESC",
            (str(player_id),),
        ).fetchall()
        opponents = conn.execute(
            "SELECT opponent_team, COUNT(DISTINCT match_id) AS matches, "
            "SUM(CAST(Runs AS INTEGER)) AS runs, SUM(CAST(Balls_Faced AS INTEGER)) AS balls "
            "FROM batting WHERE player_id = ? AND opponent_team <> '' "
            "GROUP BY opponent_team ORDER BY runs DESC LIMIT 10",
            (str(player_id),),
        ).fetchall()
        profile = dict(person)
        # Existing photo paths have not been identity-checked or licensed for public use.
        profile.pop("photo_url", None)
        return {"profile": profile, "career_batting": dict(summary) if summary else None,
                "batting_by_format": [dict(row) for row in formats],
                "batting_vs_team": [dict(row) for row in opponents],
                "recent_batting": [dict(row) for row in batting], "recent_bowling": [dict(row) for row in bowling]}


@app.get("/api/matches")
def matches(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT s.match_id, s.match_date, s.format, s.team1, s.team2, "
            "s.Team1_Runs, s.Team1_Wickets, s.Team2_Runs, s.Team2_Wickets, "
            "m.venue, m.event_name FROM match_summary s "
            "LEFT JOIN matches m ON m.match_id = s.match_id "
            "ORDER BY s.match_date DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/matches/{match_id}")
def match(match_id: int):
    with connect() as conn:
        match_row = conn.execute(
            "SELECT s.*, m.venue, m.city, m.event_name FROM match_summary s "
            "LEFT JOIN matches m ON m.match_id = s.match_id WHERE s.match_id = ?",
            (str(match_id),),
        ).fetchone()
        if match_row is None:
            raise HTTPException(404, "Match not found")
        batting = conn.execute(
            "SELECT b.player_id, COALESCE(p.display_name, b.batter) AS player, "
            "b.batting_team AS team, b.Runs, b.Balls_Faced, b.Fours, b.Sixes, b.Dismissals "
            "FROM batting b LEFT JOIN players p ON p.player_id = b.player_id "
            "WHERE b.match_id = ? ORDER BY b.batting_team, CAST(b.Runs AS INTEGER) DESC",
            (str(match_id),),
        ).fetchall()
        bowling = conn.execute(
            "SELECT b.player_id, COALESCE(p.display_name, b.player) AS player, "
            "b.bowling_team AS team, b.wickets, b.runs_conceded, b.legal_balls, b.Economy "
            "FROM bowling b LEFT JOIN players p ON p.player_id = b.player_id "
            "WHERE b.match_id = ? ORDER BY b.bowling_team, CAST(b.wickets AS INTEGER) DESC",
            (str(match_id),),
        ).fetchall()
        return {"match": dict(match_row), "batting": [dict(row) for row in batting],
                "bowling": [dict(row) for row in bowling]}

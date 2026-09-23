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
            "FROM bowling b LEFT JOIN matches m ON m.match_id = b.match_id "
            "WHERE b.player_id = ? ORDER BY m.match_date DESC LIMIT 10",
            (str(player_id),),
        ).fetchall()
        profile = dict(person)
        # Existing photo paths have not been identity-checked or licensed for public use.
        profile.pop("photo_url", None)
        return {"profile": profile, "recent_batting": [dict(row) for row in batting], "recent_bowling": [dict(row) for row in bowling]}


@app.get("/api/matches")
def matches(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    with connect() as conn:
        rows = conn.execute(
            "SELECT match_id, match_date, format, team1, team2, venue, event_name "
            "FROM matches ORDER BY match_date DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [dict(row) for row in rows]

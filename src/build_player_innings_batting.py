import pandas as pd
from pathlib import Path

INPUT = Path(r"DATA\processed\ball_by_ball.csv")
OUTPUT = Path(r"DATA\processed\player_innings_batting.csv")

USECOLS = [
    "match_id",
    "innings_no",
    "batting_team",
    "batter",
    "runs_batter",
]

print("Reading ball-by-ball data...")

df = pd.read_csv(
    INPUT,
    usecols=USECOLS,
    low_memory=False
)

print(f"Ball rows: {len(df):,}")

# ---------------------------------------------------------
# Each row in output = ONE batter in ONE innings of ONE match
# ---------------------------------------------------------

innings = (
    df.groupby(
        ["match_id", "innings_no", "batting_team", "batter"],
        as_index=False,
        dropna=False
    )
    .agg(
        Runs=("runs_batter", "sum"),
        Balls_Faced=("runs_batter", "size"),
        Fours=("runs_batter", lambda x: (x == 4).sum()),
        Sixes=("runs_batter", lambda x: (x == 6).sum()),
    )
)

innings["Strike_Rate"] = (
    innings["Runs"] * 100 / innings["Balls_Faced"]
).round(2)

# Safety checks
dup = innings.duplicated(
    subset=["match_id", "innings_no", "batter"]
).sum()

print(f"Innings rows: {len(innings):,}")
print(f"Duplicate match+innings+batter rows: {dup:,}")

if dup != 0:
    raise RuntimeError(
        "Duplicate match_id + innings_no + batter rows found."
    )

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
innings.to_csv(OUTPUT, index=False)

print("\nDONE")
print(f"Output: {OUTPUT}")
print("\nTop 20 innings by runs:")
print(
    innings.sort_values("Runs", ascending=False)
    .head(20)
    .to_string(index=False)
)
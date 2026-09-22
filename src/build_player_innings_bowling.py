import pandas as pd
from pathlib import Path

INPUT = Path(r"DATA\processed\ball_by_ball.csv")
OUTPUT = Path(r"DATA\processed\player_innings_bowling.csv")

USECOLS = [
    "match_id",
    "innings_no",
    "batting_team",
    "bowler",
    "runs_batter",
    "runs_extras",
    "extras_type",
    "wicket",
    "wicket_type",
]

print("Reading ball-by-ball data...")

df = pd.read_csv(
    INPUT,
    usecols=USECOLS,
    low_memory=False
)

print(f"Ball rows: {len(df):,}")

# Wickets credited to bowler.
# These dismissal types are NOT bowler wickets.
NON_BOWLER_WICKETS = {
    "run out",
    "retired hurt",
    "retired out",
    "obstructing the field"
}

wtype = df["wicket_type"].fillna("").str.strip().str.lower()

df["bowler_wicket"] = (
    df["wicket"].eq(1)
    & ~wtype.isin(NON_BOWLER_WICKETS)
).astype("int8")

# Bowler runs conceded:
# byes and leg-byes are not charged to bowler.
etype = df["extras_type"].fillna("").str.strip().str.lower()

df["bowler_runs"] = (
    df["runs_batter"]
    + df["runs_extras"].where(
        ~etype.isin(["byes", "legbyes", "leg byes"]),
        0
    )
)

innings = (
    df.groupby(
        ["match_id", "innings_no", "bowler"],
        as_index=False,
        dropna=False
    )
    .agg(
        Wickets=("bowler_wicket", "sum"),
        Runs_Conceded=("bowler_runs", "sum"),
    )
)

dup = innings.duplicated(
    ["match_id", "innings_no", "bowler"]
).sum()

print(f"Bowling innings rows: {len(innings):,}")
print(f"Duplicate match+innings+bowler rows: {dup:,}")

if dup:
    raise RuntimeError("Duplicate bowling innings rows found.")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
innings.to_csv(OUTPUT, index=False)

print("\nDONE")
print(f"Output: {OUTPUT}")

print("\nTop 20 bowling innings:")
print(
    innings.sort_values(
        ["Wickets", "Runs_Conceded"],
        ascending=[False, True]
    )
    .head(20)
    .to_string(index=False)
)
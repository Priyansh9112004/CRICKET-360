import pandas as pd
from pathlib import Path

INPUT = Path(r"DATA\processed\ball_by_ball.csv")
OUTPUT = Path(r"DATA\processed\bowler_dot_balls.csv")

print("Reading ball-by-ball data...")

df = pd.read_csv(
    INPUT,
    usecols=[
        "match_id",
        "bowler",
        "runs_batter",
        "runs_extras"
    ],
    low_memory=False
)

print(f"Ball rows: {len(df):,}")

# Dot ball = delivery on which total runs scored = 0
df["Dot_Ball"] = (
    (df["runs_batter"].fillna(0) == 0)
    & (df["runs_extras"].fillna(0) == 0)
).astype("int8")

summary = (
    df.groupby(
        ["match_id", "bowler"],
        as_index=False,
        dropna=False
    )
    .agg(
        Dot_Balls=("Dot_Ball", "sum")
    )
)

duplicates = summary.duplicated(
    ["match_id", "bowler"]
).sum()

print(f"Summary rows: {len(summary):,}")
print(f"Duplicate match+bowler rows: {duplicates:,}")

if duplicates:
    raise RuntimeError("Duplicate match+bowler rows found.")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
summary.to_csv(OUTPUT, index=False)

print("\nDONE")
print(f"Output: {OUTPUT}")

print("\nTop 20 bowler-match dot-ball counts:")
print(
    summary.sort_values(
        "Dot_Balls",
        ascending=False
    )
    .head(20)
    .to_string(index=False)
)
import pandas as pd
from pathlib import Path

INPUT = Path(r"DATA\processed\ball_by_ball.csv")
OUTPUT = Path(r"DATA\processed\player_ducks.csv")

print("Reading ball-by-ball data...")

df = pd.read_csv(
    INPUT,
    usecols=[
        "match_id",
        "innings_no",
        "batter",
        "runs_batter",
        "player_out",
        "wicket_type"
    ],
    low_memory=False
)

print(f"Ball rows: {len(df):,}")

# Runs scored by each batter in each innings
innings = (
    df.groupby(
        ["match_id", "innings_no", "batter"],
        as_index=False
    )
    .agg(Runs=("runs_batter", "sum"))
)

# Dismissal records
dismissals = df[
    df["player_out"].notna()
    & df["wicket_type"].notna()
].copy()

# These do NOT count as a duck dismissal
non_dismissal_types = {
    "retired hurt",
    "retired not out",
    "obstructing the field"
}

dismissals["wicket_type_clean"] = (
    dismissals["wicket_type"]
    .astype(str)
    .str.strip()
    .str.lower()
)

dismissals = dismissals[
    ~dismissals["wicket_type_clean"].isin(non_dismissal_types)
]

dismissed = (
    dismissals[
        ["match_id", "innings_no", "player_out"]
    ]
    .drop_duplicates()
    .rename(columns={"player_out": "batter"})
)

innings = innings.merge(
    dismissed.assign(Dismissed=1),
    on=["match_id", "innings_no", "batter"],
    how="left"
)

innings["Dismissed"] = innings["Dismissed"].fillna(0)

# Duck = dismissed for exactly zero
ducks = innings[
    (innings["Runs"] == 0)
    & (innings["Dismissed"] == 1)
].copy()

ducks["Duck"] = 1

output = ducks[
    ["match_id", "innings_no", "batter", "Duck"]
].copy()

duplicates = output.duplicated(
    ["match_id", "innings_no", "batter"]
).sum()

print(f"Duck innings: {len(output):,}")
print(f"Duplicate rows: {duplicates:,}")

if duplicates:
    raise RuntimeError("Duplicate duck innings found.")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
output.to_csv(OUTPUT, index=False)

print("\nDONE")
print(f"Output: {OUTPUT}")

print("\nTop 20 duck counts:")
print(
    output.groupby("batter")["Duck"]
    .sum()
    .sort_values(ascending=False)
    .head(20)
    .to_string()
)
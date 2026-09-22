import pandas as pd
from pathlib import Path

INPUT = Path(r"DATA\processed\ball_by_ball.csv")
OUTPUT = Path(r"DATA\processed\bowler_maidens.csv")

print("Reading ball-by-ball data...")

df = pd.read_csv(
    INPUT,
    usecols=[
        "match_id",
        "innings_no",
        "over",
        "bowler",
        "runs_batter",
        "runs_extras",
        "extras_type"
    ],
    low_memory=False
)

print(f"Ball rows: {len(df):,}")

# Clean extras
extra = (
    df["extras_type"]
    .fillna("")
    .astype(str)
    .str.lower()
)

# Wides and no-balls are NOT legal deliveries
df["Legal_Ball"] = (
    ~extra.str.contains("wides", regex=False)
    & ~extra.str.contains("noballs", regex=False)
).astype("int8")

# Runs charged to bowler:
# Batter runs always count.
# Byes and leg-byes do NOT count against bowler.
#
# For wides/no-balls, runs_extras are charged to bowler.
is_bye_or_legbye = (
    extra.str.contains("byes", regex=False)
    | extra.str.contains("legbyes", regex=False)
)

# But strings such as "byes,noballs" contain byes AND no-ball.
# No-ball component is bowler-conceded, so don't classify those
# as pure bye/leg-bye deliveries.
has_no_ball = extra.str.contains("noballs", regex=False)

pure_bye_or_legbye = is_bye_or_legbye & ~has_no_ball

df["Bowler_Runs"] = df["runs_batter"].fillna(0)

df.loc[~pure_bye_or_legbye, "Bowler_Runs"] += (
    df.loc[~pure_bye_or_legbye, "runs_extras"].fillna(0)
)

# Build each bowler-over
overs = (
    df.groupby(
        ["match_id", "innings_no", "over", "bowler"],
        as_index=False,
        dropna=False
    )
    .agg(
        Legal_Balls=("Legal_Ball", "sum"),
        Bowler_Runs=("Bowler_Runs", "sum")
    )
)

# Maiden = complete over (6 legal balls) and zero bowler runs.
# >=6 handles datasets where an over has extra legal deliveries
# because of source quirks, while wides/no-balls themselves are excluded.
overs["Maiden"] = (
    (overs["Legal_Balls"] >= 6)
    & (overs["Bowler_Runs"] == 0)
).astype("int8")

maidens = (
    overs.groupby(
        ["match_id", "bowler"],
        as_index=False,
        dropna=False
    )
    .agg(Maidens=("Maiden", "sum"))
)

duplicates = maidens.duplicated(
    ["match_id", "bowler"]
).sum()

print(f"Bowler-match rows: {len(maidens):,}")
print(f"Duplicate match+bowler rows: {duplicates:,}")
print(f"Total maiden overs: {maidens['Maidens'].sum():,}")

if duplicates:
    raise RuntimeError("Duplicate match+bowler rows found.")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
maidens.to_csv(OUTPUT, index=False)

print("\nDONE")
print(f"Output: {OUTPUT}")

print("\nTop 20 career maiden counts:")
print(
    maidens.groupby("bowler")["Maidens"]
    .sum()
    .sort_values(ascending=False)
    .head(20)
    .to_string()
)
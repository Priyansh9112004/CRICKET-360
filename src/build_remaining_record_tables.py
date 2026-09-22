import pandas as pd
from pathlib import Path

INPUT = Path(r"DATA\processed\ball_by_ball.csv")
OUT = Path(r"DATA\processed")

print("Reading ball_by_ball.csv...")
df = pd.read_csv(INPUT, low_memory=False)
print(f"Ball rows: {len(df):,}")

# ---------------------------------------------------------
# BASIC CLEANING
# ---------------------------------------------------------

for col in ["runs_batter", "runs_extras", "runs_total"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

extra = (
    df["extras_type"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.lower()
)

has_wide = extra.str.contains("wides", regex=False)
has_noball = extra.str.contains("noballs", regex=False)

df["Legal_Ball"] = (~has_wide & ~has_noball).astype("int8")

# =========================================================
# 1. MAIDEN OVERS
# =========================================================

print("\n[1/5] Building maiden overs...")

is_bye = extra.str.contains("byes", regex=False)
is_legbye = extra.str.contains("legbyes", regex=False)

pure_bye_legbye = (is_bye | is_legbye) & ~has_noball

df["Bowler_Runs"] = df["runs_batter"]

df.loc[~pure_bye_legbye, "Bowler_Runs"] += (
    df.loc[~pure_bye_legbye, "runs_extras"]
)

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

overs["Maiden"] = (
    (overs["Legal_Balls"] >= 6)
    & (overs["Bowler_Runs"] == 0)
).astype("int8")

maidens = (
    overs.groupby(
        ["match_id", "bowler"],
        as_index=False
    )
    .agg(Maidens=("Maiden", "sum"))
)

maidens.to_csv(
    OUT / "bowler_maidens.csv",
    index=False
)

print(
    f"bowler_maidens.csv -> "
    f"{len(maidens):,} rows"
)

# =========================================================
# 2. NOT OUTS
# =========================================================

print("\n[2/5] Building not outs...")

batting = (
    df.groupby(
        ["match_id", "innings_no", "batter"],
        as_index=False
    )
    .agg(Runs=("runs_batter", "sum"))
)

dismissal_types = (
    df["wicket_type"]
    .fillna("")
    .astype(str)
    .str.strip()
    .str.lower()
)

# Dismissals which count as batter being out
not_out_types = {
    "",
    "retired hurt",
    "retired not out"
}

dismissed_rows = df[
    df["player_out"].notna()
    & ~dismissal_types.isin(not_out_types)
][
    ["match_id", "innings_no", "player_out"]
].drop_duplicates()

dismissed_rows = dismissed_rows.rename(
    columns={"player_out": "batter"}
)

batting = batting.merge(
    dismissed_rows.assign(Dismissed=1),
    on=["match_id", "innings_no", "batter"],
    how="left"
)

batting["Dismissed"] = (
    batting["Dismissed"]
    .fillna(0)
    .astype("int8")
)

not_outs = batting[
    batting["Dismissed"] == 0
][
    ["match_id", "innings_no", "batter"]
].copy()

not_outs["Not_Out"] = 1

not_outs.to_csv(
    OUT / "player_not_outs.csv",
    index=False
)

print(
    f"player_not_outs.csv -> "
    f"{len(not_outs):,} rows"
)

# =========================================================
# 3. FASTEST 50 / FASTEST 100
# =========================================================

print("\n[3/5] Building milestone-ball records...")

# Wides do not count as balls faced.
# No-ball deliveries can still count as a ball faced for a batter
# when the batter faces/scoring event is present, but cricket
# scorecard ball-faced treatment has edge cases.
#
# We calculate milestone arrival from chronological deliveries
# and use non-wide deliveries as batter balls.

work = df[
    [
        "match_id",
        "innings_no",
        "over",
        "ball",
        "batter",
        "runs_batter",
        "extras_type"
    ]
].copy()

work_extra = (
    work["extras_type"]
    .fillna("")
    .astype(str)
    .str.lower()
)

work["Counts_Ball"] = (
    ~work_extra.str.contains("wides", regex=False)
).astype("int8")

work = work.sort_values(
    ["match_id", "innings_no", "over", "ball"]
)

work["Cum_Runs"] = (
    work.groupby(
        ["match_id", "innings_no", "batter"]
    )["runs_batter"]
    .cumsum()
)

work["Cum_Balls"] = (
    work.groupby(
        ["match_id", "innings_no", "batter"]
    )["Counts_Ball"]
    .cumsum()
)

fifties = (
    work[work["Cum_Runs"] >= 50]
    .groupby(
        ["match_id", "innings_no", "batter"],
        as_index=False
    )
    .first()
)

fifties = fifties[
    [
        "match_id",
        "innings_no",
        "batter",
        "Cum_Balls"
    ]
].rename(
    columns={"Cum_Balls": "Balls_To_50"}
)

fifties.to_csv(
    OUT / "fastest_50.csv",
    index=False
)

hundreds = (
    work[work["Cum_Runs"] >= 100]
    .groupby(
        ["match_id", "innings_no", "batter"],
        as_index=False
    )
    .first()
)

hundreds = hundreds[
    [
        "match_id",
        "innings_no",
        "batter",
        "Cum_Balls"
    ]
].rename(
    columns={"Cum_Balls": "Balls_To_100"}
)

hundreds.to_csv(
    OUT / "fastest_100.csv",
    index=False
)

print(
    f"fastest_50.csv -> {len(fifties):,} rows"
)
print(
    f"fastest_100.csv -> {len(hundreds):,} rows"
)

# =========================================================
# 4. MOST RUNS SCORED IN AN OVER
# =========================================================

print("\n[4/5] Building batter runs in an over...")

batter_over = (
    df.groupby(
        [
            "match_id",
            "innings_no",
            "over",
            "batter"
        ],
        as_index=False
    )
    .agg(
        Runs_In_Over=("runs_batter", "sum")
    )
)

batter_over.to_csv(
    OUT / "batter_runs_by_over.csv",
    index=False
)

print(
    f"batter_runs_by_over.csv -> "
    f"{len(batter_over):,} rows"
)

# =========================================================
# 5. MOST EXPENSIVE OVER
# =========================================================

print("\n[5/5] Building bowler runs by over...")

bowler_over = (
    df.assign(Bowler_Runs_Over=df["Bowler_Runs"])
    .groupby(
        [
            "match_id",
            "innings_no",
            "over",
            "bowler"
        ],
        as_index=False
    )
    .agg(
        Runs_Conceded=("Bowler_Runs_Over", "sum")
    )
)

bowler_over.to_csv(
    OUT / "bowler_runs_by_over.csv",
    index=False
)

print(
    f"bowler_runs_by_over.csv -> "
    f"{len(bowler_over):,} rows"
)

# =========================================================
# VALIDATION
# =========================================================

print("\n==============================")
print("VALIDATION")
print("==============================")

print(
    "Maiden duplicate match+bowler:",
    maidens.duplicated(
        ["match_id", "bowler"]
    ).sum()
)

print(
    "Not-out duplicate innings:",
    not_outs.duplicated(
        ["match_id", "innings_no", "batter"]
    ).sum()
)

print(
    "Fastest 50 duplicate innings:",
    fifties.duplicated(
        ["match_id", "innings_no", "batter"]
    ).sum()
)

print(
    "Fastest 100 duplicate innings:",
    hundreds.duplicated(
        ["match_id", "innings_no", "batter"]
    ).sum()
)

print("\nTop 10 maiden bowlers:")
print(
    maidens.groupby("bowler")["Maidens"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .to_string()
)

print("\nTop 10 not-outs:")
print(
    not_outs.groupby("batter")["Not_Out"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .to_string()
)

print("\nFastest 10 fifties:")
print(
    fifties.sort_values("Balls_To_50")
    .head(10)
    .to_string(index=False)
)

print("\nFastest 10 hundreds:")
print(
    hundreds.sort_values("Balls_To_100")
    .head(10)
    .to_string(index=False)
)

print("\nHighest batter runs in one over:")
print(
    batter_over.sort_values(
        "Runs_In_Over",
        ascending=False
    )
    .head(10)
    .to_string(index=False)
)

print("\nMost expensive overs:")
print(
    bowler_over.sort_values(
        "Runs_Conceded",
        ascending=False
    )
    .head(10)
    .to_string(index=False)
)

print("\n==============================")
print("ALL RECORD TABLES BUILT")
print("==============================")

for name in [
    "bowler_maidens.csv",
    "player_not_outs.csv",
    "fastest_50.csv",
    "fastest_100.csv",
    "batter_runs_by_over.csv",
    "bowler_runs_by_over.csv",
]:
    print(OUT / name)
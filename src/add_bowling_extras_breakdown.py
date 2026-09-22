import pandas as pd

BALL = r"DATA\processed\ball_by_ball.csv"
BOWL = r"DATA\processed\player_match_bowling.csv"
MAP = r"DATA\processed\match_player_uuid_resolved.csv"
CANON = r"DATA\processed\duplicate_uuid_canonical_proposal.csv"

print("Loading...")

balls = pd.read_csv(
    BALL,
    dtype=str,
    usecols=["match_id", "bowler", "runs_extras", "extras_type"]
).fillna("")

bowling = pd.read_csv(BOWL, dtype=str).fillna("")
mapping = pd.read_csv(MAP, dtype=str).fillna("")
canonical = pd.read_csv(CANON, dtype=str).fillna("")

# ------------------------------------------------------------
# IDENTITY RESOLUTION
# ------------------------------------------------------------

uuid_to_id = dict(
    zip(canonical["uuid"], canonical["player_id"])
)

R = mapping[mapping["final_player_id"].ne("")].copy()

R["fact_name"] = (
    R["short_name"]
    .str.replace(r"\s+\(\d+\)$", "", regex=True)
    .str.strip()
)

R = R[
    [
        "match_id",
        "fact_name",
        "cricsheet_uuid",
        "final_player_id"
    ]
].drop_duplicates()

R["canonical_player_id"] = (
    R["cricsheet_uuid"].map(uuid_to_id)
)

R["resolved_player_id"] = (
    R["canonical_player_id"]
    .fillna(R["final_player_id"])
)

counts = (
    R.groupby(
        ["match_id", "fact_name"]
    )["resolved_player_id"]
    .nunique()
)

safe_keys = counts[counts.eq(1)].index

R = R.set_index(["match_id", "fact_name"])
R = R[R.index.isin(safe_keys)].reset_index()

safe_map = (
    R.set_index(
        ["match_id", "fact_name"]
    )["resolved_player_id"]
)

safe_map = safe_map[
    ~safe_map.index.duplicated(keep="first")
]

keys = pd.MultiIndex.from_arrays(
    [balls["match_id"], balls["bowler"]]
)

balls["player_id"] = safe_map.reindex(keys).to_numpy()

balls = balls[
    balls["player_id"].notna()
].copy()

# ------------------------------------------------------------
# EXTRAS
# ------------------------------------------------------------

balls["runs_extras_n"] = pd.to_numeric(
    balls["runs_extras"],
    errors="coerce"
).fillna(0)

etype = balls["extras_type"].str.lower()

for c in [
    "wides_conceded",
    "noballs_conceded",
    "byes",
    "legbyes",
    "penalty"
]:
    balls[c] = 0

# WIDES
wide = etype.str.contains("wides", regex=False)

balls.loc[
    wide,
    "wides_conceded"
] = balls.loc[
    wide,
    "runs_extras_n"
]

# NO-BALL
noball = etype.str.contains("noballs", regex=False)

balls.loc[
    noball,
    "noballs_conceded"
] = 1

# BYES
bye = (
    etype.str.contains("byes", regex=False)
    & ~etype.str.contains("legbyes", regex=False)
)

# If no-ball + byes occurs, remove the 1 no-ball penalty
balls.loc[
    bye,
    "byes"
] = (
    balls.loc[bye, "runs_extras_n"]
    - balls.loc[bye, "noballs_conceded"]
).clip(lower=0)

# LEG BYES
legbye = etype.str.contains("legbyes", regex=False)

balls.loc[
    legbye,
    "legbyes"
] = (
    balls.loc[legbye, "runs_extras_n"]
    - balls.loc[legbye, "noballs_conceded"]
).clip(lower=0)

# PENALTY
penalty = etype.str.contains("penalty", regex=False)

# Penalty is kept as the residual extra amount on penalty-tagged rows.
balls.loc[
    penalty,
    "penalty"
] = balls.loc[
    penalty,
    "runs_extras_n"
]

# ------------------------------------------------------------
# AGGREGATE BY PLAYER + MATCH
# ------------------------------------------------------------

x = (
    balls.groupby(
        ["player_id", "match_id"],
        as_index=False
    )
    .agg(
        wides_conceded=("wides_conceded", "sum"),
        noballs_conceded=("noballs_conceded", "sum"),
        byes=("byes", "sum"),
        legbyes=("legbyes", "sum"),
        penalty=("penalty", "sum")
    )
)

for df in [bowling, x]:
    df["player_id"] = df["player_id"].astype(str)
    df["match_id"] = df["match_id"].astype(str)

# Remove old breakdown columns before merge
old_cols = [
    "wides_conceded",
    "noballs_conceded",
    "byes",
    "legbyes",
    "penalty"
]

bowling = bowling.drop(
    columns=[
        c for c in old_cols
        if c in bowling.columns
    ]
)

bowling = bowling.merge(
    x,
    on=["player_id", "match_id"],
    how="left",
    validate="one_to_one"
)

for c in old_cols:
    bowling[c] = pd.to_numeric(
        bowling[c],
        errors="coerce"
    ).fillna(0).astype(int)

bowling["all_extras"] = (
    bowling["wides_conceded"]
    + bowling["noballs_conceded"]
    + bowling["byes"]
    + bowling["legbyes"]
    + bowling["penalty"]
)

bowling.to_csv(
    BOWL,
    index=False,
    encoding="utf-8-sig"
)

print("\n=== ALL EXTRAS BREAKDOWN ===")
print("Rows:", len(bowling))
print(
    "Duplicates:",
    bowling.duplicated(
        ["player_id", "match_id"]
    ).sum()
)

print("Wides:", bowling["wides_conceded"].sum())
print("No-balls:", bowling["noballs_conceded"].sum())
print("Byes:", bowling["byes"].sum())
print("Leg-byes:", bowling["legbyes"].sum())
print("Penalty:", bowling["penalty"].sum())
print("ALL EXTRAS:", bowling["all_extras"].sum())

print("\nDONE")
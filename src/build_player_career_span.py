import pandas as pd

DIM = r"DATA\processed\dim_player.csv"
MATCHES = r"DATA\processed\matches.csv"
BATTING = r"DATA\processed\player_match_batting.csv"
BOWLING = r"DATA\processed\player_match_bowling.csv"
OUT = r"DATA\processed\player_career_span_preview.csv"

dim = pd.read_csv(DIM)
matches = pd.read_csv(MATCHES, dtype={"match_id": str})
bat = pd.read_csv(BATTING, dtype={"match_id": str})
bowl = pd.read_csv(BOWLING, dtype={"match_id": str})

matches["match_date"] = pd.to_datetime(matches["match_date"], errors="coerce")

# Source player name -> stable player_id
name_map = dim[["player_id", "short_name"]].drop_duplicates()

bat = bat[["match_id", "batter"]].drop_duplicates()
bat = bat.merge(
    name_map,
    left_on="batter",
    right_on="short_name",
    how="left"
)
bat = bat[["player_id", "match_id"]]

# Bowling participation
bowl = bowl[["match_id", "player"]].drop_duplicates()
bowl = bowl.merge(
    name_map,
    left_on="player",
    right_on="short_name",
    how="left"
)
bowl = bowl[["player_id", "match_id"]]

# Combine batting + bowling match participation
participation = pd.concat([bat, bowl], ignore_index=True)
participation = participation.dropna(subset=["player_id"])
participation = participation.drop_duplicates(["player_id", "match_id"])

participation = participation.merge(
    matches[["match_id", "match_date"]],
    on="match_id",
    how="left"
)

career = (
    participation.groupby("player_id", as_index=False)
    .agg(
        career_start=("match_date", "min"),
        career_end=("match_date", "max"),
        dataset_matches=("match_id", "nunique")
    )
)

career["career_start"] = career["career_start"].dt.strftime("%Y-%m-%d")
career["career_end"] = career["career_end"].dt.strftime("%Y-%m-%d")

out = dim[["player_id", "display_name", "short_name"]].merge(
    career,
    on="player_id",
    how="left"
)

print("========== PLAYER CAREER SPAN ==========")
print("Players:", len(out))
print("Unique player_id:", out["player_id"].nunique())
print("Career start filled:", out["career_start"].notna().sum())
print("Career end filled:", out["career_end"].notna().sum())
print("Missing career span:", out["career_start"].isna().sum())
print("Participation rows:", len(participation))
print("Missing match dates:", participation["match_date"].isna().sum())
print("Earliest:", out["career_start"].dropna().min())
print("Latest:", out["career_end"].dropna().max())
out.to_csv(OUT, index=False)
print("Saved:", OUT)
print("========================================")
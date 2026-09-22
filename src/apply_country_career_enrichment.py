import pandas as pd

DIM = r"DATA\processed\dim_player.csv"
PREVIEW = r"DATA\processed\player_master_enrichment_preview.csv"

dim = pd.read_csv(DIM)
enrich = pd.read_csv(PREVIEW)

# Safety checks
assert len(dim) == 13209
assert dim["player_id"].nunique() == 13209
assert enrich["player_id"].nunique() == 13209

# Keep original structure
original_columns = dim.columns.tolist()

# Map enrichment by stable player_id
e = enrich[
    ["player_id", "country_final", "career_start", "career_end"]
].copy()

out = dim.drop(
    columns=["country", "career_start", "career_end"],
    errors="ignore"
)

out = out.merge(e, on="player_id", how="left")

out = out.rename(
    columns={
        "country_final": "country"
    }
)

# Restore original column order
out = out[original_columns]

# Final safety checks
assert len(out) == len(dim)
assert out["player_id"].nunique() == dim["player_id"].nunique()
assert out["player_id"].duplicated().sum() == 0

print("========== PRODUCTION ENRICHMENT ==========")
print("Players:", len(out))
print("Unique player_id:", out["player_id"].nunique())
print("Country filled:", out["country"].notna().sum())
print("Country missing:", out["country"].isna().sum())
print("Career start filled:", out["career_start"].notna().sum())
print("Career end filled:", out["career_end"].notna().sum())
print("Career missing:", out["career_start"].isna().sum())
print("Duplicate player_id:", out["player_id"].duplicated().sum())

out.to_csv(DIM, index=False)

print("Saved:", DIM)
print("==========================================")
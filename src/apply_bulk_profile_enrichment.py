import pandas as pd

DIM = r"DATA\processed\dim_player.csv"
PREVIEW = r"DATA\processed\player_bulk_metadata_preview.csv"
AUDIT = r"DATA\processed\player_profile_enrichment_audit.csv"

# Read as strings so text columns stay safe
d = pd.read_csv(DIM, dtype=str)
p = pd.read_csv(PREVIEW, dtype=str)

# Basic safety checks
assert len(d) == 13209
assert d["player_id"].nunique() == 13209
assert d["player_id"].duplicated().sum() == 0

assert len(p) == 13209
assert p["player_id"].nunique() == 13209
assert p["player_id"].duplicated().sum() == 0

# Keep only required preview columns
p = p[
    [
        "player_id",
        "full_name_new",
        "batting_style_new",
        "bowling_style_new",
        "role_new",
        "metadata_source",
    ]
].copy()

x = d.merge(p, on="player_id", how="left", validate="one_to_one")

# Treat blanks / textual nan as missing
def clean_missing(series):
    s = series.astype("string").str.strip()
    s = s.mask(s.isin(["", "nan", "NaN", "None", "<NA>"]))
    return s

targets = {
    "full_name": "full_name_new",
    "role": "role_new",
    "batting_style": "batting_style_new",
    "bowling_style": "bowling_style_new",
}

added = {}

for target, source in targets.items():
    old = clean_missing(x[target])
    new = clean_missing(x[source])

    fill_mask = old.isna() & new.notna()

    x[target] = old
    x.loc[fill_mask, target] = new.loc[fill_mask]

    added[target] = int(fill_mask.sum())

# Audit before dropping helper columns
audit = x[
    [
        "player_id",
        "display_name",
        "short_name",
        "key_cricinfo",
        "full_name_new",
        "role_new",
        "batting_style_new",
        "bowling_style_new",
        "metadata_source",
    ]
].copy()

audit["match_method"] = audit["metadata_source"].apply(
    lambda v: "Exact Cricinfo ID" if pd.notna(v) else pd.NA
)

audit.to_csv(AUDIT, index=False)

# Restore original production column structure only
original_columns = list(d.columns)
out = x[original_columns].copy()

# Final safety checks
assert len(out) == len(d)
assert out["player_id"].nunique() == len(d)
assert out["player_id"].duplicated().sum() == 0

# Critical fields must remain unchanged
for col in [
    "player_id",
    "display_name",
    "short_name",
    "country",
    "date_of_birth",
    "career_start",
    "career_end",
    "key_cricinfo",
]:
    before = d[col].fillna("").astype(str)
    after = out[col].fillna("").astype(str)
    assert before.equals(after), f"Unexpected change detected in {col}"

out.to_csv(DIM, index=False)

print("========== BULK PROFILE ENRICHMENT ==========")
print("Players:", len(out))
print("Unique player_id:", out["player_id"].nunique())
print("Full names added:", added["full_name"])
print("Roles added:", added["role"])
print("Batting styles added:", added["batting_style"])
print("Bowling styles added:", added["bowling_style"])

print("\nFINAL COVERAGE")
print("Full name:", clean_missing(out["full_name"]).notna().sum())
print("Role:", clean_missing(out["role"]).notna().sum())
print("Batting style:", clean_missing(out["batting_style"]).notna().sum())
print("Bowling style:", clean_missing(out["bowling_style"]).notna().sum())

print("\nUNCHANGED")
print("Country:", clean_missing(out["country"]).notna().sum())
print("DOB:", clean_missing(out["date_of_birth"]).notna().sum())
print("Career start:", clean_missing(out["career_start"]).notna().sum())
print("Career end:", clean_missing(out["career_end"]).notna().sum())

print("\nDuplicate player_id:", out["player_id"].duplicated().sum())
print("Saved:", DIM)
print("Audit:", AUDIT)
print("=============================================")
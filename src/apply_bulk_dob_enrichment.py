import pandas as pd

DIM = r"DATA\processed\dim_player.csv"
PREVIEW = r"DATA\processed\player_bulk_metadata_preview.csv"
AUDIT = r"DATA\processed\player_dob_enrichment_audit.csv"

d = pd.read_csv(DIM, dtype=str)
p = pd.read_csv(PREVIEW, dtype=str)

# ---------- SAFETY ----------
assert len(d) == 13209
assert d["player_id"].nunique() == 13209
assert d["player_id"].duplicated().sum() == 0

assert len(p) == 13209
assert p["player_id"].nunique() == 13209
assert p["player_id"].duplicated().sum() == 0

before = d.copy()

p = p[
    [
        "player_id",
        "date_of_birth_new",
        "metadata_source"
    ]
].copy()

x = d.merge(
    p,
    on="player_id",
    how="left",
    validate="one_to_one"
)

# Parse DOBs
old_dob = pd.to_datetime(
    x["date_of_birth"],
    errors="coerce"
)

new_dob = pd.to_datetime(
    x["date_of_birth_new"],
    errors="coerce"
)

# Only fill currently missing DOB
fill_mask = (
    old_dob.isna()
    & new_dob.notna()
    & x["metadata_source"].notna()
)

# Existing/new conflicts - audit only
conflict_mask = (
    old_dob.notna()
    & new_dob.notna()
    & (old_dob != new_dob)
)

# Exact agreement
agreement_mask = (
    old_dob.notna()
    & new_dob.notna()
    & (old_dob == new_dob)
)

# Apply ONLY missing DOB fills
x["date_of_birth"] = x["date_of_birth"].astype("string")

x.loc[
    fill_mask,
    "date_of_birth"
] = new_dob.loc[fill_mask].dt.strftime("%Y-%m-%d")

# ---------- AUDIT ----------
audit = x[
    [
        "player_id",
        "display_name",
        "short_name",
        "key_cricinfo",
        "career_start",
        "date_of_birth",
        "date_of_birth_new",
        "metadata_source"
    ]
].copy()

audit["dob_status"] = "No new DOB"

audit.loc[
    agreement_mask,
    "dob_status"
] = "Exact agreement"

audit.loc[
    conflict_mask,
    "dob_status"
] = "Conflict - existing preserved"

audit.loc[
    fill_mask,
    "dob_status"
] = "Filled from exact Cricinfo-ID metadata"

audit.to_csv(AUDIT, index=False)

# Restore production structure
original_columns = list(before.columns)
out = x[original_columns].copy()

# ---------- FINAL VALIDATION ----------
assert len(out) == 13209
assert out["player_id"].nunique() == 13209
assert out["player_id"].duplicated().sum() == 0

# Existing DOB values MUST remain unchanged
before_dob = pd.to_datetime(
    before["date_of_birth"],
    errors="coerce"
)

after_dob = pd.to_datetime(
    out["date_of_birth"],
    errors="coerce"
)

existing_mask = before_dob.notna()

assert (
    before_dob.loc[existing_mask].reset_index(drop=True)
    ==
    after_dob.loc[existing_mask].reset_index(drop=True)
).all(), "Existing DOB changed unexpectedly"

# No unrelated production field may change
for col in original_columns:
    if col == "date_of_birth":
        continue

    a = before[col].fillna("").astype(str)
    b = out[col].fillna("").astype(str)

    assert a.equals(b), f"Unexpected change detected in {col}"

final_dob = pd.to_datetime(
    out["date_of_birth"],
    errors="coerce"
)

assert int(fill_mask.sum()) == 4442, (
    f"Expected 4442 DOB additions, got {int(fill_mask.sum())}"
)

out.to_csv(DIM, index=False)

print("========== DOB ENRICHMENT ==========")
print("Players:", len(out))
print("DOB before:", before_dob.notna().sum())
print("New DOB added:", fill_mask.sum())
print("Exact agreements:", agreement_mask.sum())
print("Conflicts preserved:", conflict_mask.sum())
print("DOB after:", final_dob.notna().sum())
print("DOB still missing:", final_dob.isna().sum())
print("Duplicate player_id:", out["player_id"].duplicated().sum())

print("\nExisting DOB overwritten: 0")
print("Saved:", DIM)
print("Audit:", AUDIT)
print("====================================")
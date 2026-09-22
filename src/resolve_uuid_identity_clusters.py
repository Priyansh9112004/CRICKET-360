import pandas as pd
from pathlib import Path

BASE = Path("DATA")

DIM = BASE / "processed" / "dim_player.csv"
UUID_MAP = BASE / "processed" / "match_player_uuid_map.csv"
REGISTRY = BASE / "processed" / "cricsheet_people.csv"

OUT_SAFE = BASE / "processed" / "uuid_identity_safe_candidates.csv"
OUT_REVIEW = BASE / "processed" / "uuid_identity_review.csv"


def clean_series(s):
    return s.fillna("").astype(str).str.strip()


print("Loading files...")

d = pd.read_csv(DIM, dtype=str)
u = pd.read_csv(UUID_MAP, dtype=str)
r = pd.read_csv(REGISTRY, dtype=str)

print("dim_player rows:", len(d))
print("UUID map rows:", len(u))
print("Registry rows:", len(r))


# ---------------------------------------------------------
# 1. Normalize key columns
# ---------------------------------------------------------

for df, cols in [
    (d, ["player_id", "short_name"]),
    (u, ["match_id", "short_name", "cricsheet_uuid"]),
    (r, ["identifier", "name", "unique_name"])
]:
    for c in cols:
        if c in df.columns:
            df[c] = clean_series(df[c])


# ---------------------------------------------------------
# 2. Attach current production player_id to UUID map
# ---------------------------------------------------------
#
# UUID map contains:
# match_id | short_name | cricsheet_uuid
#
# player_id must therefore come from dim_player via short_name.
#
# We first check whether short_name is unique in dim_player.
# ---------------------------------------------------------

name_counts = d.groupby("short_name")["player_id"].nunique()

ambiguous_names = set(
    name_counts[name_counts > 1].index
)

print("Ambiguous short_names in dim_player:", len(ambiguous_names))


# Safe short_name -> player_id mapping only
safe_name_map = (
    d[
        d["short_name"].notna()
        & ~d["short_name"].isin(ambiguous_names)
    ][["short_name", "player_id"]]
    .drop_duplicates()
)


u = u.merge(
    safe_name_map,
    on="short_name",
    how="inner"
)

print("UUID rows linked to unique production player:", len(u))
print("Production player IDs represented:", u["player_id"].nunique())


# ---------------------------------------------------------
# 3. Registry information
# ---------------------------------------------------------

reg_cols = [
    "identifier",
    "name",
    "unique_name",
]

if "key_cricinfo" in r.columns:
    reg_cols.append("key_cricinfo")

r2 = r[reg_cols].copy()

r2 = r2.drop_duplicates("identifier")


# ---------------------------------------------------------
# 4. Merge UUID -> registry identity
# ---------------------------------------------------------

z = u.merge(
    r2,
    left_on="cricsheet_uuid",
    right_on="identifier",
    how="left"
)


# ---------------------------------------------------------
# 5. Production information
# ---------------------------------------------------------

prod_cols = [
    "player_id",
    "short_name",
    "display_name",
    "full_name",
    "key_cricinfo",
    "country",
]

prod_cols = [c for c in prod_cols if c in d.columns]

prod = d[prod_cols].copy()

prod = prod.drop_duplicates("player_id")

z = z.merge(
    prod,
    on=["player_id", "short_name"],
    how="left",
    suffixes=("_registry", "_production")
)


# ---------------------------------------------------------
# 6. Cricinfo ID normalization
# ---------------------------------------------------------

if "key_cricinfo_registry" in z.columns:
    registry_cricinfo = clean_series(
        z["key_cricinfo_registry"]
    ).str.replace(r"\.0$", "", regex=True)
else:
    registry_cricinfo = pd.Series("", index=z.index)

if "key_cricinfo_production" in z.columns:
    production_cricinfo = clean_series(
        z["key_cricinfo_production"]
    ).str.replace(r"\.0$", "", regex=True)
else:
    production_cricinfo = pd.Series("", index=z.index)


z["cricinfo_match"] = (
    registry_cricinfo.ne("")
    & production_cricinfo.ne("")
    & registry_cricinfo.eq(production_cricinfo)
)


# ---------------------------------------------------------
# 7. Name normalization
# ---------------------------------------------------------

z["short_name_clean"] = (
    clean_series(z["short_name"])
    .str.lower()
    .str.replace(r"[^a-z0-9]", "", regex=True)
)

z["registry_name_clean"] = (
    clean_series(z["name"])
    .str.lower()
    .str.replace(r"[^a-z0-9]", "", regex=True)
)

z["unique_name_clean"] = (
    clean_series(z["unique_name"])
    .str.lower()
    .str.replace(r"[^a-z0-9]", "", regex=True)
)


z["name_match"] = (
    z["short_name_clean"].ne("")
    & (
        z["short_name_clean"].eq(z["registry_name_clean"])
        | z["short_name_clean"].eq(z["unique_name_clean"])
    )
)


# ---------------------------------------------------------
# 8. Evidence score
# ---------------------------------------------------------

z["score"] = 0

z.loc[z["name_match"], "score"] += 1
z.loc[z["cricinfo_match"], "score"] += 5


# ---------------------------------------------------------
# 9. UUID-level summary
# ---------------------------------------------------------

uuid_summary = (
    z.groupby(
        ["player_id", "short_name", "cricsheet_uuid"],
        dropna=False
    )
    .agg(
        display_name=("display_name", "first"),
        production_full_name=("full_name", "first"),
        registry_name=("name", "first"),
        registry_unique_name=("unique_name", "first"),
        production_cricinfo=("key_cricinfo_production", "first"),
        registry_cricinfo=("key_cricinfo_registry", "first"),
        cricinfo_match=("cricinfo_match", "max"),
        name_match=("name_match", "max"),
        score=("score", "max"),
        match_count=("match_id", "nunique"),
    )
    .reset_index()
)


# ---------------------------------------------------------
# 10. Classification
# ---------------------------------------------------------

def classify(row):

    if row["cricinfo_match"]:
        return "SAFE_CRICINFO"

    if row["name_match"]:
        return "NAME_SUPPORT"

    return "REVIEW"


uuid_summary["classification"] = (
    uuid_summary.apply(classify, axis=1)
)


# ---------------------------------------------------------
# 11. UUID count per production player
# ---------------------------------------------------------

uuid_counts = (
    uuid_summary
    .groupby("player_id")["cricsheet_uuid"]
    .nunique()
)

uuid_summary["uuid_count_for_player"] = (
    uuid_summary["player_id"].map(uuid_counts)
)

uuid_summary["multi_uuid_player"] = (
    uuid_summary["uuid_count_for_player"] > 1
)


# ---------------------------------------------------------
# 12. SAFE candidates
# ---------------------------------------------------------

safe = uuid_summary[
    uuid_summary["classification"].isin(
        ["SAFE_CRICINFO", "NAME_SUPPORT"]
    )
].copy()

safe["action"] = "CANDIDATE_ONLY"


# ---------------------------------------------------------
# 13. REVIEW candidates
# ---------------------------------------------------------

review = uuid_summary[
    uuid_summary["classification"].eq("REVIEW")
].copy()

review["action"] = "MANUAL_REVIEW"


# ---------------------------------------------------------
# 14. IMPORTANT SAFETY RULE
# ---------------------------------------------------------
#
# If one production player_id has multiple UUIDs,
# we DO NOT automatically merge those UUIDs.
#
# They remain separate candidates for identity review.
# ---------------------------------------------------------

safe = safe.sort_values(
    ["player_id", "score", "match_count"],
    ascending=[True, False, False]
)

review = review.sort_values(
    ["player_id", "match_count"],
    ascending=[True, False]
)


# ---------------------------------------------------------
# 15. Save outputs
# ---------------------------------------------------------

safe.to_csv(
    OUT_SAFE,
    index=False,
    encoding="utf-8-sig"
)

review.to_csv(
    OUT_REVIEW,
    index=False,
    encoding="utf-8-sig"
)


# ---------------------------------------------------------
# 16. Final report
# ---------------------------------------------------------

print()
print("UUID IDENTITY RESOLUTION ANALYSIS")
print("---------------------------------")

print("UUID identities analyzed:", len(uuid_summary))

print(
    "SAFE_CRICINFO:",
    int(
        (uuid_summary["classification"] == "SAFE_CRICINFO").sum()
    )
)

print(
    "NAME_SUPPORT:",
    int(
        (uuid_summary["classification"] == "NAME_SUPPORT").sum()
    )
)

print(
    "REVIEW:",
    int(
        (uuid_summary["classification"] == "REVIEW").sum()
    )
)

print(
    "Production player IDs represented:",
    uuid_summary["player_id"].nunique()
)

print(
    "Player IDs with multiple UUIDs:",
    int(
        (uuid_counts > 1).sum()
    )
)

print()
print("Saved:")
print(OUT_SAFE)
print(OUT_REVIEW)

print()
print("Production files modified: NO")
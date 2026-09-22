import pandas as pd

BASE = r"DATA\processed"

print("Loading files...")

d = pd.read_csv(
    rf"{BASE}\dim_player.csv",
    dtype=str
)

u = pd.read_csv(
    rf"{BASE}\match_player_uuid_map.csv",
    dtype=str
)

r = pd.read_csv(
    rf"{BASE}\cricsheet_people.csv",
    dtype=str
)

print("dim_player rows:", len(d))
print("UUID map rows:", len(u))
print("Registry rows:", len(r))

# ---------------------------------------------------------
# 1. Find production players having multiple UUIDs
# ---------------------------------------------------------

uuid_counts = (
    u.groupby("short_name")["cricsheet_uuid"]
    .nunique()
    .reset_index(name="uuid_count_by_name")
)

# Link UUID map to production player_id using unique short_name
name_counts = d.groupby("short_name")["player_id"].nunique()

unique_names = set(
    name_counts[name_counts.eq(1)].index
)

u2 = u[u.short_name.isin(unique_names)].copy()

name_to_player = (
    d[d.short_name.isin(unique_names)]
    [["player_id", "short_name", "display_name", "full_name", "key_cricinfo"]]
    .drop_duplicates("short_name")
)

u2 = u2.merge(
    name_to_player,
    on="short_name",
    how="left"
)

# Only production IDs represented in UUID map
player_uuid_counts = (
    u2.groupby("player_id")["cricsheet_uuid"]
    .nunique()
)

multi_ids = set(
    player_uuid_counts[player_uuid_counts.gt(1)].index
)

print("Production IDs with multiple UUIDs:", len(multi_ids))

# ---------------------------------------------------------
# 2. Keep only ambiguous production IDs
# ---------------------------------------------------------

a = u2[u2.player_id.isin(multi_ids)].copy()

# ---------------------------------------------------------
# 3. Attach registry identity
# ---------------------------------------------------------

registry_cols = [
    "identifier",
    "name",
    "unique_name",
    "key_cricinfo"
]

registry_cols = [
    c for c in registry_cols
    if c in r.columns
]

rr = r[registry_cols].drop_duplicates("identifier")

a = a.merge(
    rr,
    left_on="cricsheet_uuid",
    right_on="identifier",
    how="left",
    suffixes=("", "_registry")
)

# ---------------------------------------------------------
# 4. Save UUID-level identity audit
# ---------------------------------------------------------

out = a[
    [
        "player_id",
        "short_name",
        "display_name",
        "full_name",
        "key_cricinfo",
        "match_id",
        "cricsheet_uuid",
        "name",
        "unique_name",
        "key_cricinfo_registry"
    ]
].copy()

out = out.rename(
    columns={
        "key_cricinfo": "production_cricinfo",
        "name": "registry_name",
        "unique_name": "registry_unique_name",
        "key_cricinfo_registry": "registry_cricinfo"
    }
)

out = out.drop_duplicates()

# Sort for easy manual inspection
out = out.sort_values(
    [
        "player_id",
        "short_name",
        "cricsheet_uuid",
        "match_id"
    ]
)

path = rf"{BASE}\player_uuid_match_identity_audit.csv"

out.to_csv(
    path,
    index=False,
    encoding="utf-8-sig"
)

# ---------------------------------------------------------
# 5. Summary
# ---------------------------------------------------------

print()
print("PLAYER UUID MATCH IDENTITY AUDIT")
print("--------------------------------")
print("Rows:", len(out))
print("Player IDs:", out.player_id.nunique())
print("UUIDs:", out.cricsheet_uuid.nunique())

print()
print("Saved:")
print(path)

print()
print("Production files modified: NO")
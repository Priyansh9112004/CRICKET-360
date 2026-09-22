import json
from pathlib import Path
import pandas as pd

RAW_DIR = Path(r"DATA\raw\json")
DIM_FILE = Path(r"DATA\processed\dim_player.csv")

OUT_MAP = Path(r"DATA\processed\match_player_uuid_map.csv")
OUT_AUDIT = Path(r"DATA\processed\player_uuid_identity_audit.csv")

# -------------------------------------------------------
# Load current player dimension
# -------------------------------------------------------

dim = pd.read_csv(DIM_FILE, dtype=str)

assert dim["player_id"].nunique() == len(dim)

name_to_player = (
    dim[["player_id", "short_name", "key_cricinfo"]]
    .drop_duplicates()
)

print("dim_player rows:", len(dim))
print("Unique player_id:", dim["player_id"].nunique())

# -------------------------------------------------------
# Read all Cricsheet JSON registry mappings
# -------------------------------------------------------

rows = []
json_files = sorted(RAW_DIR.glob("*.json"))

print("Raw JSON files:", len(json_files))

for i, path in enumerate(json_files, start=1):

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    match_id = path.stem

    people = (
        data.get("info", {})
        .get("registry", {})
        .get("people", {})
    )

    for short_name, uuid in people.items():

        if short_name is None or uuid is None:
            continue

        short_name = str(short_name).strip()
        uuid = str(uuid).strip()

        if not short_name or not uuid:
            continue

        rows.append({
            "match_id": match_id,
            "short_name": short_name,
            "cricsheet_uuid": uuid
        })

    if i % 5000 == 0:
        print("Processed JSON:", i)

mp = pd.DataFrame(rows)

mp = (
    mp.drop_duplicates(
        ["match_id", "short_name", "cricsheet_uuid"]
    )
    .reset_index(drop=True)
)

# -------------------------------------------------------
# Validate match/name uniqueness
# -------------------------------------------------------

conflict = (
    mp.groupby(["match_id", "short_name"])
    ["cricsheet_uuid"]
    .nunique()
)

conflict = conflict[conflict > 1]

print("\nMATCH-PLAYER UUID MAP")
print("Rows:", len(mp))
print("Matches:", mp["match_id"].nunique())
print("Names:", mp["short_name"].nunique())
print("UUIDs:", mp["cricsheet_uuid"].nunique())
print(
    "Same match+short_name with multiple UUIDs:",
    len(conflict)
)

# -------------------------------------------------------
# Restrict audit to names present in dim_player
# -------------------------------------------------------

linked = mp.merge(
    name_to_player,
    on="short_name",
    how="inner"
)

print("\nDIM LINKAGE")
print("Mapped rows:", len(linked))
print(
    "dim player IDs represented:",
    linked["player_id"].nunique()
)

missing_dim = set(dim["player_id"]) - set(linked["player_id"])

print(
    "dim player IDs without registry mapping:",
    len(missing_dim)
)

# -------------------------------------------------------
# Identity audit:
# How many distinct UUIDs exist under each current
# short_name/player_id?
# -------------------------------------------------------

audit = (
    linked.groupby(
        ["player_id", "short_name", "key_cricinfo"],
        dropna=False
    )
    .agg(
        UUID_Count=("cricsheet_uuid", "nunique"),
        Match_Count=("match_id", "nunique"),
        UUIDs=(
            "cricsheet_uuid",
            lambda s: " | ".join(sorted(set(s)))
        )
    )
    .reset_index()
)

collision = audit[audit["UUID_Count"] > 1].copy()

print("\nIDENTITY AUDIT")
print("Player IDs audited:", len(audit))
print(
    "IDs with exactly 1 UUID:",
    int((audit["UUID_Count"] == 1).sum())
)
print(
    "IDs with 2+ UUIDs:",
    len(collision)
)
print(
    "Maximum UUIDs under one current player_id:",
    int(audit["UUID_Count"].max())
)

if len(collision):

    print("\nUUID collision distribution:")
    print(
        collision["UUID_Count"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\nLargest collisions:")

    print(
        collision.sort_values(
            ["UUID_Count", "Match_Count"],
            ascending=[False, False]
        )[
            [
                "player_id",
                "short_name",
                "key_cricinfo",
                "UUID_Count",
                "Match_Count",
                "UUIDs"
            ]
        ]
        .head(50)
        .to_string(index=False)
    )

# -------------------------------------------------------
# Save
# -------------------------------------------------------

mp.to_csv(OUT_MAP, index=False)
audit.to_csv(OUT_AUDIT, index=False)

print("\nProduction files modified: NO")
print("Saved:", OUT_MAP)
print("Saved:", OUT_AUDIT)
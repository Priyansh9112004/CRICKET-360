from pathlib import Path
import pandas as pd
import shutil, re

ROOT = Path(r"DATA\processed")
DIM = ROOT / "dim_player.csv"
BACKUP = ROOT / "dim_player_before_final_bowling_style_cleanup.csv"
AUDIT = ROOT / "final_bowling_style_enrichment_audit.csv"

d = pd.read_csv(DIM, dtype=str).fillna("")

# Auto-detect bowling style column
cands = [c for c in d.columns if "bowl" in c.lower() and "style" in c.lower()]
if not cands:
    raise SystemExit("No bowling-style column found in dim_player.csv")
col = cands[0]

def missing(s):
    return str(s).strip().lower() in {"", "not available", "nan"}

def norm_style(s):
    s = re.sub(r"\s+", " ", str(s)).strip()
    if not s:
        return ""
    # Keep source wording mostly intact; normalize common capitalization/hyphenation only.
    repl = {
        "right arm fast": "Right-arm fast",
        "right-arm fast": "Right-arm fast",
        "right arm medium": "Right-arm medium",
        "right-arm medium": "Right-arm medium",
        "right arm medium fast": "Right-arm medium-fast",
        "right-arm medium-fast": "Right-arm medium-fast",
        "right arm fast medium": "Right-arm fast-medium",
        "right-arm fast-medium": "Right-arm fast-medium",
        "left arm fast": "Left-arm fast",
        "left-arm fast": "Left-arm fast",
        "left arm medium": "Left-arm medium",
        "left-arm medium": "Left-arm medium",
        "left arm medium fast": "Left-arm medium-fast",
        "left-arm medium-fast": "Left-arm medium-fast",
        "left arm fast medium": "Left-arm fast-medium",
        "left-arm fast-medium": "Left-arm fast-medium",
        "right arm offbreak": "Right-arm offbreak",
        "right-arm offbreak": "Right-arm offbreak",
        "right arm legbreak": "Right-arm legbreak",
        "right-arm legbreak": "Right-arm legbreak",
        "legbreak": "Legbreak",
        "legbreak googly": "Legbreak googly",
        "slow left arm orthodox": "Slow left-arm orthodox",
        "slow left-arm orthodox": "Slow left-arm orthodox",
        "left arm orthodox": "Slow left-arm orthodox",
        "left-arm orthodox": "Slow left-arm orthodox",
        "left arm wrist spin": "Left-arm wrist-spin",
        "left-arm wrist-spin": "Left-arm wrist-spin",
        "left arm chinaman": "Left-arm wrist-spin",
        "left-arm chinaman": "Left-arm wrist-spin",
    }
    return repl.get(s.lower(), s)

shutil.copy2(DIM, BACKUP)

audit_rows = []

# 1) WK missing bowling style => Not Available
wk_mask = d["role"].str.strip().eq("Wicketkeeper Batter") & d[col].map(missing)
for _, r in d.loc[wk_mask, ["player_id","full_name","role",col]].iterrows():
    audit_rows.append({
        "player_id": r["player_id"],
        "full_name": r.get("full_name",""),
        "old_bowling_style": r[col],
        "new_bowling_style": "Not Available",
        "source": "rule",
        "reason": "Wicketkeeper Batter with missing bowling style"
    })
d.loc[wk_mask, col] = "Not Available"

# 2) ESPN explicit bowling style
espn = ROOT / "espn_live_role_audit.csv"
espn_applied = 0
if espn.exists():
    e = pd.read_csv(espn, dtype=str).fillna("")
    if {"player_id","styles","returned_id","http_status"}.issubset(e.columns):
        e["bowl_new"] = e["styles"].str.extract(r"(?i)bowling:\s*([^|]+)", expand=False).fillna("").map(norm_style)

        cur = d[["player_id",col] + (["key_cricinfo"] if "key_cricinfo" in d.columns else [])].copy()
        if "key_cricinfo" in cur.columns:
            cur["cid"] = cur["key_cricinfo"].str.replace(r"\.0$","",regex=True).str.strip()
            e["rid"] = e["returned_id"].str.replace(r"\.0$","",regex=True).str.strip()
            z = e.merge(cur[["player_id","cid",col]], on="player_id", how="inner")
            z = z[
                z["http_status"].eq("200")
                & z["rid"].eq(z["cid"])
                & z["bowl_new"].ne("")
                & z[col].map(missing)
            ].copy()
        else:
            z = e[e["http_status"].eq("200") & e["bowl_new"].ne("")].merge(
                cur[["player_id",col]], on="player_id", how="inner"
            )
            z = z[z[col].map(missing)].copy()

        mp = dict(zip(z["player_id"], z["bowl_new"]))
        mask = d["player_id"].isin(mp) & d[col].map(missing) & ~d["role"].str.strip().eq("Wicketkeeper Batter")
        for _, r in d.loc[mask, ["player_id","full_name",col]].iterrows():
            nv = mp[r["player_id"]]
            audit_rows.append({
                "player_id": r["player_id"],
                "full_name": r.get("full_name",""),
                "old_bowling_style": r[col],
                "new_bowling_style": nv,
                "source": "ESPN",
                "reason": "Explicit bowling: value; returned ESPN ID matched production Cricinfo ID"
            })
        d.loc[mask, col] = d.loc[mask, "player_id"].map(mp)
        espn_applied = int(mask.sum())

# 3) CricHeroes explicit bowling_style
ch = ROOT / "cricheroes_live_role_audit.csv"
ch_applied = 0
if ch.exists():
    a = pd.read_csv(ch, dtype=str).fillna("")
    if {"player_id","bowling_style"}.issubset(a.columns):
        a["bowl_new"] = a["bowling_style"].map(norm_style)
        if "http_status" in a.columns:
            a = a[a["http_status"].eq("200")]
        a = a[a["bowl_new"].ne("")]
        mp = dict(zip(a["player_id"], a["bowl_new"]))
        mask = d["player_id"].isin(mp) & d[col].map(missing) & ~d["role"].str.strip().eq("Wicketkeeper Batter")
        for _, r in d.loc[mask, ["player_id","full_name",col]].iterrows():
            nv = mp[r["player_id"]]
            audit_rows.append({
                "player_id": r["player_id"],
                "full_name": r.get("full_name",""),
                "old_bowling_style": r[col],
                "new_bowling_style": nv,
                "source": "CricHeroes",
                "reason": "Explicit bowling_style field"
            })
        d.loc[mask, col] = d.loc[mask, "player_id"].map(mp)
        ch_applied = int(mask.sum())

# Normalize existing nonmissing values conservatively
d[col] = d[col].map(lambda x: "Not Available" if str(x).strip().lower()=="not available" else norm_style(x))

# 4) Everything still missing => Not Available
final_missing = d[col].map(missing)
remaining_before_fill = int(final_missing.sum())
for _, r in d.loc[final_missing, ["player_id","full_name","role",col]].iterrows():
    audit_rows.append({
        "player_id": r["player_id"],
        "full_name": r.get("full_name",""),
        "old_bowling_style": r[col],
        "new_bowling_style": "Not Available",
        "source": "final_sentinel",
        "reason": "No explicit bowling style recovered from available sources"
    })
d.loc[final_missing, col] = "Not Available"

pd.DataFrame(audit_rows).to_csv(AUDIT, index=False, encoding="utf-8-sig")
d.to_csv(DIM, index=False, encoding="utf-8-sig")

print("Bowling-style column:", col)
print("WK missing -> Not Available:", int(wk_mask.sum()))
print("ESPN explicit bowling styles applied:", espn_applied)
print("CricHeroes explicit bowling styles applied:", ch_applied)
print("Still missing before final Not Available fill:", remaining_before_fill)
print("Final Not Available:", int(d[col].eq("Not Available").sum()))
print("Blank remaining:", int(d[col].str.strip().eq("").sum()))
print("Available bowling styles:", int((~d[col].eq("Not Available")).sum()))
print("Total:", len(d))
print("\nTop final values:")
print(d[col].value_counts().head(25).to_string())
print("\nAudit:", AUDIT)
print("Backup:", BACKUP)

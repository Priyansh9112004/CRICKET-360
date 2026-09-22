import pandas as pd
from pathlib import Path
import shutil

OUT=Path(r'DATA/processed')

FILES=[
    'dim_player.csv',
    'match_player_uuid_resolved.csv',
    'fact_batting.csv',
    'fact_bowling.csv',
    'matches.csv',
    'player_match_batting.csv',
    'player_match_bowling.csv',
    'player_summary.csv',
    'player_by_season.csv',
    'player_career_by_format.csv',
    'player_vs_team.csv',
    'player_vs_format.csv',
]

print('=== IDENTITY-AWARE PLAYER TABLE REBUILD PRECHECK ===')
for f in FILES:
    p=OUT/f
    if p.exists():
        df=pd.read_csv(p,dtype=str)
        print(f'{f}: {len(df):,} rows | {len(df.columns)} cols')
    else:
        print(f'{f}: MISSING')

print('\\n=== CONFIRMED SPLIT IDS ===')
q=pd.read_csv(OUT/'confirmed_identity_split_mapping.csv',dtype=str).fillna('')
print(q.to_string(index=False))

print('\\n=== CURRENT DIMENSION ===')
d=pd.read_csv(OUT/'dim_player.csv',dtype=str).fillna('')
print('Rows:',len(d))
print('Unique Player_IDs:',d.player_id.nunique())
print('Duplicate Player_IDs:',d.player_id.duplicated().sum())

print('\\n=== RESOLVED UUID LAYER ===')
m=pd.read_csv(OUT/'match_player_uuid_resolved.csv',dtype=str).fillna('')
print('Rows:',len(m))
print('Unique matches:',m.match_id.nunique())
print('Unique UUIDs:',m.cricsheet_uuid.nunique())
print('Resolved rows:',m.final_player_id.ne('').sum())
print('Resolved unique Player_IDs:',m.loc[m.final_player_id.ne(''),'final_player_id'].nunique())

ids=set(q.loc[q.action.eq('CREATE_NEW_ID'),'new_player_id'])
x=m[m.final_player_id.isin(ids)]
print('\\nSplit affected rows:',len(x))
print('Split affected matches:',x.match_id.nunique())
print('Split IDs:',sorted(x.final_player_id.unique()))

print('\\n=== PRECHECK ONLY ===')
print('Production files modified: NO')
print('Backups created: NO')
print('Next: build identity-aware fact/player-table rebuild')

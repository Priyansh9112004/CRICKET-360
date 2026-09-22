from __future__ import annotations

import argparse
import re
import shutil
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
# If script is copied to project root, use project root. If run from Downloads, use current working directory.
if not (ROOT / 'DATA' / 'processed' / 'dim_player.csv').exists():
    ROOT = Path.cwd()

DIM_PLAYER = ROOT / 'DATA' / 'processed' / 'dim_player.csv'
OUT_AUDIT = ROOT / 'DATA' / 'processed' / 'role_inference_match_history_audit.csv'
OUT_UNRESOLVED = ROOT / 'DATA' / 'processed' / 'role_inference_match_history_unresolved.csv'
BACKUP = ROOT / 'DATA' / 'processed' / 'dim_player_before_match_history_role_inference.csv'
MISSING = {'', 'not available', 'nan', 'none', 'null'}

MATCH_COLS = ['match_id','matchid','game_id','gameid','fixture_id','fixtureid']
INN_COLS = ['innings','inning','innings_no','inning_no','innings_number']
BATTER_ID_COLS = ['batter_id','striker_id','batsman_id','batter_player_id','striker_player_id']
NONSTRIKER_ID_COLS = ['non_striker_id','nonstriker_id','non_striker_player_id']
BOWLER_ID_COLS = ['bowler_id','bowler_player_id']
BATTER_NAME_COLS = ['batter','striker','batsman']
NONSTRIKER_NAME_COLS = ['non_striker','nonstriker','non-striker']
BOWLER_NAME_COLS = ['bowler']
OVER_COLS = ['over','over_number','overs']
BALL_COLS = ['ball','ball_number','delivery','delivery_number']


def norm_text(x):
    return re.sub(r'[^a-z0-9]+', '', str(x).lower())


def missing_mask(s):
    return s.fillna('').astype(str).str.strip().str.lower().isin(MISSING)


def first_col(columns, choices):
    low = {str(c).lower(): c for c in columns}
    for x in choices:
        if x in low:
            return low[x]
    return None


def read_columns(path):
    try:
        if path.suffix.lower() == '.parquet':
            import pyarrow.parquet as pq
            return pq.ParquetFile(path).schema.names
        return list(pd.read_csv(path, nrows=0).columns)
    except Exception:
        return []


def find_ball_file():
    seen, candidates = set(), []
    for base in [ROOT / 'DATA' / 'processed', ROOT / 'DATA']:
        if not base.exists():
            continue
        for path in list(base.rglob('*.csv')) + list(base.rglob('*.parquet')):
            rp = str(path.resolve())
            if rp in seen or path.resolve() == DIM_PLAYER.resolve():
                continue
            seen.add(rp)
            cols = read_columns(path)
            if not cols:
                continue
            cm = {
                'match': first_col(cols, MATCH_COLS), 'innings': first_col(cols, INN_COLS),
                'batter_id': first_col(cols, BATTER_ID_COLS), 'non_id': first_col(cols, NONSTRIKER_ID_COLS),
                'bowler_id': first_col(cols, BOWLER_ID_COLS), 'batter': first_col(cols, BATTER_NAME_COLS),
                'non': first_col(cols, NONSTRIKER_NAME_COLS), 'bowler': first_col(cols, BOWLER_NAME_COLS),
                'over': first_col(cols, OVER_COLS), 'ball': first_col(cols, BALL_COLS),
            }
            if cm['match'] and cm['innings'] and (cm['batter_id'] or cm['batter']) and (cm['bowler_id'] or cm['bowler']):
                bonus = sum(10 for t in ('ball','deliver','fact','innings') if t in path.name.lower())
                candidates.append((bonus, path.stat().st_size, path, cm))
    if not candidates:
        raise SystemExit('No usable ball-by-ball CSV/Parquet auto-detected. Need match_id + innings + batter/striker + bowler in one file.')
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2], candidates[0][3]


def load_ball_data(path, cm):
    use = list(dict.fromkeys(v for v in cm.values() if v))
    print(f'Using ball-by-ball source: {path}')
    print('Detected columns:', cm)
    if path.suffix.lower() == '.parquet':
        df = pd.read_parquet(path, columns=use)
        for c in use:
            df[c] = df[c].fillna('').astype(str)
    else:
        df = pd.read_csv(path, usecols=use, dtype=str, low_memory=False).fillna('')
    df['_row'] = np.arange(len(df), dtype=np.int64)
    sort_cols = [cm['match'], cm['innings']]
    if cm['over']:
        df['_over_n'] = pd.to_numeric(df[cm['over']], errors='coerce')
        sort_cols.append('_over_n')
    if cm['ball']:
        df['_ball_n'] = pd.to_numeric(df[cm['ball']], errors='coerce')
        sort_cols.append('_ball_n')
    sort_cols.append('_row')
    df = df.sort_values(sort_cols, kind='stable').reset_index(drop=True)
    df['_seq'] = np.arange(len(df), dtype=np.int64)
    return df


def build_unique_name_map(dim):
    name_cols = [c for c in ['full_name','display_name','player_name','name'] if c in dim.columns]
    x = defaultdict(set)
    for _, r in dim.iterrows():
        pid = str(r['player_id']).replace('.0','').strip()
        for c in name_cols:
            n = norm_text(r.get(c, ''))
            if n:
                x[n].add(pid)
    return {n: next(iter(ids)) for n, ids in x.items() if len(ids) == 1}


def normalize_pid_series(s):
    return s.fillna('').astype(str).str.replace(r'\.0$', '', regex=True).str.strip()


def resolve_series(df, id_col, name_col, unique_names):
    if id_col:
        return normalize_pid_series(df[id_col])
    if name_col:
        return df[name_col].map(lambda v: unique_names.get(norm_text(v), ''))
    return pd.Series('', index=df.index, dtype='object')


def infer_role(r):
    matches = int(r.matches_observed)
    bat_inns = int(r.bat_innings)
    bowl_inns = int(r.bowl_innings)
    pos = r.median_batting_position
    bshare = float(r.bowl_match_share)
    bpm = float(r.balls_bowled_per_observed_match)
    bpi = float(r.balls_bowled_per_bowling_innings)

    if matches <= 0:
        return pd.Series(['Not Available','NONE','no match evidence'])

    meaningful_bowling = bowl_inns >= 2 and (bshare >= .25 or bpm >= 6 or bpi >= 12)
    regular_bowling = bowl_inns >= 3 and (bshare >= .40 or bpm >= 9) and bpi >= 9
    heavy_bowling = bowl_inns >= 3 and bshare >= .60 and bpi >= 15

    if bat_inns == 0:
        role = 'Bowler' if meaningful_bowling else 'Not Available'
    elif pd.isna(pos):
        role = 'Allrounder' if meaningful_bowling else 'Batter'
    elif not meaningful_bowling:
        role = 'Top order Batter' if pos <= 3.5 else ('Middle order Batter' if pos <= 7.0 else 'Batter')
    elif heavy_bowling and pos >= 7.0:
        role = 'Bowler'
    elif regular_bowling:
        if pos <= 4.5 and not heavy_bowling:
            role = 'Batting Allrounder'
        elif pos >= 6.0 and (heavy_bowling or bpi >= 18):
            role = 'Bowling Allrounder'
        else:
            role = 'Allrounder'
    else:
        role = 'Top order Batter' if pos <= 3.5 else ('Middle order Batter' if pos <= 7.0 else 'Batter')

    if role == 'Not Available':
        conf = 'NONE'
    else:
        score = (2 if matches >= 20 else 1 if matches >= 8 else 0) + (1 if (bat_inns >= 8 or bowl_inns >= 8) else 0) + (1 if matches >= 5 and (bat_inns >= 3 or bowl_inns >= 3) else 0)
        conf = 'HIGH' if score >= 3 else ('MEDIUM' if score >= 2 else 'LOW')
    ev = f'matches={matches}; bat_inns={bat_inns}; median_pos={pos if not pd.isna(pos) else "NA"}; bowl_inns={bowl_inns}; bowl_match_share={bshare:.3f}; balls/match={bpm:.1f}; balls/bowl_inn={bpi:.1f}'
    return pd.Series([role, conf, ev])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--min-confidence', choices=['LOW','MEDIUM','HIGH'], default='LOW')
    args = ap.parse_args()

    dim = pd.read_csv(DIM_PLAYER, dtype=str).fillna('')
    dim['player_id'] = normalize_pid_series(dim['player_id'])
    missing_ids = set(dim.loc[missing_mask(dim['role']), 'player_id'])
    print('Current missing roles:', len(missing_ids))

    path, cm = find_ball_file()
    balls = load_ball_data(path, cm)
    unique_names = build_unique_name_map(dim)
    balls['_batter_pid'] = resolve_series(balls, cm['batter_id'], cm['batter'], unique_names)
    balls['_non_pid'] = resolve_series(balls, cm['non_id'], cm['non'], unique_names)
    balls['_bowler_pid'] = resolve_series(balls, cm['bowler_id'], cm['bowler'], unique_names)
    valid = set(dim.player_id)
    for c in ['_batter_pid','_non_pid','_bowler_pid']:
        balls.loc[~balls[c].isin(valid), c] = ''

    mc, ic = cm['match'], cm['innings']
    balls['_innings_key'] = balls[mc].astype(str) + '||' + balls[ic].astype(str)

    obs = []
    for c in ['_batter_pid','_non_pid','_bowler_pid']:
        t = balls.loc[balls[c].ne(''), [mc,c]].drop_duplicates()
        t.columns = ['match_id','player_id']
        obs.append(t)
    observed = pd.concat(obs, ignore_index=True).drop_duplicates()
    matches_observed = observed.groupby('player_id').match_id.nunique()

    events = []
    for priority, c in enumerate(['_batter_pid','_non_pid']):
        t = balls.loc[balls[c].ne(''), ['_innings_key','_seq',c]].copy()
        t.columns = ['innings_key','seq','player_id']
        t['priority'] = priority
        events.append(t)
    be = pd.concat(events, ignore_index=True)
    first = be.sort_values(['innings_key','seq','priority']).drop_duplicates(['innings_key','player_id'])
    first['batting_position'] = first.groupby('innings_key').cumcount() + 1

    bat_inns = first.groupby('player_id').innings_key.nunique()
    mean_pos = first.groupby('player_id').batting_position.mean()
    median_pos = first.groupby('player_id').batting_position.median()
    top3 = first.assign(x=first.batting_position.le(3)).groupby('player_id').x.mean()
    top4 = first.assign(x=first.batting_position.le(4)).groupby('player_id').x.mean()
    mid = first.assign(x=first.batting_position.between(4,7)).groupby('player_id').x.mean()

    bw = balls.loc[balls['_bowler_pid'].ne(''), [mc,'_innings_key','_bowler_pid']].copy()
    bw.columns = ['match_id','innings_key','player_id']
    balls_bowled = bw.groupby('player_id').size()
    bowl_inns = bw.drop_duplicates(['innings_key','player_id']).groupby('player_id').innings_key.nunique()
    bowl_matches = bw.drop_duplicates(['match_id','player_id']).groupby('player_id').match_id.nunique()

    idx = pd.Index(sorted(missing_ids), name='player_id')
    m = pd.DataFrame(index=idx)
    m['matches_observed'] = matches_observed.reindex(idx).fillna(0).astype(int)
    m['bat_innings'] = bat_inns.reindex(idx).fillna(0).astype(int)
    m['mean_batting_position'] = mean_pos.reindex(idx)
    m['median_batting_position'] = median_pos.reindex(idx)
    m['top3_share'] = top3.reindex(idx).fillna(0.0)
    m['top4_share'] = top4.reindex(idx).fillna(0.0)
    m['middle_order_share_4_7'] = mid.reindex(idx).fillna(0.0)
    m['bowl_innings'] = bowl_inns.reindex(idx).fillna(0).astype(int)
    m['bowl_matches'] = bowl_matches.reindex(idx).fillna(0).astype(int)
    m['balls_bowled'] = balls_bowled.reindex(idx).fillna(0).astype(int)
    m['bowl_match_share'] = np.where(m.matches_observed.gt(0), m.bowl_matches / m.matches_observed, 0.0)
    m['balls_bowled_per_observed_match'] = np.where(m.matches_observed.gt(0), m.balls_bowled / m.matches_observed, 0.0)
    m['balls_bowled_per_bowling_innings'] = np.where(m.bowl_innings.gt(0), m.balls_bowled / m.bowl_innings, 0.0)
    m[['inferred_role','confidence','evidence']] = m.apply(infer_role, axis=1)
    m = m.reset_index()

    info = [c for c in ['player_id','full_name','display_name','country','key_cricinfo'] if c in dim.columns]
    audit = dim[info].merge(m, on='player_id', how='right', validate='one_to_one')
    audit['source'] = 'match_history_inference:' + str(path.relative_to(ROOT))
    audit.to_csv(OUT_AUDIT, index=False, encoding='utf-8-sig')
    audit[audit.inferred_role.eq('Not Available')].to_csv(OUT_UNRESOLVED, index=False, encoding='utf-8-sig')

    print('\nInferred role counts:')
    print(audit.inferred_role.value_counts(dropna=False).to_string())
    print('\nConfidence counts:')
    print(audit.confidence.value_counts(dropna=False).to_string())
    print('\nAudit saved:', OUT_AUDIT)
    print('Unresolved saved:', OUT_UNRESOLVED)

    if not args.apply:
        print('\nDRY RUN ONLY. Production NOT changed.')
        print('If results look sensible, run: C:\\Python312\\python.exe infer_roles_from_match_history.py --apply')
        return

    rank = {'NONE':0,'LOW':1,'MEDIUM':2,'HIGH':3}
    candidate = audit[(audit.inferred_role != 'Not Available') & (audit.confidence.map(rank).fillna(0) >= rank[args.min_confidence])]
    role_map = dict(zip(candidate.player_id, candidate.inferred_role))
    mask = dim.player_id.isin(role_map) & missing_mask(dim.role)
    shutil.copy2(DIM_PLAYER, BACKUP)
    before = int(missing_mask(dim.role).sum())
    dim.loc[mask, 'role'] = dim.loc[mask, 'player_id'].map(role_map)
    after = int(missing_mask(dim.role).sum())
    assert len(dim) == 13213 and dim.player_id.nunique() == 13213 and after <= before
    dim.to_csv(DIM_PLAYER, index=False, encoding='utf-8-sig')
    print('\nApplied inferred roles:', int(mask.sum()))
    print('Missing before:', before)
    print('Missing after:', after)
    print('Role available:', len(dim) - after)
    print('Backup:', BACKUP)

if __name__ == '__main__':
    main()

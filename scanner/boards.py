"""Pull the top 25 of every filter combo. Refreshes combos older than max_age (oldest first) within a call budget."""
import json, os, time, sys
from concurrent.futures import ThreadPoolExecutor
import combos as C
from lib import fetch_combo, HERE
PATH = os.path.join(HERE, '..', 'state', 'boards.json')


def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return {'combos': {}}


def save(b):
    tmp = PATH + '.tmp'
    json.dump(b, open(tmp, 'w'), separators=(',', ':'))
    os.replace(tmp, PATH)


def refresh(max_age=1500, budget=400, workers=4):
    b = load()
    now = time.time()
    todo = [c for c in C.all_combos() if now - (b['combos'].get(c['id']) or {}).get('ts', 0) > (min(max_age, 600) if c['lens'] in C.PRIORITY else max_age)]
    todo.sort(key=lambda c: (b['combos'].get(c['id']) or {}).get('ts', 0))
    todo = todo[:budget]
    ok = fail = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for c, r in zip(todo, ex.map(fetch_combo, todo)):
            if r is None:
                fail += 1
                continue
            b['combos'][c['id']] = r
            ok += 1
    # real 7/30-day P&L boards (one pull of the top 1000 per window, split into rank bands)
    for w in C.PNL_WINDOWS:
        ids = [C.pnl_combo_id(w, lo, hi) for lo, hi in C.PNL_BANDS]
        if all(now - (b['combos'].get(i) or {}).get('ts', 0) <= max(max_age, 6 * 3600) for i in ids):
            continue
        rows, asof = [], None
        from orca import orca
        for off in (0, 500):
            d = orca('/api/v2/business/pnl-leaderboard', {'window': w, 'order': 'desc', 'limit': 500, 'offset': off}, tries=3)
            if not d or not d.get('rows'):
                break
            asof = d.get('as_of')
            rows += [dict(wallet=r['wallet'].lower(), name=r.get('name') or r.get('display_name') or r['wallet'][:8], pnl30=round(r.get('pnl_usd') or 0),
                          rank=r.get('rank'), mk=r.get('resolved_markets')) for r in d['rows']]
        if len(rows) < 900:
            print('pnl board', w, 'short', len(rows), flush=True)
            continue
        for lo, hi in C.PNL_BANDS:
            b['combos'][C.pnl_combo_id(w, lo, hi)] = dict(ts=int(now), asOf=asof, rows=[r for r in rows if lo <= (r['rank'] or 0) <= hi])
        ok += 4
    # other OrcaLayer signal sources, graded exactly like filter combos (wallet lists refreshed every run)
    from orca import orca
    def alerts(cat):
        d = orca('/api/v2/whale-alerts', {'minutes': 360, 'category': cat, 'smart_only': 'true', 'min_usd': 500, 'limit': 500}, tries=2) or {}
        seen = {}
        for a in d.get('alerts') or []:
            wh = a.get('whale') or {}; w = (wh.get('wallet') or '').lower()
            if w and w not in seen and (a.get('trade') or {}).get('action') == 'BUY':
                seen[w] = dict(wallet=w, name=wh.get('name') or w[:8], wr=wh.get('win_rate'), pnl=round(wh.get('total_pnl') or 0))
        return list(seen.values()) if d else None
    for sid, fn in (('SIG|alerts|SPORTS', lambda: alerts('SPORTS')), ('SIG|alerts|ESPORTS', lambda: alerts('ESPORTS'))):
        rows = fn()
        if rows is not None:
            b['combos'][sid] = dict(ts=int(now), rows=rows)
    d = orca('/api/v2/hot-traders', tries=2)
    if d and d.get('traders'):
        b['combos']['SIG|hot24h|winners'] = dict(ts=int(now), rows=[dict(wallet=t['wallet'].lower(), name=t.get('name') or t['wallet'][:8], pnl24=t.get('pnl_24h'))
                                                                  for t in d['traders'] if t.get('side') != 'loss'])
    valid = {c['id'] for c in C.all_combos()} | {c['id'] for c in C.pnl_combos()} | set(C.SIGNALS)
    b['combos'] = {k: v for k, v in b['combos'].items() if k in valid}
    b['ts'] = int(now)
    save(b)
    print(f"boards: refreshed {ok}, failed {fail}, total {len(b['combos'])}/{len(valid)}", flush=True)
    return b


def members(b):
    """wallet -> {'combos': [ids], 'row': best row}"""
    out = {}
    for cid, r in b['combos'].items():
        for i, row in enumerate(r['rows']):
            m = out.setdefault(row['wallet'], {'combos': [], 'row': row, 'ranks': {}})
            m['combos'].append(cid)
            m['ranks'][cid] = i + 1
    return out


if __name__ == '__main__':
    b = refresh(max_age=int(sys.argv[1]) if len(sys.argv) > 1 else 1500)
    m = members(b)
    print('unique wallets', len(m))

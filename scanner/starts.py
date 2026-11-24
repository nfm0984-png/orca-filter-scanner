"""Game start times for settled markets (Gamma), cached in state/starts.json, so the backtest only counts
bets entered BEFORE the game started (in-play buys at 90c+ would otherwise inflate in-play traders' records)."""
import json, os, time
from concurrent.futures import ThreadPoolExecutor
from lib import get_json, iso_ts, GAMMA, HERE
PATH = os.path.join(HERE, '..', 'state', 'starts.json')


def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return {}


def fill(cids, budget_s=300, workers=8):
    st = load()
    todo = [c for c in dict.fromkeys(cids) if c and c not in st]
    batches = [todo[i:i + 20] for i in range(0, len(todo), 20)]
    t0 = time.time()

    def job(b):
        if time.time() - t0 > budget_s:
            return None
        q = '&'.join('condition_ids=' + c for c in b)
        res = {}
        for closed in ('true', 'false'):
            d = get_json(f"{GAMMA}/markets?{q}&closed={closed}&limit=50")
            if d is None:
                return None
            for m in d:
                res[(m.get('conditionId') or '').lower()] = iso_ts(m.get('gameStartTime')) or iso_ts(m.get('endDate')) or 0
            if len(res) >= len(b):
                break
        for c in b:
            res.setdefault(c, 0)
        return res
    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for r in ex.map(job, batches):
            if r:
                st.update(r); n += 1
    json.dump(st, open(PATH, 'w'), separators=(',', ':'))
    print(f"starts: {n}/{len(batches)} batches, {len(st)} cached, {time.time()-t0:.0f}s", flush=True)
    return st

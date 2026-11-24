"""Fetch graded $500+ sports bets (Polymarket Data API v2) for every wallet any combo surfaced.
Stored compactly in state/settled.json: wallet -> {ts, bets: {cid:oi -> [cost, avg, res, ts, slug, title]}}"""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import boards
from lib import settled_bets, HERE
PATH = os.path.join(HERE, '..', 'state', 'settled.json')
KEEP_DAYS = 45


def load():
    try:
        return json.load(open(PATH))
    except Exception:
        return {'wallets': {}}


def save(s):
    cut = time.time() - KEEP_DAYS * 86400
    for rec in s['wallets'].values():
        rec['bets'] = {k: v for k, v in rec['bets'].items() if v[3] >= cut}
    tmp = PATH + '.tmp'
    json.dump(s, open(tmp, 'w'), separators=(',', ':'))
    os.replace(tmp, PATH)


def refresh(wallets, since, max_age=6 * 3600, budget_s=600, workers=16):
    s = load()
    ws = s['wallets']
    now = time.time()
    todo = [w for w in wallets if now - (ws.get(w) or {}).get('ts', 0) > max_age]
    todo.sort(key=lambda w: (ws.get(w) or {}).get('ts', 0))
    t0 = time.time()

    def job(w):
        if time.time() - t0 > budget_s:
            return w, None
        rec = ws.get(w)
        st = max(since, rec['ts'] - 2 * 86400) if rec and rec.get('since', 1e18) <= since else since
        return w, settled_bets(w, st)
    n = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for w, bets in ex.map(job, todo):
            if bets is None:
                continue
            rec = ws.setdefault(w, {'bets': {}, 'since': since})
            rec['since'] = min(rec.get('since', since), since)
            for b in bets:
                rec['bets'][f"{b['cid']}:{b['oi']}"] = [b['cost'], b['avg'], b['res'], b['ts'], b['slug'], b['title'], b['outcome']]
            rec['ts'] = int(now)
            n += 1
    save(s)
    print(f"settled: refreshed {n}/{len(todo)} wallets in {time.time()-t0:.0f}s; {sum(len(r['bets']) for r in ws.values())} bets stored", flush=True)
    return s


if __name__ == '__main__':
    import calendar
    since = calendar.timegm(time.strptime(sys.argv[1] if len(sys.argv) > 1 else '2026-11-09', '%Y-%m-%d'))
    b = boards.load()
    m = boards.members(b)
    refresh(list(m), since, max_age=0, budget_s=int(sys.argv[2]) if len(sys.argv) > 2 else 1800)

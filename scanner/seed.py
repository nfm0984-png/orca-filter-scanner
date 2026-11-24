"""Backtest seed: grade every combo and trader on the settled $500+ sports bets of its members.
Combo record counts each market side once (members' money combined; if members split sides, the bigger side counts).
Flat $1 per pick at the backers' average entry price. Fees not included. Price band 5-95c."""
import json, os, time, calendar
import boards, settled, starts
from lib import flat_roi, min_cost, PX_MIN, PX_MAX, HERE
PATH = os.path.join(HERE, '..', 'state', 'seed.json')


def build(b=None, s=None, start_budget=120):
    b = b or boards.load()
    s = s or settled.load()
    ws = s['wallets']
    allc = [k.rsplit(':', 1)[0].lower() for rec in ws.values() for k in rec['bets']]
    ST = starts.fill(allc, budget_s=start_budget)
    def pregame(k, ts):
        g = ST.get(k.rsplit(':', 1)[0].lower())
        return bool(g) and ts < g  # unknown start -> excluded
    floor = {w: min_cost(m['row'].get('avg')) for w, m in boards.members(b).items()}
    traders = {}
    for w, rec in ws.items():
        n = wn = 0; tot = 0.0; edge = 0.0
        for k, (cost, avg, res, ts, slug, title, outc) in rec['bets'].items():
            if not (PX_MIN <= avg <= PX_MAX) or cost < floor.get(w, 500) or not pregame(k, ts):
                continue
            n += 1; wn += res == 'W'; tot += flat_roi(res, avg); edge += (res == 'W') - avg
        if n:
            traders[w] = [n, round(tot, 4), wn, n - wn, round(edge, 4)]
    combos = {}
    for cid, r in b['combos'].items():
        cut = 0
        if cid.startswith('PnL') and r.get('asOf'):
            cut = calendar.timegm(time.strptime(r['asOf'], '%Y-%m-%d')) + 86400  # only bets after the board's as-of day
        picks = {}
        for row in r['rows']:
            rec = ws.get(row['wallet'])
            if not rec:
                continue
            for k, (cost, avg, res, ts, slug, title, outc) in rec['bets'].items():
                if ts < cut or cost < floor.get(row['wallet'], 500) or not pregame(k, ts):
                    continue
                cond, oi = k.rsplit(':', 1)
                p = picks.setdefault(cond, {})
                q = p.setdefault(oi, [0.0, 0.0, res])
                q[0] += cost; q[1] += cost * avg
        n = wn = 0; tot = 0.0; edge = 0.0
        for cond, sides in picks.items():
            oi, (cost, cxa, res) = max(sides.items(), key=lambda kv: kv[1][0])
            px = cxa / cost
            if not (PX_MIN <= px <= PX_MAX):
                continue
            n += 1; wn += res == 'W'; tot += flat_roi(res, px); edge += (res == 'W') - px
        combos[cid] = [n, round(tot, 4), wn, n - wn, round(edge, 4)]
    since = min((r.get('since') or 1e18) for r in ws.values()) if ws else None
    out = dict(built=int(time.time()), since=since, combos=combos, traders=traders)
    json.dump(out, open(PATH, 'w'), separators=(',', ':'))
    return out


if __name__ == '__main__':
    import combos as C
    o = build(start_budget=1800)
    rows = sorted(o['combos'].items(), key=lambda kv: -(kv[1][4] / (kv[1][0] + 40)))
    print('combos', len(rows), 'traders', len(o['traders']))
    f = lambda v: f"{v[2]}-{v[3]} n={v[0]} roi={100*v[1]/max(v[0],1):+.1f}% edge={100*v[4]/max(v[0],1):+.1f}c"
    for cid, v in rows[:30]:
        print(f"{C.label(C.parse_id(cid)):58s} {f(v)}")
    print('...worst')
    for cid, v in rows[-10:]:
        print(f"{C.label(C.parse_id(cid)):58s} {f(v)}")

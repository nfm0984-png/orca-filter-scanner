#!/usr/bin/env python3
"""Orca Filter Scanner run: refresh filter-combo leaderboards -> pull members' open sports positions -> build picks,
record which combos surfaced each pick -> grade settled picks -> learn per-combo / per-trader / per-factor records -> rank.
Writes ../data.json (plaintext; the workflow encrypts it before commit) and state/*.json."""
import json, os, sys, time, math, datetime as dt, argparse
from concurrent.futures import ThreadPoolExecutor
import combos as C, boards, settled, seed, model
from lib import (min_cost, open_positions, gamma_markets, league_of_slug, sport_of, bet_kind, jl, iso_ts, fmt_pt, flat_roi,
                 MIN_COST, PX_MIN, PX_MAX, PT, HERE)

ap = argparse.ArgumentParser()
ap.add_argument('--board-age', type=int, default=1700)   # refresh each combo about every other run
ap.add_argument('--settled-budget', type=int, default=240)
ap.add_argument('--pos-workers', type=int, default=12)
A = ap.parse_args()
T0 = time.time(); NOW = int(T0)
ROOT = os.path.join(HERE, '..')
STATE = os.path.join(ROOT, 'state')
LEDGER = os.path.join(STATE, 'picks.json')
SEED_SINCE = 1794182400  # 2026-11-09 00:00 UTC (day after the real P&L boards' as-of date)


def jload(p, d):
    try:
        return json.load(open(p))
    except Exception:
        return d


# ---------- 1. filter-combo leaderboards ----------
B = boards.refresh(max_age=A.board_age)
M = boards.members(B)
print(f"universe: {len(M)} wallets from {len(B['combos'])} combos", flush=True)

# ---------- 2. settled bets (incremental) + backtest seed ----------
S = settled.refresh(list(M), SEED_SINCE, max_age=8 * 3600, budget_s=A.settled_budget)
SEED = seed.build(B, S)

# ---------- 3. open positions of every surfaced wallet ----------
now_pt = dt.datetime.fromtimestamp(NOW, PT)
today = now_pt.date()
late_night = now_pt.hour >= 19
win_days = {today + dt.timedelta(days=1)} | ({today} if True else set())
ok_dates = {(today + dt.timedelta(days=d)).isoformat() for d in (-1, 0, 1, 2, 3)}
wallets = list(M)
t1 = time.time()
with ThreadPoolExecutor(max_workers=A.pos_workers) as ex:
    POS = dict(zip(wallets, ex.map(open_positions, wallets)))
print(f"positions: {sum(1 for v in POS.values() if v is not None)}/{len(wallets)} wallets in {time.time()-t1:.0f}s", flush=True)

cand = {}  # cid -> oi -> list of backers
names = {}
for w, ps in POS.items():
    if not ps:
        continue
    bym = {}
    for x in ps:
        slug = x.get('slug') or ''
        ev = x.get('event_slug') or slug
        if not league_of_slug(ev):
            continue
        dpart = ev[-10:] if len(ev) >= 10 else ''
        import re as _re
        mm = _re.search(r'(20\d\d-\d\d-\d\d)', slug)
        if not mm or mm.group(1) not in ok_dates:
            continue
        try:
            avg = float(x.get('avg_price') or 0); size = float(x.get('current_size') or 0)
        except (TypeError, ValueError):
            continue
        cost = avg * size
        if cost <= 0:
            continue
        cid = (x.get('condition_id') or '').lower()
        oi = int(x.get('outcome_index') or 0)
        bym.setdefault(cid, {})[oi] = dict(cost=cost, avg=avg, x=x)
    for cid, sides in bym.items():
        oi, s = max(sides.items(), key=lambda kv: kv[1]['cost'])  # hedgers: bigger side only
        if s['cost'] < min_cost(M[w]['row'].get('avg')):
            continue
        if s['x'].get('name') and not s['x']['name'].startswith('0x'):
            names[w] = s['x']['name'][:30]
        cand.setdefault(cid, {}).setdefault(oi, []).append(dict(wallet=w, cost=round(s['cost']), avg=round(s['avg'], 4), x=s['x']))
print(f"candidate markets: {len(cand)}", flush=True)

GM = gamma_markets(list(cand))
print(f"gamma: {len(GM)}/{len(cand)} markets", flush=True)

# conviction clusters (3+ smart wallets on one side of an event) -> pick-level signal
CLUSTER = set()
try:
    from orca import orca as _orca
    _cd = _orca('/api/v2/conviction-clusters', {'min_whales': 3, 'limit': 200}, tries=2) or {}
    for _c in _cd.get('clusters') or []:
        if league_of_slug(_c.get('event_slug') or ''):
            CLUSTER.add(((_c.get('event_slug') or '').lower(), (_c.get('side') or '').upper()))
except Exception as _e:
    print('clusters failed', _e, flush=True)
print(f"conviction clusters (sports): {len(CLUSTER)}", flush=True)

def nm(w):
    n = M[w]['row'].get('name') or ''
    return names.get(w) or (n if n and not n.startswith('0x') else None) or (w[:6] + '…' + w[-4:])


ledger = jload(LEDGER, {'picks': {}})
LP = ledger['picks']
live_now = []
for cid, sides in cand.items():
    g = GM.get(cid)
    if not g or g.get('closed'):
        continue
    start = iso_ts(g.get('gameStartTime')) or iso_ts(g.get('endDate'))
    if not start or start < NOW - 4 * 3600 or start > NOW + 80 * 3600:
        continue
    outs = jl(g.get('outcomes'), []) or []
    pxs = [float(p) for p in (jl(g.get('outcomePrices'), []) or [])]
    tot = {oi: sum(b['cost'] for b in bs) for oi, bs in sides.items()}
    for oi, bs in sides.items():
        cur = pxs[oi] if oi < len(pxs) else None
        if cur is None:
            continue
        cost = sum(b['cost'] for b in bs)
        entry = sum(b['cost'] * b['avg'] for b in bs) / cost
        opp = sum(v for k, v in tot.items() if k != oi)
        x0 = bs[0]['x']
        pid = f"{cid}:{oi}"
        combos_ = {c for b in bs for c in M[b['wallet']]['combos']}
        _side = 'YES' if oi == 0 else 'NO'
        if (str(x0.get('event_slug') or '').lower(), _side) in CLUSTER or (str(x0.get('event_slug') or '').lower(), str(x0.get('outcome') or '').upper()) in CLUSTER:
            combos_.add('SIG|cluster')
        combos_ = sorted(combos_)
        backers = sorted([dict(wallet=b['wallet'], name=nm(b['wallet']), cost=b['cost'], avg=b['avg'],
                               combos=len(M[b['wallet']]['combos'])) for b in bs], key=lambda b: -b['cost'])
        lp = LP.get(pid)
        if lp is None:
            lp = LP[pid] = dict(id=pid, added=NOW, addPx=cur, q=g.get('question') or x0.get('title'), outcome=outs[oi] if oi < len(outs) else x0.get('outcome'),
                                slug=g.get('slug') or x0.get('slug'), event=x0.get('event_slug'), start=start,
                                league=league_of_slug(x0.get('event_slug') or ''), kind=bet_kind(x0.get('slug')),
                                timing=model.time_bucket(NOW, start), move0=model.move_bucket(entry, cur), entry0=round(entry, 4),
                                combos=[], backers={})
        if start > NOW:
            lp['timing'] = lp['timing'] if lp['timing'] == 'live' else model.time_bucket(lp['added'], start)
        lp['start'] = start
        lp['combos'] = sorted(set(lp['combos']) | set(combos_)) if start > NOW or not lp['combos'] else lp['combos']
        for b in backers:
            if start > NOW or b['wallet'] in lp['backers'] or not lp['backers']:
                lp['backers'][b['wallet']] = [b['name'], b['cost'], b['avg']]
        lp['last'] = NOW; lp['cur'] = cur
        live_now.append(dict(id=pid, cid=cid, oi=oi, cur=cur, entry=round(entry, 4), cost=round(cost), oppCost=round(opp),
                             combos=combos_, backers=backers, start=start, lp=lp))

# ---------- 4. grade settled ledger picks ----------
todo = [p for p in LP.values() if not p.get('res') and p['start'] < NOW - 2 * 3600]
if todo:
    G2 = gamma_markets([p['id'].split(':')[0] for p in todo])
    for p in todo:
        g = G2.get(p['id'].split(':')[0])
        if not g or not g.get('closed'):
            continue
        pxs = [float(v) for v in (jl(g.get('outcomePrices'), []) or [])]
        oi = int(p['id'].split(':')[1])
        if oi >= len(pxs):
            continue
        v = pxs[oi]
        p['res'] = 'W' if v >= 0.99 else 'L' if v <= 0.01 else 'P' if abs(v - 0.5) < 0.02 else None
        if p['res']:
            p['graded'] = NOW
for p in list(LP.values()):  # keep 60 days
    if p['start'] < NOW - 60 * 86400:
        LP.pop(p['id'], None)

# ---------- 5. live records from the scanner's own graded picks ----------
clive, tlive, flive = {}, {}, {}
def add(d, k, r, e):
    a = d.setdefault(k, [0, 0.0, 0, 0, 0.0]); a[0] += 1; a[1] += r; a[2] += r > 0; a[3] += r < 0; a[4] += e
graded = [p for p in LP.values() if p.get('res') in ('W', 'L') and PX_MIN <= (p.get('addPx') or 0) <= PX_MAX]
for p in graded:
    r = flat_roi(p['res'], p['addPx']); e_ = (p['res'] == 'W') - p['addPx']
    for c in p['combos']:
        add(clive, c, r, e_)
    for w in p['backers']:
        add(tlive, w, r, e_)
    for f in ('move:' + p.get('move0', 'flat'), 'time:' + p.get('timing', '1-6h'), 'kind:' + p.get('kind', 'other')):
        add(flive, f, r, e_)
pair = lambda d: {k: (v[0], v[4]) for k, v in d.items()}
cseed = {k: (v[0], v[4]) for k, v in SEED['combos'].items()}
tseed = {k: (v[0], v[4]) for k, v in SEED['traders'].items()}

# ---------- 6. score + split into Ranked / Coming Up ----------
win_end_date = today + dt.timedelta(days=1) if late_night else today
picks = []
for c in live_now:
    lp = c['lp']
    if not (PX_MIN <= c['cur'] <= PX_MAX):
        continue
    pk = dict(combos=c['combos'], backers=c['backers'], move=model.move_bucket(c['entry'], c['cur']),
              timing='live' if c['start'] <= NOW else model.time_bucket(lp['added'], c['start']), kind=lp['kind'], cost=c['cost'], oppCost=c['oppCost'])
    s, why = model.score(pk, cseed, pair(clive), tseed, pair(tlive), pair(flive))
    sd = dt.datetime.fromtimestamp(c['start'], PT).date()
    tab = 'ranked' if sd <= win_end_date else 'coming'
    tb = []
    for b in c['backers'][:6]:
        e, n = model.trader_est(b['wallet'], tseed, pair(tlive))
        sr = SEED['traders'].get(b['wallet']); lr = tlive.get(b['wallet'])
        rec = [0, 0.0, 0, 0]
        for r_ in (sr, lr):
            if r_:
                rec = [rec[0] + r_[0], rec[1] + r_[1], rec[2] + r_[2], rec[3] + r_[3]]
        # (roi shown; ranking uses edge)
        tb.append(dict(b, est=round(e, 4), w=rec[2], l=rec[3], roi=round(rec[1] / rec[0], 4) if rec[0] else None))
    picks.append(dict(id=c['id'], tab=tab, score=round(s, 4), roiEst=round(s / c['cur'], 4), why=why, q=lp['q'], outcome=lp['outcome'], league=lp['league'],
                      sport=sport_of(lp['league']), kind=lp['kind'], start=c['start'], startPT=fmt_pt(c['start']), live=c['start'] <= NOW,
                      price=c['cur'], entry=c['entry'], move=pk['move'], timing=pk['timing'], cost=c['cost'], oppCost=c['oppCost'],
                      nCombos=len(c['combos']), backers=tb, nBackers=len(c['backers']), added=lp['added'], addedPT=fmt_pt(lp['added']),
                      url=f"https://polymarket.com/event/{lp.get('event') or ''}", addPx=lp['addPx'], combos=list(c['combos'])))
# one side per market: keep the better-scored side, note the other
best = {}
for p in picks:
    cid_ = p['id'].split(':')[0]
    if cid_ not in best or p['score'] > best[cid_]['score']:
        best[cid_] = p
for p in picks:
    b_ = best[p['id'].split(':')[0]]
    if b_ is not p:
        b_['oppScore'] = p['score']; b_['oppBackers'] = p['nBackers']
picks = list(best.values())
picks.sort(key=lambda p: (p['live'], -p['score']))
ranked = [p for p in picks if p['tab'] == 'ranked']
coming = sorted([p for p in picks if p['tab'] == 'coming'], key=lambda p: (p['start'], -p['score']))
for i, p in enumerate(ranked):
    p['rank'] = i + 1

# ---------- 7. Best Filters / Best Cappers tables ----------
def rec_row(seedr, liver):
    sr = seedr or [0, 0.0, 0, 0, 0.0]; lr = liver or [0, 0.0, 0, 0, 0.0]
    return dict(seedEdge=round(sr[4] / sr[0], 4) if sr[0] else None, liveEdge=round(lr[4] / lr[0], 4) if lr[0] else None,
                seedN=sr[0], seedW=sr[2], seedL=sr[3], seedRoi=round(sr[1] / sr[0], 4) if sr[0] else None,
                liveN=lr[0], liveW=lr[2], liveL=lr[3], liveRoi=round(lr[1] / lr[0], 4) if lr[0] else None)
filters = []
for cid in list(B['combos']) + ['SIG|cluster']:
    e, neff = model.combo_est(cid, cseed, pair(clive))
    c = C.parse_id(cid)
    filters.append(dict(id=cid, label=C.label(c), url=C.site_url(c), est=round(e, 4), neff=round(neff), size=len((B['combos'].get(cid) or {}).get('rows') or []),
                        onBoard=sum(1 for p in ranked if cid in p['why'] and False) or sum(1 for p in live_now if cid in p['combos']),
                        **rec_row(SEED['combos'].get(cid), clive.get(cid))))
filters.sort(key=lambda f: -f['est'])
for i, f in enumerate(filters):
    f['rank'] = i + 1
# Filter tabs (Noel Nov 24): one site tab per top-5 filter by learned edge, holding every open pick
# that filter surfaced. Today's window first (pre-game, then LIVE), then later games soonest first.
FILTER_TABS_N, FILTER_TAB_PICKS = 5, 40
filter_tabs = []
for f in filters[:FILTER_TABS_N]:
    mine = [p for p in picks if f['id'] in p['combos']]
    today_ = sorted([p for p in mine if p['tab'] == 'ranked'], key=lambda p: (p['live'], -p['score']))
    later_ = sorted([p for p in mine if p['tab'] == 'coming'], key=lambda p: (p['start'], -p['score']))
    rows = []
    for i, p in enumerate((today_ + later_)[:FILTER_TAB_PICKS]):
        q = {k: v for k, v in p.items() if k != 'combos'}
        q['rank'] = i + 1
        rows.append(q)
    filter_tabs.append(dict(id=f['id'], rank=f['rank'], label=f['label'], url=f['url'], est=f['est'],
                            seedN=f['seedN'], seedW=f['seedW'], seedL=f['seedL'], seedRoi=f['seedRoi'],
                            liveN=f['liveN'], liveW=f['liveW'], liveL=f['liveL'], liveRoi=f['liveRoi'],
                            nToday=len(today_), nLater=len(later_), picks=rows))
for p in picks:
    p.pop('combos', None)
cappers = []
for w, m in M.items():
    sr = SEED['traders'].get(w); lr = tlive.get(w)
    if not sr and not lr:
        continue
    e, neff = model.trader_est(w, tseed, pair(tlive))
    row = m['row']
    cappers.append(dict(wallet=w, name=nm(w), est=round(e, 4), neff=round(neff), combos=len(m['combos']),
                        topCombos=sorted(m['combos'], key=lambda c: m['ranks'][c])[:3], pnl=row.get('pnl'), wrLife=row.get('wr'), skill=row.get('skill'),
                        openPicks=sum(1 for p in live_now if any(b['wallet'] == w for b in p['backers'])), **rec_row(sr, lr)))
cappers.sort(key=lambda c: -c['est'])
cappers = cappers[:150]
for i, c in enumerate(cappers):
    c['rank'] = i + 1
factors = []
for f, (pr, pn) in model.FACTOR_PRIORS.items():
    e, neff = model.factor_est(f, pair(flive))
    lr = flive.get(f) or [0, 0.0, 0, 0, 0.0]
    factors.append(dict(id=f, prior=pr, priorN=pn, est=round(e, 4), liveN=lr[0], liveW=lr[2], liveL=lr[3], liveRoi=round(lr[1] / lr[0], 4) if lr[0] else None))

recent = sorted([p for p in LP.values() if p.get('res')], key=lambda p: -p.get('graded', 0))[:60]
tot_g = [p for p in graded]
data = dict(ts=NOW, updatedPT=fmt_pt(NOW), window=f"games on {today.strftime('%a %b %-d')}" + (f" + {(today + dt.timedelta(days=1)).strftime('%a %b %-d')} (after 7 PM PT)" if late_night else ''),
            ranked=ranked[:60], coming=coming[:60], filters=filters, filterTabs=filter_tabs, cappers=cappers, factors=factors,
            record=dict(n=len(tot_g), w=sum(p['res'] == 'W' for p in tot_g), l=sum(p['res'] == 'L' for p in tot_g),
                        roi=round(sum(flat_roi(p['res'], p['addPx']) for p in tot_g) / len(tot_g), 4) if tot_g else None),
            recent=[dict(q=p['q'], outcome=p['outcome'], res=p['res'], addPx=p['addPx'], addedPT=fmt_pt(p['added']), startPT=fmt_pt(p['start'])) for p in recent],
            seed=dict(since=SEED.get('since'), sincePT=fmt_pt(SEED['since']) if SEED.get('since') else None, traders=len(SEED['traders']),
                      bets=sum(v[0] for v in SEED['traders'].values())),
            meta=dict(combos=len(B['combos']), wallets=len(M), positionsOk=sum(1 for v in POS.values() if v is not None), candidates=len(cand),
                      secs=round(time.time() - T0), lenses={k: v[0] for k, v in C.LENSES.items()}, periods=C.PERIODS, sorts=C.SORT_LABEL))
json.dump(ledger, open(LEDGER, 'w'), separators=(',', ':'))
json.dump(data, open(os.path.join(ROOT, 'data.json'), 'w'), separators=(',', ':'))
print(f"done: ranked {len(ranked)}, coming {len(coming)}, ledger {len(LP)} ({len(graded)} graded), {time.time()-T0:.0f}s", flush=True)

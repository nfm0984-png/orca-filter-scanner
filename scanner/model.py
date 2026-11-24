"""The learner. Every pick is scored by the shrunk, track-record-weighted ROI of
  (a) the filter combos that surfaced its backers, (b) the backers themselves, (c) pick factors (price move, timing, bet type).
The learned quantity is EDGE per pick = result (1 win / 0 loss) - price paid, in probability points (cents per $1 payout).
Edge has bounded variance, so one 10c longshot hit can't swamp the record the way flat-ROI would. ROI = edge / price.
Evidence sources, each a (n, edge_sum) pair:
  live  : the scanner's own graded picks (honest, forward-only)          weight 1.0
  seed  : backtest of current combo members' settled bets               weight 0.15 (in-sample: members are picked with
          hindsight), except real-P&L-board bands, whose bets all come after the board's as-of date: weight 0.6
  prior : research priors (Nov 23 audit of 1,700 graded scanner picks) as pseudo-observations
Estimate = (prior_n*prior_roi + w_seed*seed_sum + live_sum) / (prior_n + w_seed*seed_n + live_n + K)
K shrinks every estimate toward 0, so a 4-1 combo never outranks a proven 120-90 one."""
import math
import combos as C

K_COMBO, K_TRADER, K_FACTOR = 40.0, 25.0, 30.0
W_SEED, W_SEED_PNL = 0.15, 0.6

# Research priors: (roi, pseudo-n)
# (edge, pseudo-n); research ROI converted to edge at a ~0.55 typical price
COMBO_PRIORS = {
    'PnL30d|rank|1-50': (-0.05, 100), 'PnL30d|rank|51-200': (-0.04, 70),
    'PnL30d|rank|201-500': (0.10, 50), 'PnL30d|rank|501-1000': (0.055, 40),
}
FACTOR_PRIORS = {
    'move:fading': (-0.10, 130),   # price 5c+ below capper entry: Poly 89-185 -19.3%, Kalshi -41.5%
    'move:late': (0.0, 40),         # paying 5c+ over the capper: label only (downranking hurt top 3)
    'move:flat': (0.0, 40),
    'time:live': (0.0, 40),         # added after start: tagged LIVE, learns its own record
    'time:6h+': (-0.06, 60),        # added 6h+ before start: -13.6% / -9.1%
    'time:1-6h': (0.0, 40), 'time:<1h': (0.0, 40),
    'kind:moneyline': (0.01, 40), 'kind:spread': (-0.015, 40), 'kind:total': (-0.015, 40),
    'kind:draw': (0.0, 30), 'kind:other': (0.0, 30),
}


def est(prior, seed, live, k, w_seed):
    pr, pn = prior
    sn, ss = seed or (0, 0.0)
    ln, ls = live or (0, 0.0)
    return (pn * pr + w_seed * ss + ls) / (pn + w_seed * sn + ln + k), pn + w_seed * sn + ln


def combo_est(cid, seed, live):
    return est(COMBO_PRIORS.get(cid, (0.0, 0)), seed.get(cid), live.get(cid), K_COMBO, W_SEED_PNL if cid.startswith('PnL') else W_SEED)


def trader_est(w, seed, live):
    return est((0.0, 0), seed.get(w), live.get(w), K_TRADER, 0.5)


def factor_est(f, live):
    return est(FACTOR_PRIORS.get(f, (0.0, 20)), None, live.get(f), K_FACTOR, 0)


def move_bucket(entry, cur):
    if entry is None or cur is None:
        return 'flat'
    if cur <= entry - 0.05:
        return 'fading'
    if cur >= entry + 0.05:
        return 'late'
    return 'flat'


def time_bucket(added_ts, start_ts):
    if not start_ts:
        return '1-6h'
    d = start_ts - added_ts
    if d < 0:
        return 'live'
    if d < 3600:
        return '<1h'
    if d < 6 * 3600:
        return '1-6h'
    return '6h+'


def score(pick, cseed, clive, tseed, tlive, flive):
    ce = sorted(((combo_est(c, cseed, clive), c) for c in pick['combos']), key=lambda x: -x[0][0])
    top = ce[:3]
    e_combo = sum(x[0][0] for x in top) / len(top) if top else 0.0
    te = sorted(((trader_est(b['wallet'], tseed, tlive), b['wallet']) for b in pick['backers']), key=lambda x: -x[0][0])
    e_trader = te[0][0][0] if te else 0.0
    facs = ['move:' + pick['move'], 'time:' + pick['timing'], 'kind:' + pick['kind']]
    e_fac = sum(factor_est(f, flive)[0] for f in facs)
    breadth = 0.005 * math.log2(1 + len(pick['combos']))
    conflict = -0.015 if pick.get('oppCost', 0) > pick.get('cost', 0) else 0.0
    s = 0.45 * e_combo + 0.45 * e_trader + e_fac + breadth + conflict
    return s, dict(combo=round(e_combo, 4), trader=round(e_trader, 4), factors=round(e_fac, 4), breadth=round(breadth, 4),
                   conflict=conflict, topCombos=[dict(id=c, est=round(v[0], 4), n=round(v[1])) for v, c in top])

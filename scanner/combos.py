"""OrcaLayer leaderboard filter combos ("lenses") the Orca Filter Scanner tests.

Every option below comes from orcalayer.com/leaderboard (its page code calls GET /api/leaderboard):
  period   : 24h | 7d | 30d | All Time  (an activity window: who traded in that window; the stats shown are lifetime)
  category : All | Crypto | Geopolitics | Sports | Esports | Politics | Economics | Tech/AI | Culture | Weather
  sort     : pnl | win_rate | profit_factor | volume | roi | markets | mint_volume   (dir desc|asc)
  smart    : Smart Money only (filter=smart) or all wallets (filter=all); skill=1 = strict Skill badge
  style    : maker | inplay | fast | none | lp       habit: favorites | holds | ...   under_radar=1
  hide     : farmers | sports | crypto | bots
  number filters: min_wr, min_pnl, min_markets (default 10), min_profit_factor, min_conc (category share 0/50/70/90),
                  min_roi, max_active (10/20/50/100), hold_bucket (lt1h|1h1d|1d7d|7dplus),
                  avg size (50-500 | 500-5000 | 5000-50000 | 50000+), min_volume
  presets  : Niche specialist (conc 70, active<=20, WR 60+), Copyable scale (avg $50-500, ROI 25+),
             Conviction holder (hold 7d+, PF 2+), Classic whale (P&L $1M+, volume $10M+)
The scanner uses category Sports (and Esports for presets) with farmers and bots hidden: 8 presets x 4 periods x 6 sorts,\nplus ~40 floor/ceiling/style/habit variants and the Esports presets at period {7d, All} x sort {P&L, ROI}.
"""
import urllib.parse

PERIODS = ['24h', '7d', '30d', 'All Time']
PERIOD_SHORT = {'24h': '24h', '7d': '7d', '30d': '30d', 'All Time': 'All'}
SORTS = {  # site sort key -> API sort key
    'pnl': 'total_pnl', 'roi': 'roi', 'win_rate': 'win_rate', 'profit_factor': 'profit_factor',
    'volume': 'total_volume', 'markets': 'resolved_markets',
}
SORT_LABEL = {'pnl': 'P&L', 'roi': 'ROI', 'win_rate': 'Win rate', 'profit_factor': 'Profit factor', 'volume': 'Volume', 'markets': 'Markets'}
CATS = {'S': ('SPORTS', 'Sports'), 'E': ('ESPORTS', 'Esports')}


def L(label, api, url):
    return (label, api, url)


# lens key -> (label, API params, site URL params). Smart only (WR>=55%, P&L>0, 10+ markets, no farmers) is on unless filter=all.
PRESETS = {  # crossed with every period x sort on Sports, and period {7d, All} x sort {P&L, ROI} on Esports
    'base':   L('Smart money', {}, {}),
    'proven': L('Proven only', {'skill': '1'}, {'skill': '1'}),
    'spec':   L('Niche specialist', {'min_conc': '70', 'max_active': '20', 'min_wr': '60'}, {'conc': '70', 'maxact': '20', 'minwr': '60'}),
    'retail': L('Copyable scale', {'min_avg_size': '50', 'max_avg_size': '500', 'min_roi': '25'}, {'avgsz': '50-500', 'minroi': '25'}),
    'conv':   L('Conviction holder', {'hold_bucket': '7dplus', 'min_profit_factor': '2'}, {'hold': '7dplus', 'minpf': '2'}),
    'whale':  L('Classic whale', {'min_pnl': '1000000', 'min_volume': '10000000'}, {'minpnl': '1000000', 'minvol': '10000000'}),
    'radar':  L('Under the radar', {'under_radar': '1', 'filter': 'all'}, {'radar': '1', 'smart': '0'}),
    'all':    L('All wallets (Smart off)', {'filter': 'all'}, {'smart': '0'}),
}
VARIANTS = {  # Sports only, period {7d, All} x sort {P&L, ROI}
    # small-account focus: Copyable scale / Niche specialist with extra floors
    'retail+proven': L('Copyable scale + Proven', {'min_avg_size': '50', 'max_avg_size': '500', 'min_roi': '25', 'skill': '1'}, {'avgsz': '50-500', 'minroi': '25', 'skill': '1'}),
    'retail+wr60':   L('Copyable scale + WR 60%+', {'min_avg_size': '50', 'max_avg_size': '500', 'min_roi': '25', 'min_wr': '60'}, {'avgsz': '50-500', 'minroi': '25', 'minwr': '60'}),
    'retail+mk100':  L('Copyable scale + 100 mkts', {'min_avg_size': '50', 'max_avg_size': '500', 'min_roi': '25', 'min_markets': '100'}, {'avgsz': '50-500', 'minroi': '25', 'minmkt': '100'}),
    'retail+roi10':  L('Avg $50-500 + ROI 10%+', {'min_avg_size': '50', 'max_avg_size': '500', 'min_roi': '10'}, {'avgsz': '50-500', 'minroi': '10'}),
    'spec+proven':   L('Niche specialist + Proven', {'min_conc': '70', 'max_active': '20', 'min_wr': '60', 'skill': '1'}, {'conc': '70', 'maxact': '20', 'minwr': '60', 'skill': '1'}),
    'spec+mk100':    L('Niche specialist + 100 mkts', {'min_conc': '70', 'max_active': '20', 'min_wr': '60', 'min_markets': '100'}, {'conc': '70', 'maxact': '20', 'minwr': '60', 'minmkt': '100'}),
    'spec90':        L('90% Sports, <=50 active', {'min_conc': '90', 'max_active': '50'}, {'conc': '90', 'maxact': '50'}),
    'conv+sports':   L('Hold 1d-7d + PF 1.5x', {'hold_bucket': '1d7d', 'min_profit_factor': '1.5'}, {'hold': '1d7d', 'minpf': '1.5'}),
    # floors
    'wr60': L('Min WR 60%', {'min_wr': '60'}, {'minwr': '60'}), 'wr65': L('Min WR 65%', {'min_wr': '65'}, {'minwr': '65'}),
    'wr70': L('Min WR 70%', {'min_wr': '70'}, {'minwr': '70'}), 'wr80': L('Min WR 80%', {'min_wr': '80'}, {'minwr': '80'}),
    'pnl10k': L('Min P&L $10K', {'min_pnl': '10000'}, {'minpnl': '10000'}), 'pnl100k': L('Min P&L $100K', {'min_pnl': '100000'}, {'minpnl': '100000'}),
    'pnl1m': L('Min P&L $1M', {'min_pnl': '1000000'}, {'minpnl': '1000000'}),
    'roi5': L('Min ROI 5%', {'min_roi': '5'}, {'minroi': '5'}), 'roi25': L('Min ROI 25%', {'min_roi': '25'}, {'minroi': '25'}),
    'roi100': L('Min ROI 100%', {'min_roi': '100'}, {'minroi': '100'}),
    'mk100': L('Min 100 markets', {'min_markets': '100'}, {'minmkt': '100'}), 'mk500': L('Min 500 markets', {'min_markets': '500'}, {'minmkt': '500'}),
    'mk1000': L('Min 1000 markets', {'min_markets': '1000'}, {'minmkt': '1000'}),
    'pf15': L('Min PF 1.5x', {'min_profit_factor': '1.5'}, {'minpf': '1.5'}), 'pf2': L('Min PF 2x', {'min_profit_factor': '2'}, {'minpf': '2'}),
    'pf3': L('Min PF 3x', {'min_profit_factor': '3'}, {'minpf': '3'}),
    'sharp': L('WR 55+ PF 1.3+ 50 mkts', {'min_wr': '55', 'min_profit_factor': '1.3', 'min_markets': '50'}, {'minwr': '55', 'minpf': '1.3', 'minmkt': '50'}),
    # ceilings
    'act10': L('Max 10 active', {'max_active': '10'}, {'maxact': '10'}), 'act50': L('Max 50 active', {'max_active': '50'}, {'maxact': '50'}),
    # hold / size
    'hold1h': L('Holds <1h', {'hold_bucket': 'lt1h'}, {'hold': 'lt1h'}), 'hold1d': L('Holds 1h-1d', {'hold_bucket': '1h1d'}, {'hold': '1h1d'}),
    'hold7d': L('Holds 1d-7d', {'hold_bucket': '1d7d'}, {'hold': '1d7d'}),
    'avg500': L('Avg bet $500-5K', {'min_avg_size': '500', 'max_avg_size': '5000'}, {'avgsz': '500-5000'}),
    'avg5k': L('Avg bet $5K-50K', {'min_avg_size': '5000', 'max_avg_size': '50000'}, {'avgsz': '5000-50000'}),
    'avg50k': L('Avg bet $50K+', {'min_avg_size': '50000'}, {'avgsz': '50000+'}),
    # style / habit
    'maker': L('Style: Maker', {'style': 'maker'}, {'style': 'maker'}), 'inplay': L('Style: In-play', {'style': 'inplay'}, {'style': 'inplay'}),
    'fast': L('Style: Fast', {'style': 'fast'}, {'style': 'fast'}), 'nostyle': L('Style: None of these', {'style': 'none'}, {'style': 'none'}),
    'lp': L('Liquidity provider', {'lp': '1'}, {'style': 'lp'}),
    'fav': L('Habit: Buys favorites', {'habit': 'favorites'}, {'habit': 'favorites'}),
    'holds': L('Habit: Holds to resolution', {'habit': 'holds'}, {'habit': 'holds'}),
    'exits': L('Habit: Exits early', {'habit': 'exits'}, {'habit': 'exits'}),
}
LENSES = {**PRESETS, **VARIANTS}
PRIORITY = {'retail', 'spec', 'retail+proven', 'retail+wr60', 'retail+mk100', 'retail+roi10', 'spec+proven', 'spec+mk100'}  # refreshed every run
TOP_N = 25  # a wallet "is surfaced by" a combo when it is in that combo's top 25


def combo_id(cat, period, sort, lens):
    return f"{cat}|{PERIOD_SHORT[period]}|{sort}|{lens}"


def all_combos():
    out = []
    for p in PERIODS:
        for s in SORTS:
            for l in PRESETS:
                out.append(dict(id=combo_id('S', p, s, l), cat='S', period=p, sort=s, lens=l))
    for p in ('7d', 'All Time'):
        for s in ('pnl', 'roi'):
            for l in VARIANTS:
                out.append(dict(id=combo_id('S', p, s, l), cat='S', period=p, sort=s, lens=l))
            for l in PRESETS:
                out.append(dict(id=combo_id('E', p, s, l), cat='E', period=p, sort=s, lens=l))
    return out


def api_params(c, page=1, limit=TOP_N):
    lab, extra, _ = LENSES[c['lens']]
    p = dict(sort=SORTS[c['sort']], sort_dir='desc', filter='smart', page=page, hide_farmers='true', hide_sports='false',
             hide_crypto='false', hide_bots='true', period=c['period'], min_wr='0', min_pnl='0', min_markets='10',
             min_profit_factor='0', category=CATS[c['cat']][0], limit=limit)
    p.update(extra)
    return p


# Real windowed P&L boards (OrcaLayer /api/v2/business/pnl-leaderboard, window 7|30), split by rank band.
# Research prior (Nov 23): 30-day top 50 backers went -8.9%, ranks 201-1000 went +10% to +19%.
PNL_BANDS = [(1, 50), (51, 200), (201, 500), (501, 1000)]
PNL_WINDOWS = [30, 7]


def pnl_combo_id(window, lo, hi):
    return f"PnL{window}d|rank|{lo}-{hi}"


def pnl_combos():
    return [dict(id=pnl_combo_id(w, lo, hi), window=w, lo=lo, hi=hi, kind='pnl') for w in PNL_WINDOWS for lo, hi in PNL_BANDS]


# Other OrcaLayer signal sources (API, no login), graded like filter combos
SIGNALS = {
    'SIG|alerts|SPORTS': ('Whale Alerts: smart-money Sports buys, last 6h', 'https://orcalayer.com/alerts'),
    'SIG|alerts|ESPORTS': ('Whale Alerts: smart-money Esports buys, last 6h', 'https://orcalayer.com/alerts'),
    'SIG|hot24h|winners': ('Hot traders: biggest 24h winners', 'https://orcalayer.com/'),
    'SIG|cluster': ('Conviction cluster: 3+ smart wallets same side', 'https://orcalayer.com/markets'),
}


def label(c):
    if c['id'] in SIGNALS:
        return SIGNALS[c['id']][0]
    if c.get('kind') == 'pnl' or c['id'].startswith('PnL'):
        c = c if c.get('kind') == 'pnl' else parse_id(c['id'])
        return f"Real {c['window']}-day P&L board · rank {c['lo']}-{c['hi']}"
    return f"{CATS[c['cat']][1]} · {PERIOD_SHORT[c['period']]} · {SORT_LABEL[c['sort']]} · {LENSES[c['lens']][0]}"


def site_url(c):
    if c['id'] in SIGNALS:
        return SIGNALS[c['id']][1]
    if c['id'].startswith('PnL'):
        return 'https://orcalayer.com/developers#window-pnl'
    q = {'category': CATS[c['cat']][1], 'nofarm': '1', 'nobot': '1'}
    if c['period'] != 'All Time':
        q['period'] = c['period']
    if c['sort'] != 'pnl':
        q['sort'] = c['sort']
    q.update(LENSES[c['lens']][2])
    return 'https://orcalayer.com/leaderboard?' + urllib.parse.urlencode(q)


def parse_id(cid):
    if cid in SIGNALS:
        return dict(id=cid, kind='sig')
    if cid.startswith('PnL'):
        w = int(cid[3:cid.index('d')]); lo, hi = map(int, cid.split('|')[2].split('-'))
        return dict(id=cid, window=w, lo=lo, hi=hi, kind='pnl')
    cat, ps, s, l = cid.split('|')
    p = {v: k for k, v in PERIOD_SHORT.items()}[ps]
    return dict(id=cid, cat=cat, period=p, sort=s, lens=l)

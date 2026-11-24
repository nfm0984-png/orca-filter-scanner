"""Shared helpers: OrcaLayer leaderboard pulls, Polymarket Data API v2 positions, Gamma market lookups, sport parsing."""
import json, os, re, time, urllib.request, urllib.parse, urllib.error, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
import combos as C

HERE = os.path.dirname(os.path.abspath(__file__))
PT = ZoneInfo('America/Los_Angeles')
DATA_API = 'https://data-api.polymarket.com/v2'
GAMMA = 'https://gamma-api.polymarket.com'
MIN_COST = 500.0       # same $500 minimum the other scanners use ...
FETCH_MIN = 100.0      # ... except small-bankroll cappers (Copyable scale etc.), see min_cost()


def min_cost(avg_trade):
    """A wallet's conviction-bet floor: $500, or for small bettors 3x their average trade (never under $100)."""
    try:
        a = float(avg_trade or 0)
    except (TypeError, ValueError):
        a = 0
    return MIN_COST if a <= 0 else min(MIN_COST, max(FETCH_MIN, 3 * a))
PX_MIN, PX_MAX = 0.05, 0.95  # copyable price band (no 96c+ locks, no 4c lottery tickets)
SLUG_RE = re.compile(r'^([a-z][a-z0-9]{1,11})-(.+?)-(\d{4})-(\d{2})-(\d{2})(?:-(.*))?$')
NOT_SPORT = {'will', 'what', 'who', 'how', 'when', 'which', 'us', 'fed', 'btc', 'eth', 'sol', 'xrp', 'bitcoin', 'ethereum',
             'trump', 'election', 'presidential', 'highest', 'lowest', 'nyc', 'new', 'largest', 'top', 'elon', 'tweets', 'bank', 'doge'}


def get_json(url, tries=4, timeout=30):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'orca-filter-scanner/1.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get('Retry-After') or 2) + i); continue
            if e.code >= 500:
                time.sleep(1 + i); continue
            return None
        except Exception:
            time.sleep(1 + i)
    return None


def league_of_slug(slug):
    m = SLUG_RE.match(slug or '')
    if not m or m.group(1) in NOT_SPORT:
        return None
    return m.group(1).upper()


SPORT_EXACT = {
    'NBA': 'NBA', 'WNBA': 'WNBA', 'CBB': 'NCAAB', 'CWBB': 'NCAAB', 'NCAAB': 'NCAAB', 'NFL': 'NFL', 'CFB': 'NCAAF', 'NCAAF': 'NCAAF',
    'NHL': 'NHL', 'MLB': 'MLB', 'ATP': 'Tennis', 'WTA': 'Tennis', 'UFC': 'UFC/MMA', 'MMA': 'UFC/MMA',
    'CS2': 'Esports', 'CSGO': 'Esports', 'DOTA2': 'Esports', 'LOL': 'Esports', 'VAL': 'Esports',
    'EUROLEAGUE': 'Basketball', 'CRINT': 'Cricket', 'IPL': 'Cricket', 'CRIC': 'Cricket',
}


def sport_of(league):
    lg = (league or '').upper()
    if lg in SPORT_EXACT:
        return SPORT_EXACT[lg]
    if lg.startswith('BK'):
        return 'Basketball'
    if lg.startswith('CR'):
        return 'Cricket'
    if lg in ('KHL', 'AHL', 'SHL', 'DEL', 'LIIGA'):
        return 'Hockey'
    return 'Soccer'


def bet_kind(slug):
    m = SLUG_RE.match(slug or '')
    tail = (m.group(6) or '') if m else ''
    if not tail:
        return 'moneyline'
    if tail.startswith('spread'):
        return 'spread'
    if tail.startswith('total'):
        return 'total'
    if tail == 'draw':
        return 'draw'
    if re.fullmatch(r'[a-z0-9]+', tail):
        return 'moneyline'
    return 'other'


# ---------------- OrcaLayer leaderboard ----------------
def lb_row(r):
    return dict(wallet=r['wallet'].lower(), name=r.get('display_name') or r['wallet'][:8], pnl=round(r.get('total_pnl') or 0),
                wr=r.get('win_rate'), roi=r.get('roi'), pf=round(r.get('profit_factor') or 0, 2), mk=r.get('resolved_markets'),
                sp=r.get('sports_pct'), last=r.get('last_trade_ts'), avg=r.get('avg_trade_size'), skill=bool(r.get('skill_badge')))


def fetch_combo(c):
    from orca import orca
    d = orca('/api/leaderboard', C.api_params(c), tries=3, timeout=45)
    if not d or 'traders' not in d:
        return None
    return dict(ts=int(time.time()), total=d.get('total'), rows=[lb_row(r) for r in d['traders'][:C.TOP_N]])


# ---------------- Polymarket Data API v2 ----------------
def _pages(params, max_pages=6):
    out = []
    cur = None
    for _ in range(max_pages):
        p = dict(params)
        if cur:
            p['cursor'] = cur
        d = get_json(DATA_API + '/positions?' + urllib.parse.urlencode(p))
        if not d or 'data' not in d:
            return out, False
        out += d['data']
        pg = d.get('pagination') or {}
        st = params.get('start')
        if st and d['data'] and (d['data'][-1].get('last_event_at') or 0) < st:
            return out, True
        cur = pg.get('next_cursor')
        if not pg.get('has_more') or not cur:
            return out, True
    return out, True


def open_positions(w):
    xs, ok = _pages({'user': w, 'status': 'OPEN', 'limit': 500}, max_pages=4)
    return xs if ok or xs else None


def _grade(x):
    try:
        px = float(x.get('current_price'))
    except (TypeError, ValueError):
        return None
    if px >= 0.99:
        return 'W'
    if px <= 0.01:
        return 'L'
    return None


def settled_bets(w, since):
    """Graded $500+ sports game bets for wallet w since epoch `since`. Bigger side only when both sides held."""
    rows = {}
    for st in ('CLOSED', 'REDEEMABLE'):
        xs, ok = _pages({'user': w, 'status': st, 'sort_by': 'TIMESTAMP', 'sort_direction': 'DESC', 'start': int(since), 'limit': 1000})
        for x in xs:
            slug = x.get('slug') or ''
            if not league_of_slug(x.get('event_slug') or slug):
                continue
            try:
                avg = float(x.get('avg_price') or 0)
                cost = float(x.get('total_size') or 0) * avg
            except (TypeError, ValueError):
                continue
            res = _grade(x)
            ts = int(x.get('first_entry_at') or x.get('last_event_at') or 0)
            if not res or avg <= 0 or ts < since:
                continue
            cid = x.get('condition_id') or ''
            prev = rows.get(cid)
            if prev is None or cost > prev['cost']:
                rows[cid] = dict(cid=cid, oi=int(x.get('outcome_index') or 0), cost=round(cost, 2), avg=round(avg, 4), res=res,
                                 ts=ts, slug=slug, outcome=(x.get('outcome') or '')[:40], title=(x.get('title') or '')[:90])
    return [r for r in rows.values() if r['cost'] >= FETCH_MIN]


def gamma_markets(cids):
    """condition_id -> gamma market dict (question, gameStartTime, closed, outcomes, outcomePrices, slug)."""
    out = {}
    cids = [c for c in dict.fromkeys(cids) if c]
    batches = [cids[i:i + 20] for i in range(0, len(cids), 20)]

    def job(b):
        q = '&'.join('condition_ids=' + c for c in b)
        res = {}
        for closed in ('false', 'true'):
            d = get_json(f"{GAMMA}/markets?{q}&closed={closed}&limit=50") or []
            for m in d:
                res[(m.get('conditionId') or '').lower()] = m
        return res
    with ThreadPoolExecutor(max_workers=6) as ex:
        for r in ex.map(job, batches):
            out.update(r)
    return out


def jl(x, default=None):
    if isinstance(x, list):
        return x
    try:
        return json.loads(x)
    except Exception:
        return default


def iso_ts(s):
    if not s:
        return None
    try:
        s = s.replace(' ', 'T').replace('Z', '+00:00')
        if re.search(r'[+-]\d\d$', s):
            s += ':00'
        return int(dt.datetime.fromisoformat(s).timestamp())
    except Exception:
        return None


def fmt_pt(ts, with_day=True):
    d = dt.datetime.fromtimestamp(ts, PT)
    return d.strftime('%a %b %-d · %-I:%M %p PT') if with_day else d.strftime('%-I:%M %p PT')


def flat_roi(res, px):
    """$1 flat at price px."""
    if res == 'W':
        return 1.0 / px - 1.0
    if res == 'L':
        return -1.0
    return 0.0

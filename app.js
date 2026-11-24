(function () {
  var D = window.__DATA || {};
  var TEAL = "#0D9488", INK = "#042F2E", CARD = "#FFFFFF", MUTED = "#5B7C78", GREEN = "#059669", RED = "#DC2626", AMBER = "#B45309";
  var css = "" +
    "body{background:#ECFDF5;font:15px/1.4 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:" + INK + "}" +
    ".wrap{max-width:720px;margin:0 auto;padding:0 12px 60px}" +
    ".hero{background:linear-gradient(160deg,#042F2E,#0F766E);color:#fff;padding:18px 16px 14px;border-radius:0 0 22px 22px;margin:0 -12px 12px}" +
    ".hero h1{margin:0;font-size:24px;letter-spacing:-.02em}.hero .sub{color:#99F6E4;font-size:13px;font-weight:600;margin-top:4px}" +
    ".stats{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}.stat{background:rgba(255,255,255,.12);border-radius:12px;padding:7px 10px;font-size:12px;color:#CCFBF1}.stat b{display:block;color:#fff;font-size:16px}" +
    ".tabs{position:sticky;top:0;z-index:5;display:flex;gap:6px;overflow-x:auto;padding:8px 0;background:#ECFDF5}" +
    ".tab{flex:0 0 auto;border:0;border-radius:999px;padding:9px 14px;font-weight:800;font-size:14px;background:#CCFBF1;color:" + INK + "}.tab.on{background:" + TEAL + ";color:#fff}" +
    ".card{background:" + CARD + ";border-radius:16px;padding:13px 14px;margin:10px 0;box-shadow:0 1px 3px rgba(4,47,46,.12);border:1px solid #D1FAE5}" +
    ".row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.rk{background:" + TEAL + ";color:#fff;font-weight:900;border-radius:9px;padding:2px 8px;font-size:14px}" +
    ".tag{font-size:11px;font-weight:800;border-radius:6px;padding:2px 6px;background:#E6FFFA;color:#0F766E}.tag.live{background:#FEE2E2;color:" + RED + "}.tag.fade{background:#FEF3C7;color:" + AMBER + "}.tag.late{background:#F1F5F9;color:#475569}" +
    ".added{margin-left:auto;font-size:12px;font-weight:800;color:#0F766E}" +
    ".q{font-weight:800;font-size:16px;margin:7px 0 2px}.pick{font-size:15px;font-weight:700}.pick b{color:" + TEAL + "}" +
    ".meta{color:" + MUTED + ";font-size:13px;margin-top:3px}.why{margin-top:8px;border-top:1px dashed #A7F3D0;padding-top:7px;font-size:13px}" +
    ".why div{margin:2px 0}.pos{color:" + GREEN + ";font-weight:800}.neg{color:" + RED + ";font-weight:800}" +
    "a{color:#0F766E;font-weight:700}.btn{display:inline-block;margin-top:9px;background:" + TEAL + ";color:#fff;text-decoration:none;border-radius:10px;padding:8px 12px;font-size:14px}" +
    ".empty{color:" + MUTED + ";text-align:center;padding:30px 10px}.note{font-size:12.5px;color:" + MUTED + ";margin:8px 2px}" +
    "table{width:100%;border-collapse:collapse;font-size:13px}td,th{padding:6px 4px;border-bottom:1px solid #D1FAE5;text-align:left;vertical-align:top}th{font-size:11px;color:" + MUTED + ";text-transform:uppercase}" +
    ".chips{display:flex;gap:6px;flex-wrap:wrap;margin:6px 0}.chip{border:1px solid #99F6E4;background:#fff;border-radius:999px;padding:5px 10px;font-size:12.5px;font-weight:700;color:" + INK + "}.chip.on{background:" + INK + ";color:#fff}" +
    ".reload{float:right;border:0;border-radius:10px;background:rgba(255,255,255,.18);color:#fff;font-weight:800;padding:7px 10px}";
  var st = document.createElement("style"); st.textContent = css; document.head.appendChild(st);
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function pct(x, sign) { if (x == null) return "–"; var v = Math.round(x * 1000) / 10; return (sign !== false && v > 0 ? "+" : "") + v + "%"; }
  function cls(x) { return x == null ? "" : x > 0 ? "pos" : x < 0 ? "neg" : ""; }
  function edge(x) { if (x == null) return "–"; var v = Math.round(x * 1000) / 10; return (v > 0 ? "+" : "") + v + "¢"; }
  function cents(x) { return x == null ? "–" : Math.round(x * 100) + "¢"; }
  function money(x) { if (x == null) return "–"; var a = Math.abs(x); return (x < 0 ? "-$" : "$") + (a >= 1e6 ? (a / 1e6).toFixed(1) + "M" : a >= 1e3 ? (a / 1e3).toFixed(1) + "k" : Math.round(a)); }
  function rec(w, l, roi) { return (w || 0) + "-" + (l || 0) + (roi != null ? ' <span class="' + cls(roi) + '">' + pct(roi) + "</span>" : ""); }
  var FL = {}; (D.filters || []).forEach(function (f) { FL[f.id] = f; });
  var tab = (location.hash || "#ranked").slice(1), fcat = "all", showAll = {};

  function pickCard(p, i) {
    var tags = '<span class="tag">' + esc(p.league || p.sport) + "</span>";
    if (p.live) tags += '<span class="tag live">LIVE</span>';
    if (p.move === "fading") tags += '<span class="tag fade" title="Price 5¢+ below the cappers\' entry">Fading ↓</span>';
    if (p.move === "late") tags += '<span class="tag late" title="You pay 5¢+ more than the cappers did">Late ↑ worse price</span>';
    if (p.kind && p.kind !== "moneyline") tags += '<span class="tag">' + esc(p.kind) + "</span>";
    var h = '<div class="card"><div class="row">' + (p.rank ? '<span class="rk">#' + p.rank + "</span>" : "") + tags +
      '<span class="added">Added ' + esc((p.addedPT || "").split("· ").pop()) + "</span></div>" +
      '<div class="q">' + esc(p.q) + "</div>" +
      '<div class="pick">Pick: <b>' + esc(p.outcome) + "</b> · " + cents(p.price) + ' <span class="meta">(cappers in at ' + cents(p.entry) + ")</span></div>" +
      '<div class="meta">' + esc(p.startPT) + " · " + money(p.cost) + " backing" + (p.oppCost ? " vs " + money(p.oppCost) + " on the other side" : "") + (p.oppScore != null ? " (other side scores " + edge(p.oppScore) + ")" : "") +
      ' · Edge est <span class="' + cls(p.score) + '">' + edge(p.score) + "</span> (≈" + pct(p.roiEst) + " ROI)</div>";
    var why = '<div class="why"><div><b>Why:</b> surfaced by ' + p.nCombos + " filter combo" + (p.nCombos === 1 ? "" : "s") + ", best:</div>";
    (p.why && p.why.topCombos || []).forEach(function (c) {
      var f = FL[c.id] || {};
      why += '<div>• <a href="' + esc(f.url || "#") + '" target="_blank" rel="noopener">' + esc(f.label || c.id) + "</a> — backtest " + rec(f.seedW, f.seedL, f.seedRoi) +
        (f.liveN ? " · scanner " + rec(f.liveW, f.liveL, f.liveRoi) : "") + "</div>";
    });
    why += "<div><b>Cappers:</b> " + (p.backers || []).map(function (b) {
      return '<a href="https://polymarket.com/profile/' + b.wallet + '" target="_blank" rel="noopener">' + esc(b.name) + "</a> " + money(b.cost) + " @ " + cents(b.avg) +
        (b.w + b.l ? " (" + rec(b.w, b.l, b.roi) + ")" : "");
    }).join(", ") + (p.nBackers > (p.backers || []).length ? " +" + (p.nBackers - p.backers.length) + " more" : "") + "</div></div>";
    return h + why + '<a class="btn" href="' + esc(p.url) + '" target="_blank" rel="noopener">Open on Polymarket ↗</a></div>';
  }
  function ranked() {
    var r = D.ranked || [];
    var h = '<div class="note">Window: ' + esc(D.window || "") + ". Pre-game picks first, LIVE picks after. Edge est = learned edge (win rate minus price, in ¢ per $1) of the filters, cappers and pick type behind it, shrunk toward 0 until there are enough graded picks.</div>";
    if (!r.length) return h + '<div class="empty">No qualifying picks in today\'s window right now. Check Coming Up.</div>';
    return h + r.map(pickCard).join("");
  }
  function coming() {
    var r = D.coming || [];
    if (!r.length) return '<div class="empty">Nothing further out yet.</div>';
    return '<div class="note">Later games (next 3 days), soonest first. They move to Ranked Picks on game day.</div>' + r.map(pickCard).join("");
  }
  function filters() {
    var fs = (D.filters || []).filter(function (f) {
      return fcat === "all" || (fcat === "S" && f.id.indexOf("S|") === 0) || (fcat === "E" && f.id.indexOf("E|") === 0) || (fcat === "P" && f.id.indexOf("PnL") === 0) ||
        (fcat === "small" && /retail|spec/.test(f.id));
    });
    var n = showAll.f ? fs.length : 40;
    var chips = [["all", "All"], ["S", "Sports"], ["E", "Esports"], ["small", "Small-account"], ["P", "Real P&L boards"]].map(function (c) {
      return '<button class="chip' + (fcat === c[0] ? " on" : "") + '" data-fc="' + c[0] + '">' + c[1] + "</button>";
    }).join("");
    var h = '<div class="note">Every OrcaLayer leaderboard filter combo the scanner pulls (' + (D.meta && D.meta.combos) + ' combos, top 25 each), ranked by learned edge. <b>Backtest</b> = members\' settled pre-game sports bets ($500+, or 3× avg bet for small bettors) since Nov 9 (hindsight: today's members, so it's discounted). <b>Scanner</b> = this site's own graded picks (honest). Tap a name to open that exact filter on OrcaLayer.</div>" +
      '<div class="chips">' + chips + "</div>";
    h += '<div class="card"><table><tr><th>#</th><th>Filter combo</th><th>Backtest</th><th>Scanner</th><th>Edge</th></tr>' + fs.slice(0, n).map(function (f) {
      return "<tr><td>" + f.rank + '</td><td><a href="' + esc(f.url) + '" target="_blank" rel="noopener">' + esc(f.label) + "</a>" + (f.onBoard ? ' <span class="tag">' + f.onBoard + " open</span>" : "") +
        "</td><td>" + (f.seedN ? rec(f.seedW, f.seedL, f.seedRoi) : "–") + "</td><td>" + (f.liveN ? rec(f.liveW, f.liveL, f.liveRoi) : "–") + '</td><td class="' + cls(f.est) + '">' + edge(f.est) + "</td></tr>";
    }).join("") + "</table>" + (fs.length > n ? '<button class="chip" data-more="f">Show all ' + fs.length + "</button>" : "") + "</div>";
    h += '<div class="card"><b>Pick factors the scanner learns</b><table><tr><th>Factor</th><th>Starting belief</th><th>Scanner</th><th>Now</th></tr>' + (D.factors || []).map(function (f) {
      return "<tr><td>" + esc(f.id) + "</td><td>" + edge(f.prior) + " (" + f.priorN + ")</td><td>" + (f.liveN ? rec(f.liveW, f.liveL, f.liveRoi) : "–") + '</td><td class="' + cls(f.est) + '">' + edge(f.est) + "</td></tr>";
    }).join("") + '</table><div class="note">Starting beliefs come from the Nov 23 audit of ~1,700 graded scanner picks (e.g. picks whose price fell 5¢+ below the cappers\' entry went −19%). Graded results move them over time.</div></div>';
    return h;
  }
  function cappers() {
    var cs = D.cappers || [], n = showAll.c ? cs.length : 50;
    var h = '<div class="note">Cappers surfaced by the filters, ranked by learned edge (their settled $500+ sports bets, plus this scanner\'s graded picks). Small bettors count from 3× their average bet.</div>';
    h += '<div class="card"><table><tr><th>#</th><th>Capper</th><th>Record</th><th>Edge</th></tr>' + cs.slice(0, n).map(function (c) {
      return "<tr><td>" + c.rank + '</td><td><a href="https://polymarket.com/profile/' + c.wallet + '" target="_blank" rel="noopener">' + esc(c.name) + "</a>" + (c.skill ? ' <span class="tag">Proven</span>' : "") +
        (c.openPicks ? ' <span class="tag">' + c.openPicks + " open</span>" : "") + '<div class="meta">in ' + c.combos + " combos · lifetime " + money(c.pnl) + "</div></td><td>" +
        rec(c.seedW + c.liveW, c.seedL + c.liveL, null) + '<div class="meta">bt ' + pct(c.seedRoi) + (c.liveN ? " · scan " + pct(c.liveRoi) : "") + '</div></td><td class="' + cls(c.est) + '">' + edge(c.est) + "</td></tr>";
    }).join("") + "</table>" + (cs.length > n ? '<button class="chip" data-more="c">Show all ' + cs.length + "</button>" : "") + "</div>";
    return h;
  }
  function render() {
    var r = D.record || {};
    var h = '<div class="wrap"><div class="hero"><button class="reload" id="reload">↻</button><h1>Orca Filter Scanner</h1><div class="sub">Updated ' + esc(D.updatedPT || "–") + "</div>" +
      '<div class="stats"><div class="stat"><b>' + (D.ranked || []).length + "</b>Ranked</div><div class=\"stat\"><b>" + (D.coming || []).length + '</b>Coming up</div><div class="stat"><b>' +
      (r.n ? r.w + "-" + r.l : "–") + "</b>Graded" + (r.n ? " " + pct(r.roi) : "") + '</div><div class="stat"><b>' + ((D.meta && D.meta.combos) || "–") + "</b>Filter combos</div></div></div>" +
      '<div class="tabs">' + [["ranked", "Ranked Picks"], ["coming", "Coming Up"], ["filters", "Best Filters"], ["cappers", "Best Cappers"]].map(function (t) {
        return '<button class="tab' + (tab === t[0] ? " on" : "") + '" data-t="' + t[0] + '">' + t[1] + "</button>";
      }).join("") + "</div>";
    h += tab === "coming" ? coming() : tab === "filters" ? filters() : tab === "cappers" ? cappers() : ranked();
    h += '<div class="note">Not betting advice. ROI is $1 flat per pick at the price when the pick was added, fees not included.</div></div>';
    document.getElementById("root").innerHTML = h;
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest("[data-t],[data-fc],[data-more],#reload"); if (!t) return;
    if (t.id === "reload") {
      t.textContent = "…";
      (window.__loadScannerData ? window.__loadScannerData() : Promise.reject()).then(function (d) { D = d; FL = {}; (D.filters || []).forEach(function (f) { FL[f.id] = f; }); render(); }).catch(function () { location.reload(); });
      return;
    }
    if (t.dataset.t) { tab = t.dataset.t; history.replaceState(null, "", "#" + tab); window.scrollTo(0, 0); }
    if (t.dataset.fc) fcat = t.dataset.fc;
    if (t.dataset.more) showAll[t.dataset.more] = 1;
    render();
  });
  render();
})();

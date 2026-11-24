# Orca Filter Scanner
Passcode-locked GitHub Pages site. Every 15 minutes (paused midnight-6 AM PT) GitHub Actions:
1. pulls the top 25 of ~390 OrcaLayer leaderboard filter combos (`/api/leaderboard`: period x sort x preset/floor/ceiling/style/habit, Sports + Esports),
   the real 7/30-day P&L boards by rank band, Whale Alerts (smart Sports/Esports buys, 6h), hot traders and conviction clusters;
2. loads those wallets' open Polymarket sports positions (Data API v2) and builds picks (one side per market, $500+ or 3x avg bet for small bettors, 5-95c);
3. grades settled picks (Gamma) and learns per-combo / per-capper / per-factor edge (win minus price), seeded by a backtest of members' pre-game settled bets
   and research priors, with shrinkage so small samples can't top proven ones (`scanner/model.py`);
4. encrypts `data.json` + `state/picks.json` with the passcode (AES-256-GCM, PBKDF2; only salt+hash in `gate.json`) and deploys Pages.

Secrets: `ORCA_API_KEY`, `KALSHI_SCANNER_PASSCODE`. Large rebuildable state (leaderboards, settled bets, start times) lives in the Actions cache, not git.
Run locally: `cd scanner && python3 scan.py` (key in `scanner/.orca_api_key`, gitignored).

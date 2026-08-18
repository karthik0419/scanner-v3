# NEMOTRON FINDINGS — scanner-v3 Upgrade + scanner-dashboard Integration

**Analysis Date:** 2026-08-12
**Analyst:** Nemotron 3 Ultra
**Projects:** `scanner-v3/` (core engine) + `scanner-dashboard/` (SaaS wrapper)

---

## EXECUTIVE SUMMARY

### scanner-v3 (Core Engine)
**Status: Production-ready, high-quality retail swing scanner**

- **14 pattern detectors** across Daily/Weekly/Monthly — comprehensive coverage
- **v3.1 risk management** (2.0x ATR, 8% max stop, 50% T1, re-entry) — best-in-class for retail
- **Backtest validated**: 3012 trades, +1.30% expectancy, PF 1.73, 40.6% WR
- **Paper tracker live**: 144 picks tracked, WAITING_BREAKOUT + re-entry fixes 83% SL problem
- **Dual Telegram bots** via `--env-file` — clean prod/test separation
- **Automated cron** (Windows Task Scheduler) + 65-test suite
- **NEW 2026-08-12**: Daily smart scan + freshness labels (🆕 NEW / 🔁 Day N)

### scanner-dashboard (SaaS Wrapper)
**Status: Production Docker stack, NOT ready to sell (audit findings)**

- **Full-stack**: Next.js 14 + FastAPI + PostgreSQL + Redis + arq worker
- **22 API endpoints** tested passing, 13 dashboard routes
- **Subprocess isolation** — scanner runs as subprocess, no state leakage
- **Async job queue** — scans (5-55 min) run on worker via Redis
- **PEAD scanner integrated** — dual scanner support
- **Critical audit gaps**: No LICENSE, JWT_SECRET fallback, Docker build fails (missing scanner-v3 dir), guest backdoor, unpinned deps

---

## PART 1: scanner-v3 — Deep Analysis

### Architecture
```
scanner-v3/
├── scanner.py              # Weekly scan (14 detectors, smart universe)
├── daily_scan.py           # Daily volume/breakout scan
├── patterns/               # 14 modular detectors
├── backtester/engine.py    # Walk-forward backtest with re-entry
├── paper_tracker.py        # Live tracking + re-entry check
├── telegram_notify.py      # Dual bot (SwingU/SwingIQ)
├── utils/sector_rotation_v3.py  # NSE sector heat (self-contained)
├── utils/regime.py         # Nifty vs 200DMA regime filter
├── data/loader.py          # Cached yfinance + jugaad-data
└── results/                # CSVs + paper_tracker.csv + charts/
```

### Strengths
| Area | Why It Works |
|---|---|
| **Pattern coverage** | 14 detectors across 3 TFs — no gap in classical setups |
| **Backtest rigor** | Walk-forward, re-entry logic, ATR sweep (1.0-3.0x), whipsaw analysis (27% rate) |
| **Risk management** | 2.0x ATR chosen by sweep (PF 2.03, DD -46.8%), 8% max cap, 50% T1, re-entry |
| **Sector rotation** | Self-contained, 568 NSE stocks mapped to sectors — zero external deps |
| **Paper tracker** | WAITING_BREAKOUT for NEAR, auto re-entry on update — fixed 83% stop-out root cause |
| **Telegram** | `--env-file` flag — prod (SwingIQ) vs test (SwingU) separation |
| **Automation** | 2-step cron: smart scan (fresh picks) → daily scan (volume + Telegram) |
| **Freshness tracking** | 🆕 NEW / 🔁 Day N badges — see which picks are new vs tracked |

### Critical Improvements Needed

#### 1. Technical Debt (Code Hygiene)
| Issue | File | Fix |
|---|---|---|
| **Hardcoded `SECTOR_STOCKS` dict (98 lines)** | `daily_scan.py` | Remove — load exclusively from `data/nse_sectors.json` |
| **Bypasses `data.loader` cache** | `daily_scan.py` | Use `_fetch_nse()` instead of direct `yfinance` calls |
| **Duplicate ATR/stop logic** | `scanner.py` + `backtester/engine.py` | Extract to `utils/risk.py` — single source of truth |
| **No pytest / CI** | — | Add `pytest` + GitHub Actions |
| **No `__all__` in `patterns/__init__.py`** | `patterns/__init__.py` | Export clean detector registry |

#### 2. Strategy Gaps
| Gap | Recommendation |
|---|---|
| **No regime-aware position sizing** | Add `--risk-mode` (full/half/quarter) based on Nifty vs 200DMA |
| **Monthly C&H NEAR threshold too tight (5%)** | Separate per timeframe: Daily 5%, Weekly 8%, Monthly 12% |
| **No correlation filter** | Max 2 picks/sector, max 3 correlated picks |
| **Re-entry uses fixed 2% stop** | Use `0.5x ATR` for re-entry stop |
| **No slippage/fees in backtest** | Add 0.03% brokerage + 0.025% STT + 0.1% slippage |

#### 3. Operational Risks
| Risk | Mitigation |
|---|---|
| **yfinance single point of failure** | Make `jugaad-data` primary, yfinance fallback |
| **No health monitoring** | Heartbeat log + alert if no scan for 48h |
| **Windows-only cron** | Add `cron`/`systemd` configs + Dockerfile for VPS |
| **No version pinning** | Pin exact versions in `requirements.txt` |
| **Paper tracker vs backtest drift** | Monthly reconciliation report + alert if WR diverges >10% |

#### 4. Missing Analytics
| Missing | Value |
|---|---|
| Monte Carlo simulation (1000 bootstrap runs) | Stress-test expectancy distribution |
| Sector attribution | Alpha vs beta decomposition |
| Time-of-day entry analysis | Open vs midday vs close performance |
| Drawdown recovery time | How long to recover from max DD? |
| Live/backtest drift monitor | Alert if paper WR deviates >10% from backtest |

---

## PART 2: scanner-dashboard — Deep Analysis

### Architecture
```
scanner-dashboard/
├── backend/ (FastAPI)
│   ├── app/
│   │   ├── routers/        # 9 routers: auth, scans, picks, charts, screens, alerts, tracker, market, PEAD
│   │   ├── services/
│   │   │   ├── scanner_service.py  # subprocess wrapper for scanner.py
│   │   │   └── worker.py           # arq worker (run_scan_job, run_pead_scan_job)
│   │   └── models.py       # 8 ORM models (User, Scan, Pick, PeadScan, PeadPick, SavedScreen, Alert, PaperTrade)
│   └── requirements.txt
├── frontend/ (Next.js 14)
│   ├── app/               # 13 routes: landing, login, dashboard/* (scans, pead, screens, tracker, market, settings)
│   ├── lib/api.ts         # Typed API client (278 lines, JWT auto-attach, 401→login)
│   ├── lib/auth.tsx       # React Context auth
│   └── components/ui/     # Button, Input, Card, Badge, States, Instructions
├── docker-compose.yml          # 5 containers: postgres, redis, backend, worker, frontend
├── docker-compose.production.yml  # Multi-stage builds, bakes scanners into image
└── .env.example
```

### Strengths
| Area | Why It Works |
|---|---|
| **Subprocess isolation** | `scanner.py` runs as subprocess — crashes don't kill API, no global state |
| **Async job queue** | arq + Redis — scans (5-55 min) run on worker, not API process |
| **Full scanner integration** | `scanner_service.py` builds CLI, runs subprocess, parses CSV → Pick ORM |
| **PEAD dual support** | Separate scanner path, same pattern |
| **Paper tracker sync** | Reads `paper_tracker.csv` → upserts into DB with status mapping |
| **Type-safe frontend** | `lib/api.ts` 278 lines — every endpoint typed, JWT auto-attach |
| **Design system** | Tailwind custom theme, 6 reusable components, dark theme |
| **Docker production** | Multi-stage builds, health checks, memory limits, restart policies |

### Critical Audit Findings (from `AUDIT_FINDINGS.md`)

| # | Severity | Issue | Fix |
|---|---|---|---|
| 1 | **CRITICAL** | No LICENSE file | Add MIT/Apache 2.0/commercial |
| 2 | **CRITICAL** | JWT_SECRET hardcoded fallback in docker-compose & config.py | Remove fallback + startup validation |
| 3 | **CRITICAL** | Docker builds FAIL — `COPY scanner-v3` dirs don't exist in repo | Embed scanner-v3 as submodule or document as external dep |
| 4 | **CRITICAL** | Guest user backdoor (`guest`/`guest` auto-created on startup) | Remove or make opt-in via env var |
| 5 | **CRITICAL** | Python deps unpinned (`>=` instead of `==`) | Pin exact versions |
| 6 | HIGH | Password min 6 chars | Strengthen to 8+ |
| 7 | HIGH | `print()` instead of logging | Replace with `logging` |
| 8 | HIGH | Weak default DB password | Remove default |

---

## PART 3: Integration Opportunities (The "Same Backend" Opportunity)

Since both projects live in `F:\projects\claude\` and share the **same scanner-v3 engine**, there are major synergy opportunities:

### 1. Single Source of Truth for Scanner Logic
**Current**: `scanner-dashboard/backend/app/services/scanner_service.py` wraps `scanner.py` as subprocess
**Better**: Share `utils/risk.py`, `utils/sector_rotation_v3.py`, `data/loader.py` as a **shared Python package**
```bash
# In scanner-dashboard/backend/requirements.txt
-e ../scanner-v3  # editable install
```

### 2. Unified Data Layer
- `scanner-v3` writes CSVs to `results/`
- `scanner-dashboard` reads those CSVs + `paper_tracker.csv`
- **Gap**: Dashboard has its own PostgreSQL — why not write scan results directly to DB?
- **Solution**: Modify `scanner_service.py` worker to insert picks directly to PostgreSQL (already does this for scans triggered via API), but also for cron scans

### 3. Shared Telegram Bot Infrastructure
- Both projects use `telegram_notify.py` but with different configs
- **Opportunity**: Centralize bot management in dashboard → scanner-v3 cron calls dashboard API to send alerts

### 4. Paper Tracker as Single Source
- `scanner-v3/paper_tracker.py` maintains `paper_tracker.csv`
- `scanner-dashboard` syncs that CSV to PostgreSQL
- **Better**: Dashboard owns the tracker DB → scanner-v3 cron calls `POST /api/tracker/sync` after update

### 5. Sector Rotation as Shared Service
- `scanner-v3/utils/sector_rotation_v3.py` computes heat
- `scanner-dashboard` has `/api/market/sectors` endpoint
- **Unify**: Dashboard reads from scanner-v3's JSON cache, or scanner-v3 writes heat to Redis → dashboard reads

---

## PART 4: Unified Upgrade Roadmap

### Phase 1: Foundation (Week 1-2) — Fix Blockers
| Task | Project | Effort |
|---|---|---|
| Remove hardcoded `SECTOR_STOCKS` from `daily_scan.py` | scanner-v3 | 2h |
| Use `data.loader._fetch_nse` in `daily_scan.py` | scanner-v3 | 2h |
| Extract `utils/risk.py` (ATR stop, position sizing, re-entry) | scanner-v3 | 4h |
| Pin `requirements.txt` (both projects) | both | 1h |
| Add LICENSE, remove JWT_SECRET fallback, fix Docker COPY | scanner-dashboard | 4h |
| Remove guest backdoor or make opt-in | scanner-dashboard | 1h |

### Phase 2: Shared Package (Week 2-3)
| Task | Project | Effort |
|---|---|---|
| Create `scanner_core/` shared package with: `risk.py`, `sector_rotation_v3.py`, `loader.py`, `regime.py` | both | 8h |
| Install as editable dep in dashboard: `-e ../scanner-v3` | scanner-dashboard | 1h |
| Refactor `scanner.py` + `daily_scan.py` to use shared package | scanner-v3 | 4h |
| Refactor `scanner_service.py` to import shared logic directly (not subprocess) for fast paths | scanner-dashboard | 4h |

### Phase 3: Unified Data Flow (Week 3-4)
| Task | Project | Effort |
|---|---|---|
| Cron scans write directly to dashboard PostgreSQL (not just CSV) | scanner-v3 | 4h |
| Dashboard `/api/tracker/sync` called by scanner-v3 cron after `paper_tracker.py update` | both | 2h |
| Sector heat written to Redis by scanner-v3 → dashboard reads from Redis | both | 2h |
| Add health endpoint in scanner-v3 → dashboard monitors it | both | 2h |

### Phase 4: Analytics & Polish (Week 4-6)
| Task | Project | Effort |
|---|---|---|
| Add pytest + GitHub Actions CI (both) | both | 8h |
| Monte Carlo simulation module | scanner-v3 | 8h |
| Regime-aware position sizing (`--risk-mode`) | scanner-v3 | 4h |
| Correlation filter (max 2/sector) | scanner-v3 | 4h |
| Slippage/fees in backtest | scanner-v3 | 4h |
| Live/backtest drift monitor + alert | both | 4h |
| Linux cron / systemd / Dockerfile for scanner-v3 | scanner-v3 | 4h |

---

## PART 5: Decision Matrix — Build vs Buy vs Partner

| Option | Pros | Cons | Recommendation |
|---|---|---|---|
| **Keep separate** (current) | Zero coupling risk, independent deploys | Duplicate logic, manual sync, two codebases | ❌ Not sustainable |
| **Shared package** (recommended) | Single source of truth, independent deploys | Requires discipline on versioning | ✅ Do this |
| **Merge into mono-repo** | Simplest imports, atomic commits | Coupled releases, dashboard deps affect scanner | ⚠️ Only if team grows |
| **Dashboard owns scanner as library** | Clean API boundary | Scanner can't run standalone cron | ❌ Scanner needs standalone |

---

## PART 6: Quick Wins (Do This Week)

```bash
# 1. In scanner-v3/daily_scan.py — remove 98-line hardcoded SECTOR_STOCKS
#    Replace with:
from utils.sector_rotation_v3 import STOCK_SECTOR  # already has 568 mappings

# 2. In scanner-v3/daily_scan.py — use cached fetcher
from data.loader import _fetch_nse
df = _fetch_nse(symbol, days=30)  # instead of yf.Ticker(...).history(...)

# 3. In scanner-dashboard/backend/requirements.txt — pin everything
#    pandas==2.2.2, fastapi==0.115.0, etc.

# 4. In scanner-dashboard/docker-compose.yml — remove JWT_SECRET fallback
#    JWT_SECRET: ${JWT_SECRET}  # must be provided

# 5. In scanner-dashboard/backend/app/main.py — remove guest user creation
#    Or wrap in: if os.getenv("ENABLE_GUEST") == "true":

# 6. Add shared package structure:
#    scanner-v3/  →  scanner_core/  (risk, sector, loader, regime)
#    scanner-dashboard/backend/requirements.txt  →  -e ../scanner-v3
```

---

## PART 7: My Take — Bottom Line

### scanner-v3
**Grade: A-**
- Engine is genuinely excellent — backtest-validated, risk-managed, live-tracked
- Only missing: operational maturity (CI, monitoring, Linux deploy) + a few strategy refinements
- The 2026-08-12 upgrades (smart daily scan + freshness labels) show active improvement

### scanner-dashboard
**Grade: B+ (code) / D (production readiness)**
- Clean architecture, great DX (Next.js 14 + FastAPI + arq), solid Docker setup
- **But**: Audit findings are real blockers for any commercial use
- The subprocess approach is smart but creates sync complexity

### The Integration
**Massive opportunity** — you have the same engine in two places. Unifying via a shared package (`scanner_core`) eliminates duplication, enables dashboard to own the data layer, and lets scanner-v3 stay lightweight for cron.

**Recommended path**: Phase 1 fixes → Phase 2 shared package → Phase 3 unified data flow. Total ~3-4 weeks for a production-grade, sellable SaaS with a battle-tested engine underneath.

---

## APPENDIX: File Inventory for Reference

### scanner-v3 (Core)
```
scanner.py, daily_scan.py, paper_tracker.py, telegram_notify.py, gen_charts.py
backtest.py, compare_backtest.py, sweep_atr.py, whipsaw_analysis.py, rank_2week.py
patterns/ (14 detectors), backtester/, data/, utils/, results/, config/
```

### scanner-dashboard (SaaS)
```
backend/
  app/
    routers/ (auth, scans, picks, charts, screens, alerts, tracker, market, pead)
    services/ (scanner_service.py, worker.py)
    models.py, schemas.py, config.py, auth.py, database.py
  requirements.txt, Dockerfile, Dockerfile.production
frontend/
  app/ (13 routes), lib/, components/ui/
docker-compose.yml, docker-compose.production.yml, ARCHITECTURE.md, AUDIT_FINDINGS.md
```

---

*Generated by Nemotron 3 Ultra — 2026-08-12*
*Projects: F:\projects\claude\scanner-v3\ + F:\projects\claude\scanner-dashboard\*
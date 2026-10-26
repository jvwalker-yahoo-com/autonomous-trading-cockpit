# PROGRESS.md — Autonomous Trading Cockpit

## Active Milestones & Changelog

### 2026-10-26: Render Free Tier Exhaustion Resolution, Account Replication & Keep-Alive Automation
- **Diagnosis of Render Free-Tier Stoppage:**
  - Identified that Render's 750 free instance hours per calendar month were exhausted due to continuous 24/7 keep-alive pings (31 days × 24h = 744h + build overlap), triggering Render's account-wide monthly suspension until the 1st of next month.
- **Account Replication Manifest Hardening (`render.yaml`):**
  - Fully synchronized all 32 production environment variables directly in `render.yaml` Blueprint specification (including OpenRouter AI keys, eToro REST credentials, intelligence feed keys for Finnhub/TwelveData/AlphaVantage/FMP/Tavily/SerpAPI, intraday risk parameters, capital allocation, and auto-flatten thresholds).
  - Enables 1-click replication onto any new Render account via Blueprint import with zero manual typing or missing variables.
- **Automated Keep-Alive Cron Workflow (`.github/workflows/keepalive.yml`):**
  - Created an autonomous GitHub Actions scheduled keep-alive workflow targeting `/heartbeat` and root endpoints.
  - Configured intelligent trading-hour scheduling (`*/10 12-22 * * 1-5`) to keep the service permanently awake during active market sessions while consuming only ~220 hours/month (preserving > 500 hours of monthly buffer to permanently eliminate free-tier suspension).
  - Provided manual dispatch trigger and secret/input URL override for seamless switching between Render service URLs.
- **Updated Cloud Operations Runbook (`RUNBOOK.md`):**
  - Documented exact 4-step replication procedure, free-tier hour economics, and cron-job.org / GitHub Actions setup instructions.
- **Graft Code Graph Rebuild:**
  - Synchronized graft index across all modules and workflows.

### 2026-10-21: Cockpit Responsiveness, Live Mode Switch & Settings Dialog Fixes
- **Root Cause Resolution for Cloud Cockpit Freezing:**
  - **Syntax Error Fix in Frontend Script (`frontend/dashboard.js`):** Resolved an unclosed `if (btnAutoAddTopScreened)` block at line 2353 that caused browser parsing to abort with `SyntaxError: Unexpected end of input`. This prevented all UI event listeners (Config modal, Live/Demo mode toggles, screener, polling) from binding on page load.
  - **Automated Frontend Syntax Validation (`tests/test_frontend_assets.py`):** Added a Node.js VM syntax validation test to ensure `dashboard.js` and frontend assets are completely free of syntax errors across CI and test runs.
  - **Non-blocking Live Mode Switch (`backend/server.py`):** Changed `/api/mode/switch` to return immediately (instant response to browser UI) and execute portfolio synchronization and watchlist registration asynchronously in `background_tasks`.
  - **Decoupled Snapshot Polling from Broker Sync (`backend/server.py`):** Removed synchronous eToro portfolio HTTP network syncing from `/api/cockpit/snapshot`. The telemetry snapshot now reads cached broker state instantly (< 50ms), eliminating reverse proxy timeouts on Render.
  - **Instant Settings Modal Opening (`frontend/dashboard.js`):** Removed blocking `Promise.all` network gate before opening the Settings dialog. Clicking `⚙️ CONFIG` opens the modal immediately and pre-populates fields from `localStorage`, then syncs server status asynchronously in the background.
  - **Fast-fail eToro Auth Cooldown & Timeouts (`src/services/etoro/client.py`):** Enforced strict 5-6s timeouts on eToro requests (down from 25s), eliminated 20+ redundant sequential probe loops on HTTP 401 Unauthorized, and ensured immediate 60-second auth cooldown activation to avoid worker thread starvation.
  - **Pydantic Model Update (`backend/server.py`):** Added `day_trade_eod_flatten_minutes_before_close` to `ConfigUpdateRequest`.

### 2026-10-21: OpenBB Feed Integration & Market Intelligence Expansion
- **Unified Feed Wrapper (`src/openbb_feed.py`):**
  - Integrated `openbb-finance/openbb` wrapper exposing macro & economic intelligence (FRED, OECD, IMF), equity fundamentals (FMP), order book market depth (Polygon), OHLCV historical pricing (YFinance), crypto pairs (CoinGecko), and Bloomberg/financial news headlines (Tiingo).
  - Designed with graceful fallback support when optional dependencies are absent.
- **Market Intel Engine (`backend/engine/market_intel.py`):**
  - Extended `MarketIntelSuite` to bind `self.openbb` endpoints for unified consumption by decision engines.
- **Streamlit Cockpit (`streamlit_app.py`):**
  - Added dedicated OpenBB News and Equity Fundamentals inspector widgets inside the Global Macro & Market Intel tab.
- **Unit Testing & Verification (`tests/test_openbb_feed.py`):**
  - Added unit test suite covering all OpenBB feed functions, data shapes, and fallbacks.
- **Graft Code Graph:**
  - Built and synced `graft` index across all 38 codebase modules (480 nodes, 1289 edges).

---

### Previous Milestones
- **TradingAgents AI Committee:** Multi-agent decision framework (Fundamentals, Technical, Sentiment, Valuation) integrated into autonomous execution pipeline.
- **Authoritative eToro Instruments DB:** SQLite database storing normalized instrument identifiers, assets, and live order constraints.
- **Arbitration & Circuit Breaker Logic:** Dynamic drawdown, max exposure, and risk quadrant gates preventing over-leveraged orders.

# PROGRESS.md — Autonomous Trading Cockpit

## Active Milestones & Changelog

### 2026-10-21: Cockpit Responsiveness, Live Mode Switch & Settings Dialog Fixes
- **Root Cause Resolution for Cloud Cockpit Freezing:**
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

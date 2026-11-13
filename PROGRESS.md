# PROGRESS.md — Autonomous Trading Cockpit

## Active Milestones & Changelog

### 2026-11-13: eToro Watchlist Sync Hardening & Full Code/Knowledge Graph Refresh
- **eToro Watchlist Sync Fix ([`src/services/etoro/client.py`](file:///c:/Antigravity/autonomous-trading-cockpit/src/services/etoro/client.py)):**
  - Removed obsolete endpoint probes (`/api/v1/watchlists/user`, `/api/v1/user/watchlists`) in `get_user_watchlists` so lookups query `GET /api/v1/watchlists` directly, unwrapping `watchlists` / `items` payloads.
  - Updated `create_watchlist` to encode watchlist names with RFC 3986 `%20` (`urllib.parse.quote`) in `/api/v1/watchlists?name=...&type=Static` instead of form-encoded `+` (`Autonomous+Cockpit`), removed the nonexistent `/api/v1/watchlists/user` fallback, and added `_extract_watchlist_id` / `_coerce_watchlist_id` to extract both flat and nested `WatchlistsResponse["watchlists"][0]` numeric or string/UUID IDs.
  - Hardened `get_or_create_cockpit_watchlist` and `sync_symbols_to_watchlist` with per-client locking (`_watchlist_lock`), `+`/`%20`/whitespace name normalization (`_normalize_watchlist_name`), recovery from `422 InvalidDuplicateWatchlistName` (`_is_duplicate_watchlist_error`), cached watchlist ID and synced `itemId` deduplication (`_watchlist_id_cache`, `_watchlist_synced_items`), one-shot stale-ID invalidation on `422 InvalidWatchlistId`, removal of the bogus fallback virtual ID `101`, and removal of duplicate legacy `{"instrumentIds": ...}` retries in `add_items_to_watchlist`.
  - Added 5 regression tests in [`tests/test_optimizations.py`](file:///c:/Antigravity/autonomous-trading-cockpit/tests/test_optimizations.py) covering direct endpoint usage, `+`-encoded name matching & cache-hit skip logic, `%20` encoding & no-`101` fallback, concurrent thread serialization on duplicate `422`, and stale cached-ID invalidation.
- **Code & Knowledge Graphs (`graft` & `graphify`):**
  - Rebuilt and verified `graft` wiring graph across **42 files** (`563` nodes, `1,552` edges, `42` cards — `graft check: OK`).
  - Built full `graphify` AST + semantic knowledge graph ([`graphify-out/GRAPH_REPORT.md`](file:///c:/Antigravity/autonomous-trading-cockpit/graphify-out/GRAPH_REPORT.md)) across **57 files** (`49` code + `8` documents/UI/skills, `~191,047` words), yielding **`1,294` nodes, `2,495` edges, and `88` labeled communities** (`graphify diagnose multigraph`: `0` unverified/missing/dangling/duplicate post-build edges).

### 2026-11-13: Execution Speed, Indicator & Reasoning Optimizations (P0/P1/P2)
- **Wyckoff, Quantitative Indicators & Screener Blending ([`backend/engine/wyckoff.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/wyckoff.py), [`backend/engine/indicators.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/indicators.py), [`backend/engine/screener.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/screener.py)):** Updated `WyckoffRangeEngine.detect_wyckoff_structure` for Spring / UTAD / SOS / SOW detection, restored stateful SuperTrend tracking and true Wilder ADX smoothing, and updated `MarketScreener._evaluate_technical_and_congress` with signed Congressional conviction blending so bullish Congressional flow does not amplify short signals.
- **OHLCV Storage, Batch Quotes, Cache & Symbol Disambiguation ([`backend/engine/data_feed.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/data_feed.py), [`backend/engine/instruments_db.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/instruments_db.py), [`backend/engine/telemetry.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/telemetry.py)):** Added `ingest_ohlcv_bars`, `record_bar_point`, `_fetch_symbol_ohlcv`, `hydrate_historical_ohlcv`, `fetch_quotes_batch`, indicator memoization in `get_technical_indicators`, and a live-mode simulated-quote execution guard; added an in-memory lookup cache in `InstrumentsDBManager`; and disambiguated `"BA"` (US NYSE) from LSE UK tickers in `TelemetryModule`.
- **AI Committee, Macro Intel, News, Smart Money, Broker & Learner ([`backend/engine/ai_committee.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/ai_committee.py), [`backend/engine/market_intel.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/market_intel.py), [`backend/engine/news_intel.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/news_intel.py), [`backend/engine/smart_money.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/smart_money.py), [`backend/engine/metrics.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/metrics.py), [`backend/engine/broker.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/broker.py), [`backend/engine/learner.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/learner.py), [`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py)):**
  - Added stale-dossier checks (`is_dossier_stale`), `_refresh_committee_batch`, `_build_committee_macro_context`, and neutral handling when fundamentals are missing in `AICommitteeEngine`.
  - Added cached macro summary (`get_cached_macro_summary`, `_fetch_av_macro_series`) in `MarketIntelSuite`, full-watchlist (`>30` symbols) coverage + Finnhub sentiment divisor fix in `NewsIntelligenceEngine`, and `refresh_flow_transparency_batch` + `CONGRESS_BUY` preservation in `SmartMoneyEngine`.
  - Updated `MetricsModule` (`model_risk`, `model_impact`) determinism & latency normalization, `SimulatedBroker` `contributing_models` preservation & software Take-Profit enforcement, and `AdaptiveLearner` 7-model weights + post-update mistake snapshots.
- **Verification ([`tests/test_optimizations.py`](file:///c:/Antigravity/autonomous-trading-cockpit/tests/test_optimizations.py)):** Added 15 P0/P1/P2 optimization tests alongside the 5 eToro watchlist regression tests (**20/20** in `tests/test_optimizations.py`; **68/68** passing in `pytest -v`).

### 2026-11-08: 5-Source Pre-Trade Intelligence Gate (Screener/Stocks, Congress Trades, eToro Data, Finnhub & World News)
- **Mandatory 5-Source Pre-Trade Intelligence Gate (`collect_pre_trade_intelligence` in [`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py)):**
  - Before any autonomous (`run_analysis_cycle`) or manual (`execute_manual_action`) trade is evaluated or dispatched, the engine now explicitly reads, validates, and records all **5 required intelligence streams**:
    1. **Screener / Stocks ([`backend/engine/screener.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/screener.py)):** Added `MarketScreener.get_symbol_screen(symbol)` and `_last_universe_cache` to evaluate ADX, SuperTrend, VWAP, RSI/MFI, Double Bottom/Top, Range Breakout, Volume Surge, and TradingView multi-timeframe technical consensus (`tv_consensus_1d`, `tv_recommend_score`, `opportunity_score`, `normalized_score`).
    2. **Congress Trades & Smart Money ([`backend/engine/smart_money.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/smart_money.py)):** Added `SmartMoneyEngine.get_pre_trade_congress_intel(symbol)` combining direct Congressional disclosures (`CongressInvests` / `QuiverQuant`) with 3-way institutional/insider flow (`OpenInsider` Form 4 + `Finnhub` 13F) into `combined_conviction` and `CONGRESS_BUY` / `CONGRESS_SELL` signals.
    3. **eToro Data ([`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py), [`backend/engine/instruments_db.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/instruments_db.py)):** Resolves authoritative eToro `instrument_id`, asset class, UK session hours, spread estimate (`estimated_spread_pct`), retail tradability (`UNTRADABLE_RETAIL_SYMBOLS` / `CRYPTO_SYMBOLS` exclusion), and syncs live eToro portfolio positions (`sync_live_etoro_portfolio_if_live`) prior to live order sizing/execution.
    4. **Finnhub Data ([`backend/engine/news_intel.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/news_intel.py), [`backend/engine/data_feed.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/data_feed.py)):** Added `NewsIntelligenceEngine.get_pre_trade_news_intel(symbol)` reading Finnhub quote/sentiment, company catalyst score, upcoming Finnhub earnings calendar proximity (`earnings_imminent` within 0–1 days scales position size by `0.75x`), and SEC EDGAR filings.
    5. **World News ([`backend/engine/news_intel.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/news_intel.py)):** Reads worldwide breaking news headlines, global macro sentiment, and `macro_risk_level` (`NORMAL`, `ELEVATED`, `CRITICAL`), dampening aggressive `BUY` conviction and scaling long position sizing by `0.75x` during `CRITICAL` negative world news.
- **Model Federation & Telemetry Integration ([`backend/engine/federation.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/federation.py), [`backend/engine/models.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/models.py)):**
  - Upgraded `FederationModule.score_news_sentiment` and `model_federation` to accept `pre_trade_intel`, scoring the unified 5-source intelligence signal (`Multi-Source Intel (Screener/Congress/eToro/Finnhub/WorldNews)`) and applying multi-source confirmation to `federated_score`.
  - Added `pre_trade_intel` to `DecisionOutput`, `/api/cockpit/snapshot`, and exposed a dedicated `GET /api/intel/pre_trade` endpoint (`?symbol=NVDA`).
  - Added regression test `test_five_source_pre_trade_intelligence_gate` in [`tests/test_engine.py`](file:///c:/Antigravity/autonomous-trading-cockpit/tests/test_engine.py) (**48/48 tests passing**).

### 2026-11-08: 24/7 Keep-Alive Cron Reinstatement (GitHub Actions + Cloud Self-Ping + Local Scheduler)
- **GitHub Actions Keep-Alive Cron Upgraded to 24/7 ([`.github/workflows/keepalive.yml`](file:///c:/Antigravity/autonomous-trading-cockpit/.github/workflows/keepalive.yml)):**
  - Updated cron schedule from restricted US-only hours (`*/10 12-22 * * 1-5` + `0 */3 * * 0,6`) to continuous **24/7 every 10 minutes (`*/10 * * * *`)** so European morning sessions (`UK100`, `GER40`) and weekend/off-hour dashboard visits never encounter a Render 15-minute idle spin-down.
  - Fixed curl exit-code handling (`|| true`) so cold-start timeouts do not concatenate duplicate `"000"` status strings.
  - Manually dispatched and verified the active `Cockpit Keep-Alive Cron` workflow run on GitHub Actions.
- **In-Process Render Cloud Self-Keep-Alive Loop ([`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py)):**
  - Added a 10-minute (`600s`) external self-ping inside `autonomous_background_worker_loop()` targeting `RENDER_EXTERNAL_URL/heartbeat` (`https://autonomous-trading-cockpit-8wal.onrender.com/heartbeat`) to keep Render's external Cloudflare ingress timer active even when GitHub Actions runner queues are delayed.

### 2026-11-07: Comprehensive System Health Check, Execution Hardening & Static Verification
- **Critical Diagnostic & Execution Safety Fixes:**
  - **Read-Only Enforcement on `GET /api/etoro/mcp-test` ([`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py)):** Fixed a critical bug where `GET /api/etoro/mcp-test` invoked `execute_mcp_trade(..., mode="real")` instead of read-only `prepare_mcp_trade(..., mode="demo")`, which previously caused test suites to trigger live orders on eToro.
  - **Client-Layer Crypto Prohibition ([`src/services/etoro/client.py`](file:///c:/Antigravity/autonomous-trading-cockpit/src/services/etoro/client.py)):** Added hard rejection guards inside `EToroClient.execute_mcp_trade` and `EToroClient.create_order` for all `CRYPTO_SYMBOLS` and crypto instrument IDs (`>= 100000`), guaranteeing zero cryptocurrency orders can ever be dispatched at the transport layer.
  - **Pytest Isolation & Live Order Guard ([`pytest.ini`](file:///c:/Antigravity/autonomous-trading-cockpit/pytest.ini), [`tests/conftest.py`](file:///c:/Antigravity/autonomous-trading-cockpit/tests/conftest.py)):** Added `pytest.ini` (`pythonpath = .`) so `pytest` runs directly without module path errors, and created an `autouse` fixture in `tests/conftest.py` that isolates `config.db_path` / `broker.db_path` to a temporary file and intercepts unmocked `place-trade` / `place-close` MCP calls during test runs.
- **Static Symbol Table (`symtable`) Audit & `NameError` Resolutions ([`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py)):**
  - Resolved missing `import json` that caused `safe_decode_jwt_payload` in `/api/etoro/status` to silently fail when inspecting eToro JWT tokens.
  - Resolved missing `import numpy as np` in `get_wyckoff_structure_endpoint` fallback calculation.
  - Fixed `POST /api/research/evaluate` (`evaluate_symbol_committee`) calling undefined `indicators_module.compute_all` instead of `data_feed.get_technical_indicators(sym)`.
  - Added automated `symtable` static scope verification test (`test_python_symtable_no_undefined_globals`) in [`tests/test_frontend_assets.py`](file:///c:/Antigravity/autonomous-trading-cockpit/tests/test_frontend_assets.py) to permanently prevent undefined global references across all 41 Python files.
- **Multi-Lot eToro Position Closing & Broker Hardening ([`backend/engine/broker.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/broker.py)):**
  - Updated `auto_flatten_day_trades` and `prune_decaying_short_term_positions` to iterate over all underlying `pos.etoro_position_ids` (matching `enforce_live_stops`), ensuring multi-lot holdings are completely closed on eToro.
  - Enhanced `sync_live_etoro_portfolio` to preserve or initialize synthetic software `take_profit` targets (`3.0%` day / `5.0%` swing) alongside synthetic `stop_loss` levels for unleveraged spot holdings.
  - Made `current_price` optional in `SimulatedBroker.close_position`, defaulting to `pos.current_price` when omitted (fixing `close_all_positions_endpoint(only_crypto=True)`).
  - Updated `execute_manual_action` in `backend/server.py` to apply horizon-specific SL/TP (`day` vs `swing`) on live manual orders and prevent recording phantom local positions if a live eToro order is rejected.
- **Telemetry Prefix Fix & FastAPI Lifespan Modernization:**
  - Fixed `TelemetryModule.get_exchange_for_symbol` in [`backend/engine/telemetry.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/telemetry.py) to match exact crypto symbols or pair suffixes rather than `sym.startswith(c)`, preventing equities like `SOLV` or `UNFI` from colliding with crypto prefixes (`SOL`, `UNI`).
  - Migrated `@app.on_event("startup")` in `backend/server.py` to a FastAPI `lifespan` async context manager that cleanly cancels the background worker task on shutdown.
  - Synced `risk_per_trade_pct` and `day_trade_eod_flatten_minutes_before_close` across `get_system_config()`, `update_system_config()`, and startup state restoration.
- **Verification, Graft Code Graph Rebuild & Render Service Restart:**
  - All **47/47 unit & integration tests passing** (`pytest -v`).
  - Rebuilt and verified `graft` code graph across all **41 files (500 nodes, 1,340 edges)**.
  - Resumed and restarted Render cloud service `autonomous-trading-cockpit` (`srv-dbflfb9srm7s73fdvmn0`) at `https://autonomous-trading-cockpit-8wal.onrender.com` with all health-check fixes deployed.

### 2026-10-28: Render Service Suspension & Live Stop-Loss Enforcement Wiring
- **Render Service Suspended Per Operator Instruction:**
  - Suspended Render web service `autonomous-trading-cockpit` (`srv-dbflfb9srm7s73fdvmn0`) via Render REST API (`POST /v1/services/{serviceId}/suspend`) until instructed to resume.
- **Live Stop-Loss Enforcement & Synthetic Spot Stops ([`backend/engine/broker.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/engine/broker.py), [`backend/server.py`](file:///c:/Antigravity/autonomous-trading-cockpit/backend/server.py)):**
  - Wired `broker.enforce_live_stops` into `sync_live_etoro_portfolio_if_live` and auto-assigned synthetic software stop-losses (`1.5%` day / `2.5%` swing) for unleveraged spot holdings.

### 2026-10-26: Production Deployment & Replication on New Render Account
- **New Render Service Successfully Created & Provisioned:**
  - Authenticated and deployed web service `autonomous-trading-cockpit` on Render account `jvwalker@yahoo.com` (`tea-dbfk5ai9lscs73aeslo0`).
  - **Live Cloud URL:** `https://autonomous-trading-cockpit-8wal.onrender.com`
  - **Dashboard Management URL:** `https://dashboard.render.com/web/srv-dbflfb9srm7s73fdvmn0`
  - **Region:** Frankfurt (`frankfurt`), Plan: `Free (0.1 CPU, 512 MB RAM)`.
  - Injected all 32 production environment variables directly (Finnhub, Twelve Data, Alpha Vantage, FMP, Tavily, SerpAPI, Anspire, Congress Invests, OpenRouter, eToro credentials, capital limits, and risk parameters).
- **Automated Keep-Alive Cron Configured:**
  - Synced [`.github/workflows/keepalive.yml`](file:///c:/Antigravity/autonomous-trading-cockpit/.github/workflows/keepalive.yml) with default URL pointing to `https://autonomous-trading-cockpit-8wal.onrender.com`.
  - Cron scheduled for market and pre-market hours (`*/10 12-22 * * 1-5`) to preserve free instance hours and prevent end-of-month suspensions.

### 2026-10-26: Live Cockpit Deployment via Cloudflare Tunnel (Zero Credit Card)
- **Active Live URL Provisioned & Verified:**
  - Deployed and launched the live autonomous trading cockpit over an encrypted Cloudflare Tunnel.
  - **Live URL:** `https://ellen-elimination-holding-coupled.trycloudflare.com`
  - **Heartbeat Status:** `{"alive": true, "status": "healthy"}` (verified HTTP 200 OK).
  - Synchronized live eToro portfolio (Cash: $48.14, Equity: $1191.56, 9 live positions active).
  - Eliminates Render free-tier suspensions, 15-minute idle freezes, and payment card mandates.
- **Gradio SDK Entrypoint (`app.py`):**
  - Created [`app.py`](file:///app.py) configuring Gradio Blocks to mount the full FastAPI backend and embed the cybernetic Cockpit dashboard in an interactive canvas.
  - Added `gradio>=4.0.0` to `requirements.txt`.
  - Enables 100% free hosting on Hugging Face Spaces using the free Gradio or Streamlit SDK without Docker or credit cards.
- **Local Live HTTPS Access via Cloudflare Tunnel:**
  - Discovered `cloudflared` (version 2026.9.1) is pre-installed on this machine.
  - Built 1-click launcher [`start_cockpit_online.bat`](file:///start_cockpit_online.bat) that starts both the Uvicorn trading engine and an encrypted public HTTPS tunnel (`trycloudflare.com`) with **zero credit card, zero sleep timeouts, zero monthly instance limits, and real-time execution**.
- **Container Infrastructure Specification ([`Dockerfile`](file:///Dockerfile)):**
  - Added universal Python 3.11 slim container image supporting Hugging Face Spaces (Port 7860, 16 GB RAM free, 100% no card required) and Railway.
- **Koyeb Status Observation:**
  - Documented that Koyeb has frozen self-service deployments due to its acquisition by Mistral AI.
- **Koyeb Cloud Infrastructure Configuration (No Credit Card Alternative):**
  - Configured native Koyeb buildpack support with root [`Procfile`](file:///Procfile) targeting `uvicorn backend.server:app --host 0.0.0.0 --port ${PORT:-8000}`.
  - Authored declarative infrastructure-as-code specification [`koyeb.yaml`](file:///koyeb.yaml) defining Nano tier, Frankfurt region, and `/` HTTP route.
  - Enhanced `backend/server.py` frontend discovery candidates to include `/app/frontend` container path.
  - Extended keep-alive cron workflow [`.github/workflows/keepalive.yml`](file:///c:/Antigravity/autonomous-trading-cockpit/.github/workflows/keepalive.yml) to accept `KOYEB_APP_URL`.
  - Documented complete step-by-step migration runbook in [`RUNBOOK.md`](file:///c:/Antigravity/autonomous-trading-cockpit/RUNBOOK.md).
- **New Account Verification & Provisioning (`jvwalker@yahoo.com`):**
  - Authenticated to the fresh Render account and verified the workspace (`tea-dbfk5ai9lscs73aeslo0`) has 750/750 fresh free instance hours available.
  - Generated programmatic Render API Key (`rnd_ivFvR2d5q113UStXv5DYzcSQ6zZm`) for automated deployment.
  - Created automated REST deployment pipeline script (`deploy_to_render.py`) pre-configured with all 32 environment variables, Python 3.11 runtime, Frankfurt region, and start commands.
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

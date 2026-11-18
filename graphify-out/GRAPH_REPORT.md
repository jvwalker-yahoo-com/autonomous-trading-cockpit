# Graph Report - autonomous-trading-cockpit  (2026-11-18)

## Corpus Check
- 57 files · ~197,782 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 4, .bat 3, .example 1)

## Summary
- 1357 nodes · 2646 edges · 65 communities (46 shown, 19 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 207 edges (avg confidence: 0.87)
- Token cost: 2,150 input · 980 output

## Community Hubs (Navigation)
- Dashboard UI State Controller
- Cockpit Diagnostics & Telemetry API
- Live Data Feed Manager
- Quantitative Technical Indicators
- Multi-Source News Intelligence
- Smart Money & Congress Radar
- System Config & AI Committee
- Instruments SQLite Query Cache
- Emergency & Ledger Control API
- Adaptive Strategy Learner
- Gradio & OpenBB Entrypoint
- PDF & Email Audit Reporting
- Day Trade & Position Execution
- eToro API Operations Guidelines
- Live Stop-Loss Enforcement Tests
- config.py Cluster
- AI Committee Background Worker
- GitHub Keepalive Workflow
- Broker Equity & Live Sync
- Cockpit Snapshot State Endpoints
- EToroClient Cluster
- Portfolio & Account UI Bindings
- Engine API Integration Tests
- Market Trading Hours Telemetry
- Wyckoff Range Structure Engine
- Macro Market Intel Suite
- Backtest & Preset API Endpoints
- Koyeb Service Manifest
- Watchlist & Optimization Tests
- Market Regime Classification Engine
- Background News & Flow Refresh
- Execution Architecture Blueprint Docs
- Cockpit Analytics Modals UI
- Real-Time Stock & Macro Feed
- 5-Source Pre-Trade Gate Docs
- Wyckoff & Flow Endpoints
- Risk, Impact & Slippage Metrics
- Deployment & Dependency Stack
- Cockpit Desktop Web Interface
- Live Trading Safeguards Docs
- Render Cloud Blueprint Config
- .create order() Cluster
- Arbitration & Quadrant Matrix
- Cloud Hosting & Keepalive Docs
- Polymarket Strategy Ecosystem Notes
- Daily Loss Circuit Breaker Tests
- Jev External Decision Client
- Pre-Trade 5-Source Intel Gate
- app.py Cluster
- Cockpit UI Render Helpers
- subprocess Cluster
- Instruments DB Singleton Lookup
- fixture Cluster
- UI Data & Order Dispatch
- .test websocket() Cluster
- ReportLab PDF Dependency

## God Nodes (most connected - your core abstractions)
1. `EToroClient` - 58 edges
2. `SimulatedBroker` - 46 edges
3. `DataFeedManager` - 40 edges
4. `NewsIntelligenceEngine` - 30 edges
5. `TechnicalIndicators` - 28 edges
6. `SmartMoneyEngine` - 28 edges
7. `run_trading_day_simulation()` - 26 edges
8. `run_analysis_cycle()` - 23 edges
9. `TradeRecord` - 22 edges
10. `FederationModule` - 21 edges

## Surprising Connections (you probably didn't know these)
- `System Settings & eToro API Keys Modal (#settingsModal)` --conceptually_related_to--> `etoro-public-api-mcp Server (https://mcp.public-api.etoro.com)`  [INFERRED]
  frontend/index.html → .agents/skills/etoro-public-api-operations/SKILL.md
- `eToro Public API Integration (https://public-api.etoro.com)` --conceptually_related_to--> `Dual-Channel Connection Authentication (Key Pair vs OAuth Bearer)`  [INFERRED]
  frontend/index.html → .agents/skills/etoro-public-api-operations/SKILL.md
- `eToro API Portal (api-portal.etoro.com)` --semantically_similar_to--> `eToro Public API Integration (https://public-api.etoro.com)`  [INFERRED] [semantically similar]
  frontend/mobile.html → frontend/index.html
- `test_ai_committee_deliberation_and_report_tree()` --uses--> `AICommitteeDossier`  [INFERRED]
  tests/test_ai_committee.py → backend/engine/ai_committee.py
- `run_trading_day_simulation()` --calls--> `AnomalyModule`  [EXTRACTED]
  run_full_day_simulation.py → backend/engine/anomaly.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Cockpit 9-Panel Execution & Self-Learning Loop** — readme_state_panel, readme_decision_panel, readme_federation_panel, readme_arbitration_panel, readme_anomaly_detector, readme_quadrant_matrix, readme_positions_panel, readme_adaptive_learner, readme_event_timeline_ledger [EXTRACTED 1.00]
- **Nine-Panel Cockpit Telemetry, Risk & Execution Grid** — frontend_index_panel_01_state, frontend_index_panel_02_decision, frontend_index_panel_03_federation, frontend_index_panel_04_arbitration, frontend_index_panel_05_anomaly, frontend_index_panel_06_quadrant, frontend_index_panel_07_positions, frontend_index_panel_08_learning, frontend_index_panel_09_events [EXTRACTED 1.00]
- **Dual-Horizon & Intraday Protection Ruleset** — runbook_dual_horizon_trading_engine, runbook_intraday_risk_management, runbook_eod_auto_flatten, runbook_shielded_holdings, runbook_zero_crypto_policy [EXTRACTED 1.00]
- **eToro MCP Token-Gated Trade & Close Lifecycle** — agents_skills_etoro_public_api_operations_skill_tool_prepare_trade, agents_skills_etoro_public_api_operations_skill_tool_place_trade, agents_skills_etoro_public_api_operations_skill_tool_prepare_close, agents_skills_etoro_public_api_operations_skill_tool_place_close, agents_skills_etoro_public_api_operations_skill_confirmation_gate [EXTRACTED 1.00]
- **Mobile ReAuth Credential Update & Verification Flow** — frontend_mobile_section_update_keys, frontend_mobile_fn_push_keys, frontend_mobile_api_config, frontend_mobile_api_etoro_test_connection, frontend_mobile_jwt_clipboard_guard [EXTRACTED 1.00]

## Communities (65 total, 19 thin omitted)

### Community 0 - "Dashboard UI State Controller"
Cohesion: 0.02
Nodes (95): activeWatchlistPills, activeWlCount, aiCommitteeModal, aiCommitteeTickerInput, assetSelect, backtestModal, badgeFlowPrice, badgeFlowSentiment (+87 more)

### Community 1 - "Cockpit Diagnostics & Telemetry API"
Cohesion: 0.03
Nodes (44): _default_is_known_etoro_symbol(), etoro_instrument_search(), etoro_mcp_prepare(), get_congress_intelligence(), get_day_trading_status(), get_equibles_reports(), get_etoro_credentials(), get_etoro_scopes() (+36 more)

### Community 2 - "Live Data Feed Manager"
Cohesion: 0.05
Nodes (12): DataFeedManager, MarketDataPoint, MarketScreener, auto_add_top_screened(), scan_market(), test_close_all_trades_and_crypto_deactivation(), test_data_feed_and_indicators(), test_data_feed_preserves_ohlcv_bars_and_memoizes_indicators() (+4 more)

### Community 3 - "Quantitative Technical Indicators"
Cohesion: 0.07
Nodes (10): BacktesterEngine, BacktestResult, OptimizationCandidate, OptimizationResult, TechnicalIndicators, test_backtester_and_optimizer(), test_pattern_recognition_and_volume_surge(), test_quant_trading_indicators() (+2 more)

### Community 4 - "Multi-Source News Intelligence"
Cohesion: 0.06
Nodes (5): NewsIntelligenceEngine, _load_edgar(), _load_fh(), test_worldwide_news_and_macro_radar(), test_news_intel_covers_full_watchlist_beyond_30_and_fixes_finnhub_divisor()

### Community 6 - "System Config & AI Committee"
Cohesion: 0.08
Nodes (8): AICommitteeDossier, AICommitteeEngine, FederationModule, FederationOutput, ModelSignal, test_ai_committee_deliberation_and_report_tree(), test_federation_incorporates_ai_committee(), test_ai_committee_neutral_without_fundamentals()

### Community 7 - "Instruments SQLite Query Cache"
Cohesion: 0.10
Nodes (4): InstrumentsDBManager, test_authoritative_etoro_instrument_ids_and_no_crypto_collision(), test_etoro_portfolio_sync_seeds_instrument_ids_and_resolves_fvd_bac_no_collision(), test_instruments_db_in_memory_cache_hits()

### Community 8 - "Emergency & Ledger Control API"
Cohesion: 0.06
Nodes (18): add_to_watchlist(), clear_trade_ledger(), close_all_positions_endpoint(), close_crypto_positions_endpoint(), get_portfolio(), manual_flatten_day_trades(), prune_short_term_positions_endpoint(), remove_from_watchlist() (+10 more)

### Community 9 - "Adaptive Strategy Learner"
Cohesion: 0.14
Nodes (9): AdaptiveLearner, DecisionOutput, LearningStatsOutput, MistakeLogEntry, MultiDayPerformanceReport, PortfolioSummary, StockPerformanceSummary, TradeRecord (+1 more)

### Community 10 - "Gradio & OpenBB Entrypoint"
Cohesion: 0.13
Nodes (8): _env(), get_crypto_price(), get_equity_fundamentals(), get_equity_market_depth(), get_equity_price_history(), get_macro_data(), get_news(), TestOpenBBFeed

### Community 11 - "PDF & Email Audit Reporting"
Cohesion: 0.09
Nodes (6): EmailReportDispatcher, ReportPDFGenerator, download_pdf_report(), email_pdf_report(), EmailReportRequest, get_daily_report()

### Community 12 - "Day Trade & Position Execution"
Cohesion: 0.10
Nodes (5): test_adaptive_learner_and_broker(), test_day_trading_and_eod_auto_flatten(), test_multi_lot_flatten_prune_and_crypto_hard_block(), test_trading_hours_check_before_placing_trade(), test_auto_flatten_only_expired_preserves_active_day_trades()

### Community 13 - "eToro API Operations Guidelines"
Cohesion: 0.15
Nodes (22): eToro Public API Operations Skill (v1.19.1), etoro-public-api-mcp Server (https://mcp.public-api.etoro.com), eToro OAuth Scopes & Umbrella Grants, Partner API Routes Visibility, Referenced eToro Public REST API Paths, execute-read MCP Tool, execute-write MCP Tool, get-all-routes MCP Tool (+14 more)

### Community 14 - "Live Stop-Loss Enforcement Tests"
Cohesion: 0.10
Nodes (7): Position, test_enforce_live_stops_decimal_normalization_and_spot(), test_live_mode_enforces_stop_loss_and_closes_all_etoro_lots(), test_sync_live_etoro_portfolio_preserves_metadata_all_position_ids_and_short_units(), test_sync_live_etoro_portfolio_synthetic_stop_loss(), test_broker_preserves_contributing_models_and_enforces_take_profit(), test_sync_live_etoro_portfolio_ignores_0001_placeholder_and_prevents_mismatched_entry_stop_churn()

### Community 17 - "AI Committee Background Worker"
Cohesion: 0.11
Nodes (12): get_ai_committee_engine(), auto_reset_circuit_breaker_endpoint(), autonomous_background_worker_loop(), _refresh_committee_batch(), _build_committee_macro_context(), build_prioritized_watchlist(), check_and_auto_recover_circuit_breaker(), evaluate_symbol_committee() (+4 more)

### Community 18 - "GitHub Keepalive Workflow"
Cohesion: 0.09
Nodes (21): DEFAULT_URL, INPUT_URL, SECRET_URL, target_url, jobs, keepalive, runs-on, steps (+13 more)

### Community 19 - "Broker Equity & Live Sync"
Cohesion: 0.15
Nodes (3): SimulatedBroker, test_circuit_breaker_health_diagnostic_and_auto_reset(), test_sync_live_etoro_trading_history_preserves_and_infers_day_trade_horizon()

### Community 21 - "Cockpit Snapshot State Endpoints"
Cohesion: 0.10
Nodes (10): _format_wyckoff_pattern_desc(), get_anomaly_detector(), get_arbitration(), get_cockpit_full_snapshot(), get_decision(), get_federation(), get_quadrant(), get_state() (+2 more)

### Community 22 - "EToroClient Cluster"
Cohesion: 0.12
Nodes (3): EToroClient, main(), test_etoro_update_position_patch_sl_tp()

### Community 23 - "Portfolio & Account UI Bindings"
Cohesion: 0.14
Nodes (19): eToro Auth Status Alert Banner (#etoroAuthAlertBanner), Portfolio Summary Stats Strip (.portfolio-stats-bar), POST /api/config, GET /api/etoro/credentials, GET /api/etoro/status, POST /api/etoro/test_connection, GET /api/portfolio, eToro API Portal (api-portal.etoro.com) (+11 more)

### Community 24 - "Engine API Integration Tests"
Cohesion: 0.10
Nodes (6): test_day_trading_api_endpoints(), test_flow_transparency_api_endpoints(), test_flow_transparency_engine(), test_sync_live_etoro_portfolio(), test_world_news_api_endpoint(), test_wyckoff_api_endpoints_and_webhooks()

### Community 25 - "Market Trading Hours Telemetry"
Cohesion: 0.14
Nodes (4): HeartbeatOutput, SyncDriftOutput, TelemetryModule, test_telemetry_ba_is_us_nyse_not_lse()

### Community 26 - "Wyckoff Range Structure Engine"
Cohesion: 0.16
Nodes (4): WyckoffRangeEngine, test_wyckoff_range_engine(), test_wyckoff_detects_spring_and_sos_breakout(), test_wyckoff_detects_utad_and_sow_breakdown()

### Community 28 - "Backtest & Preset API Endpoints"
Cohesion: 0.12
Nodes (10): apply_parameters_endpoint(), ApplyParametersRequest, BacktestRequest, optimize_parameters_endpoint(), OptimizeRequest, PositionUpdateRequest, run_backtest_endpoint(), set_watchlist_preset() (+2 more)

### Community 29 - "Koyeb Service Manifest"
Cohesion: 0.12
Nodes (16): branch, build_command, repository, run_command, name, port, protocol, path (+8 more)

### Community 30 - "Watchlist & Optimization Tests"
Cohesion: 0.18
Nodes (7): _make_mock_etoro_client(), test_etoro_watchlist_creation_uses_percent20_nested_id_and_never_falls_back_to_101(), test_etoro_watchlist_duplicate_422_recovers_existing_and_serializes_threads(), test_etoro_watchlist_invalidates_stale_cached_id_on_422(), test_etoro_watchlist_matches_plus_encoded_name_and_skips_redundant_writes(), test_etoro_watchlist_queries_real_endpoint_directly(), fake_request()

### Community 31 - "Market Regime Classification Engine"
Cohesion: 0.19
Nodes (7): QuadrantOutput, RegimeState, QuadrantModule, RegimeModule, run_trading_day_simulation(), test_quadrant_matrix(), test_regime_classification()

### Community 32 - "Background News & Flow Refresh"
Cohesion: 0.13
Nodes (9): ConfigUpdateRequest, force_news_refresh(), _do_refresh(), force_smart_money_refresh(), get_system_config(), ModeSwitchRequest, switch_execution_mode(), _bg_live_init() (+1 more)

### Community 33 - "Execution Architecture Blueprint Docs"
Cohesion: 0.17
Nodes (12): 10 Core Blueprint & Cockpit REST API Endpoints, Panel 02: Decision Action Engine, Panel 09: Event Timeline & Immutable Ledger, Panel 03: Federation Multi-Strategy Ensemble, Panel 07: Live Fractional Positions, Predictive Execution Cockpit (9-Panel Architecture), Panel 06: Risk vs. Impact Quadrant Matrix, Panel 01: State Telemetry (+4 more)

### Community 34 - "Cockpit Analytics Modals UI"
Cohesion: 0.17
Nodes (14): eToro Public API Integration (https://public-api.etoro.com), External Market, Macro News & Alternative Flow Data Feeds, AI Investment Committee Modal (#aiCommitteeModal), Quantitative Backtester & Parameter Optimizer Modal (#backtestModal), Daily Report & 5-Day Performance Audit Modal (#dailyReportModal), 3-Way Market Flow Transparency Modal (#flowTransparencyModal), Live Trading Mode Switch Modal (#modeSwitchModal), Universal Market Screener & Stock Universe Modal (#screenerModal) (+6 more)

### Community 36 - "5-Source Pre-Trade Gate Docs"
Cohesion: 0.15
Nodes (11): collect_pre_trade_intelligence (backend/server.py), eToro Data & Live Portfolio Sync, Graft Code Graph Index (41 files, 500 nodes, 1,340 edges), Authoritative eToro Instruments DB (SQLite), MarketScreener (backend/engine/screener.py), FederationModule & Pre-Trade Intel Telemetry, NewsIntelligenceEngine (Finnhub, SEC EDGAR & World News), SmartMoneyEngine (backend/engine/smart_money.py) (+3 more)

### Community 37 - "Wyckoff & Flow Endpoints"
Cohesion: 0.16
Nodes (6): get_flow_transparency(), get_flow_transparency_ticker(), get_wyckoff_structure_endpoint(), get_wyckoff_structure_ticker_endpoint(), receive_wyckoff_webhook(), root_health()

### Community 38 - "Risk, Impact & Slippage Metrics"
Cohesion: 0.23
Nodes (3): clamp(), MetricsModule, test_metrics_computation()

### Community 39 - "Deployment & Dependency Stack"
Cohesion: 0.18
Nodes (13): Cloudflare Tunnel & Gradio SDK Hosting (app.py), Frontend Dashboard Responsiveness (frontend/dashboard.js), OpenBB Unified Feed Wrapper (src/openbb_feed.py), Local Uvicorn Server Launch (backend.server:app), fastapi>=0.100.0, gradio>=4.0.0, gunicorn>=21.2.0, pydantic>=2.0.0 (+5 more)

### Community 40 - "Cockpit Desktop Web Interface"
Cohesion: 0.23
Nodes (12): Predictive Execution Cockpit UI (frontend/index.html), Cockpit Client Controller (dashboard.js), Panel 01: STATE // REGIME MONITOR, Panel 02: DECISION // ACTION ENGINE, Panel 03: FEDERATION // MODEL ENSEMBLE, Panel 04: ARBITRATION // RISK GATES, Panel 05: ANOMALY DETECTOR, Panel 06: QUADRANT // RISK x IMPACT (+4 more)

### Community 41 - "Live Trading Safeguards Docs"
Cohesion: 0.18
Nodes (5): requests>=2.31.0, Antigravity Project Catalog & Historical Sessions, Pytest Automated Regression Test Suite (tests/test_engine.py), Autonomous Stock Trading System (9-Panel Cockpit & Backend), Official eToro REST v2 Execution Engine

### Community 44 - "Render Cloud Blueprint Config"
Cohesion: 0.18
Nodes (10): key, sync, value, services, buildCommand, envVars, name, runtime (+2 more)

### Community 46 - "Arbitration & Quadrant Matrix"
Cohesion: 0.29
Nodes (4): ArbitrationModule, ArbitrationOutput, test_daily_loss_circuit_breaker_and_arbitration(), test_day_trading_gate_blocks_instead_of_silent_swing_conversion_and_enforces_allocation_and_eod_window()

### Community 47 - "Cloud Hosting & Keepalive Docs"
Cohesion: 0.27
Nodes (8): Koyeb Cloud Infrastructure (Procfile & koyeb.yaml), Render Cloud Blueprint & Account Replication (render.yaml), Finnhub Market Data & Offline Tick Simulation Fallback, 1-Click Render Cloud Deployment (render.yaml), python-dotenv>=1.0.0, External Data & AI API Providers (Finnhub, Twelve Data, FMP, Alpha Vantage, Tavily, SerpAPI, Anspire, OpenRouter, Congress Invests, Equibles), Koyeb Free Hobby Tier Deployment (Procfile), Render Blueprint Replication & 750h Free Tier Economics

### Community 49 - "Polymarket Strategy Ecosystem Notes"
Cohesion: 0.20
Nodes (10): aarora4 Awesome Prediction Markets (>150 Tools), caiovicentino Claude-Powered Polymarket Trading Terminal, github.com/ccxt/ccxt, ent0n29/polybot Trader Behavior Analyzer, evan-kolberg Historical Market Backtesting Simulator, HarrierOnChain Trading Bot Toolkit, lihanyu81 Polymarket Limit Order Liquidity Bot, Polymarket Prediction Market Trading Ecosystem (+2 more)

### Community 50 - "Daily Loss Circuit Breaker Tests"
Cohesion: 0.33
Nodes (4): AnomalyModule, AnomalyDetectorOutput, test_anomaly_detection(), test_metrics_deterministic_and_normalizes_healthy_http_latency()

### Community 52 - "Pre-Trade 5-Source Intel Gate"
Cohesion: 0.22
Nodes (5): collect_pre_trade_intelligence(), execute_manual_action(), get_pre_trade_intelligence_endpoint(), ManualTradeRequest, test_five_source_pre_trade_intelligence_gate()

### Community 55 - "Cockpit UI Render Helpers"
Cohesion: 0.29
Nodes (7): fetchEtoroStatus(), renderCockpit(), renderPositionsTable(), setFlagActive(), setHorizonFilter(), updateExecutionModeUI(), updateGateItem()

### Community 56 - "subprocess Cluster"
Cohesion: 0.33
Nodes (3): test_dashboard_js_syntax(), test_python_symtable_no_undefined_globals(), check_table()

### Community 57 - "Instruments DB Singleton Lookup"
Cohesion: 0.40
Nodes (3): get_etoro_id(), get_instruments_db(), test_instruments_sqlite_db_and_endpoints()

### Community 59 - "UI Data & Order Dispatch"
Cohesion: 0.50
Nodes (5): fetchCockpitData(), fetchDayTradingStatus(), loadScreenerScan(), triggerManualTrade(), updateWatchlistUI()

## Ambiguous Edges - Review These
- `Polymarket Prediction Market Trading Ecosystem` → `X/Twitter Reference Posts (x_insider4 & RohOnChain)`  [AMBIGUOUS]
  tradingStrategies.txt · relation: cites
- `github.com/myhhub/stock` → `X/Twitter Reference Posts (x_insider4 & RohOnChain)`  [AMBIGUOUS]
  tradingStrategies.txt · relation: cites
- `github.com/ccxt/ccxt` → `X/Twitter Reference Posts (x_insider4 & RohOnChain)`  [AMBIGUOUS]
  tradingStrategies.txt · relation: cites

## Knowledge Gaps
- **36 isolated node(s):** `eToro Public API Operations Skill (v1.19.1)`, `get-trader-profile-summary MCP Tool (Phase 0.75)`, `Telemetry Heartbeat & Sync Drift Monitor`, `10 Core Blueprint & Cockpit REST API Endpoints`, `1-Click Render Cloud Deployment (render.yaml)` (+31 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 653 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SmartMoneyEngine` connect `Smart Money & Congress Radar` to `Cockpit Diagnostics & Telemetry API`, `Live Data Feed Manager`, `Engine Package Architecture Docs`, `Watchlist & Optimization Tests`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Are the 7 inferred relationships involving `SimulatedBroker` (e.g. with `AdaptiveLearner` and `MistakeLogEntry`) actually correct?**
  _`SimulatedBroker` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `eToro Public API Operations Skill (v1.19.1)`, `get-trader-profile-summary MCP Tool (Phase 0.75)`, `Telemetry Heartbeat & Sync Drift Monitor` to the rest of the system?**
  _36 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Dashboard UI State Controller` be split into smaller, more focused modules?**
  _Cohesion score 0.01904761904761905 - nodes in this community are weakly interconnected._
- **Why does `EToroClient` connect `EToroClient Cluster` to `Cockpit Diagnostics & Telemetry API`, `Instruments SQLite Query Cache`, `.bootstrap instrument ids() Cluster`, `.call mcp tool() Cluster`, `Day Trade & Position Execution`, `.create order() Cluster`, `config.py Cluster`, `eToro Live API Client`, `.close all positions() Cluster`, `Engine API Integration Tests`, `.resolve instrument id() Cluster`, `.test websocket() Cluster`, `Watchlist & Optimization Tests`?**
  _High betweenness centrality (0.072) - this node is a cross-community bridge._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Polymarket Prediction Market Trading Ecosystem` and `X/Twitter Reference Posts (x_insider4 & RohOnChain)`?**
  _Edge tagged AMBIGUOUS (relation: cites) - confidence is low._
- **What is the exact relationship between `github.com/myhhub/stock` and `X/Twitter Reference Posts (x_insider4 & RohOnChain)`?**
  _Edge tagged AMBIGUOUS (relation: cites) - confidence is low._
"""
Comprehensive unit and integration test suite for the Predictive Execution Cockpit
and Autonomous Trading Engine.
"""
import pytest
from fastapi.testclient import TestClient

from backend.config import config
from backend.server import app, broker
from backend.engine.data_feed import DataFeedManager
from backend.engine.metrics import MetricsModule
from backend.engine.regime import RegimeModule
from backend.engine.federation import FederationModule
from backend.engine.arbitration import ArbitrationModule
from backend.engine.anomaly import AnomalyModule
from backend.engine.quadrant import QuadrantModule
from backend.engine.telemetry import TelemetryModule
from backend.engine.learner import AdaptiveLearner
from backend.engine.broker import SimulatedBroker
from backend.engine.models import TradeRecord

client = TestClient(app)

def test_root_health():
    response = client.get("/")
    assert response.status_code == 200
    # Root endpoint serves dashboard HTML or health status JSON
    assert "html" in response.headers.get("content-type", "") or response.json() == {"status": "ok"}
    head_resp = client.head("/")
    assert head_resp.status_code == 200

def test_data_feed_and_indicators():
    feed = DataFeedManager()
    quote = feed.get_latest_quote("AAPL")
    assert quote.symbol == "AAPL"
    assert quote.price > 0
    
    indicators = feed.get_technical_indicators("AAPL")
    assert "ema_9" in indicators
    assert "rsi_14" in indicators
    assert "bb_upper" in indicators
    assert 0 <= indicators["rsi_14"] <= 100

def test_metrics_computation():
    metrics_mod = MetricsModule()
    indicators = {"volatility_std": 2.5, "bb_mid": 150.0}
    metrics = metrics_mod.compute_all(indicators, actual_latency_ms=10.0)
    
    assert 0.0 <= metrics["risk"] <= 1.0
    assert 0.0 <= metrics["impact"] <= 1.0
    assert 0.0 <= metrics["slippage"] <= 1.0
    assert metrics["latency"] >= 1.0

def test_regime_classification():
    regime_mod = RegimeModule()
    # Test OK mode
    m_ok = {"risk": 0.2, "impact": 0.2, "slippage": 0.2, "latency": 10.0}
    ind = {"ema_9": 105.0, "ema_21": 100.0, "rsi_14": 60.0, "macd_line": 0.5, "adx": 30.0}
    res_ok = regime_mod.model_mode(m_ok, ind)
    assert res_ok.mode == "OK"
    assert res_ok.trend == "BULL_TREND"

    # Test CRITICAL mode
    m_crit = {"risk": 0.9, "impact": 0.8, "slippage": 0.7, "latency": 25.0}
    res_crit = regime_mod.model_mode(m_crit, ind)
    assert res_crit.mode == "CRITICAL"

def test_quadrant_matrix():
    q_mod = QuadrantModule()
    assert q_mod.quadrant(0.2, 0.2).quadrant == "LOW"
    assert q_mod.quadrant(0.5, 0.5).quadrant == "MEDIUM"
    assert q_mod.quadrant(0.5, 0.8).quadrant == "HIGH"
    assert q_mod.quadrant(0.8, 0.2).quadrant == "CRITICAL"

def test_anomaly_detection():
    anom_mod = AnomalyModule()
    normal_metrics = {"risk": 0.3, "impact": 0.3, "slippage": 0.3, "latency": 12.0}
    res_normal = anom_mod.anomaly_detector(normal_metrics, [100.0]*20, [1000.0]*20)
    assert not res_normal.anomaly_detected

    spike_metrics = {"risk": 0.92, "impact": 0.4, "slippage": 0.3, "latency": 25.0}
    res_spike = anom_mod.anomaly_detector(spike_metrics, [100.0]*20, [1000.0]*20)
    assert res_spike.anomaly_detected
    assert res_spike.risk_spike
    assert res_spike.latency_spike

def test_adaptive_learner_and_broker():
    learner = AdaptiveLearner()
    broker = SimulatedBroker(initial_capital=10000.0, learner=learner)
    
    # 1. Execute fractional order
    pos = broker.execute_order(
        symbol="NVDA",
        direction="LONG",
        allocated_usd=500.0,
        current_price=125.0,
        stop_loss_pct=0.02,
        take_profit_pct=0.05,
        rationale="Test Long Order",
        contributing_models={"momentum_trend": 0.8, "mean_reversion": -0.2}
    )
    assert pos is not None
    assert pos.symbol == "NVDA"
    assert pos.shares > 0
    assert pos.shares == round(500.0 / (125.0 * 1.0005), 4)
    assert "NVDA" in broker.positions

    # 2. Simulate Stop-Loss trigger (Loss scenario)
    trades = broker.update_price_and_check_stops("NVDA", 120.0)
    assert len(trades) == 1
    assert not trades[0].win
    assert trades[0].realized_pnl_usd < 0
    
    # Verify self-learning feedback triggered
    stats = learner.get_stats()
    assert stats.total_trades_evaluated >= 1
    assert len(stats.mistake_history) >= 1
    assert "NVDA" in stats.mistake_history[0].symbol
    # Verify model weight was adapted
    assert learner.weights["momentum_trend"] < 0.25 # Down-weighted after failure

def test_all_api_endpoints():
    orig_mode = config.execution_mode
    config.execution_mode = "simulated"
    try:
        # 10 Core Blueprint Endpoints
        r = client.get("/state?symbol=AAPL")
        assert r.status_code == 200
        assert "risk" in r.json()

        r = client.get("/decision?symbol=AAPL")
        assert r.status_code == 200
        assert "signal" in r.json()

        r = client.get("/federation?symbol=AAPL")
        assert r.status_code == 200
        assert "federation" in r.json()

        r = client.get("/arbitration?symbol=AAPL")
        assert r.status_code == 200
        assert "approved" in r.json()

        r = client.get("/anomaly_detector?symbol=AAPL")
        assert r.status_code == 200
        assert "anomaly_detected" in r.json()

        r = client.get("/node_events")
        assert r.status_code == 200
        assert "events" in r.json()

        r = client.get("/quadrant?symbol=AAPL")
        assert r.status_code == 200
        assert "quadrant" in r.json()

        r = client.get("/heartbeat")
        assert r.status_code == 200
        assert r.json()["alive"] is True

        r = client.get("/sync_drift")
        assert r.status_code == 200
        assert "drift_ms" in r.json()

        # Extended endpoints
        r = client.get("/api/cockpit/snapshot?symbol=AAPL")
        assert r.status_code == 200
        assert "state" in r.json()
        assert "decision" in r.json()
        assert "portfolio" in r.json()
        assert "learning" in r.json()

        r = client.get("/api/portfolio")
        assert r.status_code == 200
        assert "cash" in r.json()

        r = client.get("/api/trades")
        assert r.status_code == 200
        assert "trades" in r.json()

        r = client.get("/api/learning/stats")
        assert r.status_code == 200
        assert "strategy_weights" in r.json()

        r = client.post("/api/action/trade", json={"symbol": "MSFT", "action": "BUY", "amount_usd": 300.0, "bypass_market_hours": True})
        assert r.status_code == 200

        r = client.post("/api/action/trade", json={"symbol": "MSFT", "action": "CLOSE"})
        assert r.status_code == 200

        r = client.post("/api/portfolio/reset")
        assert r.status_code == 200
        assert r.json()["cash"] > 0

        # Circuit breaker reset endpoint test
        r = client.post("/api/circuit_breaker/reset")
        assert r.status_code == 200
        assert r.json()["status"] == "success"
        assert r.json()["drawdown_pct"] == 0.0
        assert r.json()["circuit_breaker_active"] is False
    finally:
        config.execution_mode = orig_mode

def test_backtester_and_optimizer():
    from backend.engine.backtester import BacktesterEngine
    bt = BacktesterEngine()

    # 1. Run backtest simulation
    res = bt.run_backtest(
        symbol="SOXL",
        initial_capital=10000.0,
        stop_loss_pct=0.03,
        take_profit_pct=0.06,
        adx_threshold=20.0,
        num_ticks=100
    )
    assert res.symbol == "SOXL"
    assert res.starting_capital == 10000.0
    assert res.ending_equity > 0
    assert isinstance(res.trades, list)

    # 2. Run parameter optimizer
    opt = bt.optimize_parameters(symbol="SOXL", initial_capital=10000.0)
    assert opt.symbol == "SOXL"
    assert opt.total_combinations_tested == 48
    assert opt.optimal_candidate is not None
    assert opt.optimal_candidate.rank == 1
    assert len(opt.top_candidates) == 5
    assert "Optimal configuration for SOXL" in opt.recommendation_summary

def test_backtest_api_endpoints():
    client = TestClient(app)

    # Test single-asset backtest run endpoint
    r = client.post("/api/backtest/run", json={
        "symbol": "TQQQ",
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.050,
        "adx_threshold": 20.0,
        "num_ticks": 80
    })
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "TQQQ"
    assert "ending_equity" in data
    assert "win_rate_pct" in data

    # Test Portfolio-Wide (ALL) backtest run endpoint
    r_all = client.post("/api/backtest/run", json={
        "symbol": "ALL",
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.050,
        "adx_threshold": 20.0,
        "num_ticks": 60
    })
    assert r_all.status_code == 200
    all_data = r_all.json()
    assert "PORTFOLIO" in all_data["symbol"]
    assert "per_stock_breakdown" in all_data
    assert len(all_data["per_stock_breakdown"]) >= 5

    # Test Crypto & Commodity backtesting
    r_btc = client.post("/api/backtest/run", json={"symbol": "BTC", "num_ticks": 60})
    assert r_btc.status_code == 200
    r_gold = client.post("/api/backtest/run", json={"symbol": "GOLD", "num_ticks": 60})
    assert r_gold.status_code == 200

    # Test backtest optimize endpoint
    r = client.post("/api/backtest/optimize", json={"symbol": "MARA"})
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "MARA"
    assert "optimal_candidate" in data

    # Test backtest apply endpoint
    r = client.post("/api/backtest/apply", json={
        "symbol": "MARA",
        "stop_loss_pct": 0.035,
        "take_profit_pct": 0.075,
        "adx_threshold": 22.0
    })
    assert r.status_code == 200
    assert r.json()["status"] == "applied"

def test_pdf_and_email_report_endpoints():
    client = TestClient(app)

    # 1. Test Daily PDF generation
    r = client.get("/api/reports/pdf?report_type=daily")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 1000

    # 2. Test 5-Day PDF generation
    r = client.get("/api/reports/pdf?report_type=5day")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 1000

    # 3. Test Email Dispatch endpoint to lisawalker6898@gmail.com
    r = client.post("/api/reports/email", json={
        "recipient": "lisawalker6898@gmail.com",
        "report_type": "daily"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "success"
    assert data["recipient"] == "lisawalker6898@gmail.com"
    assert "trading_report_daily_" in data["filename"]

def test_screener_and_dynamic_watchlist():
    client = TestClient(app)

    # 1. Test Universe Endpoint
    r = client.get("/api/screener/universe")
    assert r.status_code == 200
    u = r.json()
    assert u["total_instruments"] >= 50
    assert "NVDA" in u["universe"]
    assert "TSLA" in u["universe"]

    # 2. Test Real-time Market Screener Scan
    r = client.get("/api/screener/scan?top_n=20")
    assert r.status_code == 200
    screened = r.json()
    assert len(screened) == 20
    assert "opportunity_score" in screened[0]
    assert "supertrend" in screened[0]

    # 3. Test Adding custom stock (e.g. TSLA, PLTR)
    r = client.post("/api/watchlist/add", json={"symbol": "PLTR"})
    assert r.status_code == 200
    assert "PLTR" in r.json()["active_watchlist"]

    # 4. Test Preset Loading
    r = client.post("/api/watchlist/preset", json={"preset_key": "ai_tech_titans"})
    assert r.status_code == 200
    assert "NVDA" in r.json()["active_watchlist"]

    # 5. Test Auto-Add Top Screened
    r = client.post("/api/screener/auto_add_top?top_n=10")
    assert r.status_code == 200
    assert r.json()["status"] == "success"

def test_etoro_api_client_and_mode_switching():
    from src.services.etoro.client import EToroClient
    import uuid

    # 1. Test EToroClient unit methods
    client_instance = EToroClient(api_key="test_api_key_12345", user_key="test_user_key_67890", base_url="https://api.etoro.com")
    assert client_instance.is_configured() is True
    
    headers = client_instance._build_headers()
    assert headers["x-api-key"] == "test_api_key_12345"
    assert headers["x-user-key"] == "test_user_key_67890"
    assert "x-request-id" in headers
    # Verify valid UUID v4
    val_uuid = uuid.UUID(headers["x-request-id"], version=4)
    assert str(val_uuid) == headers["x-request-id"]

    # 2. Test API status endpoint
    test_app_client = TestClient(app)
    r = test_app_client.get("/api/etoro/status")
    assert r.status_code == 200
    status_data = r.json()
    assert "execution_mode" in status_data
    assert "base_url" in status_data

    # 3. Test Test Connection endpoint (Read-only)
    r_conn = test_app_client.post("/api/etoro/test_connection")
    assert r_conn.status_code == 200
    conn_data = r_conn.json()
    assert "status" in conn_data

    # 4. Test Mode Switch to Demo (preserving original mode)
    orig_mode = config.execution_mode
    orig_sim = config.simulation_mode
    try:
        r_demo = test_app_client.post("/api/mode/switch", json={"mode": "demo"})
        assert r_demo.status_code == 200
        assert r_demo.json()["execution_mode"] == "demo"
    finally:
        config.execution_mode = orig_mode
        config.simulation_mode = orig_sim
        broker.save_state({"execution_mode": orig_mode, "simulation_mode": orig_sim})

    # 4b. Test POST /api/config endpoint update
    r_cfg = test_app_client.post("/api/config", json={"risk_per_trade_pct": 0.02})
    assert r_cfg.status_code == 200
    assert r_cfg.json()["status"] == "updated"
    assert "config" in r_cfg.json()

    # 5. Test Instrument ID Resolution
    # AAPL=1001 confirmed from official eToro API docs.
    # BTC=100000 consistent across community eToro API wrappers.
    aapl_id = client_instance.resolve_instrument_id("AAPL")
    btc_id = client_instance.resolve_instrument_id("BTC")
    assert aapl_id == 1001, f"AAPL should be 1001 per official eToro docs, got {aapl_id}"
    assert btc_id == 100000, f"BTC should be 100000 per community-verified sources, got {btc_id}"

    # 6. Test 5-Day Trade Watchlist Sync Endpoint
    r_sync_5d = test_app_client.post("/api/etoro/sync_5day_trades")
    assert r_sync_5d.status_code == 200
    d_5d = r_sync_5d.json()
    assert d_5d["status"] == "success"
    assert d_5d["synced_stocks_count"] >= 5

    # 7. Test Active Watchlist Sync Endpoint
    r_sync_wl = test_app_client.post("/api/etoro/sync_watchlist")
    assert r_sync_wl.status_code == 200
    d_wl = r_sync_wl.json()
    assert d_wl["status"] == "success"
    assert len(d_wl["synced_symbols"]) >= 5

    # 8. Test WebSocket & MCP diagnostic endpoints
    r_ws = test_app_client.get("/api/etoro/ws-test")
    assert r_ws.status_code == 200
    assert "status" in r_ws.json()

    r_mcp = test_app_client.get("/api/etoro/mcp-test?symbol=BTC")
    assert r_mcp.status_code == 200
    assert "success" in r_mcp.json() or "error" in r_mcp.json()

    # 9. Test eToro Auth Cooldown & 401 Re-Auth Safeguard
    from backend.server import etoro_client as server_etoro_client
    assert not client_instance.is_in_auth_cooldown()
    client_instance.trigger_auth_cooldown("Test 401 Unauthorized", cooldown_sec=15.0)
    assert client_instance.is_in_auth_cooldown() is True
    
    # Verify create_order immediately suppresses orders during cooldown without burning API calls
    cooldown_order = client_instance.create_order(symbol="AAPL", amount_usd=50.0)
    assert cooldown_order["success"] is False
    assert cooldown_order["status_code"] == 401
    assert "re-auth cooldown" in cooldown_order["error"]

    # Verify /api/etoro/status reflects active cooldown on server client
    server_etoro_client.trigger_auth_cooldown("Test 401 Unauthorized", cooldown_sec=15.0)
    r_status = test_app_client.get("/api/etoro/status")
    assert r_status.status_code == 200
    stat_json = r_status.json()
    assert stat_json["auth_cooldown"] is True
    assert stat_json["auth_cooldown_remaining_sec"] > 0
    assert "Test 401" in stat_json["last_auth_error"]

    # Clear cooldown for subsequent tests
    client_instance._auth_cooldown_until = 0.0
    client_instance._last_auth_error = ""
    server_etoro_client._auth_cooldown_until = 0.0
    server_etoro_client._last_auth_error = ""
    assert client_instance.is_in_auth_cooldown() is False
    assert server_etoro_client.is_in_auth_cooldown() is False


def test_instruments_sqlite_db_and_endpoints():
    """
    Tests the durable SQLite instruments database, ticker-to-ID lookup function,
    alias normalization, and associated REST endpoints.
    """
    from backend.engine.instruments_db import get_etoro_id, get_instruments_db

    db = get_instruments_db()

    # 1. Test get_etoro_id() function across diverse asset classes
    assert get_etoro_id("BTC") == 100000
    assert get_etoro_id("ETH") == 100001
    assert get_etoro_id("AAPL") == 1001
    assert get_etoro_id("NVDA") == 1137
    assert get_etoro_id("VTI") == 2010
    assert get_etoro_id("NVDL") == 2014
    assert get_etoro_id("FRA40") == 2106

    # 2. Test alias normalization (e.g. commodities with .FUT suffix)
    assert get_etoro_id("CORN.FUT") == 3014
    assert get_etoro_id("CORN") == 3014
    assert get_etoro_id("GOLD.FUT") == 3001
    assert get_etoro_id("GOLD") == 3001

    # 3. Test dynamic insertion and immediate lookup
    db.upsert_instrument("TESTTICKER", 999999, name="Test Instrument Asset", category="Testing")
    assert get_etoro_id("TESTTICKER") == 999999
    inst_data = db.get_instrument("TESTTICKER")
    assert inst_data is not None
    assert inst_data["instrument_id"] == 999999
    assert inst_data["name"] == "Test Instrument Asset"

    # 4. Test REST API: GET /api/instruments
    test_client = TestClient(app)
    r_list = test_client.get("/api/instruments")
    assert r_list.status_code == 200
    data_list = r_list.json()
    assert data_list["status"] == "success"
    assert data_list["total_in_db"] >= 100
    assert len(data_list["instruments"]) >= 50

    # 5. Test REST API: GET /api/instruments with query filter
    r_query = test_client.get("/api/instruments?query=AAPL")
    assert r_query.status_code == 200
    data_q = r_query.json()
    assert any(item["symbol"] == "AAPL" for item in data_q["instruments"])

    # 6. Test REST API: GET /api/instruments/{symbol}
    r_aapl = test_client.get("/api/instruments/AAPL")
    assert r_aapl.status_code == 200
    data_aapl = r_aapl.json()
    assert data_aapl["symbol"] == "AAPL"
    assert data_aapl["instrument_id"] == 1001

    # 7. Test REST API: GET /api/instruments/{symbol} 404 for unknown ticker
    r_unknown = test_client.get("/api/instruments/NONEXISTENT_TICKER_XYZ")
    assert r_unknown.status_code == 404

    # 8. Test REST API: POST /api/instruments/sync
    r_sync = test_client.post("/api/instruments/sync")
    assert r_sync.status_code == 200
    data_sync = r_sync.json()
    assert data_sync["status"] == "success"
    assert "total_instruments" in data_sync
    assert data_sync["total_instruments"] >= 100


def test_close_all_trades_and_crypto_deactivation():
    """
    Verifies that:
    1. Emergency close all endpoint POST /api/positions/close_all successfully clears positions.
    2. Any attempt to manually BUY or SHORT crypto tickers (e.g. BTC, ETH) is rejected with HTTP 400.
    3. Adding crypto tickers to the active watchlist is rejected with HTTP 400.
    4. Market screener permanently excludes all crypto assets.
    """
    orig_mode = config.execution_mode
    config.execution_mode = "simulated"
    try:
        test_client = TestClient(app)

        # 1. Test POST /api/positions/close_all
        r_close = test_client.post("/api/positions/close_all")
        assert r_close.status_code == 200
        close_data = r_close.json()
        assert close_data["status"] == "success"
        assert "closed_local_trades" in close_data

        # 2. Test manual trade rejection for Crypto
        r_btc_buy = test_client.post("/api/action/trade", json={"symbol": "BTC", "action": "BUY", "amount_usd": 100.0})
        assert r_btc_buy.status_code == 400
        assert "Cryptocurrency trading is permanently deactivated" in r_btc_buy.json()["detail"]

        r_eth_short = test_client.post("/api/action/trade", json={"symbol": "ETH", "action": "SHORT", "amount_usd": 100.0})
        assert r_eth_short.status_code == 400
        assert "Cryptocurrency trading is permanently deactivated" in r_eth_short.json()["detail"]

        # 3. Test watchlist add rejection for Crypto
        r_add_crypto = test_client.post("/api/watchlist/add", json={"symbol": "SOL"})
        assert r_add_crypto.status_code == 400
        assert "Cryptocurrency trading is permanently deactivated" in r_add_crypto.json()["detail"]

        # 4. Test market screener exclusion
        from backend.engine.screener import MarketScreener
        from backend.server import CRYPTO_SYMBOLS
        screened = MarketScreener.scan_universe()
        for item in screened:
            assert item["symbol"] not in CRYPTO_SYMBOLS
            assert item.get("category", "").lower() != "crypto"
    finally:
        config.execution_mode = orig_mode


def test_sync_live_etoro_portfolio():
    """
    Verifies that SimulatedBroker.sync_live_etoro_portfolio() seamlessly parses
    and synchronizes live eToro account cash, equity, and multi-asset holdings.
    """
    from backend.server import broker

    mock_etoro_data = {
        "totals": {
            "availableCash": 1114.91,
            "totalValue": 1292.09,
            "invested": 176.24,
            "unrealizedPnL": 0.94,
            "unrealizedPnLPercent": 0.53,
            "netDeposit": 1291.15
        },
        "holdings": [
            {
                "market": {"symbol": "AAPL", "instrumentId": 1001},
                "invested": 48.0,
                "value": 48.60,
                "pnl": 0.60,
                "pnlPercent": 1.25,
                "units": 0.21,
                "avgOpenRate": 228.57,
                "currentRate": 231.42,
                "positions": [{"positionId": "10001", "openTime": "2026-09-10T14:30:00Z", "isBuy": True}]
            },
            {
                "market": {"symbol": "META", "instrumentId": 1003},
                "invested": 32.0,
                "value": 32.60,
                "pnl": 0.60,
                "pnlPercent": 1.88,
                "units": 0.06,
                "avgOpenRate": 533.33,
                "currentRate": 543.33,
                "positions": [{"positionId": "10002", "openTime": "2026-09-10T14:31:00Z", "isBuy": True}]
            },
            {
                "market": {"symbol": "TSLA", "instrumentId": 1111},
                "invested": 32.0,
                "value": 31.87,
                "pnl": -0.13,
                "pnlPercent": -0.41,
                "units": 0.14,
                "avgOpenRate": 228.57,
                "currentRate": 227.64,
                "positions": [{"positionId": "10003", "openTime": "2026-09-10T14:32:00Z", "isBuy": True}]
            },
            {
                "market": {"symbol": "PLTR", "instrumentId": 7991},
                "invested": 32.0,
                "value": 31.81,
                "pnl": -0.19,
                "pnlPercent": -0.59,
                "units": 0.90,
                "avgOpenRate": 35.56,
                "currentRate": 35.34,
                "positions": [{"positionId": "10004", "openTime": "2026-09-10T14:33:00Z", "isBuy": True}]
            },
            {
                "market": {"symbol": "NVDA", "instrumentId": 1137},
                "invested": 32.24,
                "value": 32.30,
                "pnl": 0.06,
                "pnlPercent": 0.19,
                "units": 0.28,
                "avgOpenRate": 115.14,
                "currentRate": 115.36,
                "positions": [{"positionId": "10005", "openTime": "2026-09-10T14:34:00Z", "isBuy": True}]
            }
        ]
    }

    broker.sync_live_etoro_portfolio(mock_etoro_data)

    assert broker.cash == 1114.91
    assert broker.get_equity() == 1292.09
    assert len(broker.positions) == 5
    assert "AAPL" in broker.positions
    assert "META" in broker.positions
    assert "TSLA" in broker.positions
    assert "PLTR" in broker.positions
    assert "NVDA" in broker.positions

    summary = broker.get_portfolio_summary()
    assert summary.cash == 1114.91
    assert summary.equity == 1292.09
    assert summary.unrealized_pnl_usd == 0.94
    assert len(summary.open_positions) == 5


def test_pattern_recognition_and_volume_surge():
    """
    Tests technical pattern recognition algorithms ported from myhhub/stock:
    Double Bottom, Double Top, Range Breakout, Volume Surge, and Chip Distribution.
    """
    import numpy as np
    from backend.engine.indicators import TechnicalIndicators

    # 1. Volume Surge Factor
    normal_vols = np.array([100000.0] * 20 + [250000.0])
    surge = TechnicalIndicators.calc_volume_surge(normal_vols, period=20)
    assert surge >= 2.0

    # 2. Consolidation Range Breakout
    highs = np.array([100.0] * 20 + [108.0])
    lows = np.array([90.0] * 20 + [99.0])
    prices = np.array([95.0] * 20 + [106.0])
    breakout_type, lvl = TechnicalIndicators.detect_range_breakout(prices, highs, lows, period=20)
    assert breakout_type == "BULL_BREAKOUT"
    assert lvl == 100.0

    # 3. Double Bottom ('W' Reversal Pattern)
    # Construct W pattern: decline -> low 1 (90) -> rally (96) -> low 2 (90.5) -> recovery (95)
    w_prices = np.array(
        [100, 98, 95, 92, 90, 90, 91, 93, 95, 96, 95, 93, 91, 90.5, 91, 93, 94, 95, 96, 97],
        dtype=float
    )
    detected, neck, conf = TechnicalIndicators.detect_double_bottom(w_prices, threshold_pct=0.02)
    assert detected is True
    assert neck >= 95.0
    assert conf > 0.5

    # 4. Double Top ('M' Reversal Pattern)
    m_prices = np.array(
        [100, 105, 110, 112, 112, 110, 106, 104, 102, 104, 108, 111.5, 112, 110, 108, 105, 103, 101, 99, 98],
        dtype=float
    )
    m_det, m_neck, m_conf = TechnicalIndicators.detect_double_top(m_prices, threshold_pct=0.02)
    assert m_det is True
    assert m_neck <= 104.0

    # 5. Chip Distribution
    vol_arr = np.array([50000.0] * len(w_prices))
    chips = TechnicalIndicators.calc_chip_distribution_density(w_prices, vol_arr)
    assert "chip_core_price" in chips
    assert "chip_support" in chips


def test_day_trading_and_eod_auto_flatten():
    """
    Tests the Day Trading sub-engine:
    1. Executes orders with horizon='day' vs horizon='swing'.
    2. Verifies tight stops calibration for day trades.
    3. Verifies EOD Auto-Flatten routine auto-liquidates 'day' trades while preserving 'swing' positions.
    4. Verifies core holdings (AAPL, NVDA) are permanently shielded from liquidation.
    """
    from backend.engine.broker import SimulatedBroker
    test_broker = SimulatedBroker(initial_capital=5000.0)

    # 1. Open Long-Term Swing Position on MSFT
    swing_pos = test_broker.execute_order(
        symbol="MSFT",
        direction="LONG",
        allocated_usd=300.0,
        current_price=400.0,
        stop_loss_pct=0.025,
        take_profit_pct=0.050,
        rationale="Multi-day swing momentum",
        horizon="swing"
    )
    assert swing_pos is not None
    assert swing_pos.horizon == "swing"
    assert swing_pos.max_hold_until is None

    # 2. Open Intraday Day Trade on TSLA
    day_pos = test_broker.execute_order(
        symbol="TSLA",
        direction="LONG",
        allocated_usd=200.0,
        current_price=220.0,
        stop_loss_pct=0.012,
        take_profit_pct=0.024,
        rationale="Intraday breakout momentum",
        horizon="day",
        max_hold_hours=3.5
    )
    assert day_pos is not None
    assert day_pos.horizon == "day"
    assert day_pos.max_hold_until is not None

    # Verify positions exist
    assert "MSFT" in test_broker.positions
    assert "TSLA" in test_broker.positions

    # 3. Simulate EOD Auto-Flatten Routine
    flattened = test_broker.auto_flatten_day_trades(
        current_prices={"TSLA": 224.0, "MSFT": 405.0},
        exit_rationale="EOD Auto-Flatten: Approaching market close"
    )

    # TSLA (day trade) MUST be closed
    assert len(flattened) == 1
    assert flattened[0].symbol == "TSLA"
    assert flattened[0].horizon == "day"
    assert "TSLA" not in test_broker.positions

    # MSFT (swing trade) MUST remain open and untouched!
    assert "MSFT" in test_broker.positions
    assert test_broker.positions["MSFT"].horizon == "swing"


def test_daily_loss_circuit_breaker_and_arbitration():
    """
    Tests that the Risk Engine trips the daily loss circuit breaker when
    intraday losses hit the limit, halting new day trades while keeping portfolio safe.
    """
    from backend.engine.arbitration import ArbitrationModule
    arb_mod = ArbitrationModule()

    # Case A: Normal trading day
    normal_arb = arb_mod.arbitration(
        main_mode="OK",
        quadrant="LOW",
        anomaly_detected=False,
        current_drawdown_pct=0.01,
        max_drawdown_limit_pct=0.15,
        current_exposure_pct=0.20,
        max_exposure_limit_pct=0.85,
        active_positions_count=2,
        daily_drawdown_usd=5.0,
        max_daily_loss_usd=35.0,
        daily_drawdown_pct=0.004,
        max_daily_loss_pct=0.025,
        estimated_spread_pct=0.0005,
        max_spread_pct_day_trade=0.0015,
        active_day_trades=1,
        max_active_day_trades=4,
        day_trading_enabled=True
    )
    assert normal_arb.approved is True
    assert normal_arb.day_trade_approved is True
    assert normal_arb.daily_loss_circuit_breaker_active is False

    # Case B: Daily loss limit hit ($40 > $35 limit)
    hit_arb = arb_mod.arbitration(
        main_mode="OK",
        quadrant="LOW",
        anomaly_detected=False,
        current_drawdown_pct=0.03,
        max_drawdown_limit_pct=0.15,
        current_exposure_pct=0.20,
        max_exposure_limit_pct=0.85,
        active_positions_count=2,
        daily_drawdown_usd=40.0,
        max_daily_loss_usd=35.0,
        daily_drawdown_pct=0.031,
        max_daily_loss_pct=0.025,
        estimated_spread_pct=0.0005,
        max_spread_pct_day_trade=0.0015,
        active_day_trades=1,
        max_active_day_trades=4,
        day_trading_enabled=True
    )
    assert hit_arb.daily_loss_circuit_breaker_active is True
    assert hit_arb.day_trade_approved is False # Day trades halted!


def test_day_trading_api_endpoints():
    """Tests the new Day Trading REST endpoints: status, toggle, and manual flatten."""
    r_stat = client.get("/api/day_trading/status")
    assert r_stat.status_code == 200
    stat = r_stat.json()
    assert "enabled" in stat
    assert "active_day_trades_count" in stat
    assert "daily_loss_limit_usd" in stat

    r_toggle = client.post("/api/day_trading/toggle")
    assert r_toggle.status_code == 200
    assert "enabled" in r_toggle.json()

    # Toggle back to ensure enabled
    if not r_toggle.json()["enabled"]:
        client.post("/api/day_trading/toggle")

    r_flat = client.post("/api/day_trading/flatten")
    assert r_flat.status_code == 200
    assert r_flat.json()["status"] == "success"


def test_trading_hours_check_before_placing_trade():
    """
    Verifies that the Cockpit checks trading hours before checking whether to place a trade:
    1. Telemetry checks trading hours per asset class (LSE, US Equities, Crypto, Indices, Commodities).
    2. run_analysis_cycle enforces market hours and bypasses trade evaluation when market is closed.
    3. Manual trade endpoint rejects orders outside trading hours when market is closed.
    4. Broker execute_order respects market_open and enforce_market_hours safeguards.
    """
    telemetry = TelemetryModule()

    # 1. Telemetry verification: BTC is 24/7, Gold is continuous with maintenance
    btc_open, btc_msg = telemetry.check_trading_hours_before_trade("BTC")
    assert btc_open is True
    assert "24/7" in btc_msg

    vuke_open, vuke_msg = telemetry.check_trading_hours_before_trade("VUKE")
    assert "London Stock Exchange (LSE)" in vuke_msg

    # 2. Decision engine check: When market is closed, trade evaluation must be bypassed
    from backend.server import run_analysis_cycle
    analysis = run_analysis_cycle("VUKE")
    dec = analysis.get("decision")
    arb = analysis.get("arbitration")

    # Outside trading hours, decision signal MUST be HOLD and arbitration rejected
    if not vuke_open and config.enforce_market_hours:
        assert dec.signal == "HOLD"
        assert "Trading hours closed" in dec.rationale
        assert arb.approved is False
        assert any("Market Closed" in r for r in arb.reasons)

    # 3. Manual trade endpoint: Rejects live trades outside market hours
    if not vuke_open and config.enforce_market_hours:
        r = client.post("/api/action/trade", json={"symbol": "VUKE", "action": "BUY", "amount_usd": 100.0})
        # In live mode, should reject with 400
        if config.execution_mode == "live":
            assert r.status_code == 400
            assert "Trading hours are currently closed" in r.json()["detail"]

    # 4. Broker execution safeguard: Returns None if market is closed and enforced
    from backend.engine.broker import SimulatedBroker
    test_broker = SimulatedBroker(initial_capital=1000.0)
    blocked_pos = test_broker.execute_order(
        symbol="AAPL",
        direction="LONG",
        allocated_usd=100.0,
        current_price=220.0,
        market_open=False,
        enforce_market_hours=True
    )
    assert blocked_pos is None

def test_quant_trading_indicators():
    """
    Validates algorithms incorporated from je-suis-tm/quant-trading:
    1. Dual Thrust Range Breakout
    2. London Opening Range Breakout
    3. Heikin-Ashi Smoothed Trend Filter
    4. DataFeedManager Integration
    """
    from backend.engine.indicators import TechnicalIndicators
    from backend.engine.data_feed import DataFeedManager
    import numpy as np

    # 1. Dual Thrust Calculation
    highs = np.array([100.0, 102.0, 103.0, 105.0, 104.0])
    lows = np.array([96.0, 97.0, 99.0, 100.0, 99.0])
    closes = np.array([98.0, 101.0, 102.0, 103.0, 101.0])
    open_p = 101.0

    # 1. Dual Thrust Calculation (lookback=4 by default: highs[-4:], lows[-4:], closes[-4:])
    # HH = 105, LC = 101 -> 4. HC = 103, LL = 97 -> 6. Range = max(4, 6) = 6.0.
    # buy_line = 101 + 0.5 * 6 = 104.0
    # sell_line = 101 - 0.5 * 6 = 98.0
    res_buy = TechnicalIndicators.calc_dual_thrust(highs, lows, closes, open_price=open_p, current_price=105.0, k1=0.5, k2=0.5)
    assert res_buy["dual_thrust_signal"] == "BUY"
    assert res_buy["dual_thrust_buy_line"] == 104.0

    res_short = TechnicalIndicators.calc_dual_thrust(highs, lows, closes, open_price=open_p, current_price=97.0, k1=0.5, k2=0.5)
    assert res_short["dual_thrust_signal"] == "SHORT"
    assert res_short["dual_thrust_sell_line"] == 98.0

    res_neutral = TechnicalIndicators.calc_dual_thrust(highs, lows, closes, open_price=open_p, current_price=101.0, k1=0.5, k2=0.5)
    assert res_neutral["dual_thrust_signal"] == "NONE"

    # 2. London Breakout Calculation
    premarket = np.array([8400.0, 8420.0, 8410.0, 8430.0, 8390.0])
    # high = 8430 * 1.001 = 8438.43, low = 8390 * 0.999 = 8381.61
    res_london_buy = TechnicalIndicators.calc_london_breakout(premarket, current_price=8450.0, buffer_pct=0.001)
    assert res_london_buy["london_breakout_signal"] == "BUY"
    assert res_london_buy["london_range_high"] > 8430.0

    res_london_short = TechnicalIndicators.calc_london_breakout(premarket, current_price=8370.0, buffer_pct=0.001)
    assert res_london_short["london_breakout_signal"] == "SHORT"

    res_london_none = TechnicalIndicators.calc_london_breakout(premarket, current_price=8400.0, buffer_pct=0.001)
    assert res_london_none["london_breakout_signal"] == "NONE"

    # 3. Heikin-Ashi Smoothing
    ha_opens = np.array([100.0, 102.0, 104.0, 106.0, 108.0])
    ha_highs = np.array([103.0, 105.0, 107.0, 109.0, 111.0])
    ha_lows = np.array([99.0, 101.0, 103.0, 105.0, 107.0])
    ha_closes = np.array([102.5, 104.5, 106.5, 108.5, 110.5])

    res_ha = TechnicalIndicators.calc_heikin_ashi(ha_opens, ha_highs, ha_lows, ha_closes)
    assert res_ha["ha_trend"] == "BULLISH"
    assert res_ha["ha_bullish"] is True
    assert res_ha["ha_consecutive_bars"] >= 2
    assert "ha_open" in res_ha and "ha_close" in res_ha

    # 4. DataFeedManager Integration Check
    feed = DataFeedManager()
    feed.get_latest_quote("VUKE")
    ti = feed.get_technical_indicators("VUKE")
    assert "dual_thrust_signal" in ti
    assert "dual_thrust_buy_line" in ti
    assert "dual_thrust_sell_line" in ti
    assert "london_breakout_signal" in ti
    assert "london_range_high" in ti
    assert "london_range_low" in ti
    assert "heikin_ashi_trend" in ti
    assert "heikin_ashi_consecutive" in ti


def test_worldwide_news_and_macro_radar():
    """Validates classification of worldwide news headlines, macro themes, severity, and risk."""
    from backend.engine.news_intel import NewsIntelligenceEngine

    intel = NewsIntelligenceEngine()

    # Test classification of rate hike headline
    art_fed = intel._classify_macro_article(
        title="Federal Reserve signals interest rate hike as inflation exceeds CPI forecast",
        summary="Jerome Powell warns rates may stay elevated to combat persistence.",
        source="Reuters"
    )
    assert art_fed["theme"] == "CENTRAL_BANKS_RATES"
    assert "SPY" in art_fed["affected_assets"] or "QQQ" in art_fed["affected_assets"]
    assert art_fed["severity"] in ("HIGH", "MEDIUM")

    # Test classification of geopolitical war headline
    art_geo = intel._classify_macro_article(
        title="Middle east missile attacks disrupt oil shipping through Strait of Hormuz",
        summary="Military action causes crude oil prices to surge.",
        source="Bloomberg"
    )
    assert art_geo["theme"] in ("GEOPOLITICS_CONFLICT", "ENERGY_COMMODITIES")
    assert art_geo["severity"] == "HIGH"
    assert "ENERGY" in art_geo["affected_assets"]

    # Test classification of tech semiconductor headline
    art_tech = intel._classify_macro_article(
        title="Nvidia announces breakthrough in Blackwell AI chip foundry with TSMC",
        summary="Jensen Huang highlights record demand for AI processors.",
        source="CNBC"
    )
    assert "NVDA" in art_tech["affected_assets"]
    assert art_tech["sentiment"] == "BULLISH"
    assert art_tech["score"] > 0


def test_world_news_api_endpoint():
    """Validates GET /api/news/world endpoint response format and macro risk telemetry."""
    r = client.get("/api/news/world")
    assert r.status_code == 200
    data = r.json()
    assert "macro_risk" in data
    assert "macro_sentiment" in data["macro_risk"]
    assert "macro_risk_level" in data["macro_risk"]
    assert "macro_themes" in data["macro_risk"]
    assert "articles" in data
    assert isinstance(data["articles"], list)


def test_flow_transparency_engine():
    """Validates 3-way market transparency engine (OpenInsider + Quiver Quant + Finnhub 13F)."""
    from backend.server import smart_money
    flow = smart_money.get_unified_flow_transparency("AAPL", current_price=175.50)
    assert flow["symbol"] == "AAPL"
    assert flow["price"] == 175.50
    assert -1.0 <= flow["flow_conviction"] <= 1.0
    assert flow["flow_sentiment"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert "congress" in flow
    assert "institutional" in flow
    assert "insiders" in flow
    assert "summary" in flow
    assert isinstance(flow["insiders"], list)
    assert isinstance(flow["congress"], list)
    assert isinstance(flow["institutional"], list)

    conv = smart_money.get_flow_conviction("AAPL")
    assert -1.0 <= conv <= 1.0


def test_flow_transparency_api_endpoints():
    """Validates GET /api/flow/transparency and GET /api/flow/transparency/{symbol} endpoints."""
    # Test query param
    r1 = client.get("/api/flow/transparency?symbol=NVDA")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["symbol"] == "NVDA"
    assert "flow_conviction" in d1
    assert "summary" in d1

    # Test path param
    r2 = client.get("/api/flow/transparency/MSFT")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["symbol"] == "MSFT"
    assert "flow_sentiment" in d2


def test_wyckoff_range_engine():
    """Validates Wyckoff Range Engine structure, phase transitions, and multi-TP setups."""
    from backend.engine.wyckoff import WyckoffRangeEngine
    import numpy as np

    # Test on Gold simulation array
    prices = np.array([2480.0, 2485.0, 2490.0, 2482.0, 2510.0, 2505.0, 2495.0, 2478.0, 2492.0, 2515.0, 2520.0, 2525.0])
    res = WyckoffRangeEngine.detect_wyckoff_structure(prices=prices, symbol="GOLD", style="Balanced")

    assert res["symbol"] == "GOLD"
    assert res["structure_type"] in ("ACCUMULATION", "DISTRIBUTION", "NEUTRAL")
    assert res["phase_code"] in ("A", "B", "C", "D", "E")
    assert "creek_resistance" in res
    assert "ice_support" in res
    assert res["creek_resistance"] >= res["ice_support"]
    assert res["historical_win_rate_pct"] == 90.0
    assert 0 <= res["climax_score"] <= 100
    assert 0 <= res["spring_quality_score"] <= 100
    
    # Verify built-in trade setup R-multiples
    setup = res["trade_setup"]
    assert setup["direction"] in ("LONG", "SHORT", "NEUTRAL")
    assert "entry_price" in setup
    assert "stop_loss" in setup
    assert "tp1" in setup
    assert "tp2" in setup
    assert "tp3" in setup
    assert setup["breakeven_trigger"] == "TP1"


def test_wyckoff_api_endpoints_and_webhooks():
    """Validates /api/wyckoff/structure and /api/wyckoff/webhook endpoints."""
    # 1. Query parameter structure test
    r = client.get("/api/wyckoff/structure?symbol=GOLD&style=Balanced")
    assert r.status_code == 200
    data = r.json()
    assert data["symbol"] == "GOLD"
    assert "creek_resistance" in data
    assert "ice_support" in data
    assert "event_checklist" in data

    # 2. Path parameter structure test
    r_btc = client.get("/api/wyckoff/structure/BTC")
    assert r_btc.status_code == 200
    d_btc = r_btc.json()
    assert d_btc["symbol"] == "BTC"
    assert "trade_setup" in d_btc

    # 3. Webhook receiver test (JSON alert)
    r_hook = client.post("/api/wyckoff/webhook", json={
        "symbol": "GOLD",
        "event": "SPRING_CONFIRMED",
        "phase": "C",
        "quality": 88,
        "entry": 2510.50,
        "tp1": 2530.00,
        "tp2": 2560.00,
        "sl": 2490.00
    })
    assert r_hook.status_code == 200
    assert r_hook.json()["status"] == "success"
    assert r_hook.json()["processed"] is True

    # 4. Verify snapshot includes Wyckoff data
    r_snap = client.get("/api/cockpit/snapshot?symbol=GOLD")
    assert r_snap.status_code == 200
    snap = r_snap.json()
    assert "wyckoff" in snap

    # 5. Verify Federation includes Wyckoff Range Engine model
    fed = snap.get("federation") or {}
    models = fed.get("model_details") or []
    wyck_models = [m for m in models if "Wyckoff" in m.get("name", "")]
    assert len(wyck_models) > 0, "Wyckoff model should be present in Model Federation"











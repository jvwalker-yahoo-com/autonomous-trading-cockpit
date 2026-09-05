"""
Comprehensive unit and integration test suite for the Predictive Execution Cockpit
and Autonomous Trading Engine.
"""
import pytest
from fastapi.testclient import TestClient

from backend.config import config
from backend.server import app
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
    assert response.json() == {"status": "ok"}

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
    ind = {"ema_9": 105.0, "ema_21": 100.0, "rsi_14": 60.0, "macd_line": 0.5}
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

    r = client.post("/api/action/trade", json={"symbol": "MSFT", "action": "BUY", "amount_usd": 300.0})
    assert r.status_code == 200

    r = client.post("/api/action/trade", json={"symbol": "MSFT", "action": "CLOSE"})
    assert r.status_code == 200

    r = client.post("/api/portfolio/reset")
    assert r.status_code == 200
    assert r.json()["cash"] == config.initial_capital

    # Circuit breaker reset endpoint test
    r = client.post("/api/circuit_breaker/reset")
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert r.json()["drawdown_pct"] == 0.0
    assert r.json()["circuit_breaker_active"] is False

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

    # 4. Test Mode Switch to Demo
    r_demo = test_app_client.post("/api/mode/switch", json={"mode": "demo"})
    assert r_demo.status_code == 200
    assert r_demo.json()["execution_mode"] == "demo"

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
    assert get_etoro_id("NVDA") == 1007
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





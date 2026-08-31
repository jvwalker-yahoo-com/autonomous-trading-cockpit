"""
Comprehensive unit and integration test suite for the Predictive Execution Cockpit
and Autonomous Trading Engine.
"""
import pytest
from fastapi.testclient import TestClient

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
    assert r.json()["cash"] == 10000.0

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

    # Test backtest run endpoint
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


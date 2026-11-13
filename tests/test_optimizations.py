"""
Regression & Optimization Test Suite (P0/P1/P2).
Covers:
  - Wyckoff Range Engine Spring / UTAD / SOS / SOW detection
  - SuperTrend statefulness & true Wilder ADX
  - Screener Congressional signed conviction blending
  - OHLCV bar storage, indicator memoization, live-mode simulated-quote guard
  - Metrics determinism & real-latency normalization vs Anomaly threshold
  - AdaptiveLearner 7-model weights & post-update mistake snapshots
  - Broker contributing_models preservation & software Take-Profit enforcement
  - AICommitteeEngine neutral handling when fundamentals=None
  - Telemetry "BA" US/UK symbol disambiguation
  - NewsIntelligence full watchlist coverage (>30) & Finnhub article divisor fix
  - InstrumentsDBManager in-memory lookup cache
  - SmartMoney CONGRESS_BUY preservation under cached 3-way flow
"""
import sqlite3
import tempfile
import os
import time
from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from backend.engine.wyckoff import WyckoffRangeEngine
from backend.engine.indicators import TechnicalIndicators
from backend.engine.screener import MarketScreener
from backend.engine.data_feed import DataFeedManager, MarketDataPoint
from backend.engine.metrics import MetricsModule
from backend.engine.anomaly import AnomalyModule
from backend.engine.learner import AdaptiveLearner
from backend.engine.broker import SimulatedBroker
from backend.engine.ai_committee import AICommitteeEngine
from backend.engine.telemetry import TelemetryModule
from backend.engine.news_intel import NewsIntelligenceEngine
from backend.engine.smart_money import SmartMoneyEngine
from backend.engine.instruments_db import InstrumentsDBManager
from backend.engine.models import TradeRecord, Position
from src.services.etoro.client import EToroClient


# ── P0.1: Wyckoff Spring / UTAD / SOS / SOW Detection ──────────────────────────

def test_wyckoff_detects_spring_and_sos_breakout():
    """
    A classic accumulation range [96..104] followed by a liquidity Spring below 96
    and a high-volume SOS breakout above 104 must detect SPRING/SOS and advance
    out of Phase A into Phase C/D/E with BULLISH bias.
    """
    n = 42
    # Bars 0..24: stable trading range 96..104
    base_pattern = [100.0, 102.0, 104.0, 101.0, 98.0, 96.0, 99.0, 103.0] * 4
    closes = list(base_pattern[:26])
    highs = [p + 0.5 for p in closes]
    lows = [p - 0.5 for p in closes]
    vols = [100_000.0] * 26

    # Bar 26-27: Test near range bottom
    closes.extend([97.5, 96.5])
    highs.extend([98.2, 97.5])
    lows.extend([96.8, 96.1])
    vols.extend([110_000.0, 115_000.0])

    # Bar 28: SMART SPRING (sweeps well below Ice ~95.5 to 91.5, closes back inside range at 97.8)
    closes.append(97.8)
    highs.append(98.4)
    lows.append(91.5)
    vols.append(260_000.0)

    # Bars 29..36: recovery rally inside range
    for p in [99.0, 100.5, 101.5, 102.0, 103.0, 103.8, 104.2, 104.4]:
        closes.append(p)
        highs.append(p + 0.4)
        lows.append(p - 0.4)
        vols.append(120_000.0)

    # Bars 37..41: SOS Breakout above Creek (~104.5) on expanding volume
    for p in [105.6, 107.0, 108.5, 109.8, 111.0]:
        closes.append(p)
        highs.append(p + 0.6)
        lows.append(p - 0.3)
        vols.append(310_000.0)

    res = WyckoffRangeEngine.detect_wyckoff_structure(
        prices=np.array(closes, dtype=float),
        volumes=np.array(vols, dtype=float),
        highs=np.array(highs, dtype=float),
        lows=np.array(lows, dtype=float),
        symbol="NVDA",
    )
    event_types = {e["event"] for e in res["events_detected"]}
    assert "SPRING" in event_types, f"Expected SPRING event, got {event_types} in phase {res['phase_code']}"
    assert "SOS" in event_types, f"Expected SOS event, got {event_types} in phase {res['phase_code']}"
    assert res["phase_code"] in ("C", "D", "E")
    assert "BULLISH" in res["bias"]
    assert res["signal"] == "BUY"


def test_wyckoff_detects_utad_and_sow_breakdown():
    """
    Distribution range [96..104] followed by UTAD sweep above 104 and SOW breakdown
    below 96 on high volume must detect UTAD/SOW and BEARISH bias.
    """
    base_pattern = [100.0, 98.0, 96.0, 99.0, 102.0, 104.0, 101.0, 97.0] * 4
    closes = list(base_pattern[:26])
    highs = [p + 0.5 for p in closes]
    lows = [p - 0.5 for p in closes]
    vols = [100_000.0] * 26

    # Bar 26-27: up toward Creek
    closes.extend([103.0, 103.8])
    highs.extend([103.8, 104.3])
    lows.extend([102.2, 103.1])
    vols.extend([110_000.0, 120_000.0])

    # Bar 28: UTAD Upthrust above Creek ~104.5 to 108.5, rejecting back inside to 102.5
    closes.append(102.5)
    highs.append(108.5)
    lows.append(102.0)
    vols.append(270_000.0)

    # Bars 29..36: drift down toward Ice
    for p in [101.5, 100.2, 99.0, 98.2, 97.4, 96.6, 96.1, 95.8]:
        closes.append(p)
        highs.append(p + 0.4)
        lows.append(p - 0.4)
        vols.append(125_000.0)

    # Bars 37..41: SOW breakdown below Ice on high volume
    for p in [94.4, 93.0, 91.5, 90.2, 89.0]:
        closes.append(p)
        highs.append(p + 0.3)
        lows.append(p - 0.6)
        vols.append(320_000.0)

    res = WyckoffRangeEngine.detect_wyckoff_structure(
        prices=np.array(closes, dtype=float),
        volumes=np.array(vols, dtype=float),
        highs=np.array(highs, dtype=float),
        lows=np.array(lows, dtype=float),
        symbol="AAPL",
    )
    event_types = {e["event"] for e in res["events_detected"]}
    assert "UTAD" in event_types, f"Expected UTAD event, got {event_types}"
    assert "SOW" in event_types, f"Expected SOW event, got {event_types}"
    assert res["phase_code"] in ("C", "D", "E")
    assert "BEARISH" in res["bias"]


# ── P0.2: Stateful SuperTrend & True Wilder ADX ────────────────────────────────

def test_supertrend_stateful_on_minor_pullback():
    """
    In a strong established uptrend, a tiny 1-tick pullback far above the ATR
    trailing stop must NOT flip SuperTrend from +1 (Bullish) to -1 (Bearish).
    """
    closes = np.array([100.0 + i * 1.2 for i in range(28)] + [132.4 - 0.15], dtype=float)
    highs = closes + 0.6
    lows = closes - 0.6
    val, trend = TechnicalIndicators.calc_supertrend(highs, lows, closes, period=10, multiplier=3.0)
    assert trend == 1, f"Expected SuperTrend to stay +1 on minor pullback, got {trend} (band={val})"
    assert val < closes[-1]


def test_adx_true_wilder_smoothing_exceeds_capped_blend():
    """
    A clean 45-bar monotonic uptrend has near-100 DX across >28 bars so true
    Wilder ADX exceeds 60.0 (impossible under the old `dx*0.4 + 20*0.6 <= 52` shortcut).
    """
    closes = np.array([100.0 + i * 1.5 for i in range(45)], dtype=float)
    highs = closes + 0.2
    lows = closes - 0.1
    adx, plus_di, minus_di = TechnicalIndicators.calc_adx(highs, lows, closes, period=14)
    assert plus_di > 80.0
    assert minus_di < 10.0
    assert adx > 60.0, f"Expected true Wilder ADX > 60 on strong 45-bar trend, got {adx}"


# ── P0.3: Screener Signed Congress Conviction ──────────────────────────────────

def test_screener_congress_buy_does_not_amplify_short_conviction():
    """
    When technicals are bearish (SHORT) and Congress has strong BUY conviction (+0.85),
    Congress conviction must attenuate/offset the bearish normalized_score rather than
    magnifying the SHORT score toward -1.0.
    """
    feed = DataFeedManager()
    # Realistic stair-step downtrend with bounce candles so RSI stays ~37 (avoiding <30 oversold flip)
    bear_prices = [150.0]
    for i in range(1, 35):
        step = -1.20 if (i % 2 == 1) else 0.70
        bear_prices.append(round(bear_prices[-1] + step, 4))
    feed.history_windows["NVDA"] = list(bear_prices)
    feed.high_windows["NVDA"] = [p + 0.3 for p in bear_prices]
    feed.low_windows["NVDA"] = [p - 0.3 for p in bear_prices]
    feed.volume_windows["NVDA"] = [120_000.0] * 35
    feed.last_quotes["NVDA"] = MarketDataPoint(
        symbol="NVDA", price=bear_prices[-1], high=bear_prices[-1] + 0.3,
        low=bear_prices[-1] - 0.3, open_p=bear_prices[-2],
        prev_close=bear_prices[-2], volume=150_000.0, source="finnhub"
    )
    feed._quote_cache["NVDA"] = (time.time(), feed.last_quotes["NVDA"])

    sm_neutral = SmartMoneyEngine()
    res_neutral = MarketScreener.get_symbol_screen("NVDA", data_feed_manager=feed, smart_money_engine=sm_neutral, refresh_tv=False)
    assert res_neutral["signal"].startswith("SHORT"), f"Expected bearish SHORT setup first, got {res_neutral['signal']}"
    assert res_neutral["normalized_score"] < 0.0

    sm_bull_cong = SmartMoneyEngine()
    sm_bull_cong._symbol_congress_scores["NVDA"] = 0.85
    # Force cache bypass for indicator/screen
    MarketScreener._last_universe_cache.pop("NVDA", None)
    res_bull_cong = MarketScreener.get_symbol_screen("NVDA", data_feed_manager=feed, smart_money_engine=sm_bull_cong, refresh_tv=False)

    assert res_bull_cong["normalized_score"] > res_neutral["normalized_score"], (
        f"Bullish Congress (+0.85) must increase signed normalized_score relative to neutral "
        f"(neutral={res_neutral['normalized_score']}, bull_cong={res_bull_cong['normalized_score']})"
    )


# ── P0.4: OHLCV Real Bars, Indicator Memoization & Live Simulated-Quote Guard ──

def test_data_feed_preserves_ohlcv_bars_and_memoizes_indicators():
    feed = DataFeedManager()
    # Ingest real wide-range OHLCV bars (e.g., 6% intraday bars vs synthetic 0.8%)
    bars = [
        {
            "open": 100.0,
            "high": 104.0,
            "low": 98.0,
            "close": 101.0 + (i % 3) * 0.5,
            "volume": 200_000.0,
        }
        for i in range(30)
    ]
    feed.ingest_ohlcv_bars("AAPL", bars)

    assert len(feed.high_windows["AAPL"]) == 30
    assert len(feed.low_windows["AAPL"]) == 30
    assert max(feed.high_windows["AAPL"]) >= 104.0

    ind1 = feed.get_technical_indicators("AAPL")
    # Real ATR reflects ~$6 bar range, not synthetic 0.008 * 101 ≈ $0.81
    assert ind1["atr"] >= 4.0, f"Expected real OHLCV ATR >= 4.0, got {ind1['atr']}"

    # Memoization: second call without bar updates must return identical object / skip recompute
    ind2 = feed.get_technical_indicators("AAPL")
    assert ind1 is ind2

    # Appending a new quote invalidates memoization cache
    q = MarketDataPoint(
        symbol="AAPL", price=112.0, high=114.0, low=110.0,
        open_p=102.0, prev_close=101.5, volume=300_000.0, source="finnhub"
    )
    feed.record_bar_point("AAPL", q)
    ind3 = feed.get_technical_indicators("AAPL")
    assert ind3 is not ind1


def test_live_mode_blocks_simulated_quotes_from_placing_real_etoro_orders():
    """
    When execution_mode == 'live' and quote.source == 'simulated', autonomous
    run_analysis_cycle must NOT call etoro_client.create_order().
    """
    from backend import server

    orig_mode = server.config.execution_mode
    orig_sim = server.config.simulation_mode
    orig_hours = server.config.enforce_market_hours

    fake_quote = MarketDataPoint(
        symbol="AAPL", price=185.0, high=186.0, low=184.0,
        open_p=185.0, prev_close=184.5, volume=100_000.0, source="simulated"
    )
    mock_create_order = MagicMock(return_value={"success": True, "orderId": "should-not-run"})
    try:
        server.config.execution_mode = "live"
        server.config.simulation_mode = False
        server.config.enforce_market_hours = False
        with patch.object(server.data_feed, "get_latest_quote", return_value=fake_quote), \
             patch.object(server.etoro_client, "is_configured", return_value=True), \
             patch.object(server.etoro_client, "create_order", mock_create_order):
            out = server.run_analysis_cycle("AAPL")
            mock_create_order.assert_not_called()
            assert "decision" in out
    finally:
        server.config.execution_mode = orig_mode
        server.config.simulation_mode = orig_sim
        server.config.enforce_market_hours = orig_hours


# ── P1.1: Metrics Determinism & Healthy HTTP Latency Normalization ─────────────

def test_metrics_deterministic_and_normalizes_healthy_http_latency():
    m = MetricsModule()
    low_vol_ind = {"volatility_std": 0.1, "bb_mid": 100.0, "atr": 0.25, "volume_surge": 1.0}

    r1 = m.compute_all(low_vol_ind, actual_latency_ms=220.0)
    r2 = m.compute_all(low_vol_ind, actual_latency_ms=220.0)
    assert r1 == r2, "MetricsModule must be deterministic (no random/sin jitter)"
    assert r1["risk"] < 0.25, f"Low-vol market should have low risk, got {r1['risk']}"
    assert r1["latency"] < 20.0, f"Healthy 220ms HTTP call should not breach 20ms anomaly limit: {r1['latency']}"

    anomaly = AnomalyModule()
    det_ok = anomaly.anomaly_detector(r1, [100.0] * 10, [100_000.0] * 10)
    assert det_ok.latency_spike is False

    # Stalled API (>= 2000ms) must breach 20ms and trigger AnomalyModule latency_spike
    r_slow = m.compute_all(low_vol_ind, actual_latency_ms=2500.0)
    assert r_slow["latency"] > 20.0
    det_slow = anomaly.anomaly_detector(r_slow, [100.0] * 10, [100_000.0] * 10)
    assert det_slow.latency_spike is True


# ── P1.2: AdaptiveLearner 7-Model Support & Post-Update Mistake Snapshot ───────

def test_adaptive_learner_includes_news_and_committee_and_logs_updated_weights():
    learner = AdaptiveLearner()
    assert "news_sentiment" in learner.weights
    assert "ai_committee" in learner.weights
    assert abs(sum(learner.weights.values()) - 1.0) < 0.01

    losing_trade = TradeRecord(
        id="TRD-OPT-1",
        symbol="NVDA",
        direction="LONG",
        shares=1.0,
        entry_price=100.0,
        exit_price=95.0,
        cost_basis_usd=100.0,
        exit_value_usd=95.0,
        realized_pnl_usd=-5.0,
        realized_pnl_pct=-5.0,
        win=False,
        entry_time="2026-01-01T10:00:00Z",
        exit_time="2026-01-01T11:00:00Z",
        entry_rationale="Test entry",
        exit_rationale="Stop Loss Hit",
        contributing_models={"news_sentiment": 0.9, "ai_committee": 0.85, "wyckoff_engine": -0.2},
    )
    before_news = learner.weights["news_sentiment"]
    learner.evaluate_closed_trade(losing_trade)

    assert learner.weights["news_sentiment"] < before_news
    assert learner.mistake_history[0].adjusted_weights["news_sentiment"] == pytest.approx(learner.weights["news_sentiment"], abs=1e-4)


# ── P1.3: Broker Preserves Contributing Models & Enforces Software Take Profit ─

def test_broker_preserves_contributing_models_and_enforces_take_profit():
    broker = SimulatedBroker(initial_capital=2000.0)
    broker.positions["MSFT"] = Position(
        id="pos-msft",
        symbol="MSFT",
        direction="LONG",
        horizon="swing",
        shares=2.0,
        entry_price=400.0,
        current_price=405.0,
        cost_basis_usd=800.0,
        market_value_usd=810.0,
        unrealized_pnl_usd=10.0,
        unrealized_pnl_pct=1.25,
        stop_loss=385.0,
        take_profit=420.0,
        entry_time="2026-01-01T10:00:00Z",
        etoro_position_ids=["999001"],
        rationale="AI entry",
        contributing_models={"wyckoff_engine": 0.65, "news_sentiment": 0.4},
    )

    broker.sync_live_etoro_portfolio({
        "totals": {"availableCash": 1200.0, "totalValue": 2010.0},
        "holdings": [{
            "market": {"symbol": "MSFT"},
            "invested": 800.0,
            "value": 844.0,
            "pnl": 44.0,
            "pnlPercent": 5.5,
            "units": 2.0,
            "avgOpenRate": 400.0,
            "currentRate": 422.0,
            "positions": [{"positionId": 999001, "isBuy": True, "openTime": "2026-01-01T10:00:00Z"}],
        }]
    })
    assert broker.positions["MSFT"].contributing_models == {"wyckoff_engine": 0.65, "news_sentiment": 0.4}

    mock_feed = MagicMock()
    mock_feed.get_latest_quote.return_value = MarketDataPoint(symbol="MSFT", price=422.0, source="finnhub")
    mock_etoro = MagicMock()
    mock_etoro.is_configured.return_value = True
    mock_etoro.close_position.return_value = {"success": True}

    closed = broker.enforce_live_stops(etoro_client=mock_etoro)
    assert len(closed) == 1
    assert closed[0].symbol == "MSFT"
    assert "Take Profit" in closed[0].exit_rationale


# ── P1.4: AICommittee Neutral When Fundamentals Unavailable ────────────────────

def test_ai_committee_neutral_without_fundamentals():
    committee = AICommitteeEngine(reports_dir=tempfile.mkdtemp())
    neutral_inds = {
        "adx": 18.0, "supertrend_dir": 0.0, "rsi_14": 50.0, "macd_line": 0.0,
        "macd_signal": 0.0, "ema_9": 100.0, "ema_21": 100.0,
        "wyckoff_phase": "Phase A", "wyckoff_phase_code": "A", "wyckoff_bias": "EQUILIBRIUM",
    }
    res = committee.evaluate(
        symbol="TEST",
        price=100.0,
        indicators=neutral_inds,
        sentiment_score=0.0,
        smart_money_conviction=0.0,
        fundamentals=None,
    )
    # Without fundamentals, missing data must NOT fabricate +0.25 bullish bias!
    assert abs(res.conviction_score) < 0.10, f"Expected near-zero conviction_score when all inputs missing/neutral, got {res.conviction_score}"
    fund_report = res.analyst_reports.get("fundamental", "")
    assert "UNAVAILABLE" in fund_report or "NEUTRAL" in fund_report


# ── P1.5: Telemetry BA Symbol Disambiguation & NewsIntel Full Watchlist/Divisor ─

def test_telemetry_ba_is_us_nyse_not_lse():
    is_open, label = TelemetryModule().is_etoro_uk_market_open("BA")
    assert "US Equities" in label or "NYSE" in label, f"'BA' (Boeing) misclassified as {label}"


def test_news_intel_covers_full_watchlist_beyond_30_and_fixes_finnhub_divisor():
    ni = NewsIntelligenceEngine(finnhub_api_key="dummy_key_12345")
    symbols = [f"SYM{i}" for i in range(36)]

    called_syms = []
    def fake_fh(sym, req_mod):
        called_syms.append(sym)
        return 0.1, []

    with patch.object(ni, "_fetch_rss_feeds", return_value={"headlines": [], "symbol_scores": {}, "symbol_news": {}}), \
         patch.object(ni, "_fetch_global_market_news", return_value=([], 0.0, "NORMAL", [])), \
         patch.object(ni, "_fetch_finnhub_news", side_effect=fake_fh), \
         patch.object(ni, "_fetch_tavily_catalysts", return_value=({}, {})), \
         patch.object(ni, "_fetch_alpha_vantage_sentiment", return_value=({}, {})), \
         patch.object(ni, "_fetch_edgar_filings", return_value=([], 0.0)):
        ni.refresh_all(symbols)

    assert len(called_syms) == 36, f"Expected all 36 symbols scanned, got {len(called_syms)}"

    # Test Finnhub divisor: 25 identical positive articles -> average across top 10 evaluated must equal single article score, not 10/25!
    articles = [{"headline": "Company beats earnings and upgrades guidance surge growth", "summary": "record rally outperform", "source": "Finnhub", "url": "", "datetime": 0} for _ in range(25)]
    single_score = ni._score_text(articles[0]["headline"] + " " + articles[0]["summary"])
    mock_req = MagicMock()
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = articles
    mock_req.get.return_value = mock_resp
    avg_score, parsed = ni._fetch_finnhub_news("NVDA", mock_req)
    assert len(parsed) == 10
    assert avg_score == pytest.approx(single_score, abs=0.02), (
        f"Expected avg_score ≈ {single_score} over 10 evaluated articles, got {avg_score}"
    )


# ── P1.6: SmartMoney Preserves CONGRESS_BUY Under Cached OpenInsider ───────────

def test_smart_money_congress_buy_survives_cached_flow():
    sm = SmartMoneyEngine()
    with sm._lock:
        sm._transparency_feed_cache["NVDA"] = {"flow_conviction": -0.45}
        sm._symbol_congress_scores["NVDA"] = 0.42
        sm._symbol_congress_trades["NVDA"] = [{"ticker": "NVDA", "trade_type": "Purchase"}]
    intel = sm.get_pre_trade_congress_intel("NVDA")
    assert intel["signal"] == "CONGRESS_BUY"


# ── P2.1: InstrumentsDBManager In-Memory Cache ─────────────────────────────────

def test_instruments_db_in_memory_cache_hits():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "inst_test.db")
        mgr = InstrumentsDBManager(db_path=db_path)
        mgr.upsert_instrument(symbol="NVDA", instrument_id=1001, name="Nvidia Corp")

        orig_connect = sqlite3.connect
        connect_calls = []

        def tracked_connect(*args, **kwargs):
            connect_calls.append(1)
            return orig_connect(*args, **kwargs)

        with patch("sqlite3.connect", side_effect=tracked_connect):
            # Clear cache first or read repeatedly
            for _ in range(25):
                assert mgr.get_etoro_id("NVDA") == 1001
                inst = mgr.get_instrument("NVDA")
                assert inst["name"] == "Nvidia Corp"

        # Repeated lookups across 25 calls should hit SQLite at most once (or 0 times after upsert warmup)
        assert len(connect_calls) <= 1, f"Expected in-memory cache hit (<=1 DB open), saw {len(connect_calls)} opens"


# ── eToro Watchlist Regression Fixes (422 Duplicate/InvalidId & 429 Quota) ─────

def _make_mock_etoro_client():
    client = EToroClient(api_key="unit_test_api_key_value", user_key="unit_test_user_key_value")
    client.is_configured = lambda: True
    client.resolve_instrument_id = lambda s: {"UK100": 30, "GER40": 32, "NVDA": 1002}.get(s.upper())
    return client


def test_etoro_watchlist_queries_real_endpoint_directly():
    client = _make_mock_etoro_client()
    calls = []

    def fake_request(method, endpoint, params=None, json_data=None, **kwargs):
        calls.append((method, endpoint, params, json_data))
        if endpoint != "/api/v1/watchlists":
            raise AssertionError(f"Should not probe obsolete endpoint {endpoint}")
        return True, 200, {
            "watchlists": [
                {"watchlistId": "4421", "name": "Autonomous+Cockpit", "items": [{"itemId": 30, "itemType": "Instrument"}]}
            ]
        }

    client._request = fake_request
    watchlists = client.get_user_watchlists()
    assert len(calls) == 1
    assert calls[0][0] == "GET" and calls[0][1] == "/api/v1/watchlists"
    assert len(watchlists) == 1 and watchlists[0]["watchlistId"] == "4421"


def test_etoro_watchlist_matches_plus_encoded_name_and_skips_redundant_writes():
    client = _make_mock_etoro_client()
    calls = []

    def fake_request(method, endpoint, params=None, json_data=None, **kwargs):
        calls.append((method, endpoint, params, json_data))
        if method == "GET" and endpoint == "/api/v1/watchlists":
            return True, 200, {
                "watchlists": [
                    {
                        "watchlistId": "4421",
                        "name": "Autonomous+Cockpit",
                        "items": [{"itemId": 30, "itemType": "Instrument"}],
                    }
                ]
            }
        if method == "POST" and endpoint == "/api/v1/watchlists/4421/items":
            return True, 201, {"isSucceeded": True}
        raise AssertionError(f"Unexpected HTTP call: {method} {endpoint} params={params} json={json_data}")

    client._request = fake_request

    # First sync: UK100 (30) is already present -> only GER40 (32) should be posted, NO POST /api/v1/watchlists!
    res1 = client.sync_symbols_to_watchlist(["UK100", "GER40"], watchlist_name="Autonomous Cockpit")
    assert res1["watchlist_id"] == 4421
    assert len(calls) == 2  # 1 GET + 1 POST items
    post_items_payload = calls[1][3]
    assert [it["itemId"] for it in post_items_payload] == [32]

    # Second sync of already-synced symbols hits memory cache -> 0 API calls (avoids 429 rate limits)
    calls.clear()
    res2 = client.sync_symbols_to_watchlist(["UK100", "GER40"], watchlist_name="Autonomous Cockpit")
    assert res2["watchlist_id"] == 4421
    assert calls == [], f"Expected 0 HTTP calls on cached re-sync, saw {calls}"


def test_etoro_watchlist_creation_uses_percent20_nested_id_and_never_falls_back_to_101():
    # Sub-case 1: Fresh creation encodes %20 (never '+') and unwraps nested WatchlistsResponse + string IDs
    client = _make_mock_etoro_client()
    calls = []

    def fake_create(method, endpoint, params=None, json_data=None, **kwargs):
        calls.append((method, endpoint, params, json_data))
        if method == "GET" and endpoint == "/api/v1/watchlists":
            return True, 200, {"watchlists": []}
        if method == "POST" and endpoint == "/api/v1/watchlists/wl-uuid-99/items":
            return True, 201, {"isSucceeded": True}
        if method == "POST" and endpoint.startswith("/api/v1/watchlists?"):
            assert "Autonomous%20Cockpit" in endpoint, f"Expected %20 encoding, got {endpoint} params={params}"
            assert params is None or "name" not in params
            return True, 201, {"watchlists": [{"watchlistId": "wl-uuid-99", "name": "Autonomous Cockpit"}]}
        raise AssertionError(f"Unexpected HTTP call: {method} {endpoint}")

    client._request = fake_create
    res = client.sync_symbols_to_watchlist(["UK100"], watchlist_name="Autonomous Cockpit")
    assert res["watchlist_id"] == "wl-uuid-99"

    # Sub-case 2: Total API failure must NEVER fall back to bogus hardcoded ID 101
    broken = _make_mock_etoro_client()
    broken_calls = []

    def fake_fail(method, endpoint, params=None, json_data=None, **kwargs):
        broken_calls.append((method, endpoint))
        if "/101" in endpoint:
            raise AssertionError(f"Must never call fake watchlist ID 101: {endpoint}")
        return False, 422, {"exception": {"reason": "UnknownError"}}

    broken._request = fake_fail
    wl_id, _ = broken.get_or_create_cockpit_watchlist("Autonomous Cockpit")
    assert wl_id is None
    sync_fail = broken.sync_symbols_to_watchlist(["UK100"], watchlist_name="Autonomous Cockpit")
    assert sync_fail["watchlist_id"] is None
    assert sync_fail["status"] != "success"
    assert all("/101" not in ep for _, ep in broken_calls)


def test_etoro_watchlist_duplicate_422_recovers_existing_and_serializes_threads():
    import threading
    client = _make_mock_etoro_client()
    calls = []
    lock = threading.Lock()

    def fake_request(method, endpoint, params=None, json_data=None, **kwargs):
        with lock:
            calls.append((method, endpoint, json_data))
        if method == "GET" and endpoint == "/api/v1/watchlists":
            # First call simulates transient miss (or empty), second recovery call sees existing plus-encoded row
            get_count = sum(1 for m, ep, _ in calls if m == "GET")
            if get_count == 1:
                return False, 429, {}
            return True, 200, {
                "watchlists": [{"watchlistId": "7788", "name": "Autonomous+Cockpit", "items": []}]
            }
        if method == "POST" and endpoint.startswith("/api/v1/watchlists?"):
            return False, 422, {"exception": {"reason": "InvalidDuplicateWatchlistName"}}
        if method == "POST" and endpoint == "/api/v1/watchlists/7788/items":
            return True, 201, {"isSucceeded": True}
        raise AssertionError(f"Unexpected HTTP call: {method} {endpoint}")

    client._request = fake_request

    results = []
    def worker(sym):
        results.append(client.sync_symbols_to_watchlist([sym], watchlist_name="Autonomous Cockpit"))

    t1 = threading.Thread(target=worker, args=("UK100",))
    t2 = threading.Thread(target=worker, args=("GER40",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert all(r["watchlist_id"] == 7788 for r in results), f"Expected recovered watchlist_id=7788, got {results}"
    post_create_calls = [c for c in calls if c[0] == "POST" and c[1].startswith("/api/v1/watchlists?")]
    assert len(post_create_calls) == 1, f"Expected serialized single recovery create attempt, saw {post_create_calls}"


def test_etoro_watchlist_invalidates_stale_cached_id_on_422():
    client = _make_mock_etoro_client()
    # Pre-seed stale cached watchlist ID 4421
    client._watchlist_id_cache["autonomous cockpit"] = 4421
    client._watchlist_synced_items["4421"] = set()
    calls = []

    def fake_request(method, endpoint, params=None, json_data=None, **kwargs):
        calls.append((method, endpoint))
        if method == "POST" and endpoint == "/api/v1/watchlists/4421/items":
            return False, 422, {"exception": {"reason": "InvalidWatchlistId", "message": "Watchlist with id '4421' not found"}}
        if method == "GET" and endpoint == "/api/v1/watchlists":
            return True, 200, {"watchlists": []}
        if method == "POST" and endpoint.startswith("/api/v1/watchlists?"):
            return True, 201, {"watchlists": [{"watchlistId": "9001", "name": "Autonomous Cockpit"}]}
        if method == "POST" and endpoint == "/api/v1/watchlists/9001/items":
            return True, 201, {"isSucceeded": True}
        raise AssertionError(f"Unexpected call: {method} {endpoint}")

    client._request = fake_request
    res = client.sync_symbols_to_watchlist(["UK100"], watchlist_name="Autonomous Cockpit")
    assert res["status"] == "success"
    assert res["watchlist_id"] == 9001
    assert client._watchlist_id_cache["autonomous cockpit"] == 9001
    assert ("POST", "/api/v1/watchlists/9001/items") in calls

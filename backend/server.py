"""
FastAPI Server and Background Autonomous Engine for the Predictive Execution Cockpit.
Provides all 10 core endpoints specified in the architectural design, plus live portfolio management,
self-learning evaluation, Finnhub integration, and static UI serving.
"""
import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel

from .config import config
from .engine.data_feed import DataFeedManager
from .engine.metrics import MetricsModule
from .engine.regime import RegimeModule
from .engine.federation import FederationModule
from .engine.arbitration import ArbitrationModule
from .engine.anomaly import AnomalyModule
from .engine.quadrant import QuadrantModule
from .engine.telemetry import TelemetryModule
from .engine.learner import AdaptiveLearner
from .engine.broker import SimulatedBroker
from .engine.backtester import BacktesterEngine, BacktestResult, OptimizationResult
from .engine.reporter import ReportPDFGenerator, EmailReportDispatcher
from .engine.screener import MarketScreener, MASTER_STOCK_UNIVERSE, PRESET_WATCHLISTS
from .engine.etoro_client import EToroClient
from .engine.data_feed import BASE_PRICES
from .engine.models import (
    RegimeState, FederationOutput, ArbitrationOutput,
    DecisionOutput, AnomalyDetectorOutput, QuadrantOutput,
    HeartbeatOutput, SyncDriftOutput, PortfolioSummary,
    LearningStatsOutput, TradeRecord
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auton-cockpit")

# Instantiate Core Engine Components
data_feed = DataFeedManager(api_key=config.finnhub_api_key)
etoro_client = EToroClient(api_key=config.etoro_api_key, user_key=config.etoro_user_key, base_url=config.etoro_base_url)
metrics_module = MetricsModule()
regime_module = RegimeModule()
federation_module = FederationModule()
arbitration_module = ArbitrationModule()
anomaly_module = AnomalyModule()
quadrant_module = QuadrantModule()
telemetry_module = TelemetryModule()
learner = AdaptiveLearner()
broker = SimulatedBroker(initial_capital=config.initial_capital, db_path=config.db_path, learner=learner)
backtester = BacktesterEngine()

active_symbol = "AAPL"
is_autonomous_loop_running = True

app = FastAPI(
    title="Predictive Execution Cockpit API",
    description="Autonomous Trading Engine with Real-Time Learning & Predictive Cockpit",
    version="2.0.0"
)

@app.on_event("startup")
async def start_autonomous_background_worker():
    """Starts the continuous background autonomous execution loop."""
    asyncio.create_task(autonomous_background_worker_loop())

async def autonomous_background_worker_loop():
    logger.info("Autonomous Background Trading Loop initialized.")
    while True:
        try:
            for sym in config.watchlist:
                run_analysis_cycle(sym)
                await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Autonomous background cycle exception: {e}")
        await asyncio.sleep(config.execution_loop_interval)

# CORS enabled for static hosting / global access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigUpdateRequest(BaseModel):
    finnhub_api_key: Optional[str] = None
    active_symbol: Optional[str] = None
    simulation_mode: Optional[bool] = None
    risk_per_trade_pct: Optional[float] = None
    etoro_api_key: Optional[str] = None
    etoro_user_key: Optional[str] = None
    etoro_base_url: Optional[str] = None
    execution_mode: Optional[str] = None

class ModeSwitchRequest(BaseModel):
    mode: str # "demo" or "live"

class ManualTradeRequest(BaseModel):
    symbol: str
    action: str # "BUY", "SHORT", "CLOSE"
    amount_usd: Optional[float] = 500.0

def run_analysis_cycle(symbol: str) -> Dict[str, Any]:
    """
    Executes one complete analytical and autonomous execution pass for a symbol.
    """
    global active_symbol
    active_symbol = symbol

    # 1. Fetch live or high-fidelity simulated quote & indicators
    quote = data_feed.get_latest_quote(symbol)
    indicators = data_feed.get_technical_indicators(symbol)
    sentiment = data_feed.get_news_sentiment(symbol)
    
    # 2. Check stops on existing open positions
    broker.update_price_and_check_stops(symbol, quote.price)

    # 3. Compute telemetry metrics (Risk, Impact, Slippage, Latency)
    metrics = metrics_module.compute_all(indicators, actual_latency_ms=data_feed.api_latency_ms)

    # 4. Regime classification
    regime = regime_module.model_mode(metrics, indicators)

    # 5. Anomaly detection
    price_hist = data_feed.history_windows.get(symbol, [quote.price])
    vol_hist = data_feed.volume_windows.get(symbol, [quote.volume])
    anomalies = anomaly_module.anomaly_detector(metrics, price_hist, vol_hist)

    # 6. Quadrant classification
    quadrant = quadrant_module.quadrant(metrics["risk"], metrics["impact"])

    # 7. Model Federation (Multi-Strategy Scoring + Adaptive Weights)
    federation = federation_module.model_federation(indicators, quote.price, sentiment, learner.weights)

    # 8. Arbitration & Risk Gates (including eToro UK Market Hours gate)
    equity = broker.get_equity()
    peak = max(broker.peak_equity, equity)
    drawdown_pct = (peak - equity) / max(1.0, peak)
    total_invested = sum(p.market_value_usd for p in broker.positions.values())
    exposure_pct = total_invested / max(1.0, equity)
    market_open, session_msg = telemetry_module.is_etoro_uk_market_open(symbol)
    
    arbitration = arbitration_module.arbitration(
        main_mode=regime.mode,
        quadrant=quadrant.quadrant,
        anomaly_detected=anomalies.anomaly_detected,
        current_drawdown_pct=drawdown_pct,
        max_drawdown_limit_pct=config.max_drawdown_limit_pct,
        current_exposure_pct=exposure_pct,
        max_exposure_limit_pct=config.max_portfolio_exposure_pct,
        active_positions_count=len(broker.positions),
        market_open=market_open,
        enforce_market_hours=config.enforce_market_hours
    )

    # 9. Decision Engine & Autonomous Execution
    signal = "HOLD"
    allocated_usd = 0.0
    target_shares = 0.0
    confidence = abs(federation.federated_score)
    rationale = f"Ensemble score: {federation.federated_score:+.2f} | Winning model: {federation.federation}"

    # Determine directional signal
    if federation.federated_score >= 0.30:
        signal = "BUY"
    elif federation.federated_score <= -0.30:
        signal = "SHORT"

    # Execution if arbitration approved
    if arbitration.approved and signal in ("BUY", "SHORT"):
        # Position sizing based on confidence & risk budget
        alloc_base = config.max_position_size_usd * confidence
        allocated_usd = max(50.0, min(config.max_position_size_usd, alloc_base))
        target_shares = round(allocated_usd / max(0.01, quote.price), 4)

        # Autonomous trade entry (if not already holding this direction)
        existing = broker.positions.get(symbol)
        if not existing or (existing.direction != ("LONG" if signal == "BUY" else "SHORT")):
            trade_dir = "LONG" if signal == "BUY" else "SHORT"
            broker.execute_order(
                symbol=symbol,
                direction=trade_dir,
                allocated_usd=allocated_usd,
                current_price=quote.price,
                stop_loss_pct=config.default_stop_loss_pct,
                take_profit_pct=config.default_take_profit_pct,
                rationale=f"Autonomous {trade_dir} entry on {symbol}. {rationale}. Dominant: {federation.federation}",
                contributing_models=federation.outputs
            )

    decision = DecisionOutput(
        symbol=symbol,
        signal=signal,
        main_mode=regime.mode,
        finalMode=arbitration.final_mode,
        target_shares=target_shares,
        allocated_usd=round(allocated_usd, 2),
        confidence=round(confidence, 2),
        current_price=quote.price,
        stop_loss=round(quote.price * (0.975 if signal == "BUY" else 1.025), 2) if signal != "HOLD" else None,
        take_profit=round(quote.price * (1.05 if signal == "BUY" else 0.95), 2) if signal != "HOLD" else None,
        rationale=rationale
    )

    return {
        "quote": quote,
        "metrics": metrics,
        "regime": regime,
        "anomalies": anomalies,
        "quadrant": quadrant,
        "federation": federation,
        "arbitration": arbitration,
        "decision": decision
    }

# ==========================================
# 10 CORE BLUEPRINT ENDPOINTS (From PDF)
# ==========================================

@app.get("/", tags=["Cockpit Core"])
def root_health(request: Request):
    """Health check endpoint: {status: 'ok'} or serve Cockpit HTML if accessed via browser."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return {"status": "ok"}

@app.get("/state", response_model=RegimeState, tags=["Cockpit Core"])
def get_state(symbol: Optional[str] = None):
    """Core regime state: risk, impact, slippage, latency, events"""
    sym = symbol or active_symbol
    res = run_analysis_cycle(sym)
    return res["regime"]

@app.get("/decision", response_model=DecisionOutput, tags=["Cockpit Core"])
def get_decision(symbol: Optional[str] = None):
    """Automation decision: main_mode, finalMode, signal, rationale"""
    sym = symbol or active_symbol
    res = run_analysis_cycle(sym)
    return res["decision"]

@app.get("/federation", response_model=FederationOutput, tags=["Cockpit Core"])
def get_federation(symbol: Optional[str] = None):
    """Model federation: outputs, weights, federation consensus"""
    sym = symbol or active_symbol
    res = run_analysis_cycle(sym)
    return res["federation"]

@app.get("/arbitration", response_model=ArbitrationOutput, tags=["Cockpit Core"])
def get_arbitration(symbol: Optional[str] = None):
    """Final arbitration: final_mode, risk gates, approved status"""
    sym = symbol or active_symbol
    res = run_analysis_cycle(sym)
    return res["arbitration"]

@app.get("/anomaly_detector", response_model=AnomalyDetectorOutput, tags=["Cockpit Core"])
def get_anomaly_detector(symbol: Optional[str] = None):
    """Anomaly flags: risk_spike, latency_spike, Z-scores"""
    sym = symbol or active_symbol
    res = run_analysis_cycle(sym)
    return res["anomalies"]

@app.get("/node_events", tags=["Cockpit Core"])
def get_node_events():
    """Recent system and execution events list"""
    events = list(regime_module.recent_events)
    # Include recent trades in event log
    for t in broker.trade_ledger[:5]:
        status_icon = "WIN" if t.win else "LOSS"
        events.append(f"Trade [{status_icon}] {t.direction} {t.shares} {t.symbol} | PnL: ${t.realized_pnl_usd:+.2f} ({t.realized_pnl_pct:+.1f}%)")
    return {"events": list(reversed(events[-20:]))}

@app.get("/quadrant", response_model=QuadrantOutput, tags=["Cockpit Core"])
def get_quadrant(symbol: Optional[str] = None):
    """Risk/impact quadrant classification (LOW, MEDIUM, HIGH, CRITICAL)"""
    sym = symbol or active_symbol
    res = run_analysis_cycle(sym)
    return res["quadrant"]

@app.get("/heartbeat", response_model=HeartbeatOutput, tags=["Cockpit Core"])
def get_heartbeat():
    """Liveness and system uptime heartbeat"""
    return telemetry_module.heartbeat()

@app.get("/sync_drift", response_model=SyncDriftOutput, tags=["Cockpit Core"])
def get_sync_drift():
    """Clock drift, market open state, and telemetry latency"""
    return telemetry_module.sync_drift()

# ==========================================
# EXTENDED PORTFOLIO & LEARNING ENDPOINTS
# ==========================================

@app.get("/api/cockpit/snapshot", tags=["Cockpit Extended"])
def get_cockpit_full_snapshot(symbol: Optional[str] = None):
    """
    Returns full aggregate snapshot of all 9 panels in a single fast call for smooth UI polling.
    """
    sym = symbol or active_symbol
    analysis = run_analysis_cycle(sym)
    portfolio = broker.get_portfolio_summary(active_symbol=sym, simulation_mode=config.simulation_mode)
    learning = learner.get_stats()
    heartbeat = telemetry_module.heartbeat()
    sync_drift = telemetry_module.sync_drift()

    return {
        "state": analysis["regime"],
        "decision": analysis["decision"],
        "federation": analysis["federation"],
        "arbitration": analysis["arbitration"],
        "anomaly": analysis["anomalies"],
        "quadrant": analysis["quadrant"],
        "node_events": list(reversed(regime_module.recent_events[-15:])),
        "heartbeat": heartbeat,
        "sync_drift": sync_drift,
        "portfolio": portfolio,
        "learning": learning,
        "quote": {
            "symbol": analysis["quote"].symbol,
            "price": analysis["quote"].price,
            "change": round(analysis["quote"].change, 2),
            "change_pct": round(analysis["quote"].change_pct, 2),
            "high": analysis["quote"].high,
            "low": analysis["quote"].low,
            "volume": int(analysis["quote"].volume)
        },
        "watchlist": config.watchlist
    }

@app.get("/api/portfolio", response_model=PortfolioSummary, tags=["Portfolio"])
def get_portfolio():
    """Current portfolio metrics, cash, equity, win-rate, and active positions"""
    return broker.get_portfolio_summary(active_symbol=active_symbol, simulation_mode=config.simulation_mode)

@app.get("/api/trades", response_model=Dict[str, Any], tags=["Portfolio"])
def get_trades():
    """Historical trade ledger with entry/exit rationale, PnL, and mistake post-mortems"""
    return {
        "total_trades": len(broker.trade_ledger),
        "trades": broker.trade_ledger
    }

@app.get("/api/daily_report", tags=["Portfolio"])
def get_daily_report():
    """
    Generates full end-of-day summary and learning audit (e.g. for review at 10 PM UK time).
    """
    now_utc = datetime.now(timezone.utc)
    # UK London time is typically UTC+1 in BST (or UTC in winter)
    summary = broker.get_portfolio_summary()
    learning = learner.get_stats()
    
    # Calculate initial vs final weights delta
    baseline_w = 0.25
    weight_shifts = {
        k: {
            "current_weight": round(v, 3),
            "current_pct": f"{round(v * 100, 1)}%",
            "shift_from_baseline": f"{'+' if v >= baseline_w else ''}{round((v - baseline_w) * 100, 1)}%"
        }
        for k, v in learning.strategy_weights.items()
    }

    # Calculate per-stock aggregated summary
    stock_summaries = broker.get_per_stock_summary()

    return {
        "report_generated_time_utc": now_utc.isoformat(),
        "report_time_uk": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "initial_capital": broker.initial_capital,
        "current_equity": broker.get_equity(),
        "available_cash": round(broker.cash, 2),
        "net_pnl_usd": summary.total_realized_pnl_usd,
        "net_pnl_pct": summary.total_realized_pnl_pct,
        "total_trades_today": summary.total_trades,
        "winning_trades": summary.win_count,
        "losing_trades": summary.loss_count,
        "win_rate_pct": summary.win_rate_pct,
        "profit_factor": summary.profit_factor,
        "max_drawdown_pct": summary.max_drawdown_pct,
        "open_positions": [p.model_dump() for p in broker.positions.values()],
        "per_stock_summary": [s.model_dump() for s in stock_summaries],
        "strategy_weight_evolution": weight_shifts,
        "diagnosed_mistakes": [m.model_dump() for m in learning.mistake_history],
        "full_trade_ledger": [t.model_dump() for t in broker.trade_ledger]
    }

@app.get("/api/reports/five_day", tags=["Audit & Reporting"])
@app.get("/api/reports/multi_day", tags=["Audit & Reporting"])
def get_five_day_report(days: int = 5):
    """
    Returns aggregated performance over the last 5 working days,
    summarized per individual stock and across the total portfolio.
    """
    return broker.get_multi_day_report(days=days)

class EmailReportRequest(BaseModel):
    recipient: Optional[str] = None
    report_type: Optional[str] = "daily" # "daily" or "5day"

@app.get("/api/reports/pdf", tags=["Audit & Reporting"])
def download_pdf_report(report_type: str = "daily"):
    """
    Generates and returns an executive PDF performance audit report.
    """
    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    is_5day = report_type.lower() in ("5day", "fiveday", "weekly")

    if is_5day:
        report_data = broker.get_multi_day_report(days=5).model_dump()
        filename = f"trading_report_5day_{date_str}.pdf"
    else:
        report_data = get_daily_report()
        filename = f"trading_report_daily_{date_str}.pdf"

    pdf_bytes = ReportPDFGenerator.generate_pdf(report_data, is_five_day=is_5day)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )

@app.post("/api/reports/email", tags=["Audit & Reporting"])
def email_pdf_report(req: EmailReportRequest):
    """
    Generates a PDF audit report and emails it to the recipient (e.g. lisawalker6898@gmail.com).
    """
    recipient = (req.recipient or config.report_recipient_email).strip()
    if not recipient:
        recipient = "lisawalker6898@gmail.com"

    now_utc = datetime.now(timezone.utc)
    date_str = now_utc.strftime("%Y-%m-%d")
    is_5day = (req.report_type or "daily").lower() in ("5day", "fiveday", "weekly")

    if is_5day:
        report_data = broker.get_multi_day_report(days=5).model_dump()
        filename = f"trading_report_5day_{date_str}.pdf"
    else:
        report_data = get_daily_report()
        filename = f"trading_report_daily_{date_str}.pdf"

    pdf_bytes = ReportPDFGenerator.generate_pdf(report_data, is_five_day=is_5day)

    success, message = EmailReportDispatcher.send_report_email(
        recipient_email=recipient,
        pdf_bytes=pdf_bytes,
        filename=filename,
        report_data=report_data,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_pass=config.smtp_pass,
        smtp_sender=config.smtp_sender,
        is_five_day=is_5day
    )

    return {
        "status": "success" if success else "error",
        "recipient": recipient,
        "filename": filename,
        "message": message
    }


@app.get("/api/learning/stats", response_model=LearningStatsOutput, tags=["Adaptive Learning"])
def get_learning_stats():
    """Dynamic strategy weights, mistake history, and adaptation performance"""
    return learner.get_stats()

@app.post("/api/action/trade", tags=["Manual Controls"])
def execute_manual_action(req: ManualTradeRequest):
    """Executes a manual Buy, Short, or Close position order."""
    quote = data_feed.get_latest_quote(req.symbol)
    if req.action.upper() == "CLOSE":
        trade = broker.close_position(req.symbol, quote.price, exit_rationale="Manual user close")
        if not trade:
            raise HTTPException(status_code=400, detail="No active position found for this symbol")
        return {"status": "success", "closed_trade": trade}
    
    direction = "LONG" if req.action.upper() == "BUY" else "SHORT"
    pos = broker.execute_order(
        symbol=req.symbol,
        direction=direction,
        allocated_usd=req.amount_usd or 500.0,
        current_price=quote.price,
        rationale=f"Manual user execution of {direction} on {req.symbol}"
    )
    if not pos:
        raise HTTPException(status_code=400, detail="Insufficient capital or invalid order parameters")
    return {"status": "success", "position": pos}

@app.post("/api/action/tick", tags=["Manual Controls"])
def trigger_analysis_tick(symbol: Optional[str] = None):
    """Manually triggers an analysis and execution cycle."""
    sym = symbol or active_symbol
    return run_analysis_cycle(sym)

@app.get("/api/config", tags=["Configuration"])
def get_system_config():
    """Returns current system configuration and API status."""
    return {
        "finnhub_api_key_configured": bool(config.finnhub_api_key and len(config.finnhub_api_key) > 5),
        "etoro_api_key_configured": bool(config.etoro_api_key and len(config.etoro_api_key) > 5),
        "etoro_user_key_configured": bool(config.etoro_user_key and len(config.etoro_user_key) > 5),
        "etoro_base_url": config.etoro_base_url,
        "execution_mode": config.execution_mode,
        "active_symbol": active_symbol,
        "simulation_mode": config.simulation_mode,
        "watchlist": config.watchlist,
        "initial_capital": config.initial_capital,
        "max_position_size_usd": config.max_position_size_usd,
        "max_drawdown_limit_pct": config.max_drawdown_limit_pct
    }

@app.post("/api/config", tags=["Configuration"])
def update_system_config(req: ConfigUpdateRequest):
    """Updates API key, active symbol, or trading parameters."""
    global active_symbol
    if req.finnhub_api_key is not None:
        config.finnhub_api_key = req.finnhub_api_key.strip()
        data_feed.set_api_key(config.finnhub_api_key)
    if req.etoro_api_key is not None:
        config.etoro_api_key = req.etoro_api_key.strip()
        etoro_client.api_key = config.etoro_api_key
    if req.etoro_user_key is not None:
        config.etoro_user_key = req.etoro_user_key.strip()
        etoro_client.user_key = config.etoro_user_key
    if req.etoro_base_url is not None:
        config.etoro_base_url = req.etoro_base_url.strip()
        etoro_client.base_url = config.etoro_base_url
    if req.execution_mode is not None:
        config.execution_mode = req.execution_mode.strip().lower()
    if req.active_symbol:
        active_symbol = req.active_symbol.upper()
    if req.simulation_mode is not None:
        config.simulation_mode = req.simulation_mode
    if req.risk_per_trade_pct is not None:
        config.risk_per_trade_pct = req.risk_per_trade_pct
    return {"status": "updated", "config": get_system_config()}

# ==========================================
# ETORO LIVE INTEGRATION & MODE SWITCH APIS
# ==========================================

@app.get("/api/etoro/status", tags=["eToro Live Integration"])
def get_etoro_status():
    """Returns eToro API configuration, credentials presence, and active execution mode."""
    return {
        "execution_mode": config.execution_mode,
        "is_configured": etoro_client.is_configured(),
        "base_url": etoro_client.base_url,
        "has_api_key": bool(etoro_client.api_key),
        "has_user_key": bool(etoro_client.user_key)
    }

@app.post("/api/etoro/test_connection", tags=["eToro Live Integration"])
def test_etoro_connection():
    """Validates eToro API credentials in read-only mode without placing trades."""
    return etoro_client.test_connection()

@app.post("/api/mode/switch", tags=["eToro Live Integration"])
def switch_execution_mode(req: ModeSwitchRequest):
    """Switches execution mode between demo (learning/simulation) and live (eToro real orders)."""
    target_mode = req.mode.strip().lower()
    if target_mode not in ("demo", "live"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'demo' or 'live'.")

    if target_mode == "live" and not etoro_client.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Cannot switch to LIVE mode: eToro API Key and User Key are not configured. Please enter them in Settings."
        )

    config.execution_mode = target_mode
    logger.info(f"Execution mode switched to: {config.execution_mode.upper()}")
    return {
        "status": "success",
        "execution_mode": config.execution_mode,
        "message": f"Switched to {'⚡ LIVE eToro Trading' if target_mode == 'live' else '🛡️ Demo & Learning Simulation'}"
    }

# ==========================================
# UNIVERSAL MARKET SCREENER & WATCHLIST APIS
# ==========================================

class WatchlistAddRequest(BaseModel):
    symbol: str

class WatchlistPresetRequest(BaseModel):
    preset_key: str

@app.get("/api/screener/scan", tags=["Market Screener"])
def scan_market(category: Optional[str] = None, top_n: int = 35):
    """Scans all multi-asset instruments across Crypto, Commodities, Indices, ETFs, and Equities."""
    return MarketScreener.scan_universe(data_feed, category_filter=category, top_n=top_n)

@app.get("/api/screener/universe", tags=["Market Screener"])
def get_market_universe():
    """Returns complete list of 100+ tradable assets, sectors, and presets."""
    return {
        "total_instruments": len(MASTER_STOCK_UNIVERSE),
        "universe": MASTER_STOCK_UNIVERSE,
        "presets": PRESET_WATCHLISTS
    }

@app.get("/api/watchlist", tags=["Watchlist Manager"])
def get_watchlist():
    """Returns active bot watchlist and available preset packages."""
    return {
        "active_watchlist": config.watchlist,
        "count": len(config.watchlist),
        "presets": {k: v["title"] for k, v in PRESET_WATCHLISTS.items()}
    }

@app.post("/api/watchlist/add", tags=["Watchlist Manager"])
def add_to_watchlist(req: WatchlistAddRequest):
    """Adds ANY custom stock ticker to the active trading bot."""
    sym = req.symbol.strip().upper()
    if not sym:
        raise HTTPException(status_code=400, detail="Symbol cannot be empty")
    if sym not in config.watchlist:
        config.watchlist.append(sym)
    # Warmup data feed for new symbol
    data_feed.get_latest_quote(sym)
    return {"status": "added", "symbol": sym, "active_watchlist": config.watchlist}

@app.post("/api/watchlist/remove", tags=["Watchlist Manager"])
def remove_from_watchlist(req: WatchlistAddRequest):
    """Removes a stock ticker from the active trading bot."""
    sym = req.symbol.strip().upper()
    if sym in config.watchlist:
        config.watchlist.remove(sym)
    return {"status": "removed", "symbol": sym, "active_watchlist": config.watchlist}

@app.post("/api/watchlist/preset", tags=["Watchlist Manager"])
def set_watchlist_preset(req: WatchlistPresetRequest):
    """Loads a pre-built watchlist preset (e.g. all_top_50, crypto_high_beta, ai_tech_titans)."""
    preset = PRESET_WATCHLISTS.get(req.preset_key)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    config.watchlist = list(preset["symbols"])
    # Warmup quotes for all symbols in preset
    for s in config.watchlist:
        data_feed.get_latest_quote(s)
    return {
        "status": "loaded",
        "preset_title": preset["title"],
        "active_watchlist": config.watchlist
    }

@app.post("/api/screener/auto_add_top", tags=["Market Screener"])
def auto_add_top_screened(top_n: int = 15):
    """Automatically scans universe and adds top ranked momentum opportunities to the active trading bot."""
    screened = MarketScreener.scan_universe(data_feed, top_n=top_n)
    top_symbols = [s["symbol"] for s in screened]
    for sym in top_symbols:
        if sym not in config.watchlist:
            config.watchlist.append(sym)
    return {
        "status": "success",
        "added_symbols": top_symbols,
        "active_watchlist": config.watchlist
    }


@app.post("/api/portfolio/reset", tags=["Portfolio"])
def reset_portfolio():
    """Resets simulated portfolio to initial capital."""
    broker.cash = config.initial_capital
    broker.peak_equity = config.initial_capital
    broker.positions.clear()
    broker.trade_ledger.clear()
    learner.mistake_history.clear()
    learner.total_trades_evaluated = 0
    learner.winning_trades_count = 0
    learner.losing_trades_count = 0
    learner.total_win_usd = 0.0
    learner.total_loss_usd = 0.0
    learner.weights = {
        "momentum_trend": 0.25,
        "mean_reversion": 0.25,
        "volatility_breakout": 0.25,
        "news_sentiment": 0.25
    }
    broker.save_state()
    return {"status": "reset", "cash": broker.cash}

# ==========================================
# QUANTITATIVE BACKTESTING & OPTIMIZER
# ==========================================
class BacktestRequest(BaseModel):
    symbol: str = "SOXL"
    stop_loss_pct: float = 0.025
    take_profit_pct: float = 0.050
    adx_threshold: float = 20.0
    num_ticks: int = 150

class OptimizeRequest(BaseModel):
    symbol: str = "SOXL"

class ApplyParametersRequest(BaseModel):
    symbol: str
    stop_loss_pct: float
    take_profit_pct: float
    adx_threshold: float

@app.post("/api/backtest/run", tags=["Backtest"])
def run_backtest_endpoint(req: BacktestRequest):
    """Executes quantitative backtest simulation on an individual asset or portfolio-wide across all active stocks."""
    base_p = BASE_PRICES.get(req.symbol.upper(), 100.0)
    return backtester.run_backtest(
        symbol=req.symbol.upper(),
        initial_capital=config.initial_capital,
        stop_loss_pct=req.stop_loss_pct,
        take_profit_pct=req.take_profit_pct,
        adx_threshold=req.adx_threshold,
        num_ticks=req.num_ticks,
        base_price=base_p,
        watchlist_symbols=config.watchlist
    )

@app.post("/api/backtest/optimize", tags=["Backtest"])
def optimize_parameters_endpoint(req: OptimizeRequest):
    """Runs grid-search optimization to discover highest-performing Stop-Loss, Take-Profit, and ADX filters."""
    return backtester.optimize_parameters(
        symbol=req.symbol.upper(),
        initial_capital=config.initial_capital,
        watchlist_symbols=config.watchlist
    )

@app.post("/api/backtest/apply", tags=["Backtest"])
def apply_parameters_endpoint(req: ApplyParametersRequest):
    """Applies optimal stop-loss, take-profit, and ADX filters directly to live trading engine."""
    config.default_stop_loss_pct = req.stop_loss_pct
    config.default_take_profit_pct = req.take_profit_pct
    return {
        "status": "applied",
        "symbol": req.symbol.upper(),
        "applied_stop_loss_pct": req.stop_loss_pct,
        "applied_take_profit_pct": req.take_profit_pct,
        "applied_adx_threshold": req.adx_threshold,
        "message": f"Optimal parameters for {req.symbol.upper()} successfully applied to live cloud trader!"
    }


# ==========================================
# STATIC UI FILE SERVING (For Render & Local)
# ==========================================
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/cockpit", include_in_schema=False)
    @app.get("/app", include_in_schema=False)
    async def serve_cockpit_ui():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return JSONResponse({"error": "Frontend UI index.html not found"}, status_code=404)

    @app.get("/style.css", include_in_schema=False)
    async def serve_css():
        css_file = FRONTEND_DIR / "style.css"
        if css_file.exists():
            return FileResponse(css_file, media_type="text/css")
        return JSONResponse({"error": "style.css not found"}, status_code=404)

    @app.get("/dashboard.js", include_in_schema=False)
    async def serve_js():
        js_file = FRONTEND_DIR / "dashboard.js"
        if js_file.exists():
            return FileResponse(js_file, media_type="application/javascript")
        return JSONResponse({"error": "dashboard.js not found"}, status_code=404)

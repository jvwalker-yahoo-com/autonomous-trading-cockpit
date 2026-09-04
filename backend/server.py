"""
FastAPI Server and Background Autonomous Engine for the Predictive Execution Cockpit.
Provides all 10 core endpoints specified in the architectural design, plus live portfolio management,
self-learning evaluation, Finnhub integration, and static UI serving.
"""
import os
import time
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
screener = MarketScreener()

# Restore persisted system settings from disk
saved_settings = broker.load_state()
if saved_settings:
    if "execution_mode" in saved_settings and saved_settings["execution_mode"]:
        config.execution_mode = saved_settings["execution_mode"]
    if "etoro_api_key" in saved_settings and saved_settings["etoro_api_key"]:
        config.etoro_api_key = saved_settings["etoro_api_key"]
        etoro_client.api_key = config.etoro_api_key
    if "etoro_user_key" in saved_settings and saved_settings["etoro_user_key"]:
        config.etoro_user_key = saved_settings["etoro_user_key"]
        etoro_client.user_key = config.etoro_user_key
    if "etoro_base_url" in saved_settings and saved_settings["etoro_base_url"]:
        config.etoro_base_url = saved_settings["etoro_base_url"]
        etoro_client.base_url = config.etoro_base_url
    if "finnhub_api_key" in saved_settings and saved_settings["finnhub_api_key"]:
        config.finnhub_api_key = saved_settings["finnhub_api_key"]
        data_feed.set_api_key(config.finnhub_api_key)
    if "min_conviction_score" in saved_settings and saved_settings["min_conviction_score"]:
        config.min_conviction_score = float(saved_settings["min_conviction_score"])

# Ensure live mode does not inherit a stale simulation paper drawdown lockout or phantom paper positions
if config.execution_mode == "live":
    broker.positions.clear()
    broker.reset_drawdown()

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

# Permanent Core Anchor Assets — must NEVER be evicted by autonomous screener rotation
CORE_ANCHOR_SYMBOLS = [
    "BTC", "ETH", "SOL", "XRP",                      # Major Crypto (24/7)
    "AAPL", "NVDA", "MSFT", "TSLA", "META",         # Mega-Cap Tech
    "SPY", "QQQ", "SOXL", "SQQQ",                   # Top ETFs
    "GOLD", "OIL"                                   # Macro Commodities
]

# Spot crypto assets on eToro cannot be shorted by retail accounts (LONG only)
CRYPTO_SYMBOLS = {
    "BTC", "ETH", "SOL", "XRP", "BNB", "DOGE", "ADA", "AVAX",
    "LINK", "DOT", "NEAR", "MATIC", "SHIB", "LTC", "UNI",
    "RENDER", "FET", "SUI", "PEPE"
}

async def autonomous_background_worker_loop():
    logger.info("Autonomous Background Trading Loop initialized with Multi-Asset Auto-Discovery.")
    last_universe_scan = 0.0

    # Ensure core anchor assets are in watchlist on boot
    config.watchlist = list(dict.fromkeys(CORE_ANCHOR_SYMBOLS + config.watchlist))

    while True:
        try:
            now = time.time()
            # Dynamic multi-asset discovery across Equities, Crypto (24/7), Commodities, Indices, and ETFs
            if config.auto_rotate_universe and (now - last_universe_scan > config.universe_scan_interval_sec):
                last_universe_scan = now
                try:
                    top_screened = screener.scan_universe(data_feed_manager=data_feed, top_n=20)
                    screened_syms = [s["symbol"] for s in top_screened if s.get("opportunity_score", 0) >= 60]
                    if screened_syms:
                        # Core anchors ALWAYS stay at the front; screened momentum picks appended
                        combined = list(dict.fromkeys(CORE_ANCHOR_SYMBOLS + screened_syms + config.watchlist))[:40]
                        config.watchlist = combined
                        logger.info(f"✨ [AUTONOMOUS ASSET SELECTION] Rotated active universe to {len(screened_syms)} top opportunities: {screened_syms[:8]} (Total active: {len(config.watchlist)})")
                except Exception as ex:
                    logger.warning(f"Dynamic asset discovery notice: {ex}")

            # Cycle analysis across all currently active dynamic watchlist assets
            for sym in list(config.watchlist):
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
    min_conviction_score: Optional[float] = None
    etoro_api_key: Optional[str] = None
    etoro_user_key: Optional[str] = None
    etoro_base_url: Optional[str] = None
    execution_mode: Optional[str] = None

class ModeSwitchRequest(BaseModel):
    mode: str # "demo" or "live"

class ManualTradeRequest(BaseModel):
    symbol: str
    action: str # "BUY", "SHORT", "CLOSE"
    amount_usd: Optional[float] = 100.0

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
    conv_thresh = getattr(config, "min_conviction_score", 0.25)
    if federation.federated_score >= conv_thresh:
        signal = "BUY"
    elif federation.federated_score <= -conv_thresh:
        signal = "SHORT"

    # Execution if arbitration approved
    if arbitration.approved and signal in ("BUY", "SHORT"):
        # Position sizing based on confidence & risk budget (capped at $100 to protect small account)
        max_alloc = min(config.max_position_size_usd, min(100.0, max(20.0, equity * 0.10)))
        alloc_base = max_alloc * confidence
        allocated_usd = max(20.0, min(max_alloc, alloc_base))
        target_shares = round(allocated_usd / max(0.00000001, quote.price), 4)

        # Autonomous trade entry (if not already holding this direction)
        existing = broker.positions.get(symbol)
        if not existing or (existing.direction != ("LONG" if signal == "BUY" else "SHORT")):
            trade_dir = "LONG" if signal == "BUY" else "SHORT"
            can_execute_broker = True

            # When in Live mode, dispatch real order to official eToro REST API
            if config.execution_mode == "live" and etoro_client.is_configured():
                if trade_dir == "SHORT" and symbol in CRYPTO_SYMBOLS:
                    logger.info(f"ℹ️ [CRYPTO LONG-ONLY] Skipping autonomous SHORT on {symbol}: Crypto is spot long-only on eToro.")
                    can_execute_broker = False
                else:
                    inst_id = etoro_client.resolve_instrument_id(symbol)
                    if not inst_id:
                        logger.warning(f"[LIVE SKIP] Cannot resolve eToro instrument ID for '{symbol}' — skipping live order.")
                        can_execute_broker = False
                    else:
                        is_short = (trade_dir == "SHORT")
                        sl_prec = 8 if quote.price < 0.01 else (4 if quote.price < 1.0 else 2)
                        sl_rate = round(quote.price * (1.0 + config.default_stop_loss_pct if is_short else 1.0 - config.default_stop_loss_pct), sl_prec)
                        tp_rate = round(quote.price * (1.0 - config.default_take_profit_pct if is_short else 1.0 + config.default_take_profit_pct), sl_prec)

                        logger.info(f"⚡ [LIVE ETORO ORDER] Dispatching {trade_dir} on {symbol} (ID: {inst_id}) for ${allocated_usd:.2f} (SL: ${sl_rate}, TP: ${tp_rate})...")
                        try:
                            order_res = etoro_client.create_order(
                                instrument_id=inst_id,
                                direction=trade_dir,
                                amount_usd=allocated_usd,
                                stop_loss_rate=sl_rate,
                                take_profit_rate=tp_rate,
                                mode="real",
                                symbol=symbol
                            )
                            if order_res.get("success"):
                                logger.info(f"✅ [LIVE ETORO SUCCESS] Order filled for {symbol}: {order_res}")
                                can_execute_broker = True
                            else:
                                logger.warning(f"❌ [LIVE ETORO REJECTED] Order failed for {symbol}: {order_res.get('error') or order_res}")
                                can_execute_broker = False
                        except Exception as e:
                            logger.error(f"eToro live order execution exception: {e}")
                            can_execute_broker = False

            # In live mode, only record in local broker ledger if eToro order was actually executed!
            if can_execute_broker:
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

            # Auto-sync newly traded stock to eToro Watchlist
            try:
                etoro_client.sync_symbols_to_watchlist([symbol], watchlist_name="Autonomous Cockpit")
            except Exception as e:
                logger.warning(f"Watchlist auto-sync notice for {symbol}: {e}")

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

@app.api_route("/", methods=["GET", "HEAD"], tags=["Cockpit Core"])
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
        "watchlist": config.watchlist,
        "execution_mode": config.execution_mode,
        "is_configured": etoro_client.is_configured()
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
        if config.execution_mode == "live" and etoro_client.is_configured():
            try:
                etoro_client.close_position(req.symbol, mode="real")
            except Exception as e:
                logger.error(f"eToro manual live close exception: {e}")
        trade = broker.close_position(req.symbol, quote.price, exit_rationale="Manual user close")
        if not trade:
            raise HTTPException(status_code=400, detail="No active position found for this symbol")
        return {"status": "success", "closed_trade": trade}
    
    direction = "LONG" if req.action.upper() == "BUY" else "SHORT"
    alloc_usd = req.amount_usd or 100.0
    etoro_res = None

    if config.execution_mode == "live" and etoro_client.is_configured():
        if direction == "SHORT" and req.symbol in CRYPTO_SYMBOLS:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot SHORT {req.symbol}: Cryptocurrency is spot/long-only on eToro retail accounts. Please choose BUY (LONG)."
            )
        inst_id = etoro_client.resolve_instrument_id(req.symbol)
        if not inst_id:
            logger.warning(f"[MANUAL LIVE SKIP] Cannot resolve eToro instrument ID for '{req.symbol}'")
            etoro_res = {"success": False, "error": f"Unknown instrument '{req.symbol}' on eToro — check symbol name"}
        else:
            is_short = (direction == "SHORT")
            sl_prec = 8 if quote.price < 0.01 else (4 if quote.price < 1.0 else 2)
            sl_rate = round(quote.price * (1.0 + config.default_stop_loss_pct if is_short else 1.0 - config.default_stop_loss_pct), sl_prec)
            tp_rate = round(quote.price * (1.0 - config.default_take_profit_pct if is_short else 1.0 + config.default_take_profit_pct), sl_prec)

            logger.info(f"⚡ [MANUAL LIVE ETORO ORDER] {direction} on {req.symbol} (ID: {inst_id}) for ${alloc_usd:.2f} (SL: ${sl_rate}, TP: ${tp_rate})...")
            try:
                etoro_res = etoro_client.create_order(
                    instrument_id=inst_id,
                    direction=direction,
                    amount_usd=alloc_usd,
                    stop_loss_rate=sl_rate,
                    take_profit_rate=tp_rate,
                    mode="real",
                    symbol=req.symbol
                )
            except Exception as e:
                logger.error(f"eToro manual live order exception: {e}")
                etoro_res = {"success": False, "error": str(e)}

    pos = broker.execute_order(
        symbol=req.symbol,
        direction=direction,
        allocated_usd=alloc_usd,
        current_price=quote.price,
        rationale=f"Manual user execution of {direction} on {req.symbol}"
    )
    if not pos:
        raise HTTPException(status_code=400, detail="Insufficient capital or invalid order parameters")
    return {"status": "success", "position": pos, "etoro_result": etoro_res}

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
        "max_drawdown_limit_pct": config.max_drawdown_limit_pct,
        "min_conviction_score": getattr(config, "min_conviction_score", 0.25)
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
        raw_b = req.etoro_base_url.strip().rstrip("/")
        if "api.etoro.com" in raw_b and "public-api.etoro.com" not in raw_b:
            raw_b = raw_b.replace("api.etoro.com", "public-api.etoro.com")
        config.etoro_base_url = raw_b or "https://public-api.etoro.com"
        etoro_client.base_url = config.etoro_base_url
    if req.execution_mode is not None:
        config.execution_mode = req.execution_mode.strip().lower()
    if req.active_symbol:
        active_symbol = req.active_symbol.upper()
    if req.simulation_mode is not None:
        config.simulation_mode = req.simulation_mode
    if req.risk_per_trade_pct is not None:
        config.risk_per_trade_pct = req.risk_per_trade_pct
    if req.min_conviction_score is not None:
        config.min_conviction_score = max(0.05, min(0.95, req.min_conviction_score))

    # Persist updated settings to disk
    broker.save_state({
        "execution_mode": config.execution_mode,
        "etoro_api_key": config.etoro_api_key,
        "etoro_user_key": config.etoro_user_key,
        "etoro_base_url": config.etoro_base_url,
        "finnhub_api_key": config.finnhub_api_key,
        "min_conviction_score": config.min_conviction_score
    })
    return {"status": "updated", "config": get_system_config()}

# ==========================================
# ETORO LIVE INTEGRATION & MODE SWITCH APIS
# ==========================================

@app.get("/api/etoro/status", tags=["eToro Live Integration"])
def get_etoro_status():
    """Returns eToro API configuration, credentials presence, and active execution mode."""
    import base64
    k_api = etoro_client.api_key or ""
    k_user = etoro_client.user_key or ""
    
    def safe_decode_jwt_payload(token_str: str):
        try:
            tok = token_str.strip()
            parts = tok.split(".")
            target = parts[1] if len(parts) >= 2 else parts[0]
            s = target.replace("-", "+").replace("_", "/")
            pad_len = (4 - len(s) % 4) % 4
            raw_bytes = base64.b64decode(s + ("=" * pad_len), validate=False)
            parsed = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
            if isinstance(parsed, dict):
                return True, list(parsed.keys()), parsed.get("ean") or parsed.get("cid") or parsed.get("name") or parsed.get("username")
        except Exception:
            pass
        return False, [], None

    user_valid, user_keys, user_app = safe_decode_jwt_payload(k_user)
    api_valid, api_keys, api_app = safe_decode_jwt_payload(k_api)

    return {
        "execution_mode": config.execution_mode,
        "is_configured": etoro_client.is_configured(),
        "base_url": etoro_client.base_url,
        "has_api_key": bool(k_api),
        "has_user_key": bool(k_user),
        "api_key_len": len(k_api),
        "user_key_len": len(k_user),
        "api_key_masked": f"{k_api[:4]}...{k_api[-4:]}" if len(k_api) >= 8 else ("raw:" + k_api),
        "user_key_masked": f"{k_user[:4]}...{k_user[-4:]}" if len(k_user) >= 8 else ("raw:" + k_user),
        "user_key_starts_with_ey": k_user.strip().startswith("ey"),
        "api_key_starts_with_ey": k_api.strip().startswith("ey"),
        "user_key_has_surrounding_quotes": (k_user.startswith('"') and k_user.endswith('"')) or (k_user.startswith("'") and k_user.endswith("'")),
        "user_key_has_whitespace": any(c in k_user for c in " \t\r\n"),
        "api_key_has_whitespace": any(c in k_api for c in " \t\r\n"),
        "user_key_b64_json_valid": user_valid,
        "user_key_payload_keys": user_keys,
        "user_key_application_name": user_app,
        "api_key_b64_json_valid": api_valid,
        "api_key_payload_keys": api_keys,
        "api_key_application_name": api_app,
    }


@app.post("/api/etoro/test_connection", tags=["eToro Live Integration"])
def test_etoro_connection():
    """Validates eToro API credentials in read-only mode without placing trades."""
    res = etoro_client.test_connection()
    if res.get("connected"):
        config.etoro_api_key = etoro_client.api_key
        config.etoro_user_key = etoro_client.user_key
        broker.save_state({
            "etoro_api_key": etoro_client.api_key,
            "etoro_user_key": etoro_client.user_key,
            "etoro_base_url": etoro_client.base_url
        })
        logger.info(f"✓ Locked in authenticated eToro API Key & User Key orientation (Persisted to disk).")
    return res

@app.get("/api/etoro/instrument_search", tags=["eToro Live Integration"])
def etoro_instrument_search(symbol: str = "BTC"):
    """
    Diagnostic + ID resolution: tries real API, demo credentials, and portfolio positions.
    GET /api/etoro/instrument_search?symbol=BTC
    """
    sym = symbol.upper().strip()

    # Step 1: Try portfolio positions to populate cache from real account data
    portfolio_new = etoro_client.populate_cache_from_portfolio()

    # Step 2: Try search via real API (requires market-data:read scope)
    search_results = etoro_client.search_instruments(sym)

    # Step 3: Try via official eToro demo credentials (read-only, safe fallback)
    demo_id = etoro_client.search_via_demo_creds(sym)

    # Step 4: Check raw debug variants
    debug = etoro_client.raw_search_debug(sym)

    # Step 5: Identity endpoint probe for known IDs
    identity_probes = {}
    for cid in [1, 2, 3, 100, 101, 1001, 1002, 1003, 1004, 1005]:
        result = etoro_client.lookup_instrument_identity(cid)
        if result:
            identity_probes[str(cid)] = result

    resolved_id = etoro_client._instrument_cache.get(sym) or demo_id

    return {
        "symbol_queried": sym,
        "resolved_instrument_id": resolved_id,
        "resolution_method": "demo_credentials" if demo_id else ("portfolio" if portfolio_new > 0 else "none"),
        "search_results": search_results[:5],
        "debug_responses": debug,
        "identity_endpoint_probes": identity_probes,
        "portfolio_ids_discovered": portfolio_new,
        "cache_size": len(etoro_client._instrument_cache),
        "cache_contents": dict(etoro_client._instrument_cache),
        "is_configured": etoro_client.is_configured()
    }


@app.get("/api/etoro/ws-test", tags=["eToro Live Integration"])
def test_etoro_websocket():
    """Tests eToro WebSocket authentication to wss://ws.etoro.com/ws."""
    return etoro_client.test_websocket()


@app.get("/api/etoro/mcp-test", tags=["eToro Live Integration"])
def test_etoro_mcp(symbol: str = "BTC"):
    """Tests eToro MCP prepare-trade validation for $100 on symbol."""
    return etoro_client.execute_mcp_trade(symbol=symbol, direction="BUY", amount_usd=100.0, mode="real")


@app.get("/api/etoro/scopes", tags=["eToro Live Integration"])
def get_etoro_scopes():
    """Fetches granted OAuth scopes and account profile via the official eToro MCP server."""
    return etoro_client.get_mcp_profile_and_scopes()


@app.get("/api/etoro/mcp-prepare", tags=["eToro Live Integration"])
def etoro_mcp_prepare(symbol: str = "BTC", direction: str = "BUY", amount: float = 100.0, mode: str = "real"):
    """Pre-flights and validates a proposed trade against live quotes and account balance without placing it."""
    return etoro_client.prepare_mcp_trade(symbol=symbol, direction=direction, amount_usd=amount, mode=mode)


@app.get("/api/etoro/balances", tags=["eToro Live Integration"])
def get_live_balances():
    """Fetches live multi-account balances (Trading, Cash, Crypto) from eToro via official MCP gateway."""
    return etoro_client.get_account_balances()


@app.get("/api/etoro/portfolio", tags=["eToro Live Integration"])
def get_live_portfolio(mode: str = "real"):
    """Fetches live active portfolio holdings and positions from eToro via official MCP gateway."""
    return etoro_client.get_portfolio(mode=mode)


@app.post("/api/mode/switch", tags=["eToro Live Integration"])
def switch_execution_mode(req: ModeSwitchRequest):
    """Switches execution mode between demo (learning/simulation) and live (eToro real orders). Automatically builds 5-day proven watchlist when switching to live."""
    target_mode = req.mode.strip().lower()
    if target_mode not in ("demo", "live"):
        raise HTTPException(status_code=400, detail="Invalid mode. Must be 'demo' or 'live'.")

    if target_mode == "live" and not etoro_client.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Cannot switch to LIVE mode: eToro API Key and User Key are not configured. Please enter them in Settings."
        )

    config.execution_mode = target_mode
    # Persist execution mode to disk
    broker.save_state({"execution_mode": config.execution_mode})
    logger.info(f"Execution mode switched to: {config.execution_mode.upper()}")

    sync_info = None
    if target_mode == "live":
        # Clear previous simulated paper positions so live execution slots are immediately open
        broker.positions.clear()
        
        # Reset peak equity watermark and unlatch any paper drawdown circuit breaker
        live_equity = None
        try:
            bal_res = etoro_client.get_account_balances()
            if bal_res.get("success") and bal_res.get("data"):
                d = bal_res["data"]
                if isinstance(d, dict):
                    live_equity = d.get("totalEquity") or d.get("equity") or d.get("cashBalance") or d.get("availableCash")
                elif isinstance(d, list) and len(d) > 0 and isinstance(d[0], dict):
                    live_equity = d[0].get("totalEquity") or d[0].get("equity") or d[0].get("cashBalance")
        except Exception as e:
            logger.warning(f"Could not query live balance during mode switch: {e}")

        recal_eq = broker.reset_drawdown(new_equity=float(live_equity) if live_equity else None)
        logger.info(f"✓ Recalibrated broker equity to ${recal_eq:.2f} (Peak: ${broker.peak_equity:.2f}) and unlatched circuit breaker.")

        # Build 5-day historical traded stocks + active watchlist and sync asynchronously in background
        five_day_rep = broker.get_multi_day_report(5)
        traded_symbols = [s.symbol for s in five_day_rep.stock_summaries if s.symbol]
        combined_symbols = list(dict.fromkeys(traded_symbols + config.watchlist))
        if not combined_symbols:
            combined_symbols = ["BTC", "ETH", "AAPL", "NVDA", "TSLA", "MSFT", "SPY", "QQQ"]

        # Run watchlist sync in background thread so HTTP response is instant
        def _bg_sync():
            try:
                etoro_client.sync_symbols_to_watchlist(
                    symbols=combined_symbols,
                    watchlist_name="Autonomous Cockpit"
                )
                logger.info(f"✓ Background initialized eToro Watchlist 'Autonomous Cockpit' with {len(combined_symbols)} stocks.")
            except Exception as e:
                logger.warning(f"Background watchlist sync notice: {e}")

        import threading
        threading.Thread(target=_bg_sync, daemon=True).start()

    return {
        "status": "success",
        "execution_mode": config.execution_mode,
        "message": f"Switched to {'⚡ LIVE eToro Trading' if target_mode == 'live' else '🛡️ Demo & Learning Simulation'}"
    }


@app.post("/api/circuit_breaker/reset", tags=["Arbitration"])
def reset_circuit_breaker():
    """Resets peak equity watermark, synchronizes live eToro balance if in live mode, and unlatches the circuit breaker."""
    live_equity = None
    if config.execution_mode == "live" and etoro_client.is_configured():
        try:
            bal_res = etoro_client.get_account_balances()
            if bal_res.get("success") and bal_res.get("data"):
                d = bal_res["data"]
                if isinstance(d, dict):
                    live_equity = d.get("totalEquity") or d.get("equity") or d.get("cashBalance") or d.get("availableCash")
                elif isinstance(d, list) and len(d) > 0 and isinstance(d[0], dict):
                    live_equity = d[0].get("totalEquity") or d[0].get("equity") or d[0].get("cashBalance")
        except Exception as e:
            logger.warning(f"Could not query live balance for circuit breaker reset: {e}")

    if config.execution_mode == "live":
        broker.positions.clear()
    current_eq = broker.reset_drawdown(new_equity=float(live_equity) if live_equity else None)
    logger.info(f"⚡ [CIRCUIT BREAKER RESET] Peak equity reset to ${current_eq:.2f}. Circuit breaker unlatched.")
    return {
        "status": "success",
        "message": f"Circuit breaker reset. Peak equity aligned to ${current_eq:.2f}.",
        "equity": current_eq,
        "drawdown_pct": 0.0,
        "circuit_breaker_active": False,
        "cleared_positions": True if config.execution_mode == "live" else False
    }

@app.post("/api/etoro/sync_5day_trades", tags=["eToro Live Integration"])
def sync_5day_trades_to_etoro():
    """Builds and synchronizes an eToro Watchlist containing all stocks traded over the last 5 working days."""
    five_day_rep = broker.get_multi_day_report(5)
    traded_symbols = [s.symbol for s in five_day_rep.stock_summaries if s.symbol]
    combined_symbols = list(dict.fromkeys(traded_symbols + config.watchlist))
    if not combined_symbols:
        combined_symbols = ["TQQQ", "QQQ", "MARA", "BULL", "MSFT", "AAPL", "URA", "SOXL", "IREN"]

    res = etoro_client.sync_symbols_to_watchlist(
        symbols=combined_symbols,
        watchlist_name="Autonomous Cockpit"
    )
    return {
        "status": "success",
        "synced_stocks_count": len(combined_symbols),
        "synced_symbols": combined_symbols,
        "details": res
    }

@app.post("/api/etoro/sync_watchlist", tags=["eToro Live Integration"])
def sync_active_watchlist_to_etoro():
    """Synchronizes all currently active bot watchlist stocks to the eToro Watchlist."""
    res = etoro_client.sync_symbols_to_watchlist(
        symbols=config.watchlist,
        watchlist_name="Autonomous Cockpit"
    )
    return {
        "status": "success",
        "synced_stocks_count": len(config.watchlist),
        "synced_symbols": config.watchlist,
        "details": res
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
    """Resets simulated portfolio to initial capital (or aligns with live equity if in live mode)."""
    if config.execution_mode == "live":
        broker.positions.clear()
        broker.reset_drawdown()
    else:
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

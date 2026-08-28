"""
Autonomous Full Trading Day Simulation Runner.
Simulates a full 6.5-hour trading day session (390 minutes/ticks) on US Equities & ETFs
with a £1,000 initial virtual account, recording all decisions, rationale, P&L,
and self-learning adaptations.
"""
import sys
import json
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Ensure UTF-8 stdout encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')

from backend.config import config
from backend.engine.data_feed import DataFeedManager, BASE_PRICES
from backend.engine.metrics import MetricsModule
from backend.engine.regime import RegimeModule
from backend.engine.federation import FederationModule
from backend.engine.arbitration import ArbitrationModule
from backend.engine.anomaly import AnomalyModule
from backend.engine.quadrant import QuadrantModule
from backend.engine.telemetry import TelemetryModule
from backend.engine.learner import AdaptiveLearner
from backend.engine.broker import SimulatedBroker

def run_trading_day_simulation(initial_capital_gbp: float = 1000.0, total_ticks: int = 150):
    print("=" * 80)
    print(f"[START] FULL TRADING DAY AUTONOMOUS SIMULATION")
    print(f"Initial Capital: £{initial_capital_gbp:,.2f}")
    print(f"Target Watchlist: {', '.join(config.watchlist)}")
    print("=" * 80)

    # Initialize independent isolated simulation instance
    data_feed = DataFeedManager(api_key=config.finnhub_api_key)
    metrics_module = MetricsModule()
    regime_module = RegimeModule()
    federation_module = FederationModule()
    arbitration_module = ArbitrationModule()
    anomaly_module = AnomalyModule()
    quadrant_module = QuadrantModule()
    learner = AdaptiveLearner()
    
    # £1,000 starting cash
    broker = SimulatedBroker(initial_capital=initial_capital_gbp, db_path="", learner=learner)
    
    # Track hourly progression
    hourly_snapshots = []
    
    print("\n[SESSION TIMELINE PROGRESSION]")
    print(f"{'Time':<8} | {'Active Symbol':<13} | {'Signal':<6} | {'Price':<8} | {'Ensemble':<9} | {'Regime':<8} | {'Open Pos':<8} | {'Equity (£)':<10}")
    print("-" * 88)

    simulated_minutes = total_ticks * 2.5 # ~375 minutes (full 6.5 hr day)
    
    for tick_idx in range(total_ticks):
        current_minute = int(tick_idx * (390 / total_ticks))
        hour = 9 + (current_minute + 30) // 60
        minute = (current_minute + 30) % 60
        time_str = f"{hour:02d}:{minute:02d}"

        # Rotate scanning across the watchlist
        for symbol in config.watchlist:
            # 1. Fetch market tick & indicators
            quote = data_feed.get_latest_quote(symbol)
            indicators = data_feed.get_technical_indicators(symbol)
            sentiment = data_feed.get_news_sentiment(symbol)

            # 2. Check and enforce Stop-Loss / Take-Profit on open positions
            broker.update_price_and_check_stops(symbol, quote.price)

            # 3. Compute telemetry metrics (Risk, Impact, Slippage, Latency)
            metrics = metrics_module.compute_all(indicators, actual_latency_ms=data_feed.api_latency_ms)

            # 4. Regime & Anomaly
            regime = regime_module.model_mode(metrics, indicators)
            price_hist = data_feed.history_windows.get(symbol, [quote.price])
            vol_hist = data_feed.volume_windows.get(symbol, [quote.volume])
            anomalies = anomaly_module.anomaly_detector(metrics, price_hist, vol_hist)
            quadrant = quadrant_module.quadrant(metrics["risk"], metrics["impact"])

            # 5. Multi-Model Strategy Federation (using dynamically adapted weights)
            federation = federation_module.model_federation(indicators, quote.price, sentiment, learner.weights)

            # 6. Arbitration Risk Gate Check
            equity = broker.get_equity()
            peak = max(broker.peak_equity, equity)
            drawdown_pct = (peak - equity) / max(1.0, peak)
            total_invested = sum(p.market_value_usd for p in broker.positions.values())
            exposure_pct = total_invested / max(1.0, equity)

            arbitration = arbitration_module.arbitration(
                main_mode=regime.mode,
                quadrant=quadrant.quadrant,
                anomaly_detected=anomalies.anomaly_detected,
                current_drawdown_pct=drawdown_pct,
                max_drawdown_limit_pct=config.max_drawdown_limit_pct,
                current_exposure_pct=exposure_pct,
                max_exposure_limit_pct=config.max_portfolio_exposure_pct,
                active_positions_count=len(broker.positions)
            )

            # 7. Autonomous Decision & Sizing
            signal = "HOLD"
            confidence = abs(federation.federated_score)
            
            if federation.federated_score >= 0.28:
                signal = "BUY"
            elif federation.federated_score <= -0.28:
                signal = "SHORT"

            # Execute trade if approved
            if arbitration.approved and signal in ("BUY", "SHORT"):
                # Position allocation: ~£150 - £250 per fractional position
                alloc_usd = min(250.0, max(80.0, broker.cash * 0.25 * confidence))
                
                existing = broker.positions.get(symbol)
                if not existing:
                    trade_dir = "LONG" if signal == "BUY" else "SHORT"
                    broker.execute_order(
                        symbol=symbol,
                        direction=trade_dir,
                        allocated_usd=alloc_usd,
                        current_price=quote.price,
                        stop_loss_pct=0.020, # 2.0% stop loss
                        take_profit_pct=0.040, # 4.0% take profit
                        rationale=f"Autonomous {trade_dir} on {symbol}. Score: {federation.federated_score:+.2f} ({federation.federation}). Rationale: {federation.model_details[0].rationale}",
                        contributing_models=federation.outputs
                    )

        # Print periodic log
        if tick_idx % 15 == 0 or tick_idx == total_ticks - 1:
            sym_sample = config.watchlist[tick_idx % len(config.watchlist)]
            quote_s = data_feed.last_quotes[sym_sample]
            fed_s = federation_module.model_federation(
                data_feed.get_technical_indicators(sym_sample),
                quote_s.price,
                0.0,
                learner.weights
            )
            sig_s = "BUY" if fed_s.federated_score >= 0.28 else ("SHORT" if fed_s.federated_score <= -0.28 else "HOLD")
            eq = broker.get_equity()
            print(f"{time_str:<8} | {sym_sample:<13} | {sig_s:<6} | £{quote_s.price:<7.2f} | {fed_s.federated_score:<+9.2f} | {regime.mode:<8} | {len(broker.positions):<8} | £{eq:<10.2f}")
            
            hourly_snapshots.append({
                "time": time_str,
                "equity": eq,
                "cash": broker.cash,
                "open_positions": len(broker.positions),
                "regime": regime.mode
            })

    # Close any remaining open positions at market close
    print("\n[MARKET CLOSE: 16:00 EST] Settling all remaining intraday positions...")
    for sym in list(broker.positions.keys()):
        q = data_feed.get_latest_quote(sym)
        broker.close_position(sym, q.price, exit_rationale="End-of-day market close session settlement")

    # Generate Final Results
    final_equity = broker.get_equity()
    total_net_pnl = final_equity - initial_capital_gbp
    pnl_pct = (total_net_pnl / initial_capital_gbp) * 100.0
    summary = broker.get_portfolio_summary()
    learning_stats = learner.get_stats()

    print("\n" + "=" * 80)
    print("FINAL TRADING DAY PERFORMANCE SUMMARY")
    print("=" * 80)
    print(f"* Starting Capital:     £{initial_capital_gbp:,.2f}")
    print(f"* Ending Equity:        £{final_equity:,.2f}")
    pnl_sign = "+" if total_net_pnl >= 0 else ""
    print(f"* Net Realized P&L:     {pnl_sign}£{total_net_pnl:,.2f} ({pnl_sign}{pnl_pct:.2f}%)")
    print(f"* Total Trades:         {summary.total_trades} ({summary.win_count} Wins / {summary.loss_count} Losses)")
    print(f"* Win Rate:             {summary.win_rate_pct:.1f}%")
    print(f"* Profit Factor:        {summary.profit_factor:.2f}")
    print(f"* Max Drawdown:         {summary.max_drawdown_pct:.2f}%")

    # Save detailed JSON summary for report presentation
    report_data = {
        "initial_capital_gbp": initial_capital_gbp,
        "final_equity_gbp": final_equity,
        "total_net_pnl_gbp": round(total_net_pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "total_trades": summary.total_trades,
        "win_count": summary.win_count,
        "loss_count": summary.loss_count,
        "win_rate_pct": summary.win_rate_pct,
        "profit_factor": summary.profit_factor,
        "max_drawdown_pct": summary.max_drawdown_pct,
        "hourly_snapshots": hourly_snapshots,
        "trade_ledger": [t.model_dump() for t in broker.trade_ledger],
        "learning_stats": learning_stats.model_dump()
    }

    report_path = BASE_DIR / "day_trading_session_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    return report_data

if __name__ == "__main__":
    run_trading_day_simulation(1000.0, total_ticks=120)

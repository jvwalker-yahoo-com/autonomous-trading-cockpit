"""
Predictive Execution Cockpit - Streamlit Cloud Edition.
Deployable 24/7 on Streamlit Community Cloud (share.streamlit.io) without keeping PC on.
"""
import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime, timezone

from backend.config import config
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

st.set_page_config(
    page_title="Predictive Execution Cockpit",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Singleton state initialization
if "data_feed" not in st.session_state:
    st.session_state.data_feed = DataFeedManager(api_key=config.finnhub_api_key)
    st.session_state.metrics_mod = MetricsModule()
    st.session_state.regime_mod = RegimeModule()
    st.session_state.federation_mod = FederationModule()
    st.session_state.arbitration_mod = ArbitrationModule()
    st.session_state.anomaly_mod = AnomalyModule()
    st.session_state.quadrant_mod = QuadrantModule()
    st.session_state.telemetry_mod = TelemetryModule()
    st.session_state.learner = AdaptiveLearner()
    st.session_state.broker = SimulatedBroker(
        initial_capital=config.initial_capital,
        learner=st.session_state.learner
    )

feed = st.session_state.data_feed
metrics_mod = st.session_state.metrics_mod
regime_mod = st.session_state.regime_mod
fed_mod = st.session_state.federation_mod
arb_mod = st.session_state.arbitration_mod
anom_mod = st.session_state.anomaly_mod
quad_mod = st.session_state.quadrant_mod
tel_mod = st.session_state.telemetry_mod
learner = st.session_state.learner
broker = st.session_state.broker

# Sidebar Configuration
st.sidebar.title("⚙️ Cockpit Settings")
api_key_input = st.sidebar.text_input("Finnhub API Key", value=config.finnhub_api_key, type="password")
if api_key_input != config.finnhub_api_key:
    config.finnhub_api_key = api_key_input
    feed.set_api_key(api_key_input)

sel_symbol = st.sidebar.selectbox("Active Asset", config.watchlist, index=0)
auto_run = st.sidebar.checkbox("Autonomous Execution Loop", value=True)

if st.sidebar.button("🔄 Reset Account ($10k)"):
    broker.cash = 10000.0
    broker.peak_equity = 10000.0
    broker.positions.clear()
    broker.trade_ledger.clear()
    learner.mistake_history.clear()
    learner.weights = {"momentum_trend": 0.25, "mean_reversion": 0.25, "volatility_breakout": 0.25, "news_sentiment": 0.25}
    st.sidebar.success("Account reset to $10,000!")

# Execution cycle
quote = feed.get_latest_quote(sel_symbol)
indicators = feed.get_technical_indicators(sel_symbol)
sentiment = feed.get_news_sentiment(sel_symbol)
broker.update_price_and_check_stops(sel_symbol, quote.price)

metrics = metrics_mod.compute_all(indicators, actual_latency_ms=feed.api_latency_ms)
regime = regime_mod.model_mode(metrics, indicators)
anomalies = anom_mod.anomaly_detector(metrics, feed.history_windows.get(sel_symbol, []), feed.volume_windows.get(sel_symbol, []))
quadrant = quad_mod.quadrant(metrics["risk"], metrics["impact"])
federation = fed_mod.model_federation(indicators, quote.price, sentiment, learner.weights)

equity = broker.get_equity()
drawdown = max(0.0, (broker.peak_equity - equity) / max(1.0, broker.peak_equity))
exposure = sum(p.market_value_usd for p in broker.positions.values()) / max(1.0, equity)

arbitration = arb_mod.arbitration(
    main_mode=regime.mode,
    quadrant=quadrant.quadrant,
    anomaly_detected=anomalies.anomaly_detected,
    current_drawdown_pct=drawdown,
    max_drawdown_limit_pct=config.max_drawdown_limit_pct,
    current_exposure_pct=exposure,
    max_exposure_limit_pct=config.max_portfolio_exposure_pct,
    active_positions_count=len(broker.positions)
)

# Autonomous decision
signal = "HOLD"
if federation.federated_score >= 0.28:
    signal = "BUY"
elif federation.federated_score <= -0.28:
    signal = "SHORT"

if auto_run and arbitration.approved and signal in ("BUY", "SHORT"):
    existing = broker.positions.get(sel_symbol)
    if not existing:
        trade_dir = "LONG" if signal == "BUY" else "SHORT"
        broker.execute_order(
            symbol=sel_symbol,
            direction=trade_dir,
            allocated_usd=min(500.0, broker.cash * 0.25),
            current_price=quote.price,
            rationale=f"Autonomous {trade_dir} on {sel_symbol}. Score: {federation.federated_score:+.2f} ({federation.federation})"
        )

# Header & Top KPI Bar
st.title("⚡ PREDICTIVE EXECUTION COCKPIT")
st.caption("AUTONOMOUS QUANTITATIVE TRADING ENGINE // 24/7 CLOUD HOSTED")

summary = broker.get_portfolio_summary()
kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
kpi1.metric("PORTFOLIO EQUITY", f"${equity:,.2f}", f"${summary.total_realized_pnl_usd:+.2f}")
kpi2.metric("AVAILABLE CASH", f"${broker.cash:,.2f}")
kpi3.metric("WIN RATE", f"{summary.win_rate_pct:.1f}%", f"{summary.win_count}W / {summary.loss_count}L")
kpi4.metric("PROFIT FACTOR", f"{summary.profit_factor:.2f}")
kpi5.metric("ACTIVE REGIME", regime.mode, regime.trend)
kpi6.metric(f"{sel_symbol} PRICE", f"${quote.price:.2f}", f"{quote.change_pct:+.2f}%")

st.divider()

# Main Cockpit Tabs
tab_cockpit, tab_positions, tab_learning, tab_daily_report = st.tabs([
    "📡 Live Cockpit (9 Panels)",
    "💼 Active Positions",
    "🧠 Self-Learning & Mistake Audit",
    "📊 End-of-Day Audit Report"
])

with tab_cockpit:
    col_left, col_mid, col_right = st.columns(3)

    with col_left:
        st.subheader("01 // State & Regime")
        st.progress(min(1.0, metrics["risk"]), text=f"Risk Coefficient: {metrics['risk']:.3f}")
        st.progress(min(1.0, metrics["impact"]), text=f"Market Impact: {metrics['impact']:.3f}")
        st.progress(min(1.0, metrics["slippage"]), text=f"Estimated Slippage: {metrics['slippage']:.3f}")
        st.caption(f"Latency: {metrics['latency']:.1f}ms | Combined Score: {regime.score:.3f}")

        st.subheader("04 // Arbitration Gates")
        st.write(f"• **Approval Status:** `{'APPROVED' if arbitration.approved else 'RESTRICTED'}`")
        st.write(f"• **Drawdown Gate:** `{'✓ PASS' if arbitration.drawdown_ok else '✗ FAIL'}`")
        st.write(f"• **Exposure Gate:** `{'✓ PASS' if arbitration.exposure_ok else '✗ FAIL'}`")

    with col_mid:
        st.subheader("02 // Decision Engine")
        sig_color = "green" if signal == "BUY" else ("red" if signal == "SHORT" else "gray")
        st.markdown(f"### Signal: :{sig_color}[{signal}]")
        st.write(f"• **Confidence:** {abs(federation.federated_score)*100:.0f}%")
        st.write(f"• **Dominant Model:** `{federation.federation}`")
        st.info(f"**Rationale:** {federation.model_details[0].rationale}")

        st.subheader("05 // Anomaly Detector")
        st.write(f"• **Status:** `{'ANOMALY DETECTED' if anomalies.anomaly_detected else 'NOMINAL'}`")
        st.write(f"• **Price Z-Score:** `{anomalies.z_score_price:+.2f}σ` | **Vol Z-Score:** `{anomalies.z_score_vol:+.2f}σ`")

    with col_right:
        st.subheader("03 // Strategy Federation")
        for m in federation.model_details:
            st.write(f"**{m.name}** (Weight: {m.weight*100:.0f}%) → `{m.signal}`")
            st.progress(min(1.0, (m.score + 1.0) / 2.0))

        st.subheader("06 // Risk Quadrant")
        st.success(f"**Quadrant: {quadrant.quadrant}** — {quadrant.description}")

with tab_positions:
    st.subheader(f"Open Positions ({len(broker.positions)})")
    if broker.positions:
        pos_data = [
            {
                "Symbol": p.symbol,
                "Direction": p.direction,
                "Shares": f"{p.shares:.4f}",
                "Entry Price": f"${p.entry_price:.2f}",
                "Current Price": f"${p.current_price:.2f}",
                "Market Value": f"${p.market_value_usd:.2f}",
                "Unrealized P&L": f"${p.unrealized_pnl_usd:+.2f} ({p.unrealized_pnl_pct:+.2f}%)",
                "Stop Loss": f"${p.stop_loss:.2f}",
                "Take Profit": f"${p.take_profit:.2f}"
            }
            for p in broker.positions.values()
        ]
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True)
    else:
        st.info("No active open positions. Scanner is evaluating market opportunities.")

with tab_learning:
    st.subheader("🧠 Adaptive Strategy Re-Calibration")
    st.write("Dynamic weights assigned to strategies based on historical trade outcomes:")
    cols = st.columns(4)
    w = learner.weights
    cols[0].metric("MOMENTUM TREND", f"{w.get('momentum_trend', 0.25)*100:.1f}%")
    cols[1].metric("MEAN REVERSION", f"{w.get('mean_reversion', 0.25)*100:.1f}%")
    cols[2].metric("VOLATILITY BREAKOUT", f"{w.get('volatility_breakout', 0.25)*100:.1f}%")
    cols[3].metric("NEWS SENTIMENT", f"{w.get('news_sentiment', 0.25)*100:.1f}%")

    st.subheader("Mistake Diagnosis & Post-Mortems")
    if learner.mistake_history:
        for m in learner.mistake_history:
            st.error(f"🔴 **[{m.symbol} {m.direction}] -${abs(m.pnl_usd):.2f}:** {m.primary_failure_cause}")
            st.caption(f"↳ **Corrective Adaptation:** {m.adaptation_action}")
    else:
        st.info("No losing trade mistakes recorded yet. All strategies in baseline calibration.")

with tab_daily_report:
    st.subheader("📊 End-of-Day Audit Report")
    report_json = {
        "report_time": datetime.now(timezone.utc).isoformat(),
        "equity": equity,
        "cash": broker.cash,
        "realized_pnl_usd": summary.total_realized_pnl_usd,
        "win_rate_pct": summary.win_rate_pct,
        "total_trades": summary.total_trades,
        "strategy_weights": learner.weights,
        "mistake_history": [m.model_dump() for m in learner.mistake_history],
        "trades": [t.model_dump() for t in broker.trade_ledger]
    }
    
    st.download_button(
        label="💾 Download Session Audit JSON",
        data=json.dumps(report_json, indent=2),
        file_name=f"trading_report_{datetime.now().strftime('%Y-%m-%d')}.json",
        mime="application/json"
    )

    if broker.trade_ledger:
        trades_df = pd.DataFrame([
            {
                "Time": t.exit_time,
                "Symbol": t.symbol,
                "Dir": t.direction,
                "Shares": t.shares,
                "Entry": f"${t.entry_price:.2f}",
                "Exit": f"${t.exit_price:.2f}",
                "P&L ($)": f"${t.realized_pnl_usd:+.2f}",
                "P&L (%)": f"{t.realized_pnl_pct:+.2f}%",
                "Outcome": "WIN" if t.win else "LOSS",
                "Rationale": t.entry_rationale
            }
            for t in broker.trade_ledger
        ])
        st.dataframe(trades_df, use_container_width=True)

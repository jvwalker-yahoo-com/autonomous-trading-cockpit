# Predictive Execution Cockpit // Autonomous Stock Trading System

A real-time, autonomous stock trading engine and operational cockpit built with **FastAPI** and a modern, high-density **Frontend Terminal**.

The system runs autonomously in simulation (paper-trading) mode against real US stock market data (Finnhub API integration with fallback high-fidelity ticks), models fractional share executions matching the eToro UK broker structure, maintains an immutable ledger of every trade action and rationale, and features an **adaptive self-learning feedback loop** that penalizes faulty strategy hypotheses and reinforces winning models.

---

## Key Features

1. **Predictive Execution Cockpit (9-Panel Architecture)**:
   - **01 State**: Telemetry metrics (`model_risk()`, `model_impact()`, `model_slippage()`, `model_latency()`) & Regime state (`OK`, `WARN`, `CRITICAL`).
   - **02 Decision**: Real-time actionable signals (`BUY`, `SHORT`, `HOLD`), fractional share calculations, Stop Loss / Take Profit targets, and AI rationale breakdown.
   - **03 Federation**: Multi-strategy quantitative ensemble (Momentum Trend, Mean Reversion, Volatility Breakout, News Sentiment) with dynamically calibrated weight bars.
   - **04 Arbitration**: Risk gates, maximum portfolio drawdown circuit breaker (15%), exposure limit (75%), and safety overrides.
   - **05 Anomaly Detector**: Real-time spike monitors (Risk > 0.85, Impact > 0.85, Slippage > 0.85, Latency > 20ms) and price/volume Z-score outliers.
   - **06 Quadrant Matrix**: 2x2 Risk vs. Impact operational classifier (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - **07 Positions (Fractional)**: Live table of active Long and Short positions with fractional share sizing, unrealized P&L, SL/TP levels, and manual close triggers.
   - **08 Adaptive Learning**: Self-learning engine that audits closed trades, diagnoses failure causes, and automatically tunes model weights.
   - **09 Event Timeline & Ledger**: Full audit trail of market events, executions, and realized P&L settlements.
   - **Telemetry**: Heartbeat liveness and market clock sync drift monitor.

2. **Market Data & Finnhub Integration**:
   - Real-time quote polling and sentiment analysis for mega-cap US equities & ETFs (`AAPL`, `NVDA`, `MSFT`, `TSLA`, `AMZN`, `GOOGL`, `META`, `SPY`, `QQQ`).
   - High-fidelity offline simulation fallback for continuous 24/7 testing.

3. **eToro UK Fractional Share Model**:
   - Supports purchasing fractional shares by dollar allocation (e.g. \$100 into a \$500 stock = 0.20 shares).
   - Long and Short (CFD) support with spread simulation and automatic stop-loss / take-profit order execution.

4. **1-Click Render Cloud Deployment**:
   - Ready for global web deployment on Render with `render.yaml`.

---

## 10 Core Blueprint Endpoints (REST API)

| Endpoint | Method | Purpose | Response Payload |
|---|---|---|---|
| `/` | GET | Health & Liveness | `{"status": "ok"}` |
| `/state` | GET | Core regime state | `risk`, `impact`, `slippage`, `latency`, `mode`, `trend`, `events` |
| `/decision` | GET | Automation decision | `symbol`, `signal`, `target_shares`, `allocated_usd`, `confidence`, `rationale` |
| `/federation` | GET | Model federation | `outputs`, `weights`, `federation`, `model_details` |
| `/arbitration` | GET | Final arbitration | `main_mode`, `final_mode`, `approved`, `risk_gate_passed`, `reasons` |
| `/anomaly_detector`| GET | Anomaly flags | `risk_spike`, `impact_jump`, `slippage_jump`, `latency_spike`, `z_scores` |
| `/node_events` | GET | Recent events | List of recent trade and regime events |
| `/quadrant` | GET | Risk/Impact quadrant | `quadrant` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `description` |
| `/heartbeat` | GET | Liveness | `alive: true`, `uptime_seconds`, `timestamp` |
| `/sync_drift` | GET | Clock drift | `drift_ms`, `status` (`OK` / `DRIFTING`), `market_open` |

### Additional API Endpoints
- `GET /api/cockpit/snapshot`: Full aggregate snapshot of all 9 panels for smooth UI polling.
- `GET /api/portfolio`: Current cash, equity, open positions, win-rate, and profit factor.
- `GET /api/trades`: Complete trade ledger with entry/exit rationale and mistake analyses.
- `GET /api/learning/stats`: Dynamic strategy weights, mistake history, and adaptation status.
- `POST /api/action/trade`: Execute manual BUY, SHORT, or CLOSE order.
- `POST /api/action/tick`: Step an analytical cycle.
- `POST /api/config`: Update Finnhub API key or parameters.
- `POST /api/portfolio/reset`: Reset simulation account to \$10,000.

---

## Quick Start Guide

### 1. Local Run
```bash
# Clone or navigate to directory
cd auton-trading-cockpit

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m uvicorn backend.server:app --reload --port 8000
```
Open your browser to:
- **Cockpit UI**: `http://localhost:8000/cockpit` or `http://localhost:8000/static/index.html`
- **Interactive API Docs**: `http://localhost:8000/docs`

### 2. Configure Finnhub API Key
1. Click **⚙️ CONFIG** in the top navigation bar of the Cockpit UI.
2. Paste your **Finnhub API Key** and click **Save Config**.
*(Or set `FINNHUB_API_KEY=your_key` in a `.env` file).*

### 3. Deploy to Render (Global Web Access)
1. Push this project to a GitHub repository.
2. In [Render Dashboard](https://dashboard.render.com/):
   - Click **New** > **Blueprint**.
   - Connect your GitHub repository.
   - Render will automatically detect `render.yaml` and deploy your Web Service.
3. Once deployed, open your Render URL (e.g. `https://your-service.onrender.com/cockpit`) to access your trading cockpit from anywhere in the world!

---

## Self-Learning & Adaptation Engine

When a simulated trade closes:
- If the trade **won**: Positive reinforcement rewards the strategies that correctly signaled the trade.
- If the trade **lost**:
  1. The **AdaptiveLearner** diagnoses the root cause (e.g. *counter-trend mean-reversion trap*, *false breakout in high-volatility envelope*, or *sentiment divergence*).
  2. Generates a **Mistake Post-Mortem** recorded into the ledger.
  3. Updates the multi-armed bandit strategy weights $\mathbf{w}$ using policy gradient decay on the faulty model, dynamically shifting portfolio allocation to more robust strategies.
  4. All learned weights and mistake history are persisted to disk in `data/trading_state.json`.

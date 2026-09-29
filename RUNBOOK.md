# Autonomous Stock Trading System: Complete Runbook & Operations Guide

## 1. System Overview & Architecture
The **Autonomous Stock Trading System** is a production-tested algorithmic trading platform and real-time execution cockpit engineered with **FastAPI** (Python 3.11+) and a high-density, cyberpunk-styled **HTML5/JS Cockpit UI**.

### Core Architecture Components
1. **Predictive Execution Cockpit (9 Reactive Panels)**:
   - **01 State Telemetry**: Real-time risk, market impact, slippage estimation, execution latency, and structural trend.
   - **02 Decision Action Engine**: Live model-ensemble recommendations (`BUY`, `SHORT`, `HOLD`), fractional share allocation, dynamic Stop-Loss / Take-Profit calculations, and AI decision rationale.
   - **03 Federation Ensemble**: Multi-model consensus combining **Momentum Trend**, **Mean Reversion**, **Volatility Breakout**, **News Sentiment**, and **Pattern Recognition** (`calc_volume_surge`, `detect_range_breakout`, `detect_double_bottom`, `detect_double_top`, `calc_chip_distribution_density`).
   - **04 Arbitration & Risk Gates**: Portfolio drawdown enforcement, daily loss circuit breaker, exposure caps, and spread filters.
   - **05 Anomaly Detector**: Real-time statistical outlier detection (Z-scores on price velocity and volume spikes).
   - **06 Quadrant Matrix**: Operational execution safety classification (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - **07 Active Positions**: Live order monitoring with fractional share accounting, unrealized P&L tracking, horizon badges (`☀️ DAY` vs `🌙 SWING`), horizon filters, and 1-click `[⚡ FLATTEN DAY TRADES]` and `[🚨 CLOSE ALL TRADES]` controls.
   - **08 Adaptive Learning**: Post-mortem audit engine that inspects losing trades, diagnoses failure causes, and automatically calibrates strategy weights.
   - **09 Event Timeline & Ledger**: Complete audit trail of system events, fills, and realized P&L settlements.
2. **Official eToro REST v2 Execution Engine**:
   - Transmits real-money orders to `https://public-api.etoro.com`.
   - Injects required headers: `x-api-key`, `x-user-key`, dynamic `x-request-id` (UUID v4), and standard User-Agent.
   - Automatic token validation, base64 payload inspection, and 60-second rate-limiting cooldown safeguard against repeated 401s.
3. **Dual-Horizon Trading Engine**:
   - **☀️ Day Trading**: Tight intraday parameters (1.2% SL, 2.4% TP, 4-hour max hold, 35% capital allocation cap across 4 positions max).
   - **🌙 Long-Term Swing Trading**: Longer holding periods operating concurrently on independent rules.
   - **Shielded Holdings**: Manual holdings (`AAPL`, `NVDA`) are permanently immune from automated liquidation or flattening.
   - **Zero Crypto Policy**: Strict 100% exclusion of all cryptocurrency assets across screening, feeds, and execution.

---

## 2. Requirements & Prerequisites
- **Operating System**: Windows 10/11, Linux, or macOS.
- **Python**: Version 3.11+ (Python 3.13 tested and verified).
- **Git**: Installed and configured.
- **eToro Account**: Real or Virtual account with API access from [api-portal.etoro.com](https://api-portal.etoro.com).

---

## 3. Quickstart & Local Execution

### Option A: 1-Click Launch (Windows)
Double-click `start_cockpit.bat` in the project root:
- Automatically verifies Python installation.
- Installs or updates dependencies from `requirements.txt`.
- Launches the server and opens `http://localhost:8000` in your default browser.

### Option B: Manual Command Line
```powershell
# 1. Navigate to project root
cd C:\Antigravity\autonomous-trading-cockpit

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch FastAPI server
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8000 --reload
```

### URLs
- **Cockpit Dashboard**: [http://localhost:8000](http://localhost:8000)
- **Interactive OpenAPI Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 4. eToro API Configuration & Authentication

### Generating API Credentials
1. Log in to [https://api-portal.etoro.com](https://api-portal.etoro.com).
2. Generate your **Public API Key** (`ETORO_API_KEY`).
3. Generate your **User Key JWT Token** (`ETORO_USER_KEY`, starts with `ey...`).
4. Note: eToro JWT user keys expire periodically. When expired, the upstream API returns `HTTP 401 Unauthorized`.

### Configuring the Keys
You can configure keys in three ways:
1. **Via Cockpit UI**:
   - Click **⚙️ CONFIG** in the top navigation bar.
   - Paste your `ETORO_API_KEY` and `ETORO_USER_KEY`.
   - Click **🧪 TEST REST API** to verify authentication.
   - Click **💾 SAVE CONFIG** (persists securely to disk and browser `localStorage`).
2. **Via `.env` file**:
   ```env
   ETORO_API_KEY=your_public_key_here
   ETORO_USER_KEY=eyJhbGciOi...
   ETORO_BASE_URL=https://public-api.etoro.com
   EXECUTION_MODE=live
   ```
3. **Via REST API**:
   ```bash
   curl -X POST http://localhost:8000/api/config \
     -H "Content-Type: application/json" \
     -d '{"etoro_api_key":"...","etoro_user_key":"...","etoro_base_url":"https://public-api.etoro.com"}'
   ```

---

## 5. Day Trading & Intraday Risk Management

### Intraday Safety Rules
- **Daily Loss Circuit Breaker**: If total intraday losses reach **$35.00** (2.5% drawdown on £1,000 / $1,300 capital), all new day trades are halted immediately.
- **Spread Filter**: Rejects day trade entries if the asset's bid-ask spread exceeds **15 basis points (0.15%)**.
- **Max Concurrent Day Trades**: Strictly limited to **4 active positions** (35% capital allocation cap).
- **Position Sizing**: Evaluated using **14-period ATR volatility sizing** ($20–$100 for stocks).

### End-of-Day (EOD) Auto-Flatten Routine
Holding stock CFDs overnight incurs daily rollover interest and overnight gap risk:
- At **19:45 UTC** (15 minutes before US market close at 20:00 UTC / 21:00 UK), the background worker triggers `auto_flatten_day_trades()`.
- Automatically liquidates all open `horizon="day"` positions.
- All swing positions and core holdings (`AAPL`, `NVDA`) are preserved.
- Any day trade open longer than **4.0 hours** is automatically closed if SL or TP hasn't fired.

### Manual Flatten Trigger
- Click **`[⚡ FLATTEN DAY TRADES]`** in Panel 07 to immediately liquidate active day trades on demand.

---

## 6. Cloud Deployment (Render)

### Live Production Deployment
- **Live URL**: [https://autonomous-trading-cockpit.onrender.com](https://autonomous-trading-cockpit.onrender.com)
- **Deployment Manifest**: `render.yaml`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn backend.server:app --host 0.0.0.0 --port $PORT`

### Manual Trigger on Render Dashboard
If automatic deployment is set to manual:
1. Log in to [dashboard.render.com](https://dashboard.render.com).
2. Select `autonomous-trading-cockpit`.
3. Click **Manual Deploy** > **Deploy latest commit**.

### 24/7 Keep-Alive via External Cron Job
Render free/starter web services spin down after 15 minutes of inactivity. To keep the autonomous trading bot running continuously 24/7:
1. Log in to [cron-job.org](https://cron-job.org).
2. Create a new cron job:
   - **URL**: `https://autonomous-trading-cockpit.onrender.com/` (or `/heartbeat`)
   - **Schedule**: Every 5 minutes (`*/5 * * * *`).
   - **Method**: GET.

---

## 7. Verification & Automated Test Suite
To run the automated regression test suite:
```powershell
python -m pytest tests/test_engine.py -v
```
Or double-click `run_tests.bat`.

### Test Coverage (20 Tests)
- Technical Pattern Recognition (Volume Surge, Range Breakouts, Double Bottom 'W', Double Top 'M', Chip Distribution).
- Day Trading Horizon Tagging & EOD Auto-Flattening.
- Daily Loss Circuit Breaker ($35.00 limit) and Spread Filter Arbitration.
- Day Trading REST API Endpoints (`/api/day_trading/*`).
- Multi-Model Federation Consensus.
- Fractional Share Math and eToro CFD Order Translation.
- Circuit Breaker Latching and Manual Unlatching.
- Adaptive Learning Weight Adaptation and Mistake Auditing.

---

## 8. Antigravity Project Organization
In the **Google Antigravity** environment, this project is cataloged as:
- **Project Name**: `Autonomous Stock Trading System`
- **Project UUID**: `99384721-55c3-48e2-aa01-f4b24d83610c`
- **Workspace URI**: `file:///c:/Antigravity/autonomous-trading-cockpit`
- **Linked Historical Conversations**:
  1. `ce28921d-4460-4ffa-8906-cd5e6d151810` (Primary 7,500+ step session: Full Cockpit & Day Trading Engine)
  2. `16d99905-bff4-4106-ac4a-122a5987c4e9` (eToro Account Balance & Spending Limits)
  3. `f558fcbd-438f-492f-9bee-c139336ced66` (Automated Trading Log Diagnostics)
  4. `b3e7648c-cb84-449e-b0fe-42af72a57334` (Mobile eToro Key Reauthorisation APK)

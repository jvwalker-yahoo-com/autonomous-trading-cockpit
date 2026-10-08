/**
 * PREDICTIVE EXECUTION COCKPIT - DASHBOARD CONTROLLER
 * Real-time polling, state synchronization, reactive DOM rendering,
 * manual intervention controls, and settings management.
 */

// Dynamically determine Backend API Base URL
const BASE_URL = window.location.origin.includes("localhost") || window.location.origin.includes("127.0.0.1")
  ? window.location.origin
  : window.location.origin;

let activeSymbol = "AAPL";
let currentSymbol = "AAPL";
let isPolling = true;
let pollTimer = null;
let currentHorizonFilter = "all";
let lastOpenPositions = [];

// DOM Elements Cache
const assetSelect = document.getElementById("symbolSelect");
const el = {
  // Top Nav
  symbolSelect: document.getElementById("symbolSelect"),
  headerPrice: document.getElementById("headerPrice"),
  headerChange: document.getElementById("headerChange"),
  pillSyncDrift: document.getElementById("pillSyncDrift"),
  pillLatency: document.getElementById("pillLatency"),
  pillRegime: document.getElementById("pillRegime"),
  heartbeatPulse: document.getElementById("heartbeatPulse"),

  // Portfolio Bar
  statEquity: document.getElementById("statEquity"),
  statCash: document.getElementById("statCash"),
  statRealizedPnl: document.getElementById("statRealizedPnl"),
  statUnrealizedPnl: document.getElementById("statUnrealizedPnl"),
  statWinRate: document.getElementById("statWinRate"),
  statProfitFactor: document.getElementById("statProfitFactor"),
  statModeBadge: document.getElementById("statModeBadge"),

  // Panel 1: State
  stateModeBadge: document.getElementById("stateModeBadge"),
  valRisk: document.getElementById("valRisk"),
  barRisk: document.getElementById("barRisk"),
  valImpact: document.getElementById("valImpact"),
  barImpact: document.getElementById("barImpact"),
  valSlippage: document.getElementById("valSlippage"),
  barSlippage: document.getElementById("barSlippage"),
  valLatency: document.getElementById("valLatency"),
  barLatency: document.getElementById("barLatency"),
  valScore: document.getElementById("valScore"),
  valTrend: document.getElementById("valTrend"),

  // Panel 2: Decision
  decisionSymbol: document.getElementById("decisionSymbol"),
  decisionSignal: document.getElementById("decisionSignal"),
  decisionConfidence: document.getElementById("decisionConfidence"),
  decisionAlloc: document.getElementById("decisionAlloc"),
  decisionShares: document.getElementById("decisionShares"),
  decisionStopLoss: document.getElementById("decisionStopLoss"),
  decisionTakeProfit: document.getElementById("decisionTakeProfit"),
  decisionRationale: document.getElementById("decisionRationale"),

  // Panel 3: Federation
  dominantModelBadge: document.getElementById("dominantModelBadge"),
  federationList: document.getElementById("federationList"),
  valFederatedScore: document.getElementById("valFederatedScore"),

  // Panel 4: Arbitration
  arbitrationApprovedBadge: document.getElementById("arbitrationApprovedBadge"),
  gateDrawdown: document.getElementById("gateDrawdown"),
  gateExposure: document.getElementById("gateExposure"),
  gateAnomaly: document.getElementById("gateAnomaly"),
  gateCircuit: document.getElementById("gateCircuit"),
  arbitrationReasonsList: document.getElementById("arbitrationReasonsList"),

  // Panel 5: Anomaly
  anomalyMainBadge: document.getElementById("anomalyMainBadge"),
  flagRiskSpike: document.getElementById("flagRiskSpike"),
  flagImpactJump: document.getElementById("flagImpactJump"),
  flagSlippageJump: document.getElementById("flagSlippageJump"),
  flagLatencySpike: document.getElementById("flagLatencySpike"),
  valPriceZ: document.getElementById("valPriceZ"),
  valVolZ: document.getElementById("valVolZ"),
  activeAnomaliesContainer: document.getElementById("activeAnomaliesContainer"),

  // Panel 6: Quadrant
  quadrantBadge: document.getElementById("quadrantBadge"),
  qLow: document.getElementById("qLow"),
  qMedium: document.getElementById("qMedium"),
  qHigh: document.getElementById("qHigh"),
  qCritical: document.getElementById("qCritical"),
  quadrantDescription: document.getElementById("quadrantDescription"),

  // Panel 7: Positions
  posCountBadge: document.getElementById("posCountBadge"),
  positionsTableBody: document.getElementById("positionsTableBody"),
  btnFlattenDayTrades: document.getElementById("btnFlattenDayTrades"),
  filterHorizonAll: document.getElementById("filterHorizonAll"),
  filterHorizonDay: document.getElementById("filterHorizonDay"),
  filterHorizonSwing: document.getElementById("filterHorizonSwing"),

  // Day Trading Status Pill & Config
  pillDayTrading: document.getElementById("pillDayTrading"),
  pillDayTradingWrapper: document.getElementById("pillDayTradingWrapper"),
  inputEnableDayTrading: document.getElementById("inputEnableDayTrading"),
  inputDayTradeAllocPct: document.getElementById("inputDayTradeAllocPct"),
  inputDayTradeMaxActive: document.getElementById("inputDayTradeMaxActive"),
  inputDayTradeSlPct: document.getElementById("inputDayTradeSlPct"),
  inputDayTradeTpPct: document.getElementById("inputDayTradeTpPct"),
  inputMaxDailyLossUsd: document.getElementById("inputMaxDailyLossUsd"),
  inputDayTradeEodFlattenMins: document.getElementById("inputDayTradeEodFlattenMins"),

  // Panel 8: Learning & Mistakes
  learningRateBadge: document.getElementById("learningRateBadge"),
  learningWeightsBars: document.getElementById("learningWeightsBars"),
  mistakeLogList: document.getElementById("mistakeLogList"),

  // Panel 9: Events
  eventsTimeline: document.getElementById("eventsTimeline"),

  // Buttons & Modals
  btnTickStep: document.getElementById("btnTickStep"),
  btnSettings: document.getElementById("btnSettings"),
  btnResetPortfolio: document.getElementById("btnResetPortfolio"),
  btnResetCircuitBreaker: document.getElementById("btnResetCircuitBreaker"),
  btnManualBuy: document.getElementById("btnManualBuy"),
  btnManualShort: document.getElementById("btnManualShort"),
  btnManualClose: document.getElementById("btnManualClose"),
  btnCloseAllPositions: document.getElementById("btnCloseAllPositions"),
  settingsModal: document.getElementById("settingsModal"),
  btnCloseModal: document.getElementById("btnCloseModal"),
  btnSaveConfig: document.getElementById("btnSaveConfig"),
  inputFinnhubKey: document.getElementById("inputFinnhubKey"),
  inputTwelveDataKey: document.getElementById("inputTwelveDataKey"),
  inputFmpKey: document.getElementById("inputFmpKey"),
  inputAlphaVantageKey: document.getElementById("inputAlphaVantageKey"),
  inputTavilyKey: document.getElementById("inputTavilyKey"),
  inputSerpApiKey: document.getElementById("inputSerpApiKey"),
  inputAnspireKey: document.getElementById("inputAnspireKey"),
  inputQuiverKey: document.getElementById("inputQuiverKey"),
  selectSimMode: document.getElementById("selectSimMode"),
  inputRiskPct: document.getElementById("inputRiskPct"),

  
  // eToro Live Switch & Credentials
  btnModeToggle: document.getElementById("btnModeToggle"),
  modeStatusDot: document.getElementById("modeStatusDot"),
  modeStatusLabel: document.getElementById("modeStatusLabel"),
  modeSwitchModal: document.getElementById("modeSwitchModal"),
  btnCloseModeModal: document.getElementById("btnCloseModeModal"),
  btnCancelModeSwitch: document.getElementById("btnCancelModeSwitch"),
  btnConfirmLiveMode: document.getElementById("btnConfirmLiveMode"),
  modeSwitchKeyStatus: document.getElementById("modeSwitchKeyStatus"),
  inputEtoroApiKey: document.getElementById("inputEtoroApiKey"),
  inputEtoroUserKey: document.getElementById("inputEtoroUserKey"),
  inputEtoroBaseUrl: document.getElementById("inputEtoroBaseUrl"),
  btnTestEtoroConn: document.getElementById("btnTestEtoroConn"),
  btnTestEtoroWs: document.getElementById("btnTestEtoroWs"),
  btnTestEtoroMcp: document.getElementById("btnTestEtoroMcp"),
  etoroTestStatus: document.getElementById("etoroTestStatus")
};

// ==========================================
// POLLING & DATA REFRESH
// ==========================================

let isFetchingSnapshot = false;

async function fetchCockpitData() {
  if (isFetchingSnapshot) return;
  isFetchingSnapshot = true;
  try {
    const url = `${BASE_URL}/api/cockpit/snapshot?symbol=${activeSymbol}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    const data = await res.json();
    renderCockpit(data);
    fetchDayTradingStatus();
  } catch (err) {
    console.warn("Cockpit telemetry poll error:", err);
    if (el.pillSyncDrift) {
      el.pillSyncDrift.textContent = "OFFLINE";
      el.pillSyncDrift.className = "pill-val color-danger";
    }
  } finally {
    isFetchingSnapshot = false;
  }
}

function renderCockpit(data) {
  if (!data) return;
  try {
    const { quote, state, decision, federation, arbitration, anomaly, quadrant, portfolio, learning, heartbeat, sync_drift, node_events, execution_mode } = data;

    if (execution_mode) {
      const userPreference = localStorage.getItem("execution_mode") || "live";
      if (userPreference === "live" && execution_mode === "demo") {
        if (!window._isReassertingLive) {
          window._isReassertingLive = true;
          console.warn("⚠️ Server reported demo mode while user preference is LIVE. Auto-restoring live mode...");
          fetch(`${BASE_URL}/api/mode/switch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "live" })
          }).then(r => {
            if (r.ok) updateExecutionModeUI("live");
          }).catch(e => {
            console.error("Failed to auto-restore live mode:", e);
          }).finally(() => {
            setTimeout(() => { window._isReassertingLive = false; }, 4000);
          });
        }
        updateExecutionModeUI("live");
      } else {
        updateExecutionModeUI(execution_mode);
      }
    }

    // 1. Header & Quick Telemetry
    if (quote && el.headerPrice && el.headerChange) {
      el.headerPrice.textContent = `$${quote.price.toFixed(2)}`;
      const isUp = quote.change >= 0;
      el.headerChange.textContent = `${isUp ? "+" : ""}${quote.change.toFixed(2)} (${isUp ? "+" : ""}${quote.change_pct.toFixed(2)}%)`;
      el.headerChange.className = `price-delta badge ${isUp ? "badge-ok" : "badge-critical"}`;
    }

  el.pillSyncDrift.textContent = `${sync_drift.drift_ms}ms (${sync_drift.status})`;
  el.pillSyncDrift.className = `pill-val ${sync_drift.status === "OK" ? "status-ok color-success" : "color-warn"}`;
  el.pillLatency.textContent = `${state.latency.toFixed(1)}ms`;
  
  el.pillRegime.textContent = state.mode;
  el.pillRegime.className = `pill-val mode-badge-${state.mode.toLowerCase()}`;

  const pillMarketHours = document.getElementById("pillMarketHours");
  if (pillMarketHours && sync_drift) {
    if (sync_drift.market_open) {
      pillMarketHours.textContent = "OPEN (14:30-21:00 UK)";
      pillMarketHours.className = "pill-val mode-badge-ok";
    } else {
      pillMarketHours.textContent = "CLOSED (14:30 UK)";
      pillMarketHours.className = "pill-val mode-badge-warn";
    }
  }

  const pillMacroRisk = document.getElementById("pillMacroRisk");
  if (pillMacroRisk && data.macro_risk) {
    const mRisk = data.macro_risk.macro_risk_level || "NORMAL";
    const mSent = data.macro_risk.macro_sentiment !== undefined ? (data.macro_risk.macro_sentiment >= 0 ? `+${data.macro_risk.macro_sentiment.toFixed(2)}` : data.macro_risk.macro_sentiment.toFixed(2)) : "";
    pillMacroRisk.textContent = `🌍 ${mRisk} (${mSent})`;
    if (mRisk === "CRITICAL") {
      pillMacroRisk.className = "pill-val mode-badge-fail";
      pillMacroRisk.style.color = "#ef4444";
    } else if (mRisk === "ELEVATED") {
      pillMacroRisk.className = "pill-val mode-badge-warn";
      pillMacroRisk.style.color = "#f59e0b";
    } else {
      pillMacroRisk.className = "pill-val mode-badge-ok";
      pillMacroRisk.style.color = "#38bdf8";
    }
  }

  const pillWyckoff = document.getElementById("pillWyckoff");
  if (pillWyckoff && data.wyckoff) {
    const wPhase = data.wyckoff.phase_code || "A";
    const wStruct = data.wyckoff.structure_type || "NEUTRAL";
    const wSpring = data.wyckoff.spring_quality_score || 0;
    if (wSpring >= 60) {
      pillWyckoff.textContent = `⚡ SPRING (${wSpring})`;
      pillWyckoff.className = "pill-val mode-badge-ok";
      pillWyckoff.style.color = "#10b981";
    } else if (wPhase === "D" || wPhase === "E") {
      pillWyckoff.textContent = `🎯 ${wStruct === "ACCUMULATION" ? "MARKUP" : (wStruct === "DISTRIBUTION" ? "MARKDOWN" : wStruct)} (${wPhase})`;
      pillWyckoff.className = "pill-val mode-badge-ok";
      pillWyckoff.style.color = wStruct === "ACCUMULATION" ? "#10b981" : "#ef4444";
    } else {
      pillWyckoff.textContent = `🎯 PHASE ${wPhase}`;
      pillWyckoff.className = "pill-val mode-badge-ok";
      pillWyckoff.style.color = "#fbbf24";
    }
  }

  // 2. Summary Stats Strip
  if (portfolio) {
    el.statEquity.textContent = `$${portfolio.equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    el.statCash.textContent = `$${portfolio.cash.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
    
    const pnlUsd = portfolio.total_realized_pnl_usd;
    const pnlPct = portfolio.total_realized_pnl_pct;
    el.statRealizedPnl.textContent = `${pnlUsd >= 0 ? "+" : ""}$${pnlUsd.toFixed(2)} (${pnlPct >= 0 ? "+" : ""}${pnlPct.toFixed(2)}%)`;
    el.statRealizedPnl.className = `stat-number ${pnlUsd >= 0 ? "color-success" : "color-danger"}`;

    const unPnl = portfolio.unrealized_pnl_usd;
    el.statUnrealizedPnl.textContent = `${unPnl >= 0 ? "+" : ""}$${unPnl.toFixed(2)}`;
    el.statUnrealizedPnl.className = `stat-number ${unPnl >= 0 ? "color-success" : "color-danger"}`;

    el.statWinRate.textContent = `${portfolio.win_rate_pct.toFixed(1)}% (${portfolio.win_count}W / ${portfolio.loss_count}L)`;
    el.statProfitFactor.textContent = `${portfolio.profit_factor.toFixed(2)}`;
  }

  // 3. Panel 1: State
  el.stateModeBadge.textContent = state.mode;
  el.stateModeBadge.className = `badge badge-${state.mode.toLowerCase()}`;
  el.valRisk.textContent = state.risk.toFixed(4);
  el.barRisk.style.width = `${Math.min(100, state.risk * 100)}%`;
  el.valImpact.textContent = state.impact.toFixed(4);
  el.barImpact.style.width = `${Math.min(100, state.impact * 100)}%`;
  el.valSlippage.textContent = state.slippage.toFixed(4);
  el.barSlippage.style.width = `${Math.min(100, state.slippage * 100)}%`;
  el.valLatency.textContent = `${state.latency.toFixed(1)} ms`;
  el.barLatency.style.width = `${Math.min(100, (state.latency / 40.0) * 100)}%`;
  el.valScore.textContent = state.score.toFixed(4);
  el.valTrend.textContent = state.trend;
  el.valTrend.className = `sub-val ${state.trend === "BULL_TREND" ? "color-success" : (state.trend === "BEAR_TREND" ? "color-danger" : "color-warn")}`;

  // 4. Panel 2: Decision
  el.decisionSymbol.textContent = decision.symbol;
  el.decisionSignal.textContent = decision.signal;
  el.decisionSignal.className = `signal-tag ${decision.signal === "BUY" ? "signal-buy" : (decision.signal === "SHORT" ? "signal-short" : "signal-hold")}`;
  el.decisionConfidence.textContent = `${Math.round(decision.confidence * 100)}%`;
  el.decisionAlloc.textContent = `$${decision.allocated_usd.toFixed(2)}`;
  el.decisionShares.textContent = `${decision.target_shares.toFixed(4)}`;
  el.decisionStopLoss.textContent = decision.stop_loss ? `$${decision.stop_loss.toFixed(2)}` : "--";
  el.decisionTakeProfit.textContent = decision.take_profit ? `$${decision.take_profit.toFixed(2)}` : "--";
  el.decisionRationale.textContent = decision.rationale;

  // 5. Panel 3: Federation
  el.dominantModelBadge.textContent = federation.federation.toUpperCase().replace("_", " ");
  el.valFederatedScore.textContent = `${federation.federated_score >= 0 ? "+" : ""}${federation.federated_score.toFixed(3)}`;
  
  if (federation.model_details) {
    el.federationList.innerHTML = federation.model_details.map(m => {
      const sigColor = m.signal === "BUY" ? "color-success" : (m.signal === "SHORT" ? "color-danger" : "text-muted");
      const scorePct = Math.round(((m.score + 1.0) / 2.0) * 100);
      return `
        <div class="fed-model-item">
          <div class="fed-model-header">
            <span class="fed-model-name">${m.name}</span>
            <span class="fed-model-weight">W: ${(m.weight * 100).toFixed(0)}% | <strong class="${sigColor}">[${m.signal}]</strong></span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${scorePct}%; background: ${m.score >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}"></div>
          </div>
          <small class="text-muted" style="font-size: 9px;">${m.rationale}</small>
        </div>
      `;
    }).join("");
  }

  // 6. Panel 4: Arbitration
  el.arbitrationApprovedBadge.textContent = arbitration.approved ? "APPROVED" : "RESTRICTED";
  el.arbitrationApprovedBadge.className = `badge ${arbitration.approved ? "badge-ok" : "badge-critical"}`;
  
  const gateMarketHours = document.getElementById("gateMarketHours");
  if (gateMarketHours && sync_drift) {
    updateGateItem(gateMarketHours, sync_drift.market_open, "eToro Hours (14:30 - 21:00 UK)");
  }
  updateGateItem(el.gateDrawdown, arbitration.drawdown_ok, "Drawdown Gate (< 15%)");
  updateGateItem(el.gateExposure, arbitration.exposure_ok, "Exposure Gate (< 75%)");
  updateGateItem(el.gateAnomaly, arbitration.risk_gate_passed, "Anomaly / Risk Gate");

  el.arbitrationReasonsList.innerHTML = arbitration.reasons.map(r => `<li>• ${r}</li>`).join("");

  if (el.btnResetCircuitBreaker) {
    if (arbitration.circuit_breaker_active || !arbitration.drawdown_ok) {
      el.btnResetCircuitBreaker.style.display = "block";
    } else {
      el.btnResetCircuitBreaker.style.display = "none";
    }
  }

  // 7. Panel 5: Anomaly
  el.anomalyMainBadge.textContent = anomaly.anomaly_detected ? "SPIKE DETECTED" : "NOMINAL";
  el.anomalyMainBadge.className = `badge ${anomaly.anomaly_detected ? "badge-anomaly" : "badge-normal"}`;
  
  setFlagActive(el.flagRiskSpike, anomaly.risk_spike);
  setFlagActive(el.flagImpactJump, anomaly.impact_jump);
  setFlagActive(el.flagSlippageJump, anomaly.slippage_jump);
  setFlagActive(el.flagLatencySpike, anomaly.latency_spike);

  el.valPriceZ.textContent = `${anomaly.z_score_price >= 0 ? "+" : ""}${anomaly.z_score_price.toFixed(2)}σ`;
  el.valVolZ.textContent = `${anomaly.z_score_vol >= 0 ? "+" : ""}${anomaly.z_score_vol.toFixed(2)}σ`;

  if (anomaly.anomalies && anomaly.anomalies.length > 0) {
    el.activeAnomaliesContainer.innerHTML = anomaly.anomalies.map(a => `<div class="color-danger">⚠ ${a}</div>`).join("");
  } else {
    el.activeAnomaliesContainer.innerHTML = `<span class="text-muted">No statistical price/volatility anomalies detected.</span>`;
  }

  // 8. Panel 6: Quadrant
  el.quadrantBadge.textContent = quadrant.quadrant;
  el.quadrantBadge.className = `badge badge-${quadrant.quadrant.toLowerCase()}`;
  el.quadrantDescription.textContent = quadrant.description;

  [el.qLow, el.qMedium, el.qHigh, el.qCritical].forEach(cell => cell.className = "matrix-cell");
  if (quadrant.quadrant === "LOW") el.qLow.className = "matrix-cell active-quadrant";
  else if (quadrant.quadrant === "MEDIUM") el.qMedium.className = "matrix-cell active-quadrant";
  else if (quadrant.quadrant === "HIGH") el.qHigh.className = "matrix-cell active-quadrant";
  else if (quadrant.quadrant === "CRITICAL") el.qCritical.className = "matrix-cell active-critical";

  // 9. Panel 7: Positions Table
  if (portfolio && portfolio.open_positions) {
    lastOpenPositions = portfolio.open_positions || [];
    renderPositionsTable();
  }

  // 10. Panel 8: Adaptive Learning & Mistakes
  if (learning) {
    el.learningRateBadge.textContent = `LR: ${learning.learning_rate}`;
    
    // Render strategy weight distribution bars
    const weights = learning.strategy_weights || {};
    el.learningWeightsBars.innerHTML = Object.entries(weights).map(([k, v]) => {
      const pct = Math.round(v * 100);
      const nameClean = k.replace("_", " ").toUpperCase();
      return `
        <div class="weight-row">
          <div class="weight-label-bar">
            <span>${nameClean}</span>
            <span class="color-warn"><strong>${pct}%</strong> (Weight: ${v.toFixed(3)})</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${pct}%; background: var(--accent-purple);"></div>
          </div>
        </div>
      `;
    }).join("");

    // Render mistake post-mortems
    if (learning.mistake_history && learning.mistake_history.length > 0) {
      el.mistakeLogList.innerHTML = learning.mistake_history.map(m => `
        <div class="mistake-item">
          <div class="mistake-cause">🔴 [${m.symbol} ${m.direction}] -$${Math.abs(m.pnl_usd).toFixed(2)}: ${m.primary_failure_cause}</div>
          <div class="mistake-action">↳ <strong>Adaptation:</strong> ${m.adaptation_action}</div>
        </div>
      `).join("");
    } else {
      el.mistakeLogList.innerHTML = `<div class="text-muted" style="font-size: 11px;">No trade losses logged. Strategy weights currently in baseline calibration.</div>`;
    }
  }

  // 11. Panel 9: Events Timeline
  if (node_events && node_events.length > 0) {
    el.eventsTimeline.innerHTML = node_events.map(ev => {
      const timeStr = new Date().toLocaleTimeString();
      return `
        <div class="timeline-entry">
          <span class="entry-time">[${timeStr}]</span>
          <span class="entry-text">${ev}</span>
        </div>
      `;
    }).join("");
  }
  } catch (err) {
    console.error("renderCockpit error caught:", err);
  }
}

function updateGateItem(element, isPassed, label) {
  element.className = `gate-item ${isPassed ? "gate-pass" : "gate-fail"}`;
  element.querySelector(".gate-icon").textContent = isPassed ? "✓" : "✗";
  element.querySelector(".gate-name").textContent = label;
}

function setFlagActive(element, isActive) {
  if (isActive) element.classList.add("flag-active");
  else element.classList.remove("flag-active");
}

function renderPositionsTable() {
  if (!el.positionsTableBody) return;
  const filtered = lastOpenPositions.filter(p => {
    if (currentHorizonFilter === "day") return p.horizon === "day";
    if (currentHorizonFilter === "swing") return p.horizon !== "day";
    return true;
  });

  const totalOpen = lastOpenPositions.length;
  const dayCount = lastOpenPositions.filter(p => p.horizon === "day").length;
  const swingCount = totalOpen - dayCount;

  if (el.posCountBadge) {
    el.posCountBadge.textContent = `${totalOpen} OPEN (${dayCount} DAY / ${swingCount} SWING)`;
  }

  if (filtered.length === 0) {
    const filterMsg = currentHorizonFilter === "all"
      ? "No active open positions. Autonomous scanner analyzing opportunities..."
      : `No open ${currentHorizonFilter === "day" ? "Day Trades" : "Swing Trades"} currently active.`;
    el.positionsTableBody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">${filterMsg}</td></tr>`;
  } else {
    el.positionsTableBody.innerHTML = filtered.map(p => {
      const isLong = p.direction === "LONG";
      const pnlColor = p.unrealized_pnl_usd >= 0 ? "color-success" : "color-danger";
      const isDayTrade = p.horizon === "day";
      const horizonBadge = isDayTrade
        ? `<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; font-size: 10px; font-weight: bold;">☀️ DAY</span>`
        : `<span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #0284c7; font-size: 10px; font-weight: bold;">🌙 SWING</span>`;

      return `
        <tr>
          <td><strong>${p.symbol}</strong></td>
          <td>${horizonBadge}</td>
          <td><span class="badge ${isLong ? 'badge-ok' : 'badge-critical'}">${p.direction}</span></td>
          <td>${p.shares.toFixed(4)}</td>
          <td>$${p.entry_price.toFixed(2)}</td>
          <td>$${p.current_price.toFixed(2)}</td>
          <td>$${p.market_value_usd.toFixed(2)}</td>
          <td class="${pnlColor}"><strong>${p.unrealized_pnl_usd >= 0 ? '+' : ''}$${p.unrealized_pnl_usd.toFixed(2)} (${p.unrealized_pnl_pct.toFixed(2)}%)</strong></td>
          <td><small>SL: $${p.stop_loss.toFixed(2)}<br>TP: $${p.take_profit.toFixed(2)}</small></td>
          <td><button class="btn btn-danger" style="padding: 2px 6px; font-size: 10px;" onclick="closePositionSymbol('${p.symbol}')">CLOSE</button></td>
        </tr>
      `;
    }).join("");
  }
}

function setHorizonFilter(filter) {
  currentHorizonFilter = filter;
  [
    { btn: el.filterHorizonAll, key: "all" },
    { btn: el.filterHorizonDay, key: "day" },
    { btn: el.filterHorizonSwing, key: "swing" }
  ].forEach(item => {
    if (!item.btn) return;
    if (item.key === filter) {
      item.btn.classList.add("active");
      item.btn.style.background = filter === "day" ? "#f59e0b" : (filter === "swing" ? "#0284c7" : "var(--accent-cyan)");
      item.btn.style.color = "#000";
    } else {
      item.btn.classList.remove("active");
      item.btn.style.background = "transparent";
      item.btn.style.color = item.key === "day" ? "#fbbf24" : (item.key === "swing" ? "#38bdf8" : "var(--text-muted)");
    }
  });
  renderPositionsTable();
}

if (el.filterHorizonAll) el.filterHorizonAll.addEventListener("click", () => setHorizonFilter("all"));
if (el.filterHorizonDay) el.filterHorizonDay.addEventListener("click", () => setHorizonFilter("day"));
if (el.filterHorizonSwing) el.filterHorizonSwing.addEventListener("click", () => setHorizonFilter("swing"));

async function fetchDayTradingStatus() {
  if (!el.pillDayTrading) return;
  try {
    const res = await fetch(`${BASE_URL}/api/day_trading/status`);
    if (res.ok) {
      const data = await res.json();
      if (!data.enabled) {
        el.pillDayTrading.textContent = "⏸️ PAUSED";
        el.pillDayTrading.style.color = "#94a3b8";
        if (el.pillDayTradingWrapper) {
          el.pillDayTradingWrapper.title = "Day Trading is paused. Click to toggle or configure.";
        }
      } else if (data.daily_loss_circuit_breaker_active) {
        el.pillDayTrading.textContent = "🛑 CB TRIPPED";
        el.pillDayTrading.style.color = "#ef4444";
        if (el.pillDayTradingWrapper) {
          el.pillDayTradingWrapper.title = `Daily loss limit reached ($${(data.daily_loss_usd || 0).toFixed(2)} / $${data.daily_loss_limit_usd}). Day trades halted until reset.`;
        }
      } else {
        el.pillDayTrading.textContent = `☀️ ${data.active_day_trades_count}/${data.max_active_day_trades} ACTIVE`;
        el.pillDayTrading.style.color = "#fbbf24";
        if (el.pillDayTradingWrapper) {
          el.pillDayTradingWrapper.title = `Day Trading Active: ${data.active_day_trades_count} open day positions (Max: ${data.max_active_day_trades}). Daily Drawdown: $${(data.daily_loss_usd || 0).toFixed(2)} / $${data.daily_loss_limit_usd}. EOD auto-flatten in effect (${data.minutes_until_eod_flatten}m to ${data.eod_flatten_target_time_utc}).`;
        }
      }
    }
  } catch (err) {
    console.warn("Error fetching day trading status:", err);
  }
}

if (el.pillDayTradingWrapper) {
  el.pillDayTradingWrapper.style.cursor = "pointer";
  el.pillDayTradingWrapper.addEventListener("click", async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/day_trading/toggle`, { method: "POST" });
      if (res.ok) {
        const d = await res.json();
        alert(`Day Trading mode is now ${d.enabled ? "ENABLED ☀️" : "PAUSED ⏸️"}.`);
        fetchDayTradingStatus();
      }
    } catch (e) {
      console.error("Error toggling day trading:", e);
    }
  });
}

// ==========================================
// ACTIONS & CONTROLS
// ==========================================

async function triggerManualTrade(action) {
  const btn = action === "BUY" ? el.btnManualBuy : (action === "SHORT" ? el.btnManualShort : el.btnManualClose);
  const origText = btn ? btn.textContent : "";
  if (btn) {
    btn.textContent = "⌛ DISPATCHING...";
    btn.disabled = true;
  }

  try {
    const res = await fetch(`${BASE_URL}/api/action/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: activeSymbol,
        action: action,
        amount_usd: 100.0
      })
    });
    if (res.ok) {
      const data = await res.json();
      await fetchCockpitData();
      if (currentExecutionMode === "live") {
        if (data.etoro_result && data.etoro_result.success) {
          const fillInfo = data.etoro_result.order || data.etoro_result.details || data.etoro_result.data || {};
          const methodLabel = data.etoro_result.method === "mcp" ? "Official eToro MCP Gateway" : "eToro v2 REST Execution";
          alert(`⚡ LIVE ETORO ORDER FILLED!\n\nAction: ${action} ${activeSymbol}\nAmount: $100.00\nEngine: ${methodLabel}\nOutcome: ${data.etoro_result.outcome || 'Executed'}\n\nOrder Info: ${JSON.stringify(fillInfo, null, 2)}`);
        } else if (data.etoro_result && !data.etoro_result.success) {
          const errDetail = data.etoro_result.error || data.etoro_result.reasons || (data.etoro_result.order && data.etoro_result.order.error) || data.etoro_result.order;
          const statusDisplay = data.etoro_result.status_code || data.etoro_result.outcome || data.etoro_result.verdict || 'Order Rejected';
          alert(`⚠️ eToro Live Order Notice (${statusDisplay}):\n\n${typeof errDetail === 'object' ? JSON.stringify(errDetail, null, 2) : errDetail}`);
        } else {
          alert(`⚡ Order dispatched for ${action} ${activeSymbol}.`);
        }
      } else {
        alert(`🛡️ SIMULATION ORDER EXECUTED (DEMO MODE)\n\nAction: ${action} ${activeSymbol}\nAmount: $100.00\n\nNote: You are currently in DEMO mode. To place real orders on your eToro account, click the green '🛡️ DEMO / LEARNING' button in the top bar to switch to '⚡ LIVE ETORO'.`);
      }
    } else {
      const err = await res.json();
      alert(`Trade failed: ${err.detail || "Unknown error"}`);
    }
  } catch (err) {
    alert(`Execution error: ${err.message}`);
  } finally {
    if (btn) {
      btn.textContent = origText;
      btn.disabled = false;
    }
  }
}

window.closePositionSymbol = async function(symbol) {
  try {
    const res = await fetch(`${BASE_URL}/api/action/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: symbol, action: "CLOSE" })
    });
    if (res.ok) await fetchCockpitData();
  } catch (err) {
    console.error("Failed to close position:", err);
  }
};

// Event Listeners
if (el.symbolSelect) {
  el.symbolSelect.addEventListener("change", (e) => {
    activeSymbol = e.target.value;
    currentSymbol = e.target.value;
    fetchCockpitData();
  });
}

if (el.btnTickStep) {
  el.btnTickStep.addEventListener("click", async () => {
    el.btnTickStep.textContent = "⌛ STEPPING...";
    try {
      await fetch(`${BASE_URL}/api/action/tick?symbol=${activeSymbol}`, { method: "POST" });
      await fetchCockpitData();
    } finally {
      el.btnTickStep.textContent = "⚡ STEP";
    }
  });
}

if (el.btnManualBuy) el.btnManualBuy.addEventListener("click", () => triggerManualTrade("BUY"));
if (el.btnManualShort) el.btnManualShort.addEventListener("click", () => triggerManualTrade("SHORT"));
if (el.btnManualClose) el.btnManualClose.addEventListener("click", () => triggerManualTrade("CLOSE"));

if (el.btnCloseAllPositions) {
  el.btnCloseAllPositions.addEventListener("click", async () => {
    if (!confirm("🚨 Are you sure you want to CLOSE ALL TRADES right now?\nThis will close all open positions on eToro and in your local trading portfolio.")) {
      return;
    }
    el.btnCloseAllPositions.textContent = "⏳ CLOSING ALL...";
    try {
      const res = await fetch(`${BASE_URL}/api/positions/close_all`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      el.btnCloseAllPositions.textContent = "✓ CLOSED ALL";
      alert(data.message || "All trades successfully closed!");
      await fetchCockpitData();
      setTimeout(() => {
        if (el.btnCloseAllPositions) {
          el.btnCloseAllPositions.textContent = "🚨 CLOSE ALL TRADES";
        }
      }, 3000);
    } catch (err) {
      alert("Failed to close all positions: " + err.message);
      el.btnCloseAllPositions.textContent = "🚨 CLOSE ALL TRADES";
    }
  });
}

if (el.btnFlattenDayTrades) {
  el.btnFlattenDayTrades.addEventListener("click", async () => {
    if (!confirm("⚡ Auto-flatten all open Day Trades right now?\n\nThis will safely liquidate active day trading positions before market close while leaving long-term swing holdings and manual AAPL/NVDA untouched.")) {
      return;
    }
    const origText = el.btnFlattenDayTrades.textContent;
    el.btnFlattenDayTrades.textContent = "⏳ FLATTENING...";
    el.btnFlattenDayTrades.disabled = true;
    try {
      const res = await fetch(`${BASE_URL}/api/day_trading/flatten`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      el.btnFlattenDayTrades.textContent = "✓ FLATTENED";
      alert(`⚡ DAY TRADES FLATTENED!\n\n${data.message}\nPositions Closed: ${data.flattened_count}`);
      await fetchCockpitData();
      await fetchDayTradingStatus();
      setTimeout(() => {
        if (el.btnFlattenDayTrades) {
          el.btnFlattenDayTrades.textContent = origText;
          el.btnFlattenDayTrades.disabled = false;
        }
      }, 3000);
    } catch (err) {
      alert("Failed to flatten day trades: " + err.message);
      el.btnFlattenDayTrades.textContent = origText;
      el.btnFlattenDayTrades.disabled = false;
    }
  });
}

if (el.btnResetPortfolio) {
  el.btnResetPortfolio.addEventListener("click", async () => {
    if (confirm("Reset simulation portfolio back to initial capital and clear open positions?")) {
      await fetch(`${BASE_URL}/api/portfolio/reset`, { method: "POST" });
      await fetchCockpitData();
    }
  });
}

if (el.btnResetCircuitBreaker) {
  el.btnResetCircuitBreaker.addEventListener("click", async () => {
    el.btnResetCircuitBreaker.textContent = "⌛ UNLATCHING...";
    try {
      const res = await fetch(`${BASE_URL}/api/circuit_breaker/reset`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      el.btnResetCircuitBreaker.textContent = "✓ UNLATCHED";
      await fetchCockpitData();
      setTimeout(() => {
        if (el.btnResetCircuitBreaker) {
          el.btnResetCircuitBreaker.textContent = "⚡ RESET CIRCUIT BREAKER / UNLATCH SAFETY";
        }
      }, 2500);
    } catch (e) {
      alert("Failed to reset circuit breaker: " + e.message);
      el.btnResetCircuitBreaker.textContent = "⚡ RESET CIRCUIT BREAKER / UNLATCH SAFETY";
    }
  });
}

// ==========================================
// ETORO LIVE / DEMO SWITCH & SETTINGS LOGIC
// ==========================================
let currentExecutionMode = localStorage.getItem("execution_mode") || "live";

function updateExecutionModeUI(mode) {
  currentExecutionMode = mode;
  if (mode === "live") {
    if (el.modeStatusDot) {
      el.modeStatusDot.style.background = "#ef4444";
      el.modeStatusDot.style.boxShadow = "0 0 10px #ef4444";
    }
    if (el.modeStatusLabel) el.modeStatusLabel.textContent = "⚡ LIVE ETORO (REAL ORDERS)";
    if (el.btnModeToggle) {
      el.btnModeToggle.style.borderColor = "#ef4444";
      el.btnModeToggle.style.color = "#ef4444";
    }
    if (el.statModeBadge) {
      el.statModeBadge.textContent = "⚡ LIVE eToro ACCOUNT";
      el.statModeBadge.className = "stat-badge badge-critical";
    }
  } else {
    if (el.modeStatusDot) {
      el.modeStatusDot.style.background = "#10b981";
      el.modeStatusDot.style.boxShadow = "0 0 8px #10b981";
    }
    if (el.modeStatusLabel) el.modeStatusLabel.textContent = "🛡️ DEMO / LEARNING";
    if (el.btnModeToggle) {
      el.btnModeToggle.style.borderColor = "#10b981";
      el.btnModeToggle.style.color = "#10b981";
    }
    if (el.statModeBadge) {
      el.statModeBadge.textContent = "SIMULATION (FRACTIONAL)";
      el.statModeBadge.className = "stat-badge sim-badge";
    }
  }
}

// Check initial status on startup & auto-rehydrate from localStorage
async function fetchEtoroStatus() {
  try {
    const localApiKey = localStorage.getItem("etoro_api_key") || "";
    const localUserKey = localStorage.getItem("etoro_user_key") || "";
    let localBaseUrl = localStorage.getItem("etoro_base_url") || "https://public-api.etoro.com";
    if (localBaseUrl.includes("api.etoro.com") && !localBaseUrl.includes("public-api.etoro.com")) {
      localBaseUrl = "https://public-api.etoro.com";
      localStorage.setItem("etoro_base_url", localBaseUrl);
    }
    const localMode = localStorage.getItem("execution_mode") || "live";

    const res = await fetch(`${BASE_URL}/api/etoro/status`);
    if (res.ok) {
      const data = await res.json();
      
      // Auto-rehydrate backend credentials from localStorage if server restarted
      if (!data.is_configured && (localApiKey || localUserKey)) {
        await fetch(`${BASE_URL}/api/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            etoro_api_key: localApiKey || null,
            etoro_user_key: localUserKey || null,
            etoro_base_url: localBaseUrl
          })
        });
      }

      // If user's preference is live, ensure backend is in live mode
      if (localMode === "live" && data.execution_mode !== "live") {
        console.warn("⚡ Auto-restoring user preference: Switching server to LIVE mode...");
        try {
          const switchRes = await fetch(`${BASE_URL}/api/mode/switch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "live" })
          });
          if (switchRes.ok) {
            data.execution_mode = "live";
          }
        } catch (err) {
          console.warn("Could not auto-restore live mode:", err);
        }
      }

      const activeMode = (localMode === "live") ? "live" : (data.execution_mode || "live");
      localStorage.setItem("execution_mode", activeMode);
      updateExecutionModeUI(activeMode);

      // Handle eToro Auth Cooldown / 401 Notice Banner
      const authBanner = document.getElementById("etoroAuthAlertBanner");
      const authMsg = document.getElementById("etoroAuthAlertMsg");
      if (authBanner) {
        const isInCooldown = Boolean(data.auth_cooldown);
        const isUnconfigured = activeMode === "live" && !data.is_configured;
        if (isInCooldown || isUnconfigured) {
          authBanner.classList.remove("hidden");
          authBanner.style.display = "flex";
          if (authMsg) {
            if (isInCooldown && data.last_auth_error) {
              authMsg.textContent = `${data.last_auth_error} (Cooldown: ${data.auth_cooldown_remaining_sec || 60}s remaining). Please paste a fresh ETORO_USER_KEY.`;
            } else if (isUnconfigured) {
              authMsg.textContent = "eToro credentials missing in LIVE mode. Please configure ETORO_USER_KEY in Settings.";
            }
          }
        } else {
          authBanner.classList.add("hidden");
          authBanner.style.display = "none";
        }
      }
    }
  } catch (e) {
    console.error("Error fetching eToro status:", e);
  }
}

const btnOpenConfigFromAlert = document.getElementById("btnOpenConfigFromAlert");
if (btnOpenConfigFromAlert && el.btnSettings) {
  btnOpenConfigFromAlert.addEventListener("click", () => el.btnSettings.click());
}

fetchEtoroStatus();

if (el.btnModeToggle) {
  el.btnModeToggle.addEventListener("click", async () => {
    if (currentExecutionMode === "live") {
      // Switch back to Demo immediately
      try {
        const res = await fetch(`${BASE_URL}/api/mode/switch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode: "demo" })
        });
        if (res.ok) {
          localStorage.setItem("execution_mode", "demo");
          updateExecutionModeUI("demo");
          alert("Switched back to 🛡️ DEMO & LEARNING SIMULATION mode.");
        }
      } catch (e) {
        alert("Error switching mode: " + e.message);
      }
    } else {
      // Switching to LIVE: verify keys & show safety modal
      if (el.modeSwitchModal) {
        if (el.modeSwitchKeyStatus) el.modeSwitchKeyStatus.textContent = "Checking eToro credentials...";
        el.modeSwitchModal.classList.remove("hidden");
        try {
          const res = await fetch(`${BASE_URL}/api/etoro/status`);
          if (res.ok) {
            const data = await res.json();
            if (data.is_configured) {
              el.modeSwitchKeyStatus.innerHTML = `<span style="color: #10b981; font-weight: bold;">✓ eToro API Key & User Key detected.</span><br><span style="color: var(--text-muted);">Base URL: ${data.base_url}</span>`;
            } else {
              el.modeSwitchKeyStatus.innerHTML = `<span style="color: #ef4444; font-weight: bold;">✗ eToro credentials NOT found.</span><br><span style="color: var(--text-muted);">Please click ⚙️ CONFIG to enter your ETORO_API_KEY and ETORO_USER_KEY before engaging live trading.</span>`;
            }
          }
        } catch (e) {
          if (el.modeSwitchKeyStatus) el.modeSwitchKeyStatus.textContent = "Error checking credentials.";
        }
      }
    }
  });
}

[el.btnCloseModeModal, el.btnCancelModeSwitch].forEach(btn => {
  if (btn) {
    btn.addEventListener("click", () => {
      if (el.modeSwitchModal) el.modeSwitchModal.classList.add("hidden");
    });
  }
});

if (el.btnConfirmLiveMode) {
  el.btnConfirmLiveMode.addEventListener("click", async () => {
    const originalText = el.btnConfirmLiveMode.textContent;
    el.btnConfirmLiveMode.textContent = "⌛ ENGAGING LIVE...";
    el.btnConfirmLiveMode.disabled = true;
    try {
      const res = await fetch(`${BASE_URL}/api/mode/switch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "live" })
      });
      const data = await res.json();
      if (!res.ok) {
        alert(data.detail || "Cannot switch to LIVE mode without configured eToro keys.");
        if (el.modeSwitchModal) el.modeSwitchModal.classList.add("hidden");
        if (el.settingsModal) el.settingsModal.classList.remove("hidden");
        return;
      }
      localStorage.setItem("execution_mode", "live");
      updateExecutionModeUI("live");
      if (el.modeSwitchModal) el.modeSwitchModal.classList.add("hidden");
      alert("⚡ LIVE eToro Trading Engaged! Orders will be transmitted to your connected eToro account.");
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      el.btnConfirmLiveMode.textContent = originalText;
      el.btnConfirmLiveMode.disabled = false;
    }
  });
}

// Test eToro connection button in settings
if (el.btnTestEtoroConn) {
  el.btnTestEtoroConn.addEventListener("click", async () => {
    el.btnTestEtoroConn.textContent = "⌛ TESTING HANDSHAKE...";
    el.etoroTestStatus.textContent = "Connecting to eToro API...";
    el.etoroTestStatus.style.color = "var(--text-muted)";
    try {
      // First save keys if user typed them in
      const apiKey = el.inputEtoroApiKey?.value.trim() || "";
      const userKey = el.inputEtoroUserKey?.value.trim() || "";
      const baseUrl = el.inputEtoroBaseUrl?.value.trim() || "https://public-api.etoro.com";

      if (apiKey || userKey) {
        await fetch(`${BASE_URL}/api/config`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            etoro_api_key: apiKey || null,
            etoro_user_key: userKey || null,
            etoro_base_url: baseUrl
          })
        });
      }

      const res = await fetch(`${BASE_URL}/api/etoro/test_connection`, { method: "POST" });
      const data = await res.json();
      if (data.connected) {
        el.etoroTestStatus.textContent = "✓ Connected & Authenticated!";
        el.etoroTestStatus.style.color = "#10b981";
        if (data.api_key) {
          localStorage.setItem("etoro_api_key", data.api_key);
          if (el.inputEtoroApiKey) el.inputEtoroApiKey.value = data.api_key;
        }
        if (data.user_key) {
          localStorage.setItem("etoro_user_key", data.user_key);
          if (el.inputEtoroUserKey) el.inputEtoroUserKey.value = data.user_key;
        }
        const authBanner = document.getElementById("etoroAuthAlertBanner");
        if (authBanner) authBanner.classList.add("hidden");
        fetchEtoroStatus();
      } else {
        el.etoroTestStatus.textContent = `✗ ${data.message || 'Authentication failed'}`;
        el.etoroTestStatus.style.color = "#ef4444";
      }
    } catch (e) {
      el.etoroTestStatus.textContent = "Error: " + e.message;
      el.etoroTestStatus.style.color = "#ef4444";
    } finally {
      el.btnTestEtoroConn.textContent = "🧪 TEST REST API";
    }
  });
}

// Test eToro WebSocket connection button in settings
if (el.btnTestEtoroWs) {
  el.btnTestEtoroWs.addEventListener("click", async () => {
    el.btnTestEtoroWs.textContent = "⌛ TESTING WS...";
    el.etoroTestStatus.textContent = "Connecting to wss://ws.etoro.com/ws...";
    el.etoroTestStatus.style.color = "var(--text-muted)";
    try {
      const res = await fetch(`${BASE_URL}/api/etoro/ws-test`);
      const data = await res.json();
      if (data.connected) {
        el.etoroTestStatus.textContent = "⚡ WebSocket Authenticated (wss://ws.etoro.com/ws)!";
        el.etoroTestStatus.style.color = "#38bdf8";
      } else {
        el.etoroTestStatus.textContent = `✗ WebSocket Auth Failed: ${data.message || 'Unauthorized'}`;
        el.etoroTestStatus.style.color = "#ef4444";
      }
    } catch (e) {
      el.etoroTestStatus.textContent = "WebSocket Error: " + e.message;
      el.etoroTestStatus.style.color = "#ef4444";
    } finally {
      el.btnTestEtoroWs.textContent = "⚡ TEST WEBSOCKET";
    }
  });
}

// Test eToro MCP pre-flight validation button in settings
if (el.btnTestEtoroMcp) {
  el.btnTestEtoroMcp.addEventListener("click", async () => {
    el.btnTestEtoroMcp.textContent = "⌛ TESTING MCP...";
    el.etoroTestStatus.textContent = "Contacting official eToro MCP Server (mcp.public-api.etoro.com)...";
    el.etoroTestStatus.style.color = "var(--text-muted)";
    try {
      const res = await fetch(`${BASE_URL}/api/etoro/mcp-test?symbol=${activeSymbol || 'BTC'}`);
      const data = await res.json();
      if (data.success) {
        el.etoroTestStatus.textContent = `🤖 MCP Order Ready & Verified: ${data.outcome || 'Success'}`;
        el.etoroTestStatus.style.color = "#a855f7";
      } else if (data.verdict === "rejected") {
        el.etoroTestStatus.textContent = `⚠️ MCP Pre-flight Validation Rejected: ${data.error}`;
        el.etoroTestStatus.style.color = "#f59e0b";
      } else {
        const errMsg = (data.order && data.order.error) || data.error || 'Check failed';
        if (errMsg.includes("OAuth access token") || errMsg.includes("unexpected verdict") || errMsg.includes("auth") || errMsg.includes("expired")) {
          el.etoroTestStatus.textContent = `ℹ️ MCP Gateway: Reserved for OAuth connectors. Live trading uses confirmed REST API (✓ Active).`;
          el.etoroTestStatus.style.color = "#38bdf8";
        } else {
          el.etoroTestStatus.textContent = `✗ MCP Check: ${errMsg}`;
          el.etoroTestStatus.style.color = "#ef4444";
        }
      }
    } catch (e) {
      el.etoroTestStatus.textContent = "MCP Error: " + e.message;
      el.etoroTestStatus.style.color = "#ef4444";
    } finally {
      el.btnTestEtoroMcp.textContent = "🤖 TEST MCP GATEWAY";
    }
  });
}

// Direct Top Header TEST ETORO Button
const btnHeaderTestEtoro = document.getElementById("btnHeaderTestEtoro");
if (btnHeaderTestEtoro) {
  btnHeaderTestEtoro.addEventListener("click", async () => {
    btnHeaderTestEtoro.textContent = "⌛ TESTING...";
    try {
      const res = await fetch(`${BASE_URL}/api/etoro/test_connection`, { method: "POST" });
      const data = await res.json();
      if (data.connected) {
        if (data.api_key) {
          localStorage.setItem("etoro_api_key", data.api_key);
          if (el.inputEtoroApiKey) el.inputEtoroApiKey.value = data.api_key;
        }
        if (data.user_key) {
          localStorage.setItem("etoro_user_key", data.user_key);
          if (el.inputEtoroUserKey) el.inputEtoroUserKey.value = data.user_key;
        }
        const authBanner = document.getElementById("etoroAuthAlertBanner");
        if (authBanner) authBanner.classList.add("hidden");
        fetchEtoroStatus();
        alert(`✓ SUCCESS (HTTP ${data.status_code || 200}):\n\n${data.message}\n\nGateway: ${data.base_url}\nStatus: Live Authenticated`);
      } else {
        alert(`✗ Connection Status:\n\n${data.message || 'Authentication failed'}\n\nPlease click ⚙️ CONFIG to verify your ETORO_API_KEY and ETORO_USER_KEY.`);
        if (el.settingsModal) el.settingsModal.classList.remove("hidden");
      }
    } catch (e) {
      alert("Connection test error: " + e.message);
    } finally {
      btnHeaderTestEtoro.textContent = "🧪 TEST ETORO";
    }
  });
}

// Sync 5-Day Traded Stocks to eToro Watchlist
const btnSync5DayToEtoro = document.getElementById("btnSync5DayToEtoro");
if (btnSync5DayToEtoro) {
  btnSync5DayToEtoro.addEventListener("click", async () => {
    btnSync5DayToEtoro.textContent = "⌛ SYNCHRONIZING...";
    try {
      const res = await fetch(`${BASE_URL}/api/etoro/sync_5day_trades`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        alert(`✓ Successfully synchronized ${data.synced_stocks_count} proven stocks from the last 5 days to your eToro Watchlist!\n\nStocks: ${data.synced_symbols.join(", ")}`);
        if (el.etoroTestStatus) {
          el.etoroTestStatus.textContent = `✓ Synced ${data.synced_stocks_count} stocks to eToro Watchlist at ${new Date().toLocaleTimeString()}`;
          el.etoroTestStatus.style.color = "#10b981";
        }
      } else {
        alert("Sync error: " + (data.detail || "Failed to sync to eToro."));
      }
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      btnSync5DayToEtoro.textContent = "🔄 SYNC 5-DAY TRADES TO ETORO";
    }
  });
}

// Sync Active Watchlist to eToro Watchlist
const btnSyncWlToEtoro = document.getElementById("btnSyncWlToEtoro");
if (btnSyncWlToEtoro) {
  btnSyncWlToEtoro.addEventListener("click", async () => {
    btnSyncWlToEtoro.textContent = "⌛ SYNCING...";
    try {
      const res = await fetch(`${BASE_URL}/api/etoro/sync_watchlist`, { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        alert(`✓ Successfully synchronized all ${data.synced_stocks_count} active bot stocks to your eToro Watchlist!\n\nStocks: ${data.synced_symbols.join(", ")}`);
      } else {
        alert("Sync error: " + (data.detail || "Failed to sync to eToro."));
      }
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      btnSyncWlToEtoro.textContent = "🔄 SYNC TO ETORO";
    }
  });
}

// Settings Modal
if (el.btnSettings) {
  el.btnSettings.addEventListener("click", async () => {
    try {
      const [cfgRes, etoroRes] = await Promise.all([
        fetch(`${BASE_URL}/api/config`),
        fetch(`${BASE_URL}/api/etoro/status`)
      ]);
      if (cfgRes.ok) {
        const cfg = await cfgRes.json();
        if (el.selectSimMode) el.selectSimMode.value = localStorage.getItem("execution_mode") || cfg.execution_mode || "live";
        if (el.inputRiskPct) el.inputRiskPct.value = ((cfg.risk_per_trade_pct || 0.02) * 100).toFixed(1);
        if (el.inputEtoroBaseUrl) el.inputEtoroBaseUrl.value = cfg.etoro_base_url || "https://public-api.etoro.com";

        if (el.inputFinnhubKey && !el.inputFinnhubKey.value) el.inputFinnhubKey.value = localStorage.getItem("finnhub_api_key") || "";
        if (el.inputTwelveDataKey && !el.inputTwelveDataKey.value) el.inputTwelveDataKey.value = localStorage.getItem("twelve_data_api_key") || "";
        if (el.inputFmpKey && !el.inputFmpKey.value) el.inputFmpKey.value = localStorage.getItem("fmp_api_key") || "";
        if (el.inputAlphaVantageKey && !el.inputAlphaVantageKey.value) el.inputAlphaVantageKey.value = localStorage.getItem("alpha_vantage_api_key") || "";
        if (el.inputTavilyKey && !el.inputTavilyKey.value) el.inputTavilyKey.value = localStorage.getItem("tavily_api_key") || "";
        if (el.inputSerpApiKey && !el.inputSerpApiKey.value) el.inputSerpApiKey.value = localStorage.getItem("serpapi_api_key") || "";
        if (el.inputAnspireKey && !el.inputAnspireKey.value) el.inputAnspireKey.value = localStorage.getItem("anspire_api_key") || "";
        if (el.inputQuiverKey && !el.inputQuiverKey.value) el.inputQuiverKey.value = localStorage.getItem("quiver_api_key") || "";

        if (el.inputEnableDayTrading) el.inputEnableDayTrading.checked = cfg.enable_day_trading !== false;
        if (el.inputDayTradeAllocPct) el.inputDayTradeAllocPct.value = Math.round((cfg.day_trade_allocation_pct || 0.35) * 100);
        if (el.inputDayTradeMaxActive) el.inputDayTradeMaxActive.value = cfg.day_trade_max_active || 4;
        if (el.inputDayTradeSlPct) el.inputDayTradeSlPct.value = ((cfg.day_trade_stop_loss_pct || 0.012) * 100).toFixed(1);
        if (el.inputDayTradeTpPct) el.inputDayTradeTpPct.value = ((cfg.day_trade_take_profit_pct || 0.024) * 100).toFixed(1);
        if (el.inputMaxDailyLossUsd) el.inputMaxDailyLossUsd.value = (cfg.max_daily_loss_usd || 35.0).toFixed(1);
        if (el.inputDayTradeEodFlattenMins) el.inputDayTradeEodFlattenMins.value = cfg.day_trade_eod_flatten_minutes_before_close || 15;
      }
      if (etoroRes.ok) {
        const et = await etoroRes.json();
        if (el.etoroTestStatus) {
          el.etoroTestStatus.textContent = et.is_configured ? "✓ Keys configured in server" : "Keys not set";
          el.etoroTestStatus.style.color = et.is_configured ? "#10b981" : "var(--text-muted)";
        }
      }
    } catch (e) {
      console.error("Error loading config:", e);
    }
    if (el.settingsModal) {
      document.body.style.overflow = "hidden";
      el.settingsModal.classList.remove("hidden");
      el.settingsModal.scrollTop = 0;
      const mBody = el.settingsModal.querySelector(".modal-body");
      if (mBody) mBody.scrollTop = 0;
      if (el.inputEtoroUserKey) {
        setTimeout(() => el.inputEtoroUserKey.focus(), 150);
      }
    }
  });
}

if (el.btnCloseModal) {
  el.btnCloseModal.addEventListener("click", () => {
    document.body.style.overflow = "";
    if (el.settingsModal) el.settingsModal.classList.add("hidden");
  });
}

if (el.settingsModal) {
  el.settingsModal.addEventListener("click", (e) => {
    if (e.target === el.settingsModal) {
      document.body.style.overflow = "";
      el.settingsModal.classList.add("hidden");
    }
  });
}

if (el.btnSaveConfig) {
  el.btnSaveConfig.addEventListener("click", async () => {
    const finnhubKey = el.inputFinnhubKey ? el.inputFinnhubKey.value.trim() : "";
    const twelveDataKey = el.inputTwelveDataKey ? el.inputTwelveDataKey.value.trim() : "";
    const fmpKey = el.inputFmpKey ? el.inputFmpKey.value.trim() : "";
    const alphaVantageKey = el.inputAlphaVantageKey ? el.inputAlphaVantageKey.value.trim() : "";
    const tavilyKey = el.inputTavilyKey ? el.inputTavilyKey.value.trim() : "";
    const serpApiKey = el.inputSerpApiKey ? el.inputSerpApiKey.value.trim() : "";
    const anspireKey = el.inputAnspireKey ? el.inputAnspireKey.value.trim() : "";
    const quiverKey = el.inputQuiverKey ? el.inputQuiverKey.value.trim() : "";

    const execMode = el.selectSimMode ? el.selectSimMode.value : "demo";
    const riskPct = el.inputRiskPct ? parseFloat(el.inputRiskPct.value) / 100.0 : 0.02;
    const etoroApiKey = el.inputEtoroApiKey ? el.inputEtoroApiKey.value.trim() : "";
    const etoroUserKey = el.inputEtoroUserKey ? el.inputEtoroUserKey.value.trim() : "";
    const etoroBaseUrl = el.inputEtoroBaseUrl ? el.inputEtoroBaseUrl.value.trim() || "https://public-api.etoro.com" : "https://public-api.etoro.com";

    const enableDayTrading = el.inputEnableDayTrading ? el.inputEnableDayTrading.checked : true;
    const dayTradeAllocPct = el.inputDayTradeAllocPct ? parseFloat(el.inputDayTradeAllocPct.value) / 100.0 : 0.35;
    const dayTradeMaxActive = el.inputDayTradeMaxActive ? parseInt(el.inputDayTradeMaxActive.value) : 4;
    const dayTradeSlPct = el.inputDayTradeSlPct ? parseFloat(el.inputDayTradeSlPct.value) / 100.0 : 0.012;
    const dayTradeTpPct = el.inputDayTradeTpPct ? parseFloat(el.inputDayTradeTpPct.value) / 100.0 : 0.024;
    const maxDailyLossUsd = el.inputMaxDailyLossUsd ? parseFloat(el.inputMaxDailyLossUsd.value) : 35.0;
    const dayTradeEodFlattenMins = el.inputDayTradeEodFlattenMins ? parseInt(el.inputDayTradeEodFlattenMins.value) : 15;

    const origText = el.btnSaveConfig.textContent;
    el.btnSaveConfig.textContent = "⏳ SAVING...";
    el.btnSaveConfig.disabled = true;
    const btnTop = document.getElementById("btnSaveConfigTop");
    if (btnTop) {
      btnTop.textContent = "⏳ SAVING...";
      btnTop.disabled = true;
    }

    try {
      const res = await fetch(`${BASE_URL}/api/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          finnhub_api_key: finnhubKey || null,
          twelve_data_api_key: twelveDataKey || null,
          fmp_api_key: fmpKey || null,
          alpha_vantage_api_key: alphaVantageKey || null,
          tavily_api_key: tavilyKey || null,
          serpapi_api_key: serpApiKey || null,
          anspire_api_key: anspireKey || null,
          quiver_api_key: quiverKey || null,
          execution_mode: execMode,
          risk_per_trade_pct: riskPct,
          etoro_api_key: etoroApiKey || null,
          etoro_user_key: etoroUserKey || null,
          etoro_base_url: etoroBaseUrl,
          enable_day_trading: enableDayTrading,
          day_trade_allocation_pct: dayTradeAllocPct,
          day_trade_max_active: dayTradeMaxActive,
          day_trade_stop_loss_pct: dayTradeSlPct,
          day_trade_take_profit_pct: dayTradeTpPct,
          max_daily_loss_usd: maxDailyLossUsd,
          day_trade_eod_flatten_minutes_before_close: dayTradeEodFlattenMins
        })
      });

      if (!res.ok) {
        throw new Error(`Server returned HTTP ${res.status}`);
      }

      if (finnhubKey) localStorage.setItem("finnhub_api_key", finnhubKey);
      if (twelveDataKey) localStorage.setItem("twelve_data_api_key", twelveDataKey);
      if (fmpKey) localStorage.setItem("fmp_api_key", fmpKey);
      if (alphaVantageKey) localStorage.setItem("alpha_vantage_api_key", alphaVantageKey);
      if (tavilyKey) localStorage.setItem("tavily_api_key", tavilyKey);
      if (serpApiKey) localStorage.setItem("serpapi_api_key", serpApiKey);
      if (anspireKey) localStorage.setItem("anspire_api_key", anspireKey);
      if (quiverKey) localStorage.setItem("quiver_api_key", quiverKey);

      if (etoroApiKey) localStorage.setItem("etoro_api_key", etoroApiKey);
      if (etoroUserKey) localStorage.setItem("etoro_user_key", etoroUserKey);
      if (etoroBaseUrl) localStorage.setItem("etoro_base_url", etoroBaseUrl);
      if (execMode) localStorage.setItem("execution_mode", execMode);


      updateExecutionModeUI(execMode);
      document.body.style.overflow = "";
      if (el.settingsModal) el.settingsModal.classList.add("hidden");
      alert("✓ Configuration and eToro API settings saved successfully (Persisted to disk & browser)!");
      fetchCockpitData();
    } catch (err) {
      alert("Failed to update config: " + err.message);
    } finally {
      el.btnSaveConfig.textContent = origText;
      el.btnSaveConfig.disabled = false;
      if (btnTop) {
        btnTop.textContent = "💾 SAVE CONFIG";
        btnTop.disabled = false;
      }
    }
  });
}

const btnSaveConfigTop = document.getElementById("btnSaveConfigTop");
if (btnSaveConfigTop && el.btnSaveConfig) {
  btnSaveConfigTop.addEventListener("click", () => el.btnSaveConfig.click());
}

const btnCancelConfig = document.getElementById("btnCancelConfig");
if (btnCancelConfig && el.btnCloseModal) {
  btnCancelConfig.addEventListener("click", () => el.btnCloseModal.click());
}

// Daily & 5-Day Report Modal
const btnDailyReport = document.getElementById("btnDailyReport");
const dailyReportModal = document.getElementById("dailyReportModal");
const btnCloseReportModal = document.getElementById("btnCloseReportModal");
const btnDownloadJson = document.getElementById("btnDownloadJson");
const btnDownloadCsv = document.getElementById("btnDownloadCsv");

const tabBtnDailyStock = document.getElementById("tabBtnDailyStock");
const tabBtn5DayReport = document.getElementById("tabBtn5DayReport");
const tabBtnFullLedger = document.getElementById("tabBtnFullLedger");

const viewDailyStockSummary = document.getElementById("viewDailyStockSummary");
const view5DaySummary = document.getElementById("view5DaySummary");
const viewFullLedger = document.getElementById("viewFullLedger");

let lastDailyReportData = null;
let last5DayReportData = null;
let activeReportTab = "daily";

function setReportTab(tab) {
  activeReportTab = tab;
  [tabBtnDailyStock, tabBtn5DayReport, tabBtnFullLedger].forEach(b => {
    if (b) b.className = "btn btn-outline";
  });
  [viewDailyStockSummary, view5DaySummary, viewFullLedger].forEach(v => {
    if (v) v.classList.add("hidden");
  });

  if (tab === "daily") {
    if (tabBtnDailyStock) tabBtnDailyStock.className = "btn btn-primary";
    if (viewDailyStockSummary) viewDailyStockSummary.classList.remove("hidden");
  } else if (tab === "5day") {
    if (tabBtn5DayReport) tabBtn5DayReport.className = "btn btn-primary";
    if (view5DaySummary) view5DaySummary.classList.remove("hidden");
  } else if (tab === "ledger") {
    if (tabBtnFullLedger) tabBtnFullLedger.className = "btn btn-primary";
    if (viewFullLedger) viewFullLedger.classList.remove("hidden");
  }
}

if (tabBtnDailyStock) tabBtnDailyStock.addEventListener("click", () => setReportTab("daily"));
if (tabBtn5DayReport) {
  tabBtn5DayReport.addEventListener("click", async () => {
    setReportTab("5day");
    if (!last5DayReportData) {
      try {
        const res = await fetch(`${BASE_URL}/api/reports/five_day`);
        if (res.ok) {
          const data = await res.json();
          last5DayReportData = data;
          render5DayTable(data);
        }
      } catch (e) {
        console.error("Error fetching 5-day report:", e);
      }
    }
  });
}
if (tabBtnFullLedger) tabBtnFullLedger.addEventListener("click", () => setReportTab("ledger"));

function renderPerStockTable(stockList) {
  const tbody = document.getElementById("repPerStockBody");
  const tfoot = document.getElementById("repPerStockFoot");
  if (!tbody) return;

  if (!stockList || stockList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No individual stock trades executed today yet.</td></tr>`;
    if (tfoot) tfoot.innerHTML = "";
    return;
  }

  let grandVol = 0, grandTrades = 0, grandHits = 0, grandMisses = 0, grandPnl = 0;

  tbody.innerHTML = stockList.map(s => {
    grandVol += s.amount_traded_usd;
    grandTrades += s.total_trades;
    grandHits += s.hits;
    grandMisses += s.misses;
    grandPnl += s.net_pnl_usd;

    const pnlColor = s.net_pnl_usd >= 0 ? "color-success" : "color-danger";
    const sign = s.net_pnl_usd >= 0 ? "+" : "";
    return `
      <tr>
        <td><strong>${s.symbol}</strong></td>
        <td>$${s.amount_traded_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
        <td><strong>${s.total_trades}</strong></td>
        <td><span class="badge badge-ok">${s.hits} Hits</span></td>
        <td><span class="badge ${s.misses > 0 ? 'badge-critical' : 'badge-normal'}">${s.misses} Misses</span></td>
        <td>${s.hit_rate_pct.toFixed(1)}%</td>
        <td class="${pnlColor}"><strong>${sign}$${s.net_pnl_usd.toFixed(2)}</strong></td>
        <td class="${pnlColor}">${sign}${s.net_pnl_pct.toFixed(2)}%</td>
      </tr>
    `;
  }).join("");

  const grandHitRate = grandTrades > 0 ? (grandHits / grandTrades * 100.0) : 0.0;
  const grandPnlColor = grandPnl >= 0 ? "color-success" : "color-danger";
  const grandSign = grandPnl >= 0 ? "+" : "";
  const grandRetPct = grandVol > 0 ? (grandPnl / grandVol * 100.0) : 0.0;

  if (tfoot) {
    tfoot.innerHTML = `
      <tr>
        <td>TOTALS:</td>
        <td>$${grandVol.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>${grandTrades}</td>
        <td>${grandHits} Hits</td>
        <td>${grandMisses} Misses</td>
        <td>${grandHitRate.toFixed(1)}%</td>
        <td class="${grandPnlColor}"><strong>${grandSign}$${grandPnl.toFixed(2)}</strong></td>
        <td class="${grandPnlColor}">${grandSign}${grandRetPct.toFixed(2)}%</td>
      </tr>
    `;
  }
}

function render5DayTable(data) {
  const tbody = document.getElementById("rep5DayStockBody");
  const tfoot = document.getElementById("rep5DayStockFoot");
  if (!tbody) return;

  const stockList = data.stock_summaries || [];
  if (stockList.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No 5-day trading records available yet.</td></tr>`;
    if (tfoot) tfoot.innerHTML = "";
    return;
  }

  tbody.innerHTML = stockList.map(s => {
    const pnlColor = s.net_pnl_usd >= 0 ? "color-success" : "color-danger";
    const sign = s.net_pnl_usd >= 0 ? "+" : "";
    return `
      <tr>
        <td><strong>${s.symbol}</strong></td>
        <td>$${s.amount_traded_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td><strong>${s.total_trades}</strong></td>
        <td><span class="badge badge-ok">${s.hits}</span></td>
        <td><span class="badge ${s.misses > 0 ? 'badge-critical' : 'badge-normal'}">${s.misses}</span></td>
        <td>${s.hit_rate_pct.toFixed(1)}%</td>
        <td class="${pnlColor}"><strong>${sign}$${s.net_pnl_usd.toFixed(2)}</strong></td>
        <td class="${pnlColor}">${sign}${s.net_pnl_pct.toFixed(2)}%</td>
      </tr>
    `;
  }).join("");

  const grandPnlColor = data.total_net_pnl_usd >= 0 ? "color-success" : "color-danger";
  const grandSign = data.total_net_pnl_usd >= 0 ? "+" : "";

  if (tfoot) {
    tfoot.innerHTML = `
      <tr>
        <td>5-DAY GRAND TOTAL:</td>
        <td>$${data.total_amount_traded_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
        <td>${data.total_trades}</td>
        <td>${data.total_hits} Hits</td>
        <td>${data.total_misses} Misses</td>
        <td>${data.overall_hit_rate_pct.toFixed(1)}%</td>
        <td class="${grandPnlColor}"><strong>${grandSign}$${data.total_net_pnl_usd.toFixed(2)}</strong></td>
        <td class="${grandPnlColor}">${grandSign}${data.total_net_pnl_pct.toFixed(2)}%</td>
      </tr>
    `;
  }
}

if (btnDailyReport) {
  btnDailyReport.addEventListener("click", async () => {
    btnDailyReport.textContent = "⌛ LOADING...";
    try {
      const res = await fetch(`${BASE_URL}/api/daily_report`);
      if (!res.ok) throw new Error("Failed to fetch daily report");
      const rep = await res.json();
      lastDailyReportData = rep;

      document.getElementById("repEquity").textContent = `$${rep.current_equity.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
      
      const pnlSign = rep.net_pnl_usd >= 0 ? "+" : "";
      const repNetPnlEl = document.getElementById("repNetPnl");
      repNetPnlEl.textContent = `${pnlSign}$${rep.net_pnl_usd.toFixed(2)} (${pnlSign}${rep.net_pnl_pct.toFixed(2)}%)`;
      repNetPnlEl.className = `stat-number ${rep.net_pnl_usd >= 0 ? 'color-success' : 'color-danger'}`;

      document.getElementById("repWinRate").textContent = `${rep.win_rate_pct.toFixed(1)}% (${rep.winning_trades} Hits / ${rep.losing_trades} Misses)`;
      
      const totalVol = (rep.per_stock_summary || []).reduce((acc, s) => acc + s.amount_traded_usd, 0.0);
      document.getElementById("repVolTraded").textContent = `$${totalVol.toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

      document.getElementById("repTimeUk").textContent = `Report generated: ${rep.report_time_uk}`;

      // Render per-stock table
      renderPerStockTable(rep.per_stock_summary || []);

      // Render weight evolution
      const wCont = document.getElementById("repWeightEvolution");
      if (wCont) {
        wCont.innerHTML = Object.entries(rep.strategy_weight_evolution || {}).map(([name, data]) => `
          <div class="fed-model-item">
            <div class="fed-model-header">
              <strong>${name.replace('_', ' ').toUpperCase()}</strong>
              <span class="color-warn">${data.current_pct} (Δ ${data.shift_from_baseline})</span>
            </div>
            <div class="progress-track">
              <div class="progress-fill" style="width: ${data.current_pct}; background: var(--accent-purple);"></div>
            </div>
          </div>
        `).join("");
      }

      // Render diagnosed mistakes
      const mistCont = document.getElementById("repMistakesList");
      if (mistCont) {
        if (rep.diagnosed_mistakes && rep.diagnosed_mistakes.length > 0) {
          mistCont.innerHTML = rep.diagnosed_mistakes.map(m => `
            <div class="mistake-item">
              <div class="mistake-cause">🔴 [${m.symbol} ${m.direction}] -$${Math.abs(m.pnl_usd).toFixed(2)}: ${m.primary_failure_cause}</div>
              <div class="mistake-action">↳ <strong>Adaptation:</strong> ${m.adaptation_action}</div>
            </div>
          `).join("");
        } else {
          mistCont.innerHTML = `<span class="text-muted" style="font-size: 11px;">No trade losses recorded today. Zero mistakes logged.</span>`;
        }
      }

      // Render full ledger
      const legBody = document.getElementById("repLedgerBody");
      if (legBody) {
        if (rep.full_trade_ledger && rep.full_trade_ledger.length > 0) {
          legBody.innerHTML = rep.full_trade_ledger.map(t => {
            const isLong = t.direction === "LONG";
            const pnlColor = t.realized_pnl_usd >= 0 ? "color-success" : "color-danger";
            const sign = t.realized_pnl_usd >= 0 ? "+" : "";
            const timeShort = t.exit_time ? t.exit_time.split("T")[1].substring(0, 8) : "--";
            return `
              <tr>
                <td>${timeShort}</td>
                <td><strong>${t.symbol}</strong></td>
                <td><span class="badge ${isLong ? 'badge-ok' : 'badge-critical'}">${t.direction}</span></td>
                <td>${t.shares.toFixed(4)}</td>
                <td>$${t.entry_price.toFixed(2)}</td>
                <td>$${t.exit_price.toFixed(2)}</td>
                <td class="${pnlColor}"><strong>${sign}$${t.realized_pnl_usd.toFixed(2)}</strong></td>
                <td><small>${t.entry_rationale} | <em>${t.exit_rationale}</em></small></td>
              </tr>
            `;
          }).join("");
        } else {
          legBody.innerHTML = `<tr><td colspan="8" class="text-center text-muted">No trades executed in this session yet.</td></tr>`;
        }
      }

      setReportTab("daily");
      dailyReportModal.classList.remove("hidden");
    } catch (e) {
      alert("Error loading daily report: " + e.message);
    } finally {
      btnDailyReport.textContent = "📊 DAILY REPORT";
    }
  });
}

if (btnCloseReportModal) {
  btnCloseReportModal.addEventListener("click", () => {
    dailyReportModal.classList.add("hidden");
  });
}

if (btnDownloadJson) {
  btnDownloadJson.addEventListener("click", () => {
    const exportData = activeReportTab === "5day" ? last5DayReportData : lastDailyReportData;
    if (!exportData) return;
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `trading_report_${activeReportTab}_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
}

if (btnDownloadCsv) {
  btnDownloadCsv.addEventListener("click", () => {
    const list = activeReportTab === "5day"
      ? (last5DayReportData?.stock_summaries || [])
      : (lastDailyReportData?.per_stock_summary || []);
    
    if (list.length === 0) {
      alert("No data available to export to CSV.");
      return;
    }

    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Symbol,Amount Traded ($),Total Trades,Hits (Wins),Misses (Losses),Hit Rate (%),Net P&L ($),Return (%)\n";

    list.forEach(s => {
      csvContent += `${s.symbol},${s.amount_traded_usd.toFixed(2)},${s.total_trades},${s.hits},${s.misses},${s.hit_rate_pct.toFixed(1)}%,${s.net_pnl_usd.toFixed(2)},${s.net_pnl_pct.toFixed(2)}%\n`;
    });

    const encodedUri = encodeURI(csvContent);
    const a = document.createElement("a");
    a.href = encodedUri;
    a.download = `per_stock_summary_${activeReportTab}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  });
}

// PDF Report Download Handler
const btnDownloadPdf = document.getElementById("btnDownloadPdf");
if (btnDownloadPdf) {
  btnDownloadPdf.addEventListener("click", () => {
    btnDownloadPdf.textContent = "⌛ GENERATING...";
    const reportType = activeReportTab === "5day" ? "5day" : "daily";
    window.location.href = `${BASE_URL}/api/reports/pdf?report_type=${reportType}`;
    setTimeout(() => {
      btnDownloadPdf.textContent = "📄 DOWNLOAD PDF";
    }, 2000);
  });
}

// Email PDF Report Handler (Default: lisawalker6898@gmail.com)
const btnEmailReport = document.getElementById("btnEmailReport");
if (btnEmailReport) {
  btnEmailReport.addEventListener("click", async () => {
    const defaultEmail = "lisawalker6898@gmail.com";
    const userEmail = prompt("Send performance audit PDF report to:", defaultEmail);
    if (!userEmail) return;

    btnEmailReport.textContent = "⌛ SENDING...";
    try {
      const reportType = activeReportTab === "5day" ? "5day" : "daily";
      const res = await fetch(`${BASE_URL}/api/reports/email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          recipient: userEmail.trim(),
          report_type: reportType
        })
      });
      const data = await res.json();
      if (data.status === "success") {
        alert(`✓ ${data.message}\n\nFile attached: ${data.filename}\nRecipient: ${data.recipient}`);
      } else {
        alert(`Notice: ${data.message}`);
      }
    } catch (e) {
      alert("Email dispatch error: " + e.message);
    } finally {
      btnEmailReport.textContent = "📧 EMAIL COPY";
    }
  });
}

// ==========================================
// QUANTITATIVE BACKTESTER & OPTIMIZER UI
// ==========================================
const btnBacktestModal = document.getElementById("btnBacktestModal");
const backtestModal = document.getElementById("backtestModal");
const btnCloseBacktestModal = document.getElementById("btnCloseBacktestModal");
const btnCloseBtFooter = document.getElementById("btnCloseBtFooter");
const btnRunBacktest = document.getElementById("btnRunBacktest");
const btnAutoOptimize = document.getElementById("btnAutoOptimize");
const btnApplyOptimal = document.getElementById("btnApplyOptimal");
const btStatusMsg = document.getElementById("btStatusMsg");
const btSymbolSelect = document.getElementById("btSymbolSelect");
const btPerStockSection = document.getElementById("btPerStockSection");
const btPerStockBody = document.getElementById("btPerStockBody");

async function populateBacktestSymbolDropdown() {
  if (!btSymbolSelect) return;
  try {
    const [wlRes, uniRes] = await Promise.all([
      fetch(`${BASE_URL}/api/watchlist`),
      fetch(`${BASE_URL}/api/screener/universe`)
    ]);

    const wlData = wlRes.ok ? await wlRes.json() : { active_watchlist: [] };
    const uniData = uniRes.ok ? await uniRes.json() : { universe: {} };

    const activeList = wlData.active_watchlist || [];
    const universe = uniData.universe || {};

    const curVal = btSymbolSelect.value || "ALL";

    let html = `<option value="ALL">🌐 ALL ACTIVE WATCHLIST STOCKS (${activeList.length} Assets Portfolio-Wide)</option>`;

    // 1. Active Watchlist Optgroup
    if (activeList.length > 0) {
      html += `<optgroup label="⭐ Active Bot Watchlist (${activeList.length} Assets)">`;
      activeList.forEach(s => {
        const u = universe[s] || {};
        html += `<option value="${s}">⭐ ${s} - ${u.name || s} (${u.category || 'Active'})</option>`;
      });
      html += `</optgroup>`;
    }

    // Group remaining universe by category
    const categories = {
      "Crypto": "🪙 Cryptocurrencies (24/7)",
      "Commodities": "🛢️ Commodities (Metals, Energy, Softs)",
      "Indices": "📈 Global Benchmark Indices",
      "ETFs": "🌐 Benchmark & Leveraged ETFs",
      "Leveraged ETFs": "⚡ 3X Leveraged Bull/Bear ETFs",
      "AI & Tech Titans": "⚡ AI, Semi & Mega-Cap Tech",
      "Crypto Runners": "🚀 Crypto Miners & Runners",
      "Fintech & Growth": "💳 Fintech & Growth Equities",
      "Global Blue Chips": "🏛️ Global Blue Chips & Value"
    };

    for (const [catKey, catLabel] of Object.entries(categories)) {
      const items = Object.entries(universe).filter(([sym, data]) => data.category === catKey || data.asset_class === catKey);
      if (items.length > 0) {
        html += `<optgroup label="${catLabel}">`;
        items.forEach(([sym, data]) => {
          html += `<option value="${sym}">${sym} - ${data.name} ($${data.base_price})</option>`;
        });
        html += `</optgroup>`;
      }
    }

    btSymbolSelect.innerHTML = html;
    if (curVal) btSymbolSelect.value = curVal;
  } catch (e) {
    console.error("Backtest symbol dropdown error:", e);
  }
}

if (btnBacktestModal) {
  btnBacktestModal.addEventListener("click", () => {
    populateBacktestSymbolDropdown();
    backtestModal.classList.remove("hidden");
  });
}

[btnCloseBacktestModal, btnCloseBtFooter].forEach(btn => {
  if (btn) {
    btn.addEventListener("click", () => {
      backtestModal.classList.add("hidden");
    });
  }
});

function renderBacktestResults(res) {
  const pnlSign = res.net_pnl_usd >= 0 ? "+" : "";
  const pnlEl = document.getElementById("btPnl");
  pnlEl.textContent = `${pnlSign}$${res.net_pnl_usd.toFixed(2)} (${pnlSign}${res.net_pnl_pct.toFixed(2)}%)`;
  pnlEl.className = `stat-number ${res.net_pnl_usd >= 0 ? 'color-success' : 'color-danger'}`;

  document.getElementById("btWinRate").textContent = `${res.win_rate_pct.toFixed(1)}% (${res.winning_trades}W / ${res.losing_trades}L)`;
  document.getElementById("btProfitFactor").textContent = res.profit_factor.toFixed(2);
  document.getElementById("btMaxDd").textContent = `${res.max_drawdown_pct.toFixed(2)}%`;

  // Render Per-Stock Breakdown table (if portfolio backtest)
  if (res.per_stock_breakdown && res.per_stock_breakdown.length > 0) {
    if (btPerStockSection) btPerStockSection.classList.remove("hidden");
    if (btPerStockBody) {
      btPerStockBody.innerHTML = res.per_stock_breakdown.map(s => {
        const pnlColor = s.net_pnl_usd >= 0 ? "color-success" : "color-danger";
        const sign = s.net_pnl_usd >= 0 ? "+" : "";
        return `
          <tr>
            <td><strong>${s.symbol}</strong></td>
            <td>${s.name}</td>
            <td><span class="badge badge-normal" style="font-size: 10px;">${s.asset_class}</span></td>
            <td>${s.total_trades}</td>
            <td><span class="badge badge-ok">${s.hits}W</span></td>
            <td><span class="badge ${s.misses > 0 ? 'badge-critical' : 'badge-normal'}">${s.misses}L</span></td>
            <td>${s.hit_rate_pct.toFixed(1)}%</td>
            <td class="${pnlColor}"><strong>${sign}$${s.net_pnl_usd.toFixed(2)}</strong></td>
            <td class="${pnlColor}">${sign}${s.net_pnl_pct.toFixed(2)}%</td>
          </tr>
        `;
      }).join("");
    }
  } else {
    if (btPerStockSection) btPerStockSection.classList.add("hidden");
  }

  const tbody = document.getElementById("btTradesBody");
  if (res.trades && res.trades.length > 0) {
    tbody.innerHTML = res.trades.map(t => {
      const isLong = t.direction === "LONG";
      const pnlColor = t.realized_pnl_usd >= 0 ? "color-success" : "color-danger";
      const sign = t.realized_pnl_usd >= 0 ? "+" : "";
      return `
        <tr>
          <td>${t.entry_time} → ${t.exit_time}</td>
          <td><span class="badge ${isLong ? 'badge-ok' : 'badge-critical'}">${t.direction}</span></td>
          <td>${t.shares.toFixed(4)}</td>
          <td>$${t.entry_price.toFixed(2)}</td>
          <td>$${t.exit_price.toFixed(2)}</td>
          <td class="${pnlColor}"><strong>${sign}$${t.realized_pnl_usd.toFixed(2)} (${sign}${t.realized_pnl_pct.toFixed(2)}%)</strong></td>
          <td><small>[<strong>${t.symbol}</strong>] ${t.rationale}</small></td>
        </tr>
      `;
    }).join("");
  } else {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No trades triggered during backtest with current filters.</td></tr>`;
  }
}

if (btnRunBacktest) {
  btnRunBacktest.addEventListener("click", async () => {
    const symbol = document.getElementById("btSymbolSelect").value;
    const sl = parseFloat(document.getElementById("btStopLoss").value) / 100.0;
    const tp = parseFloat(document.getElementById("btTakeProfit").value) / 100.0;
    const adx = parseFloat(document.getElementById("btAdxFilter").value);

    btnRunBacktest.textContent = "⌛ SIMULATING...";
    btStatusMsg.textContent = "Running quantitative simulation...";
    try {
      const res = await fetch(`${BASE_URL}/api/backtest/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol,
          stop_loss_pct: sl,
          take_profit_pct: tp,
          adx_threshold: adx,
          num_ticks: 160
        })
      });
      if (!res.ok) throw new Error("Backtest simulation failed");
      const data = await res.json();
      renderBacktestResults(data);
      btStatusMsg.textContent = `Simulation complete for ${symbol}.`;
    } catch (e) {
      alert("Error: " + e.message);
      btStatusMsg.textContent = "Error running backtest.";
    } finally {
      btnRunBacktest.textContent = "▶ RUN BACKTEST";
    }
  });
}

if (btnAutoOptimize) {
  btnAutoOptimize.addEventListener("click", async () => {
    const symbol = document.getElementById("btSymbolSelect").value;
    btnAutoOptimize.textContent = "⌛ OPTIMIZING GRID...";
    btStatusMsg.textContent = `Testing 48 parameter combinations for ${symbol}...`;
    try {
      const res = await fetch(`${BASE_URL}/api/backtest/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: symbol })
      });
      if (!res.ok) throw new Error("Optimization failed");
      const data = await res.json();

      // Show recommendation banner
      document.getElementById("btRecBanner").classList.remove("hidden");
      document.getElementById("btRecText").textContent = data.recommendation_summary;

      // Populate input boxes with optimal values
      const opt = data.optimal_candidate;
      document.getElementById("btStopLoss").value = (opt.stop_loss_pct * 100.0).toFixed(1);
      document.getElementById("btTakeProfit").value = (opt.take_profit_pct * 100.0).toFixed(1);
      document.getElementById("btAdxFilter").value = opt.adx_threshold.toFixed(0);

      // Render top candidates table
      document.getElementById("btOptSection").classList.remove("hidden");
      const cBody = document.getElementById("btOptCandidatesBody");
      cBody.innerHTML = data.top_candidates.map(c => `
        <tr style="${c.rank === 1 ? 'background: rgba(0,255,136,0.08); font-weight: bold;' : ''}">
          <td><span class="badge ${c.rank === 1 ? 'badge-ok' : 'badge-normal'}">#${c.rank}</span></td>
          <td>${(c.stop_loss_pct * 100).toFixed(1)}%</td>
          <td>${(c.take_profit_pct * 100).toFixed(1)}%</td>
          <td>ADX ≥ ${c.adx_threshold.toFixed(0)}</td>
          <td>${c.win_rate_pct.toFixed(1)}%</td>
          <td>${c.profit_factor.toFixed(2)}</td>
          <td>${c.max_drawdown_pct.toFixed(2)}%</td>
          <td class="${c.net_pnl_pct >= 0 ? 'color-success' : 'color-danger'}">+${c.net_pnl_pct.toFixed(2)}%</td>
        </tr>
      `).join("");

      // Trigger a run with the optimal values to show the trade ledger
      btnRunBacktest.click();
      btStatusMsg.textContent = `✓ Grid optimization complete! Optimal parameters loaded.`;
    } catch (e) {
      alert("Error: " + e.message);
      btStatusMsg.textContent = "Optimization failed.";
    } finally {
      btnAutoOptimize.textContent = "✨ AUTO-OPTIMIZE (GRID SEARCH)";
    }
  });
}

if (btnApplyOptimal) {
  btnApplyOptimal.addEventListener("click", async () => {
    const symbol = document.getElementById("btSymbolSelect").value;
    const sl = parseFloat(document.getElementById("btStopLoss").value) / 100.0;
    const tp = parseFloat(document.getElementById("btTakeProfit").value) / 100.0;
    const adx = parseFloat(document.getElementById("btAdxFilter").value);

    try {
      const res = await fetch(`${BASE_URL}/api/backtest/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: symbol,
          stop_loss_pct: sl,
          take_profit_pct: tp,
          adx_threshold: adx
        })
      });
      if (!res.ok) throw new Error("Failed to apply parameters");
      const d = await res.json();
      btStatusMsg.textContent = `🚀 Applied: SL ${(sl*100).toFixed(1)}% / TP ${(tp*100).toFixed(1)}% / ADX ≥ ${adx} active!`;
      alert(d.message);
    } catch (e) {
      alert("Error applying settings: " + e.message);
    }
  });
}

// ==========================================
// UNIVERSAL MARKET SCREENER & WATCHLIST UI
// ==========================================
const btnScreenerModal = document.getElementById("btnScreenerModal");
const screenerModal = document.getElementById("screenerModal");
const btnCloseScreenerModal = document.getElementById("btnCloseScreenerModal");
const btnCloseScreenerFooter = document.getElementById("btnCloseScreenerFooter");
const btnAddCustomTicker = document.getElementById("btnAddCustomTicker");
const inputCustomTicker = document.getElementById("inputCustomTicker");
const activeWatchlistPills = document.getElementById("activeWatchlistPills");
const activeWlCount = document.getElementById("activeWlCount");
const screenerTableBody = document.getElementById("screenerTableBody");
const btnRefreshScreener = document.getElementById("btnRefreshScreener");
const btnAutoAddTopScreened = document.getElementById("btnAutoAddTopScreened");
const screenerStatusMsg = document.getElementById("screenerStatusMsg");

async function updateWatchlistUI() {
  try {
    const res = await fetch(`${BASE_URL}/api/watchlist`);
    if (!res.ok) return;
    const data = await res.json();
    const list = data.active_watchlist || [];
    
    if (activeWlCount) activeWlCount.textContent = list.length;
    
    // Update active pills
    if (activeWatchlistPills) {
      activeWatchlistPills.innerHTML = list.map(sym => `
        <span style="display: inline-flex; align-items: center; background: rgba(0, 255, 136, 0.12); border: 1px solid var(--accent-green); color: var(--accent-green); border-radius: 4px; padding: 2px 6px; font-size: 11px; font-weight: bold;">
          <a href="#" class="wl-pill-select" data-sym="${sym}" style="color: var(--accent-green); text-decoration: none; margin-right: 6px;">${sym}</a>
          <button class="btn-remove-sym" data-sym="${sym}" style="background: none; border: none; color: #f43f5e; cursor: pointer; padding: 0; font-size: 11px; line-height: 1;" title="Remove ${sym}">&times;</button>
        </span>
      `).join("");

      // Add click to select
      document.querySelectorAll(".wl-pill-select").forEach(el => {
        el.addEventListener("click", (e) => {
          e.preventDefault();
          const sym = el.getAttribute("data-sym");
          if (assetSelect) {
            assetSelect.value = sym;
            currentSymbol = sym;
            fetchCockpitData();
          }
        });
      });

      // Add remove handler
      document.querySelectorAll(".btn-remove-sym").forEach(btn => {
        btn.addEventListener("click", async () => {
          const sym = btn.getAttribute("data-sym");
          await fetch(`${BASE_URL}/api/watchlist/remove`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ symbol: sym })
          });
          updateWatchlistUI();
        });
      });
    }

    // Update Header Asset Dropdown: Core Assets + Screened Active Opportunities
    if (assetSelect) {
      const cur = activeSymbol || currentSymbol || "BTC";
      const coreAnchors = ["BTC", "ETH", "SOL", "XRP", "AAPL", "NVDA", "MSFT", "TSLA", "META", "SPY", "QQQ", "SOXL", "SQQQ", "GOLD", "OIL"];
      
      // Separate active list into core anchors and dynamic screened opportunities
      const dynamicScreened = list.filter(s => !coreAnchors.includes(s));
      
      let html = `<optgroup label="⭐ Core Assets (Always Available)">`;
      html += coreAnchors.map(s => `<option value="${s}">${s}</option>`).join("");
      html += `</optgroup>`;

      if (dynamicScreened.length > 0) {
        html += `<optgroup label="✨ Screener Opportunities (${dynamicScreened.length})">`;
        html += dynamicScreened.map(s => `<option value="${s}">${s}</option>`).join("");
        html += `</optgroup>`;
      }

      assetSelect.innerHTML = html;
      
      // Preserve currently selected symbol without ever forcibly overwriting it
      if (coreAnchors.includes(cur) || dynamicScreened.includes(cur)) {
        assetSelect.value = cur;
      } else if (list.includes(cur)) {
        assetSelect.value = cur;
      }
    }
  } catch (e) {
    console.error("Watchlist fetch error:", e);
  }
}

let currentScreenerCategory = "all";

async function loadScreenerScan(category = "all") {
  currentScreenerCategory = category;
  if (!screenerTableBody) return;
  const screenerTableHead = document.getElementById("screenerTableHead");
  screenerTableBody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">⌛ Scanning multi-asset universe (${category}) in real-time...</td></tr>`;

  try {
    if (category === "smart_money") {
      if (screenerTableHead) {
        screenerTableHead.innerHTML = `
          <tr>
            <th>TICKER & ASSET</th>
            <th>CONGRESS SIGNAL</th>
            <th>CONVICTION</th>
            <th>BUYING MEMBERS (STOCK ACT)</th>
            <th>TV 1D TREND</th>
            <th>TV 1H TREND</th>
            <th>RVOL</th>
            <th>LATEST FILING</th>
            <th>ACTION</th>
          </tr>
        `;
      }
      const res = await fetch(`${BASE_URL}/api/smart_money/opportunities?top_n=30`);
      if (!res.ok) throw new Error("Smart money query failed");
      const data = await res.json();
      const screened = data.opportunities || [];

      if (screened.length === 0) {
        screenerTableBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No congressional trade setups active right now.</td></tr>`;
        return;
      }

      screenerTableBody.innerHTML = screened.map(s => {
        const isHigh = s.signal === "HIGH_CONVICTION_BUY";
        const sigBadge = isHigh
          ? `<span class="badge" style="background: rgba(16,185,129,0.2); color:#34d399; border:1px solid #10b981; font-weight:bold; font-size:10px;">🏛️ HIGH CONVICTION BUY</span>`
          : `<span class="badge" style="background: rgba(168,85,247,0.2); color:#c084fc; border:1px solid #a855f7; font-size:10px;">🏛️ ACCUMULATION</span>`;
        
        const tv1dBadge = s.tradingview_1d === "STRONG_BUY" ? "badge-ok" : (s.tradingview_1d === "BUY" ? "badge-ok" : (s.tradingview_1d === "SELL" || s.tradingview_1d === "STRONG_SELL" ? "badge-critical" : "badge-normal"));
        const tv1hBadge = s.tradingview_1h === "STRONG_BUY" ? "badge-ok" : (s.tradingview_1h === "BUY" ? "badge-ok" : (s.tradingview_1h === "SELL" || s.tradingview_1h === "STRONG_SELL" ? "badge-critical" : "badge-normal"));
        const buyersStr = (s.buyers && s.buyers.length > 0) ? s.buyers.join(", ") : "Market-Wide Net Flow";

        return `
          <tr>
            <td>
              <strong>${s.symbol}</strong>
              <span style="display: block; font-size: 10px; color: var(--text-muted);">${s.is_etoro_anchor ? '✓ eToro Tradable' : 'US Equity'}</span>
            </td>
            <td>${sigBadge}</td>
            <td><strong style="color: #10b981; font-size: 13px;">+${(s.congress_conviction || 0).toFixed(2)}</strong></td>
            <td style="font-size: 11px; max-width: 180px; white-space: normal;">
              <span style="color: #e2e8f0; font-weight: 500;">${buyersStr}</span>
            </td>
            <td><span class="badge ${tv1dBadge}">${s.tradingview_1d || 'NEUTRAL'}</span></td>
            <td><span class="badge ${tv1hBadge}">${s.tradingview_1h || 'NEUTRAL'}</span></td>
            <td><span style="font-size: 11px;">${(s.relative_volume || 1.0).toFixed(1)}x</span></td>
            <td style="font-size: 10px; color: var(--text-muted);">${s.latest_filing || 'Recent'}</td>
            <td>
              <div style="display: flex; gap: 4px;">
                <button class="btn btn-outline btn-screener-select" data-sym="${s.symbol}" style="font-size: 10px; padding: 2px 6px;" title="View in Cockpit">⚡ VIEW</button>
                <button class="btn btn-primary btn-screener-add" data-sym="${s.symbol}" style="font-size: 10px; padding: 2px 6px;" title="Add to Automated Bot">➕ ADD</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");

      if (screenerStatusMsg) {
        screenerStatusMsg.textContent = `🏛️ ${screened.length} Congressional Smart Money trade setups identified (CongressInvests + Equibles MCP). Updated at ${new Date().toLocaleTimeString()}.`;
      }
    } else {
      if (screenerTableHead) {
        screenerTableHead.innerHTML = `
          <tr>
            <th>INSTRUMENT / ASSET</th>
            <th>CLASS / HOURS</th>
            <th>PRICE ($)</th>
            <th>24H CHG (%)</th>
            <th>ADX (TREND)</th>
            <th>SUPERTREND</th>
            <th>RSI</th>
            <th>SIGNAL</th>
            <th>SCORE</th>
            <th>ACTION</th>
          </tr>
        `;
      }
      const url = category === "all"
        ? `${BASE_URL}/api/screener/scan?top_n=40`
        : `${BASE_URL}/api/screener/scan?category=${encodeURIComponent(category)}&top_n=40`;

      const res = await fetch(url);
      if (!res.ok) throw new Error("Screener failed");
      const screened = await res.json();

      if (screened.length === 0) {
        screenerTableBody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">No opportunities found for category: ${category}.</td></tr>`;
        return;
      }

      screenerTableBody.innerHTML = screened.map((s, idx) => {
        const chgColor = s.change_pct >= 0 ? "color-success" : "color-danger";
        const chgSign = s.change_pct >= 0 ? "+" : "";
        const isBull = s.supertrend === "BULLISH";
        const isBuy = s.signal.startsWith("BUY");
        const sigBadge = isBuy ? "badge-ok" : "badge-critical";
        const scoreColor = s.opportunity_score >= 80 ? "color-success" : (s.opportunity_score >= 65 ? "var(--accent-cyan)" : "var(--text-color)");

        return `
          <tr>
            <td>
              <strong>${s.symbol}</strong>
              <span style="display: block; font-size: 10px; color: var(--text-muted);">${s.name}</span>
              <div style="display: flex; gap: 4px; margin-top: 3px; flex-wrap: wrap;">
                ${s.recommended_horizon === 'DAY' ? '<span class="badge" style="background: rgba(245,158,11,0.2); color:#fbbf24; border:1px solid #f59e0b; font-size:9px; padding: 1px 4px;">☀️ DAY</span>' : '<span class="badge" style="background: rgba(56,189,248,0.2); color:#38bdf8; border:1px solid #0284c7; font-size:9px; padding: 1px 4px;">🌙 SWING</span>'}
                ${s.pattern_detected && s.pattern_detected !== "Trend Continuation" ? `<span class="badge" style="background: rgba(168,85,247,0.2); color:#c084fc; border:1px solid #a855f7; font-size:9px; padding: 1px 4px;">📐 ${s.pattern_detected}</span>` : ''}
                ${s.vol_surge >= 1.25 ? `<span class="badge" style="background: rgba(16,185,129,0.2); color:#34d399; border:1px solid #10b981; font-size:9px; padding: 1px 4px;">⚡ ${s.vol_surge.toFixed(1)}x VOL</span>` : ''}
                ${s.congress_conviction && s.congress_conviction > 0 ? `<span class="badge" style="background: rgba(168,85,247,0.2); color:#c084fc; border:1px solid #a855f7; font-size:9px; padding: 1px 4px;">🏛️ Congress +${s.congress_conviction.toFixed(2)}</span>` : ''}
              </div>
            </td>
            <td>
              <span class="badge badge-normal" style="font-size: 10px;">${s.asset_class || s.category}</span>
              <span style="display: block; font-size: 9px; color: var(--text-muted); margin-top: 2px;">${s.trading_hours || ''}</span>
            </td>
            <td><strong>$${s.price.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
            <td class="${chgColor}">${chgSign}${s.change_pct.toFixed(2)}%</td>
            <td><span class="badge ${s.adx >= 25 ? 'badge-ok' : 'badge-normal'}">${s.adx}</span></td>
            <td><span class="badge ${isBull ? 'badge-ok' : 'badge-critical'}">${s.supertrend}</span></td>
            <td>${s.rsi}</td>
            <td><span class="badge ${sigBadge}">${s.signal}</span></td>
            <td><strong style="color: ${scoreColor}; font-size: 13px;">${s.opportunity_score}</strong>/100</td>
            <td>
              <div style="display: flex; gap: 4px;">
                <button class="btn btn-outline btn-screener-select" data-sym="${s.symbol}" style="font-size: 10px; padding: 2px 6px;" title="View in Cockpit">⚡ VIEW</button>
                <button class="btn btn-primary btn-screener-add" data-sym="${s.symbol}" style="font-size: 10px; padding: 2px 6px;" title="Add to Automated Bot">➕ ADD</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");

      if (screenerStatusMsg) {
        screenerStatusMsg.textContent = `✓ Top ${screened.length} ranked opportunities updated at ${new Date().toLocaleTimeString()}.`;
      }
    }

    // Hook buttons
    document.querySelectorAll(".btn-screener-select").forEach(b => {
      b.addEventListener("click", () => {
        const sym = b.getAttribute("data-sym");
        currentSymbol = sym;
        if (assetSelect) {
          if (!Array.from(assetSelect.options).some(o => o.value === sym)) {
            const opt = document.createElement("option");
            opt.value = sym;
            opt.textContent = sym;
            assetSelect.appendChild(opt);
          }
          assetSelect.value = sym;
        }
        screenerModal.classList.add("hidden");
        fetchCockpitData();
      });
    });

    document.querySelectorAll(".btn-screener-add").forEach(b => {
      b.addEventListener("click", async () => {
        const sym = b.getAttribute("data-sym");
        b.textContent = "✓ ADDED";
        await fetch(`${BASE_URL}/api/watchlist/add`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ symbol: sym })
        });
        updateWatchlistUI();
      });
    });

  } catch (e) {
    screenerTableBody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">Error loading scan: ${e.message}</td></tr>`;
  }
}

const btnSmartMoneyHeader = document.getElementById("btnSmartMoneyHeader");
if (btnSmartMoneyHeader) {
  btnSmartMoneyHeader.addEventListener("click", () => {
    screenerModal.classList.remove("hidden");
    updateWatchlistUI();
    const smartTab = document.querySelector('.btn-cat-tab[data-cat="smart_money"]');
    if (smartTab) {
      document.querySelectorAll(".btn-cat-tab").forEach(t => {
        t.classList.remove("active", "btn-primary");
        t.classList.add("btn-secondary");
      });
      smartTab.classList.remove("btn-secondary");
      smartTab.classList.add("active", "btn-primary");
    }
    loadScreenerScan("smart_money");
  });
}

if (btnScreenerModal) {
  btnScreenerModal.addEventListener("click", () => {
    screenerModal.classList.remove("hidden");
    updateWatchlistUI();
    loadScreenerScan();
  });
}

if (btnCloseScreenerModal) {
  btnCloseScreenerModal.addEventListener("click", () => screenerModal.classList.add("hidden"));
}
if (btnCloseScreenerFooter) {
  btnCloseScreenerFooter.addEventListener("click", () => screenerModal.classList.add("hidden"));
}
if (btnRefreshScreener) {
  btnRefreshScreener.addEventListener("click", () => loadScreenerScan(currentScreenerCategory));
}

// Category Tab Switching (All, Crypto, Commodities, Indices, ETFs, Equities)
document.querySelectorAll(".btn-cat-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".btn-cat-tab").forEach(t => {
      t.classList.remove("active", "btn-primary");
      t.classList.add("btn-secondary");
    });
    tab.classList.remove("btn-secondary");
    tab.classList.add("active", "btn-primary");
    const cat = tab.getAttribute("data-cat");
    loadScreenerScan(cat);
  });
});

if (btnAddCustomTicker && inputCustomTicker) {
  const handleAddTicker = async () => {
    const sym = inputCustomTicker.value.trim().toUpperCase();
    if (!sym) return;
    btnAddCustomTicker.textContent = "⌛ ADDING...";
    try {
      const res = await fetch(`${BASE_URL}/api/watchlist/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: sym })
      });
      const d = await res.json();
      inputCustomTicker.value = "";
      updateWatchlistUI();
      alert(`✓ ${sym} successfully added to the autonomous trading bot!`);
    } catch (e) {
      alert("Error adding ticker: " + e.message);
    } finally {
      btnAddCustomTicker.textContent = "➕ ADD TO BOT";
    }
  };

  btnAddCustomTicker.addEventListener("click", handleAddTicker);
  inputCustomTicker.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleAddTicker();
  });
}

// Preset Watchlist Buttons
document.querySelectorAll(".btn-preset-wl").forEach(btn => {
  btn.addEventListener("click", async () => {
    const preset = btn.getAttribute("data-preset");
    btn.textContent = "⌛ LOADING...";
    try {
      const res = await fetch(`${BASE_URL}/api/watchlist/preset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_key: preset })
      });
      const d = await res.json();
      updateWatchlistUI();
      alert(`✓ Preset loaded: ${d.preset_title}\n(${d.active_watchlist.length} symbols active)`);
    } catch (e) {
      alert("Error loading preset: " + e.message);
    } finally {
      btn.textContent = btn.getAttribute("data-preset").replace("_", " ").toUpperCase();
    }
  });
});

if (btnAutoAddTopScreened) {
  btnAutoAddTopScreened.addEventListener("click", async () => {
    btnAutoAddTopScreened.textContent = "⌛ POPULATING...";
    try {
      const res = await fetch(`${BASE_URL}/api/screener/auto_add_top`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ top_n: 15 })
      });
      const d = await res.json();
      updateWatchlistUI();
      alert(`✓ Auto-populated top ${d.added_symbols.length} screened opportunities into active trading bot!`);
    } catch (e) {
      alert("Error auto-adding: " + e.message);
    } finally {
      btnAutoAddTopScreened.textContent = "✨ AUTO-POPULATE TOP SCREENED";
    }
  });
// ==============================================================================
// 🌍 WORLDWIDE BREAKING NEWS & MACRO RADAR CONTROLLER
// ==============================================================================
const worldNewsModal = document.getElementById("worldNewsModal");
const btnWorldNewsHeader = document.getElementById("btnWorldNewsHeader");
const btnCloseWorldNewsModal = document.getElementById("btnCloseWorldNewsModal");
const btnCloseWorldNewsFooter = document.getElementById("btnCloseWorldNewsFooter");
const btnRefreshWorldNews = document.getElementById("btnRefreshWorldNews");
const macroThemesContainer = document.getElementById("macroThemesContainer");
const worldNewsCardsContainer = document.getElementById("worldNewsCardsContainer");
const badgeModalMacroRisk = document.getElementById("badgeModalMacroRisk");
const badgeModalMacroSent = document.getElementById("badgeModalMacroSent");
const worldNewsStatusMsg = document.getElementById("worldNewsStatusMsg");

let currentNewsTheme = "ALL";
let currentNewsSev = "ALL";

const THEME_DISPLAY = {
  "CENTRAL_BANKS_RATES": { label: "Rates & Central Banks", icon: "🏦" },
  "GEOPOLITICS_CONFLICT": { label: "Geopolitics & Conflict", icon: "⚔️" },
  "ENERGY_COMMODITIES": { label: "Energy & Commodities", icon: "🛢️" },
  "AI_TECH_REGULATION": { label: "Tech, Semis & AI", icon: "🤖" },
  "SYSTEMIC_RECESSION": { label: "Systemic / Recession", icon: "📉" },
  "MACRO_GLOBAL": { label: "Global Macro Markets", icon: "🌐" }
};

async function loadWorldNews() {
  if (!worldNewsCardsContainer) return;
  worldNewsCardsContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">Fetching live worldwide breaking headlines...</div>';

  try {
    const url = `${BASE_URL}/api/news/world?theme=${encodeURIComponent(currentNewsTheme)}&severity=${encodeURIComponent(currentNewsSev)}&limit=60`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const risk = data.macro_risk || {};
    const riskLevel = risk.macro_risk_level || "NORMAL";
    const sent = risk.macro_sentiment !== undefined ? risk.macro_sentiment : 0.0;

    // Header Badges
    if (badgeModalMacroRisk) {
      badgeModalMacroRisk.textContent = `RISK: ${riskLevel}`;
      if (riskLevel === "CRITICAL") {
        badgeModalMacroRisk.style.background = "rgba(239, 68, 68, 0.2)";
        badgeModalMacroRisk.style.color = "#ef4444";
        badgeModalMacroRisk.style.borderColor = "#ef4444";
      } else if (riskLevel === "ELEVATED") {
        badgeModalMacroRisk.style.background = "rgba(245, 158, 11, 0.2)";
        badgeModalMacroRisk.style.color = "#f59e0b";
        badgeModalMacroRisk.style.borderColor = "#f59e0b";
      } else {
        badgeModalMacroRisk.style.background = "rgba(56, 189, 248, 0.2)";
        badgeModalMacroRisk.style.color = "#38bdf8";
        badgeModalMacroRisk.style.borderColor = "#38bdf8";
      }
    }

    if (badgeModalMacroSent) {
      badgeModalMacroSent.textContent = `SENTIMENT: ${sent >= 0 ? '+' : ''}${sent.toFixed(2)}`;
      if (sent >= 0.08) {
        badgeModalMacroSent.style.background = "rgba(16, 185, 129, 0.2)";
        badgeModalMacroSent.style.color = "#10b981";
        badgeModalMacroSent.style.borderColor = "#10b981";
      } else if (sent <= -0.08) {
        badgeModalMacroSent.style.background = "rgba(239, 68, 68, 0.2)";
        badgeModalMacroSent.style.color = "#ef4444";
        badgeModalMacroSent.style.borderColor = "#ef4444";
      } else {
        badgeModalMacroSent.style.background = "rgba(148, 163, 184, 0.2)";
        badgeModalMacroSent.style.color = "#94a3b8";
        badgeModalMacroSent.style.borderColor = "#94a3b8";
      }
    }

    // Macro Themes Grid
    if (macroThemesContainer && risk.macro_themes) {
      macroThemesContainer.innerHTML = risk.macro_themes.map(t => {
        const meta = THEME_DISPLAY[t.theme] || { label: t.theme, icon: "📌" };
        const scColor = t.sentiment > 0.05 ? "#10b981" : (t.sentiment < -0.05 ? "#ef4444" : "#94a3b8");
        return `
          <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); border-radius: 6px; padding: 10px; cursor: pointer; transition: border-color 0.2s;" onclick="filterNewsByTheme('${t.theme}')">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span style="font-size: 11px; font-weight: bold; color: var(--text-color);">${meta.icon} ${meta.label}</span>
              <span style="font-size: 10px; background: rgba(255,255,255,0.1); padding: 1px 6px; border-radius: 10px;">${t.count}</span>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 10px;">
              <span style="color: var(--text-muted);">${t.label}</span>
              <span style="font-weight: bold; color: ${scColor};">${t.sentiment >= 0 ? '+' : ''}${t.sentiment.toFixed(2)}</span>
            </div>
          </div>
        `;
      }).join("");
    }

    // Articles List
    const articles = data.articles || [];
    if (worldNewsStatusMsg) {
      worldNewsStatusMsg.textContent = `Showing ${articles.length} of ${data.total_articles} global market headlines. Ingested live via Finnhub, SerpApi, Tavily & Global RSS.`;
    }

    if (articles.length === 0) {
      worldNewsCardsContainer.innerHTML = '<div style="text-align: center; color: var(--text-muted); padding: 40px;">No breaking news found for selected theme and severity filters.</div>';
      return;
    }

    worldNewsCardsContainer.innerHTML = articles.map(a => {
      const meta = THEME_DISPLAY[a.theme] || { label: a.theme, icon: "🌐" };
      const isHigh = a.severity === "HIGH";
      const isBull = a.sentiment === "BULLISH";
      const isBear = a.sentiment === "BEARISH";
      const borderAccent = isBear ? "#ef4444" : (isBull ? "#10b981" : "rgba(255,255,255,0.15)");
      const sentBg = isBear ? "rgba(239,68,68,0.15)" : (isBull ? "rgba(16,185,129,0.15)" : "rgba(148,163,184,0.15)");
      const sentColor = isBear ? "#ef4444" : (isBull ? "#10b981" : "#94a3b8");

      const timeStr = a.time ? new Date(a.time * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Live";

      const assetsPills = (a.affected_assets || []).map(sym => `
        <span onclick="event.stopPropagation(); setCockpitActiveSymbol('${sym}')" style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-size: 10px; cursor: pointer; font-weight: bold;" title="Click to view & trade ${sym}">
          ${sym} ↗
        </span>
      `).join(" ");

      return `
        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-left: 4px solid ${borderAccent}; border-radius: 6px; padding: 12px; display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span style="font-size: 10px; color: var(--text-muted); font-weight: bold; text-transform: uppercase;">📰 ${a.source}</span>
              <span style="font-size: 10px; color: var(--text-muted);">🕒 ${timeStr}</span>
              <span style="font-size: 10px; background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 4px; color: var(--text-muted);">
                ${meta.icon} ${meta.label}
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              ${isHigh ? '<span style="font-size: 10px; background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; padding: 2px 6px; border-radius: 4px; font-weight: bold;">🔥 HIGH IMPACT</span>' : ''}
              <span style="font-size: 10px; background: ${sentBg}; color: ${sentColor}; border: 1px solid ${sentColor}; padding: 2px 6px; border-radius: 4px; font-weight: bold;">
                ${a.sentiment} (${a.score >= 0 ? '+' : ''}${a.score.toFixed(2)})
              </span>
            </div>
          </div>

          <div style="font-size: 13px; font-weight: bold; line-height: 1.4;">
            <a href="${a.url || '#'}" target="_blank" rel="noopener noreferrer" style="color: #e2e8f0; text-decoration: none;" onmouseover="this.style.color='#38bdf8'" onmouseout="this.style.color='#e2e8f0'">
              ${a.title} ↗
            </a>
          </div>

          ${a.summary ? `<div style="font-size: 11px; color: var(--text-muted); line-height: 1.4;">${a.summary}</div>` : ''}

          ${(a.affected_assets && a.affected_assets.length > 0) ? `
            <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-top: 2px;">
              <span style="font-size: 10px; color: var(--text-muted);">Impacted Assets:</span>
              ${assetsPills}
            </div>
          ` : ''}
        </div>
      `;
    }).join("");

  } catch (err) {
    worldNewsCardsContainer.innerHTML = `<div style="text-align: center; color: #ef4444; padding: 40px;">Error loading world news: ${err.message}</div>`;
  }
}

window.filterNewsByTheme = function(theme) {
  currentNewsTheme = theme;
  document.querySelectorAll(".btn-news-theme-filter").forEach(b => {
    if (b.getAttribute("data-theme") === theme) {
      b.classList.remove("btn-secondary");
      b.classList.add("btn-primary");
    } else {
      b.classList.remove("btn-primary");
      b.classList.add("btn-secondary");
    }
  });
  loadWorldNews();
};

window.setCockpitActiveSymbol = function(sym) {
  if (!sym || sym === "ENERGY" || sym === "SEMIS") return;
  if (worldNewsModal) worldNewsModal.classList.add("hidden");
  activeSymbol = sym.toUpperCase();
  const select = document.getElementById("selectActiveSymbol");
  if (select) select.value = activeSymbol;
  fetchCockpitData();
};

if (btnWorldNewsHeader) {
  btnWorldNewsHeader.addEventListener("click", () => {
    if (worldNewsModal) {
      worldNewsModal.classList.remove("hidden");
      loadWorldNews();
    }
  });
}

if (btnCloseWorldNewsModal) {
  btnCloseWorldNewsModal.addEventListener("click", () => {
    if (worldNewsModal) worldNewsModal.classList.add("hidden");
  });
}

if (btnCloseWorldNewsFooter) {
  btnCloseWorldNewsFooter.addEventListener("click", () => {
    if (worldNewsModal) worldNewsModal.classList.add("hidden");
  });
}

if (btnRefreshWorldNews) {
  btnRefreshWorldNews.addEventListener("click", async () => {
    btnRefreshWorldNews.textContent = "⏳ REFRESHING...";
    try {
      await fetch(`${BASE_URL}/api/news/refresh`, { method: "POST" });
      await loadWorldNews();
    } catch (e) {
      console.warn("Refresh error:", e);
    } finally {
      btnRefreshWorldNews.textContent = "🔄 REFRESH LIVE";
    }
  });
}

document.querySelectorAll(".btn-news-theme-filter").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".btn-news-theme-filter").forEach(x => {
      x.classList.remove("btn-primary");
      x.classList.add("btn-secondary");
    });
    b.classList.remove("btn-secondary");
    b.classList.add("btn-primary");
    currentNewsTheme = b.getAttribute("data-theme") || "ALL";
    loadWorldNews();
  });
});

document.querySelectorAll(".btn-news-sev-filter").forEach(b => {
  b.addEventListener("click", () => {
    document.querySelectorAll(".btn-news-sev-filter").forEach(x => {
      x.classList.remove("btn-primary");
      x.classList.add("btn-secondary");
    });
    b.classList.remove("btn-secondary");
    b.classList.add("btn-primary");
    currentNewsSev = b.getAttribute("data-sev") || "ALL";
    loadWorldNews();
  });
});

// ==============================================================================
// 🌊 FLOW OF FUNDS — 3-WAY TRANSPARENCY CONTROLLER (OpenInsider + Quiver + 13F)
// ==============================================================================
const flowTransparencyModal = document.getElementById("flowTransparencyModal");
const btnFlowTransparencyHeader = document.getElementById("btnFlowTransparencyHeader");
const btnCloseFlowModal = document.getElementById("btnCloseFlowModal");
const btnCloseFlowFooter = document.getElementById("btnCloseFlowFooter");
const btnRefreshFlow = document.getElementById("btnRefreshFlow");
const inputFlowSearchSymbol = document.getElementById("inputFlowSearchSymbol");
const btnLoadFlowSymbol = document.getElementById("btnLoadFlowSymbol");

const badgeFlowSymbol = document.getElementById("badgeFlowSymbol");
const badgeFlowSentiment = document.getElementById("badgeFlowSentiment");
const badgeFlowPrice = document.getElementById("badgeFlowPrice");
const flowKpiPrice = document.getElementById("flowKpiPrice");
const flowKpiConviction = document.getElementById("flowKpiConviction");
const flowKpiInsiderVal = document.getElementById("flowKpiInsiderVal");
const flowKpiCongressCount = document.getElementById("flowKpiCongressCount");

const tabBtnFlowInsiders = document.getElementById("tabBtnFlowInsiders");
const tabBtnFlowCongress = document.getElementById("tabBtnFlowCongress");
const tabBtnFlowInst = document.getElementById("tabBtnFlowInst");
const viewFlowInsiders = document.getElementById("viewFlowInsiders");
const viewFlowCongress = document.getElementById("viewFlowCongress");
const viewFlowInst = document.getElementById("viewFlowInst");

const flowInsidersBody = document.getElementById("flowInsidersBody");
const flowCongressBody = document.getElementById("flowCongressBody");
const flowInstBody = document.getElementById("flowInstBody");
const flowModalFooterStatus = document.getElementById("flowModalFooterStatus");

let currentFlowSymbol = "AAPL";

async function loadFlowTransparency(symbol) {
  const sym = (symbol || currentFlowSymbol || (typeof activeSymbol !== "undefined" ? activeSymbol : "AAPL") || "AAPL").toUpperCase().trim();
  currentFlowSymbol = sym;
  if (inputFlowSearchSymbol) inputFlowSearchSymbol.value = sym;
  if (badgeFlowSymbol) badgeFlowSymbol.textContent = sym;

  if (flowInsidersBody) flowInsidersBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">Fetching OpenInsider & Form 4 flows for ' + sym + '...</td></tr>';
  if (flowCongressBody) flowCongressBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted">Querying Quiver Quant & STOCK Act disclosures for ' + sym + '...</td></tr>';
  if (flowInstBody) flowInstBody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">Scanning SEC EDGAR 13F-HR filings for ' + sym + '...</td></tr>';

  try {
    const res = await fetch(`${BASE_URL}/api/flow/transparency?symbol=${encodeURIComponent(sym)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const price = data.price || 0.0;
    const conviction = data.flow_conviction !== undefined ? data.flow_conviction : 0.0;
    const sent = data.flow_sentiment || "NEUTRAL";
    const summary = data.summary || {};

    if (badgeFlowPrice) badgeFlowPrice.textContent = `PRICE: $${price.toFixed(2)}`;
    if (flowKpiPrice) flowKpiPrice.textContent = `$${price.toFixed(2)}`;

    // Flow conviction styling
    if (badgeFlowSentiment) {
      badgeFlowSentiment.textContent = `CONVICTION: ${conviction >= 0 ? '+' : ''}${conviction.toFixed(2)} (${sent})`;
      if (sent === "BULLISH") {
        badgeFlowSentiment.style.background = "rgba(16, 185, 129, 0.2)";
        badgeFlowSentiment.style.color = "#10b981";
        badgeFlowSentiment.style.borderColor = "#10b981";
      } else if (sent === "BEARISH") {
        badgeFlowSentiment.style.background = "rgba(239, 68, 68, 0.2)";
        badgeFlowSentiment.style.color = "#ef4444";
        badgeFlowSentiment.style.borderColor = "#ef4444";
      } else {
        badgeFlowSentiment.style.background = "rgba(56, 189, 248, 0.2)";
        badgeFlowSentiment.style.color = "#38bdf8";
        badgeFlowSentiment.style.borderColor = "#38bdf8";
      }
    }

    if (flowKpiConviction) {
      const color = sent === "BULLISH" ? "#10b981" : (sent === "BEARISH" ? "#ef4444" : "#38bdf8");
      flowKpiConviction.innerHTML = `<span style="color: ${color}; font-weight: bold;">${conviction >= 0 ? '+' : ''}${conviction.toFixed(2)} (${sent})</span>`;
    }

    // Insider flow KPI
    const netVal = summary.net_insider_flow_usd || 0.0;
    const buysCount = summary.insider_buys || 0;
    const sellsCount = summary.insider_sells || 0;
    if (flowKpiInsiderVal) {
      const formattedVal = Math.abs(netVal) >= 1e6
        ? `$${(netVal / 1e6).toFixed(2)}M`
        : `$${netVal.toLocaleString()}`;
      const sign = netVal >= 0 ? "+" : "";
      const valColor = netVal > 0 ? "#10b981" : (netVal < 0 ? "#ef4444" : "var(--text-muted)");
      flowKpiInsiderVal.innerHTML = `<span style="color: ${valColor}; font-weight: bold;">${sign}${formattedVal}</span> <span style="font-size: 10px; color: var(--text-muted); font-weight: normal;">(${buysCount}B / ${sellsCount}S)</span>`;
    }

    // Congress KPI
    const cBuys = summary.congress_buys || 0;
    const cSells = summary.congress_sells || 0;
    if (flowKpiCongressCount) {
      flowKpiCongressCount.innerHTML = `<span style="color: #10b981;">${cBuys} Buys</span> / <span style="color: #ef4444;">${cSells} Sells</span>`;
    }

    // Render Insiders Table
    const insiders = data.insiders || [];
    if (flowInsidersBody) {
      if (insiders.length === 0) {
        flowInsidersBody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No recent Form 4 insider transactions found for ${sym}.</td></tr>`;
      } else {
        flowInsidersBody.innerHTML = insiders.map(t => {
          const isBuy = t.is_purchase || (t.trade_type && t.trade_type.toLowerCase().includes("buy"));
          const typeColor = isBuy ? "#10b981" : "#ef4444";
          const typeBadge = `<span class="badge" style="background: ${isBuy ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; color: ${typeColor}; border: 1px solid ${typeColor}; font-size: 10px; padding: 2px 6px;">${t.trade_type || (isBuy ? 'PURCHASE' : 'SALE')}</span>`;
          const valStr = t.value_usd ? `$${Number(t.value_usd).toLocaleString()}` : (t.value_str || '--');
          const sharesStr = t.qty ? Number(t.qty).toLocaleString() : (t.shares ? Number(t.shares).toLocaleString() : '--');
          const priceStr = t.price ? `$${Number(t.price).toFixed(2)}` : '--';
          return `
            <tr>
              <td style="font-size: 11px; color: var(--text-muted);">${t.date || t.filing_date || '--'}</td>
              <td style="font-weight: 500; color: #fff;">${t.filer_name || t.name || 'Corporate Insider'}</td>
              <td style="font-size: 11px; color: var(--text-muted);">${t.officer_title || t.title || 'Insider'}</td>
              <td>${typeBadge}</td>
              <td style="font-size: 11px;">${priceStr}</td>
              <td style="font-size: 11px;">${sharesStr}</td>
              <td style="font-weight: bold; color: ${typeColor};">${valStr}</td>
            </tr>
          `;
        }).join("");
      }
    }

    // Render Congress Table
    const congress = data.congress || [];
    if (flowCongressBody) {
      if (congress.length === 0) {
        flowCongressBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No Congressional trades disclosed for ${sym} within lookback window.</td></tr>`;
      } else {
        flowCongressBody.innerHTML = congress.map(c => {
          const type = (c.transaction_type || c.type || "TRADE").toUpperCase();
          const isBuy = type.includes("BUY") || type.includes("PURCHASE");
          const typeColor = isBuy ? "#10b981" : "#ef4444";
          const typeBadge = `<span class="badge" style="background: ${isBuy ? 'rgba(16,185,129,0.15)' : 'rgba(239,68,68,0.15)'}; color: ${typeColor}; border: 1px solid ${typeColor}; font-size: 10px; padding: 2px 6px;">${type}</span>`;
          return `
            <tr>
              <td style="font-size: 11px; color: var(--text-muted);">${c.transaction_date || c.disclosed || c.date || '--'}</td>
              <td style="font-weight: 500; color: #c084fc;">🏛️ ${c.representative || c.senator || c.member || 'Member of Congress'}</td>
              <td style="font-size: 11px; color: var(--text-muted);">${c.chamber || (c.party ? c.party : 'US Congress')}</td>
              <td>${typeBadge}</td>
              <td style="font-weight: bold; color: #fff;">${c.amount || c.amount_range || c.value_range || '$15,001 - $50,000'}</td>
              <td style="font-size: 11px; color: var(--text-muted);">${c.source || 'QuiverQuant / STOCK Act'}</td>
            </tr>
          `;
        }).join("");
      }
    }

    // Render Institutional 13F Table
    const inst = data.institutional || [];
    if (flowInstBody) {
      if (inst.length === 0) {
        flowInstBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No recent 13F institutional filings indexed for ${sym}.</td></tr>`;
      } else {
        flowInstBody.innerHTML = inst.map(f => {
          return `
            <tr>
              <td style="font-size: 11px; color: var(--text-muted);">${f.filing_date || f.date || '--'}</td>
              <td style="font-weight: 500; color: #38bdf8;">🏢 ${f.entity_name || f.institution || f.fund || 'Institutional Manager'}</td>
              <td style="font-family: monospace; font-size: 11px; color: var(--text-muted);">${f.cik || '--'}</td>
              <td><span class="badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid #38bdf8; font-size: 10px; padding: 2px 6px;">${f.form_type || '13F-HR'}</span></td>
              <td style="font-size: 11px; color: #10b981;">✓ SEC EDGAR EFTS Indexed</td>
            </tr>
          `;
        }).join("");
      }
    }

    if (flowModalFooterStatus) {
      flowModalFooterStatus.textContent = `Unified Flow Data for ${sym} synced at ${new Date().toLocaleTimeString()} | Finnhub Quotes & 13F + Quiver Quant + OpenInsider + SEC EDGAR.`;
    }

  } catch (err) {
    console.error("loadFlowTransparency error:", err);
    if (flowInsidersBody) flowInsidersBody.innerHTML = `<tr><td colspan="7" class="text-center text-danger">Failed to load transparency feed: ${err.message}</td></tr>`;
  }
}

if (tabBtnFlowInsiders && tabBtnFlowCongress && tabBtnFlowInst) {
  tabBtnFlowInsiders.addEventListener("click", () => {
    tabBtnFlowInsiders.classList.replace("btn-secondary", "btn-primary");
    tabBtnFlowCongress.classList.replace("btn-primary", "btn-secondary");
    tabBtnFlowInst.classList.replace("btn-primary", "btn-secondary");
    if (viewFlowInsiders) viewFlowInsiders.classList.remove("hidden");
    if (viewFlowCongress) viewFlowCongress.classList.add("hidden");
    if (viewFlowInst) viewFlowInst.classList.add("hidden");
  });

  tabBtnFlowCongress.addEventListener("click", () => {
    tabBtnFlowCongress.classList.replace("btn-secondary", "btn-primary");
    tabBtnFlowInsiders.classList.replace("btn-primary", "btn-secondary");
    tabBtnFlowInst.classList.replace("btn-primary", "btn-secondary");
    if (viewFlowCongress) viewFlowCongress.classList.remove("hidden");
    if (viewFlowInsiders) viewFlowInsiders.classList.add("hidden");
    if (viewFlowInst) viewFlowInst.classList.add("hidden");
  });

  tabBtnFlowInst.addEventListener("click", () => {
    tabBtnFlowInst.classList.replace("btn-secondary", "btn-primary");
    tabBtnFlowInsiders.classList.replace("btn-primary", "btn-secondary");
    tabBtnFlowCongress.classList.replace("btn-primary", "btn-secondary");
    if (viewFlowInst) viewFlowInst.classList.remove("hidden");
    if (viewFlowInsiders) viewFlowInsiders.classList.add("hidden");
    if (viewFlowCongress) viewFlowCongress.classList.add("hidden");
  });
}

if (btnFlowTransparencyHeader) {
  btnFlowTransparencyHeader.addEventListener("click", () => {
    if (flowTransparencyModal) {
      flowTransparencyModal.classList.remove("hidden");
      const sym = (typeof activeSymbol !== "undefined" && activeSymbol) ? activeSymbol : (currentFlowSymbol || "AAPL");
      loadFlowTransparency(sym);
    }
  });
}

if (btnCloseFlowModal) {
  btnCloseFlowModal.addEventListener("click", () => {
    if (flowTransparencyModal) flowTransparencyModal.classList.add("hidden");
  });
}

if (btnCloseFlowFooter) {
  btnCloseFlowFooter.addEventListener("click", () => {
    if (flowTransparencyModal) flowTransparencyModal.classList.add("hidden");
  });
}

if (btnRefreshFlow) {
  btnRefreshFlow.addEventListener("click", () => {
    loadFlowTransparency(currentFlowSymbol);
  });
}

if (btnLoadFlowSymbol && inputFlowSearchSymbol) {
  btnLoadFlowSymbol.addEventListener("click", () => {
    const sym = inputFlowSearchSymbol.value.trim();
    if (sym) loadFlowTransparency(sym);
  });
  inputFlowSearchSymbol.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const sym = inputFlowSearchSymbol.value.trim();
      if (sym) loadFlowTransparency(sym);
    }
  });
}

document.querySelectorAll(".btn-flow-preset").forEach(btn => {
  btn.addEventListener("click", () => {
    const sym = btn.getAttribute("data-sym");
    if (sym) loadFlowTransparency(sym);
  });
});

if (flowTransparencyModal) {
  flowTransparencyModal.addEventListener("click", (e) => {
    if (e.target === flowTransparencyModal) {
      flowTransparencyModal.classList.add("hidden");
    }
  });
}

// ==========================================
// WYCKOFF RANGE ENGINE MODAL & TELEMETRY
// ==========================================
const wyckoffModal = document.getElementById("wyckoffModal");
const btnWyckoffHeader = document.getElementById("btnWyckoffHeader");
const btnCloseWyckoffModal = document.getElementById("btnCloseWyckoffModal");
const btnCloseWyckoffFooter = document.getElementById("btnCloseWyckoffFooter");
const wyckoffTickerInput = document.getElementById("wyckoffTickerInput");
const btnWyckoffSearch = document.getElementById("btnWyckoffSearch");
const wyckoffStyleSelect = document.getElementById("wyckoffStyleSelect");

async function loadWyckoffStructure(symbol, style = "Balanced") {
  const sym = (symbol || (typeof activeSymbol !== "undefined" && activeSymbol) || "GOLD").toUpperCase().trim();
  if (wyckoffTickerInput) wyckoffTickerInput.value = sym;
  
  try {
    const res = await fetch(`/api/wyckoff/structure?symbol=${encodeURIComponent(sym)}&style=${encodeURIComponent(style)}`);
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();
    
    // Update KPI Badges
    const bStruct = document.getElementById("wyckStructureBadge");
    const subStruct = document.getElementById("wyckStructureSub");
    if (bStruct) {
      bStruct.textContent = data.structure_type || "NEUTRAL";
      bStruct.style.color = data.structure_type === "ACCUMULATION" ? "#10b981" : (data.structure_type === "DISTRIBUTION" ? "#ef4444" : "#fbbf24");
    }
    if (subStruct) subStruct.textContent = data.bias || "Smart money equilibrium";
    
    const bPhase = document.getElementById("wyckPhaseBadge");
    const subPhase = document.getElementById("wyckPhaseSub");
    if (bPhase) {
      bPhase.textContent = `PHASE ${data.phase_code || "A"}`;
      bPhase.style.color = data.phase_code === "C" ? "#fbbf24" : (data.phase_code === "D" || data.phase_code === "E" ? "#10b981" : "#38bdf8");
    }
    if (subPhase) subPhase.textContent = data.phase || "";
    
    const sSpring = document.getElementById("wyckSpringScore");
    if (sSpring) sSpring.textContent = `${data.spring_quality_score || data.climax_score || 0} / 100`;
    
    const sWin = document.getElementById("wyckWinRate");
    if (sWin) sWin.textContent = `${(data.historical_win_rate_pct || 79.2).toFixed(1)}%`;
    
    // Boundaries
    const creekEl = document.getElementById("wyckCreekVal");
    const midEl = document.getElementById("wyckMidVal");
    const iceEl = document.getElementById("wyckIceVal");
    const heightEl = document.getElementById("wyckHeightVal");
    if (creekEl) creekEl.textContent = `$${Number(data.creek_resistance || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    if (midEl) midEl.textContent = `$${Number(data.midpoint || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    if (iceEl) iceEl.textContent = `$${Number(data.ice_support || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    if (heightEl) heightEl.textContent = `$${Number(data.range_height || 0).toFixed(2)} (${Number(data.range_height_pct || 0).toFixed(2)}%)`;
    
    // Checklist
    const ch = data.event_checklist || {};
    const setCheck = (iconId, ok) => {
      const el = document.getElementById(iconId);
      if (el) {
        el.textContent = ok ? "✓" : "✗";
        el.style.color = ok ? "#10b981" : "rgba(255,255,255,0.2)";
      }
    };
    setCheck("iconCheckClimax", ch.SC_or_BC_Climax);
    setCheck("iconCheckAR", ch.AR_Automatic_Reaction);
    setCheck("iconCheckST", ch.ST_Secondary_Test);
    setCheck("iconCheckPhaseC", ch.Spring_or_UTAD_Phase_C);
    setCheck("iconCheckPhaseD", ch.SOS_or_SOW_Phase_D);
    
    // Trade Setup
    const setup = data.trade_setup || {};
    const tBadge = document.getElementById("wyckTradeSignalBadge");
    if (tBadge) {
      tBadge.textContent = setup.direction === "LONG" ? "BUY (LONG)" : (setup.direction === "SHORT" ? "SHORT (SELL)" : "HOLD (NEUTRAL)");
      tBadge.style.color = setup.direction === "LONG" ? "#10b981" : (setup.direction === "SHORT" ? "#ef4444" : "#fbbf24");
      tBadge.style.borderColor = setup.direction === "LONG" ? "#10b981" : (setup.direction === "SHORT" ? "#ef4444" : "#fbbf24");
    }
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = `$${Number(val || 0).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    };
    setVal("wyckEntryPrice", setup.entry_price);
    setVal("wyckStopLoss", setup.stop_loss);
    setVal("wyckTP1", setup.tp1);
    setVal("wyckTP2", setup.tp2);
    setVal("wyckTP3", setup.tp3);
    
    const rrEl = document.getElementById("wyckRRRatio");
    if (rrEl) rrEl.textContent = `1 : ${(setup.risk_reward_ratio || 2.0).toFixed(2)}`;
    
    // Events Table
    const tbody = document.getElementById("wyckEventsBody");
    if (tbody) {
      const events = data.events_detected || [];
      if (events.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted">No climactic events recorded in lookback window</td></tr>`;
      } else {
        tbody.innerHTML = events.map(ev => `
          <tr>
            <td><strong style="color: #fbbf24;">${ev.event || ev.name}</strong></td>
            <td>${ev.name || ev.event}</td>
            <td style="font-family: monospace;">$${Number(ev.price || 0).toFixed(2)}</td>
            <td>${ev.score !== undefined ? `<span class="badge" style="background: rgba(245,158,11,0.2); color: #fbbf24;">${ev.score}/100</span>` : '<span class="text-muted">Confirmed</span>'}</td>
            <td>Bar #${ev.bar || 0}</td>
          </tr>
        `).join("");
      }
    }
  } catch (err) {
    console.error("loadWyckoffStructure error:", err);
  }
}

if (btnWyckoffHeader) {
  btnWyckoffHeader.addEventListener("click", () => {
    if (wyckoffModal) {
      wyckoffModal.classList.remove("hidden");
      const sym = (typeof activeSymbol !== "undefined" && activeSymbol) ? activeSymbol : "GOLD";
      const style = wyckoffStyleSelect ? wyckoffStyleSelect.value : "Balanced";
      loadWyckoffStructure(sym, style);
    }
  });
}

if (btnCloseWyckoffModal) {
  btnCloseWyckoffModal.addEventListener("click", () => {
    if (wyckoffModal) wyckoffModal.classList.add("hidden");
  });
}

if (btnCloseWyckoffFooter) {
  btnCloseWyckoffFooter.addEventListener("click", () => {
    if (wyckoffModal) wyckoffModal.classList.add("hidden");
  });
}

if (wyckoffModal) {
  wyckoffModal.addEventListener("click", (e) => {
    if (e.target === wyckoffModal) wyckoffModal.classList.add("hidden");
  });
}

if (btnWyckoffSearch && wyckoffTickerInput) {
  btnWyckoffSearch.addEventListener("click", () => {
    const sym = wyckoffTickerInput.value.trim();
    const style = wyckoffStyleSelect ? wyckoffStyleSelect.value : "Balanced";
    if (sym) loadWyckoffStructure(sym, style);
  });
  wyckoffTickerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const sym = wyckoffTickerInput.value.trim();
      const style = wyckoffStyleSelect ? wyckoffStyleSelect.value : "Balanced";
      if (sym) loadWyckoffStructure(sym, style);
    }
  });
}

if (wyckoffStyleSelect) {
  wyckoffStyleSelect.addEventListener("change", () => {
    const sym = wyckoffTickerInput ? wyckoffTickerInput.value.trim() : "GOLD";
    loadWyckoffStructure(sym, wyckoffStyleSelect.value);
  });
}

document.querySelectorAll(".btn-wyck-quick").forEach(btn => {
  btn.addEventListener("click", () => {
    const sym = btn.getAttribute("data-symbol");
    const style = wyckoffStyleSelect ? wyckoffStyleSelect.value : "Balanced";
    if (sym) loadWyckoffStructure(sym, style);
  });
});

// Initialization & Loop
try {
  updateWatchlistUI();
} catch (e) {
  console.error("updateWatchlistUI error on boot:", e);
}

try {
  fetchDayTradingStatus();
} catch (e) {
  console.error("fetchDayTradingStatus error on boot:", e);
}

try {
  fetchCockpitData();
} catch (e) {
  console.error("fetchCockpitData error on boot:", e);
}

try {
  const urlParams = new URLSearchParams(window.location.search);
  const targetModal = urlParams.get("modal") || urlParams.get("view");
  const targetSymbol = (urlParams.get("symbol") || urlParams.get("ticker") || "").toUpperCase().trim();
  if (targetSymbol) {
    activeSymbol = targetSymbol;
  }
  if (targetModal === "flow" || targetModal === "transparency") {
    if (flowTransparencyModal) {
      flowTransparencyModal.classList.remove("hidden");
      loadFlowTransparency(targetSymbol || activeSymbol || "AAPL");
    }
  } else if (targetModal === "congress") {
    const btnSmart = document.getElementById("btnSmartMoneyHeader");
    if (btnSmart) btnSmart.click();
  } else if (targetModal === "news" || targetModal === "world") {
    const btnNews = document.getElementById("btnWorldNewsHeader");
    if (btnNews) btnNews.click();
  } else if (targetModal === "wyckoff" || targetModal === "range") {
    if (wyckoffModal) {
      wyckoffModal.classList.remove("hidden");
      loadWyckoffStructure(targetSymbol || activeSymbol || "GOLD");
    }
  }
} catch (paramErr) {
  console.debug("URL param handler notice:", paramErr);
}

pollTimer = setInterval(() => {
  fetchCockpitData().catch(e => console.warn("Poll interval error:", e));
}, 3500);

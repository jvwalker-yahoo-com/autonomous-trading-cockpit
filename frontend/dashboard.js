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
let isPolling = true;
let pollTimer = null;

// DOM Elements Cache
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
  btnManualBuy: document.getElementById("btnManualBuy"),
  btnManualShort: document.getElementById("btnManualShort"),
  btnManualClose: document.getElementById("btnManualClose"),
  settingsModal: document.getElementById("settingsModal"),
  btnCloseModal: document.getElementById("btnCloseModal"),
  btnSaveConfig: document.getElementById("btnSaveConfig"),
  inputFinnhubKey: document.getElementById("inputFinnhubKey"),
  selectSimMode: document.getElementById("selectSimMode"),
  inputRiskPct: document.getElementById("inputRiskPct")
};

// ==========================================
// POLLING & DATA REFRESH
// ==========================================

async function fetchCockpitData() {
  try {
    const url = `${BASE_URL}/api/cockpit/snapshot?symbol=${activeSymbol}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    const data = await res.json();
    renderCockpit(data);
  } catch (err) {
    console.warn("Cockpit telemetry poll error:", err);
    el.pillSyncDrift.textContent = "OFFLINE";
    el.pillSyncDrift.className = "pill-val color-danger";
  }
}

function renderCockpit(data) {
  const { quote, state, decision, federation, arbitration, anomaly, quadrant, portfolio, learning, heartbeat, sync_drift, node_events } = data;

  // 1. Header & Quick Telemetry
  if (quote) {
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
    el.posCountBadge.textContent = `${portfolio.open_positions.length} OPEN`;
    if (portfolio.open_positions.length === 0) {
      el.positionsTableBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No active open positions. Autonomous scanner analyzing opportunities...</td></tr>`;
    } else {
      el.positionsTableBody.innerHTML = portfolio.open_positions.map(p => {
        const isLong = p.direction === "LONG";
        const pnlColor = p.unrealized_pnl_usd >= 0 ? "color-success" : "color-danger";
        return `
          <tr>
            <td><strong>${p.symbol}</strong></td>
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

// ==========================================
// ACTIONS & CONTROLS
// ==========================================

async function triggerManualTrade(action) {
  try {
    const res = await fetch(`${BASE_URL}/api/action/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol: activeSymbol,
        action: action,
        amount_usd: 500.0
      })
    });
    if (res.ok) {
      await fetchCockpitData();
    } else {
      const err = await res.json();
      alert(`Trade failed: ${err.detail || "Unknown error"}`);
    }
  } catch (err) {
    alert(`Execution error: ${err.message}`);
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
el.symbolSelect.addEventListener("change", (e) => {
  activeSymbol = e.target.value;
  fetchCockpitData();
});

el.btnTickStep.addEventListener("click", async () => {
  el.btnTickStep.textContent = "⌛ STEPPING...";
  try {
    await fetch(`${BASE_URL}/api/action/tick?symbol=${activeSymbol}`, { method: "POST" });
    await fetchCockpitData();
  } finally {
    el.btnTickStep.textContent = "⚡ STEP";
  }
});

el.btnManualBuy.addEventListener("click", () => triggerManualTrade("BUY"));
el.btnManualShort.addEventListener("click", () => triggerManualTrade("SHORT"));
el.btnManualClose.addEventListener("click", () => triggerManualTrade("CLOSE"));

el.btnResetPortfolio.addEventListener("click", async () => {
  if (confirm("Reset simulation portfolio back to initial $10,000 capital and reset learning history?")) {
    await fetch(`${BASE_URL}/api/portfolio/reset`, { method: "POST" });
    await fetchCockpitData();
  }
});

// Settings Modal
el.btnSettings.addEventListener("click", () => {
  el.settingsModal.classList.remove("hidden");
});

el.btnCloseModal.addEventListener("click", () => {
  el.settingsModal.classList.add("hidden");
});

el.btnSaveConfig.addEventListener("click", async () => {
  const finnhubKey = el.inputFinnhubKey.value.trim();
  const simMode = el.selectSimMode.value === "true";
  const riskPct = parseFloat(el.inputRiskPct.value) / 100.0;

  await fetch(`${BASE_URL}/api/config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      finnhub_api_key: finnhubKey || null,
      simulation_mode: simMode,
      risk_per_trade_pct: riskPct
    })
  });

  el.settingsModal.classList.add("hidden");
  alert("Configuration saved successfully!");
  fetchCockpitData();
});

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

if (btnBacktestModal) {
  btnBacktestModal.addEventListener("click", () => {
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
          <td><small>${t.rationale}</small></td>
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

// Initialization & Loop
fetchCockpitData();
pollTimer = setInterval(fetchCockpitData, 1500);

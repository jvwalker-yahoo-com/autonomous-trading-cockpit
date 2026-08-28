"""
Pydantic schemas and data transfer models for the Autonomous Trading Engine
and Predictive Execution Cockpit.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone

def utc_now_str() -> str:
    return datetime.now(timezone.utc).isoformat()

class RegimeState(BaseModel):
    risk: float = Field(..., description="Risk metric clamp(0, 1)")
    impact: float = Field(..., description="Market impact metric clamp(0, 1)")
    slippage: float = Field(..., description="Slippage metric clamp(0, 1)")
    latency: float = Field(..., description="Latency metric in ms")
    score: float = Field(..., description="Combined regime score (risk+impact+slippage)/3")
    mode: str = Field(..., description="OK, WARN, or CRITICAL")
    trend: str = Field("CHOPPY", description="BULL_TREND, BEAR_TREND, or CHOPPY")
    events: List[str] = Field(default_factory=list, description="Recent state events")
    timestamp: str = Field(default_factory=utc_now_str)

class ModelSignal(BaseModel):
    name: str
    signal: str # "BUY", "SELL", "SHORT", "NEUTRAL"
    score: float # -1.0 to 1.0
    weight: float # Dynamic adaptive weight (0.0 to 1.0)
    rationale: str

class FederationOutput(BaseModel):
    outputs: Dict[str, float] = Field(..., description="Raw model scores (-1 to +1)")
    weights: Dict[str, float] = Field(..., description="Current adaptive model weights")
    federation: str = Field(..., description="Aggregated winning model / strategy name")
    federated_score: float = Field(..., description="Weighted ensemble score (-1 to 1)")
    model_details: List[ModelSignal] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utc_now_str)

class ArbitrationOutput(BaseModel):
    main_mode: str = Field(..., description="Input regime mode")
    final_mode: str = Field(..., description="Arbitrated final mode (OK, WARN, HALTED)")
    approved: bool = Field(..., description="Whether trading execution is permitted")
    risk_gate_passed: bool = True
    drawdown_ok: bool = True
    exposure_ok: bool = True
    circuit_breaker_active: bool = False
    reasons: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utc_now_str)

class DecisionOutput(BaseModel):
    symbol: str
    signal: str # "BUY", "SELL", "SHORT", "HOLD"
    main_mode: str
    finalMode: str
    target_shares: float # fractional shares
    allocated_usd: float
    confidence: float # 0.0 to 1.0
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rationale: str
    timestamp: str = Field(default_factory=utc_now_str)

class AnomalyDetectorOutput(BaseModel):
    risk_spike: bool = False
    impact_jump: bool = False
    slippage_jump: bool = False
    latency_spike: bool = False
    z_score_price: float = 0.0
    z_score_vol: float = 0.0
    anomaly_detected: bool = False
    anomalies: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=utc_now_str)

class QuadrantOutput(BaseModel):
    quadrant: str = Field(..., description="LOW, MEDIUM, HIGH, or CRITICAL")
    risk_level: str = "LOW"
    impact_level: str = "LOW"
    description: str = ""
    timestamp: str = Field(default_factory=utc_now_str)

class HeartbeatOutput(BaseModel):
    alive: bool = True
    timestamp: str = Field(default_factory=utc_now_str)
    uptime_seconds: float = 0.0
    status: str = "healthy"

class SyncDriftOutput(BaseModel):
    drift_ms: int = 0
    status: str = "OK" # "OK" or "DRIFTING"
    market_open: bool = True
    exchange_time: str = ""
    timestamp: str = Field(default_factory=utc_now_str)

class Position(BaseModel):
    id: str
    symbol: str
    direction: str # "LONG" or "SHORT"
    shares: float # Fractional share count (e.g. 0.354 shares)
    entry_price: float
    current_price: float
    cost_basis_usd: float
    market_value_usd: float
    unrealized_pnl_usd: float
    unrealized_pnl_pct: float
    stop_loss: float
    take_profit: float
    entry_time: str
    rationale: str
    contributing_models: Dict[str, float] = Field(default_factory=dict)

class TradeRecord(BaseModel):
    id: str
    symbol: str
    direction: str # "LONG" or "SHORT"
    shares: float # Fractional shares
    entry_price: float
    exit_price: float
    cost_basis_usd: float
    exit_value_usd: float
    realized_pnl_usd: float
    realized_pnl_pct: float
    win: bool
    entry_time: str
    exit_time: str
    entry_rationale: str
    exit_rationale: str
    contributing_models: Dict[str, float] = Field(default_factory=dict)
    mistake_analysis: Optional[str] = None

class MistakeLogEntry(BaseModel):
    timestamp: str
    trade_id: str
    symbol: str
    direction: str
    pnl_usd: float
    primary_failure_cause: str
    adaptation_action: str
    adjusted_weights: Dict[str, float]

class LearningStatsOutput(BaseModel):
    strategy_weights: Dict[str, float]
    total_trades_evaluated: int
    win_rate_pct: float
    avg_win_usd: float
    avg_loss_usd: float
    profit_factor: float
    mistake_history: List[MistakeLogEntry]
    learning_rate: float
    last_calibration_time: str

class PortfolioSummary(BaseModel):
    cash: float
    equity: float
    initial_capital: float
    total_realized_pnl_usd: float
    total_realized_pnl_pct: float
    unrealized_pnl_usd: float
    win_count: int
    loss_count: int
    total_trades: int
    win_rate_pct: float
    profit_factor: float
    max_drawdown_pct: float
    open_positions: List[Position]
    active_symbol: str
    simulation_mode: bool

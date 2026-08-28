"""
Application configuration for the Autonomous Stock Trading System.
Supports loading from environment variables with sensible production and simulation defaults.
"""
import os
from pathlib import Path
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class SystemConfig(BaseModel):
    # API credentials
    finnhub_api_key: str = os.getenv("FINNHUB_API_KEY", "")
    
    # Mode & Execution
    simulation_mode: bool = os.getenv("SIMULATION_MODE", "true").lower() in ("true", "1", "yes")
    execution_loop_interval: float = float(os.getenv("EXECUTION_LOOP_INTERVAL", "2.0")) # seconds
    
    # Portfolio & Sizing
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "10000.0"))
    max_position_size_usd: float = float(os.getenv("MAX_POSITION_SIZE_USD", "1500.0"))
    risk_per_trade_pct: float = float(os.getenv("RISK_PER_TRADE_PCT", "0.02")) # 2% max risk per trade
    max_portfolio_exposure_pct: float = float(os.getenv("MAX_PORTFOLIO_EXPOSURE_PCT", "0.75")) # Max 75% deployed
    max_drawdown_limit_pct: float = float(os.getenv("MAX_DRAWDOWN_LIMIT_PCT", "0.15")) # 15% circuit breaker
    
    # Trading Rules
    default_stop_loss_pct: float = float(os.getenv("DEFAULT_STOP_LOSS_PCT", "0.025")) # 2.5%
    default_take_profit_pct: float = float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", "0.050")) # 5.0%
    slippage_bps: float = float(os.getenv("SIM_SLIPPAGE_BPS", "5.0")) # 5 bps simulated slippage
    spread_pct: float = float(os.getenv("SIM_SPREAD_PCT", "0.0005")) # 0.05% eToro spread simulation
    
    # Target Watchlist (High Beta Equities, Leveraged ETFs & Mega-caps)
    watchlist: List[str] = [
        "MARA", "IREN", "SOXL", "TQQQ", "MSFT", "META", "APLD", "SPY", "QQQ", "BULL", "URA", "HOOD", "SOFI"
    ]
    
    # Storage & Persistence
    db_path: str = str(DATA_DIR / "trading_state.json")

config = SystemConfig()

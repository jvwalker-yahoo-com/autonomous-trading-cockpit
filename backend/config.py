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
    
    # Official eToro API Credentials
    etoro_api_key: str = os.getenv("ETORO_API_KEY", "")
    etoro_user_key: str = os.getenv("ETORO_USER_KEY", "")
    etoro_base_url: str = os.getenv("ETORO_BASE_URL", "https://public-api.etoro.com")
    
    # Mode & Execution ('demo' = Virtual Simulation & Self-Learning, 'live' = Real eToro API Execution)
    execution_mode: str = os.getenv("EXECUTION_MODE", "demo").lower() # 'demo' or 'live'
    simulation_mode: bool = os.getenv("SIMULATION_MODE", "true").lower() in ("true", "1", "yes")
    execution_loop_interval: float = float(os.getenv("EXECUTION_LOOP_INTERVAL", "2.0")) # seconds
    
    # Portfolio & Sizing (Calibrated for £1,000 GBP / ~$1,300 USD account)
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "1300.0")) # £1,000 GBP ≈ $1,300 USD
    max_position_size_usd: float = float(os.getenv("MAX_POSITION_SIZE_USD", "200.0")) # ~15% max per position
    risk_per_trade_pct: float = float(os.getenv("RISK_PER_TRADE_PCT", "0.02")) # 2% max risk per trade ($26 max risk)
    max_portfolio_exposure_pct: float = float(os.getenv("MAX_PORTFOLIO_EXPOSURE_PCT", "0.75")) # Max 75% deployed
    max_drawdown_limit_pct: float = float(os.getenv("MAX_DRAWDOWN_LIMIT_PCT", "0.15")) # 15% circuit breaker
    
    # Trading Rules
    default_stop_loss_pct: float = float(os.getenv("DEFAULT_STOP_LOSS_PCT", "0.025")) # 2.5%
    default_take_profit_pct: float = float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", "0.050")) # 5.0%
    slippage_bps: float = float(os.getenv("SIM_SLIPPAGE_BPS", "5.0")) # 5 bps simulated slippage
    spread_pct: float = float(os.getenv("SIM_SPREAD_PCT", "0.0005")) # 0.05% eToro spread simulation
    
    # eToro UK Trading Hours Restriction (14:30 to 21:00 UK Time / 09:30 - 16:00 US EST, Monday - Friday)
    enforce_market_hours: bool = os.getenv("ENFORCE_MARKET_HOURS", "true").lower() in ("true", "1", "yes")
    market_open_hour_utc: int = 13 # 13:30 UTC = 14:30 UK BST (09:30 US EST)
    market_open_minute_utc: int = 30
    market_close_hour_utc: int = 20 # 20:00 UTC = 21:00 UK BST (16:00 US EST)
    market_close_minute_utc: int = 0
    
    # Target Watchlist (High Beta Equities, Leveraged ETFs & Mega-caps)
    watchlist: List[str] = [
        "MARA", "IREN", "SOXL", "TQQQ", "MSFT", "META", "APLD", "SPY", "QQQ", "BULL", "URA", "HOOD", "SOFI"
    ]
    auto_rotate_universe: bool = os.getenv("AUTO_ROTATE_UNIVERSE", "true").lower() in ("true", "1", "yes")
    universe_scan_interval_sec: float = float(os.getenv("UNIVERSE_SCAN_INTERVAL_SEC", "30.0"))
    
    # Email Reporting (PDF Delivery to lisawalker6898@gmail.com)
    report_recipient_email: str = os.getenv("REPORT_RECIPIENT_EMAIL", "lisawalker6898@gmail.com")
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_pass: str = os.getenv("SMTP_PASS", "")
    smtp_sender: str = os.getenv("SMTP_SENDER", "Autonomous Cockpit <reports@autonomous-trading-cockpit.com>")
    auto_email_at_market_close: bool = os.getenv("AUTO_EMAIL_REPORTS", "true").lower() in ("true", "1", "yes")

    # Storage & Persistence
    db_path: str = str(DATA_DIR / "trading_state.json")

config = SystemConfig()



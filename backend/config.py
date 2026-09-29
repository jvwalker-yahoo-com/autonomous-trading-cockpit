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
    execution_mode: str = os.getenv("EXECUTION_MODE", "live").lower() # 'demo' or 'live' (permanently live by default unless user explicitly switches to demo)
    simulation_mode: bool = (os.getenv("SIMULATION_MODE", "false").lower() in ("true", "1", "yes")) if os.getenv("SIMULATION_MODE") is not None else (os.getenv("EXECUTION_MODE", "live").lower() != "live")
    execution_loop_interval: float = float(os.getenv("EXECUTION_LOOP_INTERVAL", "5.0")) # seconds
    
    # Portfolio & Sizing (Calibrated for £1,000 GBP / ~$1,300 USD account)
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "1300.0")) # £1,000 GBP ≈ $1,300 USD
    max_position_size_usd: float = float(os.getenv("MAX_POSITION_SIZE_USD", "250.0")) # ~19% max per position
    risk_per_trade_pct: float = float(os.getenv("RISK_PER_TRADE_PCT", "0.02")) # 2% max risk per trade ($26 max risk)
    max_portfolio_exposure_pct: float = float(os.getenv("MAX_PORTFOLIO_EXPOSURE_PCT", "0.85")) # Max 85% deployed
    max_drawdown_limit_pct: float = float(os.getenv("MAX_DRAWDOWN_LIMIT_PCT", "0.15")) # 15% circuit breaker
    max_concurrent_positions: int = int(os.getenv("MAX_CONCURRENT_POSITIONS", "15")) # Max 15 concurrent open positions
    
    # Trading Rules (Long-Term / Swing Trades)
    default_stop_loss_pct: float = float(os.getenv("DEFAULT_STOP_LOSS_PCT", "0.025")) # 2.5%
    default_take_profit_pct: float = float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", "0.050")) # 5.0%
    min_conviction_score: float = float(os.getenv("MIN_CONVICTION_SCORE", "0.60"))  # JEV confidence gate: 60% calibrated probability
    jev_confidence_gate: float = float(os.getenv("JEV_CONFIDENCE_GATE", "0.60"))  # JEV: minimum calibrated probability to trade
    jev_kelly_fraction_cap: float = float(os.getenv("JEV_KELLY_FRACTION_CAP", "0.25"))  # Max Kelly fraction (quarter-Kelly)
    slippage_bps: float = float(os.getenv("SIM_SLIPPAGE_BPS", "5.0")) # 5 bps simulated slippage
    spread_pct: float = float(os.getenv("SIM_SPREAD_PCT", "0.0005")) # 0.05% eToro spread simulation
    
    # Day Trading & Intraday Execution Options (Integrated alongside Long-Term Trades)
    enable_day_trading: bool = os.getenv("ENABLE_DAY_TRADING", "true").lower() in ("true", "1", "yes")
    day_trade_allocation_pct: float = float(os.getenv("DAY_TRADE_ALLOCATION_PCT", "0.50")) # Max 50% of capital for day trades
    day_trade_max_active: int = int(os.getenv("DAY_TRADE_MAX_ACTIVE", "8")) # Max 8 simultaneous active day trades
    day_trade_stop_loss_pct: float = float(os.getenv("DAY_TRADE_STOP_LOSS_PCT", "0.012")) # 1.2% tighter stop for day trades
    day_trade_take_profit_pct: float = float(os.getenv("DAY_TRADE_TAKE_PROFIT_PCT", "0.024")) # 2.4% take profit for 2:1 R:R
    day_trade_max_hold_hours: float = float(os.getenv("DAY_TRADE_MAX_HOLD_HOURS", "6.0")) # Max 6 hours holding time
    day_trade_eod_flatten_minutes_before_close: int = int(os.getenv("DAY_TRADE_EOD_FLATTEN_MINS", "15")) # 15 mins before market close
    
    # News Intelligence
    news_intel_refresh_interval_sec: float = float(os.getenv("NEWS_INTEL_REFRESH_SEC", "600.0"))  # 10 minutes
    news_intel_catalyst_weight: float = float(os.getenv("NEWS_INTEL_CATALYST_WEIGHT", "0.40"))   # 40% news weight in sentiment
    max_daily_loss_usd: float = float(os.getenv("MAX_DAILY_LOSS_USD", "35.0")) # $35.00 daily loss limit on £1,000/$1,300 account
    max_daily_loss_pct: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.025")) # 2.5% daily drawdown circuit breaker
    max_spread_pct_day_trade: float = float(os.getenv("MAX_SPREAD_PCT_DAY_TRADE", "0.0015")) # 0.15% (15 bps) spread threshold
    atr_volatility_sizing_enabled: bool = os.getenv("ATR_VOLATILITY_SIZING", "true").lower() in ("true", "1", "yes")
    
    # eToro UK Trading Hours Restriction (14:30 to 21:00 UK Time / 09:30 - 16:00 US EST, Monday - Friday)
    enforce_market_hours: bool = os.getenv("ENFORCE_MARKET_HOURS", "true").lower() in ("true", "1", "yes")
    market_open_hour_utc: int = 13 # 13:30 UTC = 14:30 UK BST (09:30 US EST)
    market_open_minute_utc: int = 30
    market_close_hour_utc: int = 20 # 20:00 UTC = 21:00 UK BST (16:00 US EST)
    market_close_minute_utc: int = 0
    
    # Target Watchlist — European Morning Coverage (UK100, GER40) + US Mega-Cap Tech Titans ($10 min, 0 crypto, 0 PRIIPs block)
    watchlist: List[str] = [
        "UK100", "GER40",
        "NVDA", "AAPL", "MSFT", "TSLA", "META", "AMZN", "GOOGL",
        "AMD", "PLTR", "ARM", "SMCI", "COIN", "MSTR", "HOOD",
        "SOFI", "ASTS", "RKLB", "LLY", "NFLX", "IREN"
    ]
    auto_rotate_universe: bool = os.getenv("AUTO_ROTATE_UNIVERSE", "true").lower() in ("true", "1", "yes")
    universe_scan_interval_sec: float = float(os.getenv("UNIVERSE_SCAN_INTERVAL_SEC", "60.0"))
    
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



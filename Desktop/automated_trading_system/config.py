"""
Central configuration for the Automated Trading System.
All tunable parameters are defined here for easy modification.

Supports: US Stocks (NYSE/NASDAQ) + Indian Stocks (NSE Nifty 50)
"""

import os
from datetime import datetime, timedelta

# ──────────────────────────────────────────────
#  General Settings
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "trading_system.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

# Load .env if available
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

# ──────────────────────────────────────────────
#  Market Presets
# ──────────────────────────────────────────────
MARKET_PRESET = os.getenv("MARKET_PRESET", "both")  # "us", "nifty50", "both", "custom"

# US Top 10
US_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
              "META", "NVDA", "JPM", "V", "JNJ"]

# Commodities (Futures via Yahoo Finance)
COMMODITY_SYMBOLS = [
    "GC=F",      # Gold Futures (COMEX)
    "SI=F",      # Silver Futures (COMEX)
]

# Indian commodity ETFs (NSE-listed, track gold/silver prices)
INDIA_COMMODITY_SYMBOLS = [
    "GOLDBEES.NS",     # Nippon India Gold BeES ETF
    "SILVERBEES.NS",   # Nippon India Silver ETF
]

# Nifty Indices
NIFTY_INDEX_SYMBOLS = [
    "^NSEI",           # Nifty 50 Index
    "^NSMIDCP",        # Nifty Midcap 150
    "NIFTY500MULTICAP5025.NS",  # Nifty 500 Multicap
]

# Nifty 50 (append .NS for yfinance)
NIFTY50_SYMBOLS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "BAJFINANCE.NS", "ASIANPAINT.NS", "MARUTI.NS",
    "TITAN.NS", "SUNPHARMA.NS", "TATAMOTORS.NS", "ULTRACEMCO.NS", "NESTLEIND.NS",
    "WIPRO.NS", "M&M.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS",
    "HCLTECH.NS", "ADANIENT.NS", "ADANIPORTS.NS", "BAJAJFINSV.NS", "TECHM.NS",
    "INDUSINDBK.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "HINDALCO.NS", "GRASIM.NS",
    "DRREDDY.NS", "CIPLA.NS", "COALINDIA.NS", "BPCL.NS", "EICHERMOT.NS",
    "APOLLOHOSP.NS", "DIVISLAB.NS", "HEROMOTOCO.NS", "TATACONSUM.NS", "SBILIFE.NS",
    "HDFCLIFE.NS", "BRITANNIA.NS", "BAJAJ-AUTO.NS", "UPL.NS", "LTIM.NS",
]

# Select active symbols based on preset
def _get_default_symbols():
    # Always include commodities and indices at top
    extra = COMMODITY_SYMBOLS + INDIA_COMMODITY_SYMBOLS + NIFTY_INDEX_SYMBOLS
    if MARKET_PRESET == "us":
        return extra + US_SYMBOLS
    elif MARKET_PRESET == "nifty50":
        return extra + NIFTY50_SYMBOLS
    elif MARKET_PRESET == "both":
        return extra + US_SYMBOLS + NIFTY50_SYMBOLS
    else:
        return extra + NIFTY50_SYMBOLS

DEFAULT_SYMBOLS = _get_default_symbols()

# ──────────────────────────────────────────────
#  Company Name Mapping
# ──────────────────────────────────────────────
SYMBOL_NAMES = {
    # Commodities
    "GC=F":          "Gold Futures (COMEX)",
    "SI=F":          "Silver Futures (COMEX)",
    "GOLDBEES.NS":   "Nippon India Gold BeES ETF",
    "SILVERBEES.NS": "Nippon India Silver ETF",
    # Indices
    "^NSEI":                     "Nifty 50 Index",
    "^NSMIDCP":                  "Nifty Midcap 150 Index",
    "NIFTY500MULTICAP5025.NS":   "Nifty 500 Multicap 50:25:25",
    # US Stocks
    "AAPL":  "Apple Inc.",
    "MSFT":  "Microsoft Corporation",
    "GOOGL": "Alphabet Inc. (Google)",
    "AMZN":  "Amazon.com Inc.",
    "TSLA":  "Tesla Inc.",
    "META":  "Meta Platforms Inc.",
    "NVDA":  "NVIDIA Corporation",
    "JPM":   "JPMorgan Chase & Co.",
    "V":     "Visa Inc.",
    "JNJ":   "Johnson & Johnson",
    "NFLX":  "Netflix Inc.",
    "DIS":   "The Walt Disney Company",
    "BA":    "Boeing Company",
    "AMD":   "Advanced Micro Devices Inc.",
    "INTC":  "Intel Corporation",
    "PYPL":  "PayPal Holdings Inc.",
    "UBER":  "Uber Technologies Inc.",
    "CRM":   "Salesforce Inc.",
    "ORCL":  "Oracle Corporation",
    "COST":  "Costco Wholesale Corporation",
    # Nifty 50 (NSE India)
    "RELIANCE.NS":   "Reliance Industries Ltd.",
    "TCS.NS":        "Tata Consultancy Services Ltd.",
    "HDFCBANK.NS":   "HDFC Bank Ltd.",
    "INFY.NS":       "Infosys Ltd.",
    "ICICIBANK.NS":  "ICICI Bank Ltd.",
    "HINDUNILVR.NS": "Hindustan Unilever Ltd.",
    "ITC.NS":        "ITC Ltd.",
    "SBIN.NS":       "State Bank of India",
    "BHARTIARTL.NS": "Bharti Airtel Ltd.",
    "KOTAKBANK.NS":  "Kotak Mahindra Bank Ltd.",
    "LT.NS":         "Larsen & Toubro Ltd.",
    "AXISBANK.NS":   "Axis Bank Ltd.",
    "BAJFINANCE.NS": "Bajaj Finance Ltd.",
    "ASIANPAINT.NS": "Asian Paints Ltd.",
    "MARUTI.NS":     "Maruti Suzuki India Ltd.",
    "TITAN.NS":      "Titan Company Ltd.",
    "SUNPHARMA.NS":  "Sun Pharmaceutical Industries Ltd.",
    "TATAMOTORS.NS": "Tata Motors Ltd.",
    "ULTRACEMCO.NS": "UltraTech Cement Ltd.",
    "NESTLEIND.NS":  "Nestle India Ltd.",
    "WIPRO.NS":      "Wipro Ltd.",
    "M&M.NS":        "Mahindra & Mahindra Ltd.",
    "NTPC.NS":       "NTPC Ltd.",
    "POWERGRID.NS":  "Power Grid Corporation of India Ltd.",
    "ONGC.NS":       "Oil & Natural Gas Corporation Ltd.",
    "HCLTECH.NS":    "HCL Technologies Ltd.",
    "ADANIENT.NS":   "Adani Enterprises Ltd.",
    "ADANIPORTS.NS": "Adani Ports & SEZ Ltd.",
    "BAJAJFINSV.NS": "Bajaj Finserv Ltd.",
    "TECHM.NS":      "Tech Mahindra Ltd.",
    "INDUSINDBK.NS": "IndusInd Bank Ltd.",
    "JSWSTEEL.NS":   "JSW Steel Ltd.",
    "TATASTEEL.NS":  "Tata Steel Ltd.",
    "HINDALCO.NS":   "Hindalco Industries Ltd.",
    "GRASIM.NS":     "Grasim Industries Ltd.",
    "DRREDDY.NS":    "Dr. Reddy's Laboratories Ltd.",
    "CIPLA.NS":      "Cipla Ltd.",
    "COALINDIA.NS":  "Coal India Ltd.",
    "BPCL.NS":       "Bharat Petroleum Corporation Ltd.",
    "EICHERMOT.NS":  "Eicher Motors Ltd.",
    "APOLLOHOSP.NS": "Apollo Hospitals Enterprise Ltd.",
    "DIVISLAB.NS":   "Divi's Laboratories Ltd.",
    "HEROMOTOCO.NS": "Hero MotoCorp Ltd.",
    "TATACONSUM.NS": "Tata Consumer Products Ltd.",
    "SBILIFE.NS":    "SBI Life Insurance Company Ltd.",
    "HDFCLIFE.NS":   "HDFC Life Insurance Company Ltd.",
    "BRITANNIA.NS":  "Britannia Industries Ltd.",
    "BAJAJ-AUTO.NS": "Bajaj Auto Ltd.",
    "UPL.NS":        "UPL Ltd.",
    "LTIM.NS":       "LTIMindtree Ltd.",
}

# Sector classification
SYMBOL_SECTORS = {
    # Commodities & Indices
    "GC=F": "Commodities", "SI=F": "Commodities",
    "GOLDBEES.NS": "Commodities", "SILVERBEES.NS": "Commodities",
    "^NSEI": "Index", "^NSMIDCP": "Index",
    "NIFTY500MULTICAP5025.NS": "Index",
    # Nifty 50
    "RELIANCE.NS": "Energy", "TCS.NS": "IT", "HDFCBANK.NS": "Banking",
    "INFY.NS": "IT", "ICICIBANK.NS": "Banking", "HINDUNILVR.NS": "FMCG",
    "ITC.NS": "FMCG", "SBIN.NS": "Banking", "BHARTIARTL.NS": "Telecom",
    "KOTAKBANK.NS": "Banking", "LT.NS": "Infrastructure", "AXISBANK.NS": "Banking",
    "BAJFINANCE.NS": "Finance", "ASIANPAINT.NS": "Consumer", "MARUTI.NS": "Auto",
    "TITAN.NS": "Consumer", "SUNPHARMA.NS": "Pharma", "TATAMOTORS.NS": "Auto",
    "ULTRACEMCO.NS": "Cement", "NESTLEIND.NS": "FMCG", "WIPRO.NS": "IT",
    "M&M.NS": "Auto", "NTPC.NS": "Power", "POWERGRID.NS": "Power",
    "ONGC.NS": "Energy", "HCLTECH.NS": "IT", "ADANIENT.NS": "Conglomerate",
    "ADANIPORTS.NS": "Infrastructure", "BAJAJFINSV.NS": "Finance", "TECHM.NS": "IT",
    "INDUSINDBK.NS": "Banking", "JSWSTEEL.NS": "Metals", "TATASTEEL.NS": "Metals",
    "HINDALCO.NS": "Metals", "GRASIM.NS": "Cement", "DRREDDY.NS": "Pharma",
    "CIPLA.NS": "Pharma", "COALINDIA.NS": "Mining", "BPCL.NS": "Energy",
    "EICHERMOT.NS": "Auto", "APOLLOHOSP.NS": "Healthcare", "DIVISLAB.NS": "Pharma",
    "HEROMOTOCO.NS": "Auto", "TATACONSUM.NS": "FMCG", "SBILIFE.NS": "Insurance",
    "HDFCLIFE.NS": "Insurance", "BRITANNIA.NS": "FMCG", "BAJAJ-AUTO.NS": "Auto",
    "UPL.NS": "Chemicals", "LTIM.NS": "IT",
    # US
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "AMZN": "Technology", "TSLA": "Auto", "META": "Technology",
    "NVDA": "Technology", "JPM": "Banking", "V": "Finance", "JNJ": "Healthcare",
}

# ──────────────────────────────────────────────
#  Market Hours
# ──────────────────────────────────────────────
# US Market (Eastern Time)
US_MARKET_OPEN_HOUR = 9
US_MARKET_CLOSE_HOUR = 16

# Indian Market (IST)
INDIA_MARKET_OPEN_HOUR = 9
INDIA_MARKET_OPEN_MINUTE = 15
INDIA_MARKET_CLOSE_HOUR = 15
INDIA_MARKET_CLOSE_MINUTE = 30

# Legacy aliases
MARKET_OPEN_HOUR = INDIA_MARKET_OPEN_HOUR if MARKET_PRESET in ("nifty50", "both") else US_MARKET_OPEN_HOUR
MARKET_CLOSE_HOUR = INDIA_MARKET_CLOSE_HOUR if MARKET_PRESET in ("nifty50", "both") else US_MARKET_CLOSE_HOUR

# ──────────────────────────────────────────────
#  Date Range
# ──────────────────────────────────────────────
DEFAULT_START_DATE = (datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d")  # 2 years back
DEFAULT_END_DATE = datetime.now().strftime("%Y-%m-%d")                           # today
DEFAULT_INTERVAL = "1d"  # 1d, 1h, 5m, etc.

# ──────────────────────────────────────────────
#  Auto-Update / Scheduler Settings
# ──────────────────────────────────────────────
AUTO_UPDATE_INTERVAL_MINUTES = 15
AUTO_UPDATE_LOG_FILE = os.path.join(BASE_DIR, "auto_update.log")

# ──────────────────────────────────────────────
#  Portfolio Settings
# ──────────────────────────────────────────────
INITIAL_CAPITAL = 100_000.0
COMMISSION_RATE = 0.001      # 0.1% per trade
SLIPPAGE_RATE = 0.0005       # 0.05% slippage

# Currency
CURRENCY = "INR" if MARKET_PRESET in ("nifty50", "both") else "USD"
CURRENCY_SYMBOL = "₹" if CURRENCY == "INR" else "$"

# ──────────────────────────────────────────────
#  Strategy Parameters
# ──────────────────────────────────────────────

# SMA Crossover
SMA_SHORT_WINDOW = 20
SMA_LONG_WINDOW = 50

# RSI Strategy
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# MACD Strategy
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9

# Bollinger Bands
BOLLINGER_WINDOW = 20
BOLLINGER_STD_DEV = 2

# SuperTrend
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

# Combined / Smart Auto
SMART_AUTO_MIN_AGREEMENT = 2  # Min strategies that must agree

# ──────────────────────────────────────────────
#  Risk Management Defaults
# ──────────────────────────────────────────────
RISK_STOP_LOSS_PCT = 3.0           # Exit if position drops 3%
RISK_TRAILING_STOP_PCT = 5.0       # Trailing stop at 5% from peak
RISK_TAKE_PROFIT_PCT = 10.0        # Take profit at 10% gain
RISK_MAX_DAILY_LOSS_PCT = 5.0      # Halt if daily loss > 5% of capital
RISK_MAX_POSITION_PCT = 20.0       # No single stock > 20% of portfolio
RISK_MAX_OPEN_POSITIONS = 5        # Max concurrent positions
RISK_COOLDOWN_HOURS = 4            # Don't re-enter same stock within 4 hours

# ──────────────────────────────────────────────
#  Broker Settings
# ──────────────────────────────────────────────
BROKER_TYPE = os.getenv("BROKER_TYPE", "paper")  # paper | zerodha | angel

# Zerodha Kite Connect
ZERODHA_API_KEY = os.getenv("ZERODHA_API_KEY", "")
ZERODHA_API_SECRET = os.getenv("ZERODHA_API_SECRET", "")
ZERODHA_USER_ID = os.getenv("ZERODHA_USER_ID", "")
ZERODHA_TOTP_SECRET = os.getenv("ZERODHA_TOTP_SECRET", "")

# Angel One SmartAPI
ANGEL_API_KEY = os.getenv("ANGEL_API_KEY", "")
ANGEL_CLIENT_ID = os.getenv("ANGEL_CLIENT_ID", "")
ANGEL_PASSWORD = os.getenv("ANGEL_PASSWORD", "")
ANGEL_TOTP_SECRET = os.getenv("ANGEL_TOTP_SECRET", "")

# ──────────────────────────────────────────────
#  Backtesting Settings
# ──────────────────────────────────────────────
RISK_FREE_RATE = 0.05        # 5% annual risk-free rate for Sharpe calc
TRADING_DAYS_PER_YEAR = 252

# ──────────────────────────────────────────────
#  Dashboard Settings
# ──────────────────────────────────────────────
DASHBOARD_PORT = 8501
DASHBOARD_THEME = "dark"


def get_symbol_name(symbol: str) -> str:
    """Get full company name for a ticker symbol."""
    return SYMBOL_NAMES.get(symbol, symbol)


def get_symbol_display(symbol: str) -> str:
    """Get display string: TICKER - Full Name."""
    name = SYMBOL_NAMES.get(symbol)
    return f"{symbol} - {name}" if name else symbol


def get_symbol_sector(symbol: str) -> str:
    """Get sector for a symbol."""
    return SYMBOL_SECTORS.get(symbol, "Other")


def is_indian_stock(symbol: str) -> bool:
    """Check if symbol is an Indian NSE stock."""
    return symbol.endswith(".NS")


def is_commodity(symbol: str) -> bool:
    """Check if symbol is a commodity futures ticker."""
    return symbol in COMMODITY_SYMBOLS or symbol in INDIA_COMMODITY_SYMBOLS


def is_index(symbol: str) -> bool:
    """Check if symbol is a market index."""
    return symbol in NIFTY_INDEX_SYMBOLS


def get_clean_ticker(symbol: str) -> str:
    """Remove .NS suffix for display purposes."""
    return symbol.replace(".NS", "") if symbol.endswith(".NS") else symbol

"""
TradePulse Dashboard — Premium Interactive Trading System with Authentication.

Pages:
    - Login / Sign Up (auth gate)
    - Market Overview — Candlestick charts with technical indicators
    - Signal Monitor — Recent signals across all strategies
    - Backtest Lab — Run backtests interactively
    - Auto Trade — Configure and monitor automated trading
    - Trade History — Full trade log
    - Portfolio — Current holdings and performance
"""

import sys
import os
import json
import base64
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import yfinance as yf
from streamlit_autorefresh import st_autorefresh
from database.db_manager import DatabaseManager
from data.fetcher import DataFetcher
from data.indicators import TechnicalIndicators
from strategy import STRATEGIES
from backtest.engine import BacktestEngine
from dashboard.auth import register_user, login_user, get_user_profile, validate_session_token, logout_user
import streamlit.components.v1 as components
from dashboard.views.market_watchlist import render as render_market_watchlist
from dashboard.views.smart_picks import render as render_smart_picks
from dashboard.views.broker_connect import render as render_broker_connect
from dashboard.views.risk_dashboard import render as render_risk_dashboard

# ──────────────────────────────────────────────
#  Page Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="TradePulse | Automated Trading",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# NOTE: Auto-refresh moved to per-page level (market_watchlist) to avoid full-page flash
# The global st_autorefresh was removed because it caused a dark screen flash on every refresh.

# ──────────────────────────────────────────────
#  Load Logo
# ──────────────────────────────────────────────
LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "logo.png")

def get_logo_base64():
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

LOGO_B64 = get_logo_base64()

# ──────────────────────────────────────────────
#  CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
        --bg-primary: #06080d;
        --bg-card: #111827;
        --border-subtle: rgba(255,255,255,0.06);
        --border-glow: rgba(0,212,170,0.25);
        --accent: #00d4aa;
        --accent-dim: rgba(0,212,170,0.15);
        --danger: #ff4757;
        --warning: #ffa502;
        --purple: #6c5ce7;
        --text-primary: #e8ecf1;
        --text-secondary: #8492a6;
        --text-muted: #5a6577;
    }
    * { font-family: 'Inter', -apple-system, sans-serif !important; }
    code, pre { font-family: 'JetBrains Mono', monospace !important; }
    .stApp { background: var(--bg-primary); }
    .main .block-container { padding-top: 1.5rem; max-width: 1400px; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #080b12 0%, #0c1018 40%, #0e1420 100%) !important;
        border-right: 1px solid var(--border-subtle) !important;
    }

    /* Brand Header */
    .brand-header {
        display: flex; align-items: center; gap: 12px;
        padding: 20px 16px 16px; margin-bottom: 8px;
        border-bottom: 1px solid var(--border-subtle);
    }
    .brand-header img { width: 42px; height: 42px; border-radius: 10px; }
    .brand-header .brand-text .brand-name {
        font-size: 20px; font-weight: 800;
        background: linear-gradient(135deg, #00d4aa, #00ffcc, #6c5ce7);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .brand-header .brand-text .brand-sub {
        font-size: 10px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 2.5px;
    }

    /* Nav */
    .nav-section-label {
        font-size: 10px; font-weight: 700; color: var(--text-muted);
        text-transform: uppercase; letter-spacing: 2px;
        padding: 16px 20px 6px; margin: 0;
    }
    /* Modern sidebar nav buttons */
    section[data-testid="stSidebar"] .stButton > button {
        background: transparent !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 10px 16px !important;
        margin: 1px 0 !important;
        width: 100% !important;
        text-align: left !important;
        font-weight: 500 !important;
        font-size: 13.5px !important;
        color: var(--text-secondary) !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
        justify-content: flex-start !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.04) !important;
        color: var(--text-primary) !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, rgba(0,212,170,0.12), rgba(108,92,231,0.08)) !important;
        border-left: 3px solid #00d4aa !important;
        color: #00d4aa !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 10px rgba(0,212,170,0.08) !important;
        padding: 10px 16px !important;
    }
    /* Hide Streamlit native multipage nav */
    div[data-testid="stSidebarNav"] { display: none !important; }
    nav[data-testid="stSidebarNav"] { display: none !important; }
    ul[data-testid="stSidebarNavItems"] { display: none !important; }

    /* Glass Card */
    .glass-card {
        background: linear-gradient(145deg, rgba(17,24,39,0.85), rgba(12,16,24,0.9));
        backdrop-filter: blur(16px); border: 1px solid var(--border-subtle);
        border-radius: 16px; padding: 22px 18px; text-align: center;
        position: relative; overflow: hidden;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .glass-card::before {
        content:''; position:absolute; top:0; left:0; right:0; height:3px;
        background: linear-gradient(90deg, transparent, var(--accent), transparent);
        opacity:0; transition: opacity 0.3s;
    }
    .glass-card:hover { transform: translateY(-3px); border-color: var(--border-glow);
        box-shadow: 0 10px 35px rgba(0,212,170,0.07); }
    .glass-card:hover::before { opacity:1; }
    .glass-card.accent-green::before { background: linear-gradient(90deg, transparent,#00d4aa,transparent); opacity:1; }
    .glass-card.accent-red::before { background: linear-gradient(90deg, transparent,#ff4757,transparent); opacity:1; }
    .glass-card.accent-blue::before { background: linear-gradient(90deg, transparent,#6c5ce7,transparent); opacity:1; }
    .glass-card.accent-amber::before { background: linear-gradient(90deg, transparent,#ffa502,transparent); opacity:1; }
    .card-label { font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:1.5px; margin-bottom:5px; }
    .card-value { font-size:28px; font-weight:800; color:var(--text-primary); line-height:1.1; margin-bottom:3px; }
    .card-sub { font-size:12px; font-weight:500; color:var(--text-secondary); }
    .val-green { color: var(--accent) !important; }
    .val-red { color: var(--danger) !important; }

    /* Page Title */
    .page-header h1 {
        font-size:30px; font-weight:800;
        background: linear-gradient(135deg, #e8ecf1, #a0aec0);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin:0;
    }
    .page-subtitle { font-size:14px; color:var(--text-secondary); margin-bottom:24px; }

    /* Section Title */
    .section-title { font-size:17px; font-weight:700; color:var(--text-primary);
        margin:32px 0 14px; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);
        display:flex; align-items:center; gap:8px; }
    .section-title .dot { width:7px; height:7px; border-radius:50%; background:var(--accent);
        box-shadow: 0 0 8px var(--accent); }

    /* Inputs */
    .stSelectbox label, .stMultiSelect label, .stDateInput label,
    .stNumberInput label, .stSlider label, .stTextInput label {
        color: var(--text-secondary) !important; font-weight:500 !important;
        font-size:12px !important; text-transform:uppercase !important; letter-spacing:0.5px !important;
    }
    .stSelectbox > div > div, .stTextInput > div > div {
        background-color: var(--bg-card) !important;
        border-color: var(--border-subtle) !important; border-radius:10px !important;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00d4aa, #00b894) !important;
        color: #06080d !important; font-weight:700 !important; border:none !important;
        border-radius:12px !important; padding:12px 28px !important;
        box-shadow: 0 4px 15px rgba(0,212,170,0.3) !important;
        transition: all 0.3s !important;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 25px rgba(0,212,170,0.45) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="secondary"] {
        background: transparent !important; border: 1px solid var(--border-subtle) !important;
        color: var(--text-primary) !important; border-radius:12px !important;
    }

    /* User pill */
    .user-pill {
        display:flex; align-items:center; gap:10px;
        padding: 10px 16px; margin: 0 8px 4px;
        background: rgba(0,212,170,0.06); border-radius:10px;
        border: 1px solid rgba(0,212,170,0.15);
    }
    .user-pill .user-avatar {
        width:32px; height:32px; border-radius:50%;
        background: linear-gradient(135deg, #00d4aa, #6c5ce7);
        display:flex; align-items:center; justify-content:center;
        font-weight:800; font-size:14px; color:#06080d;
    }
    .user-pill .user-info .user-name { font-size:13px; font-weight:600; color:var(--text-primary); }
    .user-pill .user-info .user-email { font-size:10px; color:var(--text-muted); }

    /* Sidebar stats */
    .sidebar-stat { display:flex; justify-content:space-between; padding:6px 20px; font-size:12px; }
    .sidebar-stat .stat-label { color:var(--text-muted); }
    .sidebar-stat .stat-value { color:var(--text-primary); font-weight:600; }

    /* Pulse dot */
    @keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.4;} }
    .live-dot { width:7px; height:7px; background:var(--accent); border-radius:50%;
        display:inline-block; animation:pulse 2s ease-in-out infinite; margin-right:5px; }

    /* Auth page */
    .auth-container { max-width:420px; margin:60px auto; padding:40px 36px;
        background: linear-gradient(145deg, rgba(17,24,39,0.9), rgba(12,16,24,0.95));
        border:1px solid var(--border-subtle); border-radius:20px;
        backdrop-filter: blur(20px); }
    .auth-logo { text-align:center; margin-bottom:28px; }
    .auth-logo img { width:64px; height:64px; border-radius:14px; margin-bottom:12px; }
    .auth-logo .auth-title { font-size:28px; font-weight:900;
        background: linear-gradient(135deg, #00d4aa, #6c5ce7);
        -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .auth-logo .auth-sub { font-size:12px; color:var(--text-muted); letter-spacing:2px; text-transform:uppercase; }

    /* Auto-trade status */
    .status-badge { display:inline-flex; align-items:center; gap:6px;
        padding:5px 14px; border-radius:20px; font-size:12px; font-weight:600; }
    .status-badge.active { background:rgba(0,212,170,0.15); color:#00d4aa; border:1px solid rgba(0,212,170,0.3); }
    .status-badge.inactive { background:rgba(255,71,87,0.1); color:#ff4757; border:1px solid rgba(255,71,87,0.2); }

    /* Hide ALL Streamlit default UI elements */
    #MainMenu { display:none !important; visibility:hidden !important; }
    header[data-testid="stHeader"] { display:none !important; height:0 !important; overflow:hidden !important; }
    footer { display:none !important; visibility:hidden !important; }
    /* Hide sidebar collapse / expand button — nuclear */
    button[data-testid="stSidebarCollapseButton"] { display:none !important; }
    button[data-testid="baseButton-headerNoPadding"] { display:none !important; }
    div[data-testid="collapsedControl"] { display:none !important; }
    /* Hide deploy button, toolbar, running indicator */
    .stDeployButton { display:none !important; }
    div[data-testid="stToolbar"] { display:none !important; }
    div[data-testid="stDecoration"] { display:none !important; }
    div[data-testid="stStatusWidget"] { display:none !important; }
    /* Material icon text leak (keyboard_double_arrow_left) */
    .material-symbols-outlined, .material-symbols-rounded { display:none !important; }
    span[data-icon], [data-testid="stSidebarNavCollapseIcon"] { display:none !important; }
    /* Catch-all for emotion-cache sidebar controls */
    .st-emotion-cache-1dp5vir, .st-emotion-cache-czk5ss,
    .st-emotion-cache-18ni7ap, .st-emotion-cache-h4xjwg,
    .st-emotion-cache-uf99v8, .st-emotion-cache-15ecox0,
    .st-emotion-cache-1egp75f, .st-emotion-cache-r421ms,
    .st-emotion-cache-1f3w014 { display:none !important; }
    /* Kill any top-right fixed/absolute positioned Streamlit chrome */
    header, [data-testid="stHeader"] { display:none !important; position:absolute !important; top:-9999px !important; }
    /* Sidebar top button area */
    section[data-testid="stSidebar"] > div:first-child > div:first-child > div:first-child > button { display:none !important; }
    section[data-testid="stSidebar"] button[kind="headerNoPadding"] { display:none !important; }
    /* Collapsed sidebar expand arrow */
    [data-testid="collapsedControl"] { display:none !important; width:0 !important; height:0 !important; overflow:hidden !important; }

    /* Empty state */
    .empty-state { text-align:center; padding:50px 20px; color:var(--text-muted); }
    .empty-state .empty-icon { font-size:44px; margin-bottom:14px; }
    .empty-state .empty-text { font-size:15px; font-weight:500; }
    .empty-state .empty-hint { font-size:12px; margin-top:6px; }
</style>
""", unsafe_allow_html=True)

# JavaScript to forcefully remove sidebar collapse buttons and any stray Streamlit chrome
st.markdown("""
<script>
(function() {
    function nukeStreamlitChrome() {
        // Remove sidebar collapse/expand buttons
        document.querySelectorAll(
            '[data-testid="collapsedControl"], ' +
            '[data-testid="stSidebarCollapseButton"], ' +
            'button[kind="headerNoPadding"], ' +
            '[data-testid="stToolbar"], ' +
            '[data-testid="stDecoration"], ' +
            '[data-testid="stStatusWidget"], ' +
            '.stDeployButton, ' +
            '[data-testid="stHeader"]'
        ).forEach(function(el) {
            el.style.display = 'none';
            el.style.visibility = 'hidden';
            el.style.height = '0';
            el.style.overflow = 'hidden';
            el.style.position = 'absolute';
            el.style.top = '-9999px';
        });
        // Remove any element containing 'keyboard_double' text
        document.querySelectorAll('button, span, div').forEach(function(el) {
            if (el.textContent && el.textContent.includes('keyboard_double')) {
                el.style.display = 'none';
                el.remove();
            }
        });
    }
    nukeStreamlitChrome();
    var observer = new MutationObserver(nukeStreamlitChrome);
    observer.observe(document.body, { childList: true, subtree: true });
    setInterval(nukeStreamlitChrome, 500);
})();
</script>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
#  Services (module-level singletons — one per server process)
# ──────────────────────────────────────────────
_db_instance = None
_fetcher_instance = None

def get_db_manager():
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
        _db_instance.init_db()
    return _db_instance

def get_fetcher():
    global _fetcher_instance
    if _fetcher_instance is None:
        _fetcher_instance = DataFetcher(db_manager=get_db_manager())
    return _fetcher_instance

db = get_db_manager()
fetcher = get_fetcher()

# ──────────────────────────────────────────────
#  Live Price Fetcher (near real-time via yfinance)
# ──────────────────────────────────────────────
@st.cache_data(ttl=5, show_spinner=False)  # 5s cache — near real-time
def get_live_price(symbol: str) -> dict:
    """Get near real-time price.

    Uses Ticker.info (regularMarketPrice) first — this is the quote-level
    price and is much closer to real-time, especially for commodity futures
    (GC=F, SI=F) where fast_info.lastPrice lags 10-15 min.
    Falls back to fast_info if .info fails.
    """
    try:
        ticker = yf.Ticker(symbol)
        price, prev = 0, 0
        day_high, day_low, market_cap = 0, 0, 0

        # --- primary: quote-level price (near real-time) ---
        try:
            info = ticker.info
            price = info.get("regularMarketPrice", 0) or 0
            prev  = info.get("regularMarketPreviousClose",
                     info.get("previousClose", 0)) or 0
            day_high = info.get("dayHigh", info.get("regularMarketDayHigh", 0)) or 0
            day_low  = info.get("dayLow", info.get("regularMarketDayLow", 0)) or 0
            market_cap = info.get("marketCap", 0) or 0
        except Exception:
            pass

        # --- fallback: fast_info ---
        if not price or price <= 0:
            fi = ticker.fast_info
            price = fi.get("lastPrice", 0) or fi.get("last_price", 0)
            prev  = fi.get("previousClose", 0) or fi.get("previous_close", 0)
            market_cap = fi.get("marketCap", fi.get("market_cap", 0))
            day_high = fi.get("dayHigh", fi.get("day_high", 0))
            day_low  = fi.get("dayLow", fi.get("day_low", 0))

        change = price - prev if price and prev else 0
        change_pct = (change / prev * 100) if prev else 0
        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "market_cap": market_cap,
            "day_high": round(day_high, 2) if day_high else 0,
            "day_low": round(day_low, 2) if day_low else 0,
        }
    except Exception:
        # Fallback to DB data
        data = fetcher.get_data_from_db(symbol)
        if not data.empty:
            latest = data.iloc[-1]
            prev = data.iloc[-2] if len(data) > 1 else latest
            change = latest["Close"] - prev["Close"]
            return {
                "price": round(latest["Close"], 2),
                "prev_close": round(prev["Close"], 2),
                "change": round(change, 2),
                "change_pct": round(change / prev["Close"] * 100, 2) if prev["Close"] else 0,
                "market_cap": 0, "day_high": round(latest["High"], 2),
                "day_low": round(latest["Low"], 2),
            }
        return {"price": 0, "prev_close": 0, "change": 0, "change_pct": 0,
                "market_cap": 0, "day_high": 0, "day_low": 0}

def get_live_prices_batch(symbols: list) -> dict:
    """Get live prices for multiple symbols."""
    results = {}
    for sym in symbols:
        results[sym] = get_live_price(sym)
    return results

# ──────────────────────────────────────────────
#  Auto-Refresh: update prices hourly
# ──────────────────────────────────────────────
REFRESH_INTERVAL_SECONDS = 3600  # 1 hour

def refresh_prices():
    """Fetch latest prices for all portfolio symbols + default symbols, update DB & portfolio."""
    import threading
    now = datetime.now()

    # Get symbols to update: portfolio positions + default symbols
    positions = db.get_portfolio()
    portfolio_symbols = [p.symbol for p in positions]
    all_symbols = list(set(config.DEFAULT_SYMBOLS + portfolio_symbols))

    updated = 0
    for sym in all_symbols:
        try:
            df = fetcher.fetch_latest_data(sym, period="5d")
            if not df.empty:
                latest_price = float(df.iloc[-1]["Close"])
                # Update portfolio if position exists
                for p in positions:
                    if p.symbol == sym:
                        db.update_portfolio(
                            symbol=sym,
                            quantity=p.quantity,
                            avg_cost=p.avg_cost,
                            current_price=latest_price,
                        )
                updated += 1
        except Exception:
            pass

    # Sync broker positions with latest prices
    broker = st.session_state.get("broker")
    if broker and broker.is_connected() and hasattr(broker, '_positions'):
        for sym, pos_data in broker._positions.items():
            data = fetcher.get_data_from_db(sym)
            if not data.empty:
                pos_data["current_price"] = float(data.iloc[-1]["Close"])

    st.session_state._last_price_refresh = now
    st.session_state._last_refresh_count = updated
    return updated

# Check if refresh is needed
if "_last_price_refresh" not in st.session_state:
    st.session_state._last_price_refresh = None
    st.session_state._last_refresh_count = 0

last_refresh = st.session_state._last_price_refresh
now = datetime.now()
if last_refresh is None or (now - last_refresh).total_seconds() >= REFRESH_INTERVAL_SECONDS:
    refresh_prices()  # Silent background refresh

SYMBOL_OPTIONS = [config.get_symbol_display(s) for s in config.DEFAULT_SYMBOLS]
SYMBOL_MAP = {config.get_symbol_display(s): s for s in config.DEFAULT_SYMBOLS}

def resolve_symbol(display_str):
    return SYMBOL_MAP.get(display_str, display_str.split(' - ')[0].strip())

def metric_card(label, value, accent="", sub="", val_class=""):
    ac = f"accent-{accent}" if accent else ""
    vc = f"val-{val_class}" if val_class else ""
    st.markdown(f"""<div class="glass-card {ac}">
        <div class="card-label">{label}</div>
        <div class="card-value {vc}">{value}</div>
        <div class="card-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8492a6"),
    margin=dict(l=50,r=20,t=40,b=20),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
)


# ══════════════════════════════════════════════
#  FILE-BASED SESSION PERSISTENCE
#  Bulletproof: survives every browser refresh, no JS cookies needed.
#  Stores session token in a local file that the server reads on load.
# ══════════════════════════════════════════════
_SESSION_FILE = os.path.join(config.BASE_DIR, ".session")

def _save_session_to_file(token: str, user_data: dict):
    """Write session to disk so it survives browser refresh."""
    try:
        payload = {
            "token": token,
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "full_name": user_data.get("full_name", ""),
            "email": user_data.get("email", ""),
        }
        with open(_SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception:
        pass

def _read_session_from_file() -> dict:
    """Read session from disk. Returns dict with token + user info, or empty dict."""
    try:
        if os.path.exists(_SESSION_FILE):
            with open(_SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def _clear_session_file():
    """Delete session file on logout."""
    try:
        if os.path.exists(_SESSION_FILE):
            os.remove(_SESSION_FILE)
    except Exception:
        pass

# ══════════════════════════════════════════════
#  BROKER STATE PERSISTENCE
# ══════════════════════════════════════════════
def _persist_broker_to_db():
    """Save current broker state to DB for persistence across refreshes."""
    broker = st.session_state.get("broker")
    user = st.session_state.get("user")
    if broker and user and broker.is_connected() and hasattr(broker, '_positions'):
        positions = {}
        for sym, data in broker._positions.items():
            positions[sym] = {
                "quantity": data["quantity"],
                "avg_cost": data["avg_cost"],
            }
        db.save_broker_state(
            user_id=user.get("user_id", 0),
            broker_type="paper" if not broker.is_live else "live",
            is_connected=True,
            cash=broker.cash,
            initial_capital=broker.initial_capital,
            positions=positions,
            daily_pnl=getattr(broker, '_daily_pnl', 0.0),
        )

def _restore_broker_from_db():
    """Restore broker from DB state if available."""
    user = st.session_state.get("user")
    if not user:
        return
    state = db.get_broker_state(user.get("user_id", 0))
    if state and state["is_connected"] and state["broker_type"] == "paper":
        from broker.paper import PaperBroker
        broker = PaperBroker(initial_capital=state["initial_capital"])
        broker.connect()
        broker.cash = state["cash"]
        broker._daily_pnl = state.get("daily_pnl", 0.0)
        for sym, pos_data in state.get("positions", {}).items():
            broker._positions[sym] = {
                "quantity": pos_data["quantity"],
                "avg_cost": pos_data["avg_cost"],
            }
        st.session_state["broker"] = broker

# ══════════════════════════════════════════════
#  AUTH GATE
# ══════════════════════════════════════════════
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None

# ── Try to restore session from file on refresh ──
if not st.session_state.authenticated:
    saved = _read_session_from_file()
    token = saved.get("token")
    if token:
        try:
            session = db.get_session()
            try:
                user_data = validate_session_token(session, token)
                if user_data:
                    st.session_state.authenticated = True
                    st.session_state.user = user_data
            finally:
                session.close()
        except Exception:
            # Stale session or DB schema mismatch — clear and let user login fresh
            _clear_session_file()

# ── Restore broker from DB if we just restored session ──
if st.session_state.authenticated and "broker" not in st.session_state:
    try:
        _restore_broker_from_db()
    except Exception:
        pass  # DB methods may not exist on cached manager — safe to skip

if not st.session_state.authenticated:
    # Auth page — no sidebar
    logo_html = f'<img src="data:image/png;base64,{LOGO_B64}" />' if LOGO_B64 else ''

    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        st.markdown(f"""
        <div class="auth-container">
            <div class="auth-logo">
                {logo_html}
                <div class="auth-title">TradePulse</div>
                <div class="auth-sub">Automated Trading Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        auth_tab = st.radio("Auth", ["Sign In", "Create Account"], horizontal=True, label_visibility="collapsed")

        if auth_tab == "Sign In":
            with st.form("login_form"):
                username = st.text_input("USERNAME")
                password = st.text_input("PASSWORD", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")

                if submitted:
                    if username and password:
                        session = db.get_session()
                        try:
                            result = login_user(session, username, password)
                            if result["success"]:
                                st.session_state.authenticated = True
                                st.session_state.user = result
                                _save_session_to_file(result["session_token"], result)
                                st.rerun()
                            else:
                                st.error(result["error"])
                        finally:
                            session.close()
                    else:
                        st.warning("Please fill in all fields")

        else:
            with st.form("signup_form"):
                full_name = st.text_input("FULL NAME")
                email = st.text_input("EMAIL")
                username = st.text_input("USERNAME")
                password = st.text_input("PASSWORD", type="password")
                confirm = st.text_input("CONFIRM PASSWORD", type="password")
                submitted = st.form_submit_button("Create Account", use_container_width=True, type="primary")

                if submitted:
                    if not all([full_name, email, username, password]):
                        st.warning("Please fill in all fields")
                    elif password != confirm:
                        st.error("Passwords do not match")
                    else:
                        session = db.get_session()
                        try:
                            result = register_user(session, username, email, password, full_name)
                            if result["success"]:
                                st.success("Account created! You can now sign in.")
                            else:
                                st.error(result["error"])
                        finally:
                            session.close()

    st.stop()


# ══════════════════════════════════════════════
#  SIDEBAR (authenticated)
# ══════════════════════════════════════════════
user = st.session_state.user

with st.sidebar:
    # Logo + brand
    logo_img = f'<img src="data:image/png;base64,{LOGO_B64}" />' if LOGO_B64 else ''
    st.markdown(f"""
    <div class="brand-header">
        {logo_img}
        <div class="brand-text">
            <div class="brand-name">TradePulse</div>
            <div class="brand-sub">Auto Trading</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # User pill
    initials = "".join([w[0] for w in user.get("full_name", "U").split()[:2]]).upper()
    st.markdown(f"""
    <div class="user-pill">
        <div class="user-avatar">{initials}</div>
        <div class="user-info">
            <div class="user-name">{user.get('full_name', user['username'])}</div>
            <div class="user-email">{user.get('email', '')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Nav — modern button-based
    NAV_ITEMS = [
        ("Markets", ["📊 Market Watchlist", "🧠 Smart Picks"]),
        ("Analysis", ["📡 Signal Monitor", "🧪 Backtest Lab"]),
        ("Trading", ["⚡ Auto Trade", "💰 Buy & Sell", "🔗 Broker Connect", "🛡️ Risk Dashboard"]),
        ("Account", ["📜 Trade History", "📁 Portfolio"]),
    ]

    if "_active_page" not in st.session_state:
        st.session_state._active_page = "📊 Market Watchlist"

    for group_label, pages in NAV_ITEMS:
        st.markdown(f'<p class="nav-section-label">{group_label}</p>', unsafe_allow_html=True)
        for page_name in pages:
            is_active = st.session_state._active_page == page_name
            btn_type = "primary" if is_active else "secondary"
            if st.button(page_name, key=f"nav_{page_name}", use_container_width=True, type=btn_type):
                st.session_state._active_page = page_name
                st.rerun()

    active_page = st.session_state._active_page

    # Stats
    perf = db.get_performance_summary()
    st.markdown("---")
    st.markdown(f"""
    <div class="sidebar-stat"><span class="stat-label"><span class="live-dot"></span>Signals</span><span class="stat-value">{perf['total_signals']}</span></div>
    <div class="sidebar-stat"><span class="stat-label">Trades</span><span class="stat-value">{perf['total_trades']}</span></div>
    <div class="sidebar-stat"><span class="stat-label">Win Rate</span><span class="stat-value">{perf['win_rate']:.0f}%</span></div>
    """, unsafe_allow_html=True)

    # Price refresh info with seconds
    lr = st.session_state.get("_last_price_refresh")
    lr_text = lr.strftime("%H:%M:%S") if lr else "Never"
    lr_count = st.session_state.get("_last_refresh_count", 0)
    # Calculate seconds since last refresh
    if lr:
        secs_ago = int((datetime.now() - lr).total_seconds())
        if secs_ago < 60:
            ago_text = f"{secs_ago}s ago"
        elif secs_ago < 3600:
            ago_text = f"{secs_ago // 60}m {secs_ago % 60}s ago"
        else:
            ago_text = f"{secs_ago // 3600}h {(secs_ago % 3600) // 60}m ago"
        next_in = max(0, 5 - (secs_ago % 5))
        next_text = f"{next_in}s"
    else:
        ago_text = "Never"
        next_text = "—"
    st.markdown(f"""
    <div class="sidebar-stat"><span class="stat-label">Last Refresh</span><span class="stat-value">{lr_text}</span></div>
    <div class="sidebar-stat"><span class="stat-label">Updated</span><span class="stat-value">{ago_text}</span></div>
    <div class="sidebar-stat"><span class="stat-label">Stocks Synced</span><span class="stat-value">{lr_count}</span></div>
    <div class="sidebar-stat"><span class="stat-label">Next Refresh</span><span class="stat-value">{next_text}</span></div>
    """, unsafe_allow_html=True)

    if st.button("🔄 Refresh Prices Now", use_container_width=True):
        with st.spinner("Fetching latest prices..."):
            count = refresh_prices()
        st.success(f"Updated {count} stocks!")
        st.rerun()

    st.markdown("---")
    if st.button("Sign Out", use_container_width=True):
        # Invalidate token in DB
        token = (st.session_state.user or {}).get("session_token")
        if token:
            s = db.get_session()
            try:
                logout_user(s, token)
            finally:
                s.close()
        _clear_session_file()
        # Clear broker state
        user_id = (st.session_state.user or {}).get("user_id", 0)
        if user_id:
            db.clear_broker_state(user_id)
        st.session_state.authenticated = False
        st.session_state.user = None
        if "broker" in st.session_state:
            del st.session_state["broker"]
        st.rerun()


# ══════════════════════════════════════════════
#  PAGE: Market Watchlist (module)
# ══════════════════════════════════════════════
if active_page == "📊 Market Watchlist":
    render_market_watchlist(db, fetcher)

# ══════════════════════════════════════════════
#  PAGE: Smart Picks (module)
# ══════════════════════════════════════════════
elif active_page == "🧠 Smart Picks":
    render_smart_picks(db, fetcher)

# ══════════════════════════════════════════════
#  PAGE: Broker Connect (module)
# ══════════════════════════════════════════════
elif active_page == "🔗 Broker Connect":
    render_broker_connect(db, fetcher)

# ══════════════════════════════════════════════
#  PAGE: Risk Dashboard (module)
# ══════════════════════════════════════════════
elif active_page == "🛡️ Risk Dashboard":
    render_risk_dashboard(db, fetcher)


# ══════════════════════════════════════════════
#  PAGE: Buy & Sell
# ══════════════════════════════════════════════
elif active_page == "💰 Buy & Sell":
    cs = config.CURRENCY_SYMBOL
    st.markdown('<div class="page-header"><h1>Buy & Sell</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Place manual buy and sell orders</div>', unsafe_allow_html=True)

    # Order form
    buy_tab, sell_tab = st.tabs(["🟢 Buy Order", "🔴 Sell Order"])

    for tab, side in [(buy_tab, "BUY"), (sell_tab, "SELL")]:
        with tab:
            c1, c2 = st.columns(2)
            with c1:
                sym_d = st.selectbox("STOCK", SYMBOL_OPTIONS, key=f"bs_{side}_stock")
                symbol = resolve_symbol(sym_d)
                order_type = st.selectbox("ORDER TYPE", ["Market", "Limit", "Stop Loss"], key=f"bs_{side}_type")
            with c2:
                qty = st.number_input("QUANTITY", value=1, min_value=1, step=1, key=f"bs_{side}_qty")
                if order_type != "Market":
                    limit_price = st.number_input(f"{'LIMIT' if order_type == 'Limit' else 'TRIGGER'} PRICE ({cs})",
                        value=0.0, min_value=0.0, step=0.5, key=f"bs_{side}_price")

            # Get live price
            live = get_live_price(symbol)
            latest_price = live["price"]
            if latest_price > 0:
                est_value = latest_price * qty
                change = live["change"]
                change_pct = live["change_pct"]

                c1, c2, c3, c4 = st.columns(4)
                with c1: metric_card("Live Price", f"{cs}{latest_price:.2f}", accent="green" if change >= 0 else "red")
                with c2:
                    vc = "green" if change >= 0 else "red"
                    metric_card("Change", f"{change:+.2f}", accent=vc, val_class=vc, sub=f"{change_pct:+.2f}%")
                with c3: metric_card("Est. Value", f"{cs}{est_value:,.2f}", accent="blue")
                with c4: metric_card("Commission", f"{cs}{est_value * config.COMMISSION_RATE:.2f}", accent="amber")

            st.markdown("<br>", unsafe_allow_html=True)

            btn_color = "primary"
            btn_label = f"Place {side} Order"
            broker = st.session_state.get("broker")

            if st.button(btn_label, use_container_width=True, type=btn_color, key=f"bs_{side}_btn"):
                if broker and broker.is_connected():
                    try:
                        exec_price = latest_price if latest_price > 0 else 0
                        if order_type == "Market":
                            result = broker.place_order(symbol=symbol, side=side, quantity=qty, order_type="MARKET", price=exec_price)
                        else:
                            ot = "LIMIT" if order_type == "Limit" else "SL"
                            result = broker.place_order(symbol=symbol, side=side, quantity=qty,
                                order_type=ot, price=limit_price)

                        if result.success:
                            # Save trade to DB
                            total_cost = result.price * result.quantity + result.commission
                            db.save_trade(
                                symbol=symbol,
                                side=side,
                                quantity=result.quantity,
                                price=result.price,
                                commission=result.commission,
                                slippage=0.0,
                                total_cost=total_cost,
                                pnl=result.pnl,
                                strategy_name="Manual",
                            )
                            # Update portfolio
                            broker_positions = broker.get_positions()
                            for pos in broker_positions:
                                db.update_portfolio(
                                    symbol=pos.symbol,
                                    quantity=pos.quantity,
                                    avg_cost=pos.avg_cost,
                                    current_price=pos.current_price or pos.avg_cost,
                                )
                            st.success(f"{side} order placed! {result.quantity} shares of {config.get_clean_ticker(symbol)} @ {cs}{result.price:.2f} | Order ID: {result.order_id}")
                            st.rerun()
                        else:
                            st.error(f"Order failed: {result.message or 'Unknown error'}")
                    except Exception as e:
                        st.error(f"Order error: {e}")
                else:
                    st.warning("Connect a broker first (go to Broker Connect page)")

    # Recent orders
    st.markdown('<div class="section-title"><span class="dot"></span>Recent Trades</div>', unsafe_allow_html=True)
    recent = db.get_trades(limit=15)
    if recent:
        df = pd.DataFrame([{
            "Time": t.timestamp, "Symbol": t.symbol,
            "Company": config.get_symbol_name(t.symbol),
            "Side": t.side, "Qty": t.quantity,
            "Price": f"{cs}{t.price:.2f}",
            "P&L": f"{cs}{t.pnl:.2f}" if t.pnl else "-",
        } for t in recent])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.markdown("""<div class="empty-state">
            <div class="empty-icon">💰</div>
            <div class="empty-text">No trades yet</div>
            <div class="empty-hint">Place your first order above</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: Signal Monitor
# ══════════════════════════════════════════════
elif active_page == "📡 Signal Monitor":
    st.markdown('<div class="page-header"><h1>Signal Monitor</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Live view of trading signals across all strategies</div>', unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        sd = st.selectbox("STOCK", ["All"] + SYMBOL_OPTIONS)
        sym = resolve_symbol(sd) if sd != "All" else None
    with c2:
        sf = st.selectbox("STRATEGY", ["All"] + list(STRATEGIES.keys()))

    signals = db.get_signals(symbol=sym, strategy_name=STRATEGIES[sf]().name if sf!="All" else None, limit=200)

    if signals:
        buy_c = sum(1 for s in signals if s.signal_type=="BUY")
        sell_c = sum(1 for s in signals if s.signal_type=="SELL")
        c1,c2,c3,c4 = st.columns(4)
        with c1: metric_card("Total", len(signals), accent="blue")
        with c2: metric_card("Buy", buy_c, accent="green", val_class="green")
        with c3: metric_card("Sell", sell_c, accent="red", val_class="red")
        with c4: metric_card("Hold", len(signals)-buy_c-sell_c, accent="amber")
        st.markdown("<br>", unsafe_allow_html=True)
        df = pd.DataFrame([{"Time":s.timestamp,"Symbol":s.symbol,"Company":config.get_symbol_name(s.symbol),
            "Strategy":s.strategy_name,"Signal":s.signal_type,"Price":f"{config.CURRENCY_SYMBOL}{s.price:.2f}"} for s in signals])
        st.dataframe(df, use_container_width=True, height=500)
    else:
        st.info("No signals found. Run `python main.py analyze`.")


# ══════════════════════════════════════════════
#  PAGE: Backtest Lab
# ══════════════════════════════════════════════
elif active_page == "🧪 Backtest Lab":
    st.markdown('<div class="page-header"><h1>Backtest Lab</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Simulate strategy performance against historical data</div>', unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns([1.5,1.5,1,1])
    with c1:
        bsd = st.selectbox("STOCK", SYMBOL_OPTIONS, key="bt_s")
        bt_sym = resolve_symbol(bsd)
    with c2: bt_strat = st.selectbox("STRATEGY", list(STRATEGIES.keys()), key="bt_st")
    with c3: bt_start = st.date_input("START", value=pd.to_datetime(config.DEFAULT_START_DATE))
    with c4: bt_end = st.date_input("END", value=pd.to_datetime(config.DEFAULT_END_DATE))

    ca,cb = st.columns(2)
    with ca: bt_cap = st.number_input(f"CAPITAL ({config.CURRENCY_SYMBOL})", value=config.INITIAL_CAPITAL, step=10000.0, min_value=1000.0)
    with cb: bt_comm = st.slider("COMMISSION (%)", 0.0, 1.0, config.COMMISSION_RATE*100, 0.01)/100

    if st.button("Run Backtest", use_container_width=True, type="primary"):
        strat = STRATEGIES[bt_strat]()
        engine = BacktestEngine(strategy=strat, initial_capital=bt_cap, commission_rate=bt_comm, db_manager=db)
        with st.spinner(f"Backtesting {strat.name} on {bt_sym}..."):
            result = engine.run(symbol=bt_sym, start=bt_start.strftime("%Y-%m-%d"), end=bt_end.strftime("%Y-%m-%d"))

        if result.total_trades > 0:
            c1,c2,c3,c4,c5 = st.columns(5)
            vc = "green" if result.total_return_pct>=0 else "red"
            with c1: metric_card("Return", f"{result.total_return_pct:+.2f}%", accent=vc, val_class=vc)
            with c2: metric_card("Final", f"{config.CURRENCY_SYMBOL}{result.final_value:,.0f}", accent="blue")
            with c3: metric_card("Sharpe", f"{result.sharpe_ratio or 0:.3f}", accent="amber")
            with c4: metric_card("Max DD", f"{result.max_drawdown_pct or 0:.2f}%", accent="red", val_class="red")
            with c5: metric_card("Win Rate", f"{result.win_rate or 0:.0f}%", accent="green", sub=f"{result.winning_trades}W/{result.losing_trades}L")

            fig = go.Figure()
            fig.add_trace(go.Scatter(y=result.equity_curve, mode="lines", name="Value",
                line=dict(color="#00d4aa",width=2), fill="tozeroy", fillcolor="rgba(0,212,170,0.08)"))
            fig.add_hline(y=bt_cap, line_dash="dash", line_color="rgba(255,255,255,0.15)")
            fig.update_layout(**PLOTLY_LAYOUT, title="Equity Curve", height=350)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-title"><span class="dot"></span>Previous Results</div>', unsafe_allow_html=True)
    hr = db.get_backtest_results()
    if hr:
        st.dataframe(pd.DataFrame([{"Date":r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "N/A",
            "Strategy":r.strategy_name,"Symbol":r.symbol,"Return":f"{r.total_return_pct:+.2f}%",
            "Sharpe":f"{r.sharpe_ratio:.3f}" if r.sharpe_ratio else "N/A",
            "Trades":r.total_trades,"Win Rate":f"{r.win_rate:.0f}%" if r.win_rate else "N/A"} for r in hr]), use_container_width=True)
    else:
        st.info("No results yet.")


# ══════════════════════════════════════════════
#  PAGE: Auto Trade
# ══════════════════════════════════════════════
elif active_page == "⚡ Auto Trade":
    st.markdown('<div class="page-header"><h1>Auto Trade</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Configure and monitor your automated trading bot — runs even when browser is closed</div>', unsafe_allow_html=True)

    user_id = (st.session_state.user or {}).get("user_id", 0)

    # Read status from DB (persisted, survives refresh)
    db_at_cfg = db.get_auto_trade_config(user_id)
    at_active = db_at_cfg["is_active"] if db_at_cfg else False
    last_run = db_at_cfg["last_run"].strftime("%H:%M:%S") if db_at_cfg and db_at_cfg.get("last_run") else "Never"

    # Status banner
    status_cls = "active" if at_active else "inactive"
    status_txt = "RUNNING" if at_active else "STOPPED"
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:20px;">
        <span class="status-badge {status_cls}">
            {'<span class="live-dot"></span>' if at_active else ''}{status_txt}
        </span>
        <span style="font-size:13px; color:var(--text-muted);">
            Last run: {last_run}
            {'&nbsp;·&nbsp; <span style="color:#00d4aa;">Daemon running in background</span>' if at_active else ''}
        </span>
    </div>
    """, unsafe_allow_html=True)

    if at_active:
        st.markdown("""
        <div style="background:rgba(0,212,170,0.08); border:1px solid rgba(0,212,170,0.2); border-radius:12px;
            padding:12px 16px; margin-bottom:16px; font-size:13px; color:#8492a6;">
            ✅ <strong style="color:#00d4aa;">Background daemon is active</strong> — auto-trading continues even if you close this browser tab.
            The bot will auto-buy on buy signals and <strong>auto-sell</strong> on sell signals, stop-loss, trailing-stop, and take-profit triggers.
        </div>
        """, unsafe_allow_html=True)

    # Config
    st.markdown('<div class="section-title"><span class="dot"></span>Bot Configuration</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        at_strategy = st.selectbox("STRATEGY", list(STRATEGIES.keys()), key="at_strat",
            index=list(STRATEGIES.keys()).index(db_at_cfg["strategy_name"]) if db_at_cfg and db_at_cfg["strategy_name"] in STRATEGIES else 0)
        at_interval = st.slider("UPDATE INTERVAL (MIN)", 1, 60,
            db_at_cfg["interval_minutes"] if db_at_cfg else 15, key="at_int")
        at_max_pos = st.slider("MAX POSITION SIZE (%)", 5, 50,
            int(db_at_cfg["max_position_pct"] * 100) if db_at_cfg else 20, key="at_pos")
    with c2:
        at_symbols = st.multiselect("STOCKS TO TRADE", SYMBOL_OPTIONS,
            default=SYMBOL_OPTIONS[:5], key="at_syms")
        at_market_hours = st.checkbox("Market hours only", value=True, key="at_mh")
        at_stop_loss = st.number_input("STOP LOSS (%)", value=db_at_cfg["stop_loss_pct"] if db_at_cfg and db_at_cfg["stop_loss_pct"] else 5.0,
            min_value=0.0, max_value=50.0, step=0.5, key="at_sl")
        at_take_profit = st.number_input("TAKE PROFIT (%)", value=db_at_cfg["take_profit_pct"] if db_at_cfg and db_at_cfg["take_profit_pct"] else 10.0,
            min_value=0.0, max_value=100.0, step=1.0, key="at_tp")

    st.markdown("<br>", unsafe_allow_html=True)

    c_start, c_stop, c_run_once = st.columns(3)
    with c_start:
        if st.button("▶ Start Auto-Trade", use_container_width=True, type="primary", disabled=at_active):
            resolved_syms = [resolve_symbol(s) for s in at_symbols]
            # Save config to DB
            db.save_auto_trade_config(
                user_id=user_id, is_active=True,
                strategy_name=at_strategy, symbols=resolved_syms,
                interval_minutes=at_interval, max_position_pct=at_max_pos / 100,
                stop_loss_pct=at_stop_loss, take_profit_pct=at_take_profit,
                market_hours_only=at_market_hours,
            )
            # Spawn daemon as background subprocess (survives browser close)
            import subprocess
            daemon_path = os.path.join(config.BASE_DIR, "auto_trader_daemon.py")
            subprocess.Popen(
                [sys.executable, daemon_path, "--user-id", str(user_id)],
                cwd=config.BASE_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                close_fds=True,
            )
            st.success("Auto-trading started! Background daemon launched — will continue even if you close browser.")
            st.rerun()

    with c_stop:
        if st.button("⏹ Stop Auto-Trade", use_container_width=True, type="secondary", disabled=not at_active):
            db.set_auto_trade_active(user_id, False)
            st.warning("Auto-trading stopped. Daemon will exit on next cycle.")
            st.rerun()

    with c_run_once:
        if st.button("▶ Run Once Now", use_container_width=True, type="secondary"):
            resolved_syms = [resolve_symbol(s) for s in at_symbols]
            broker = st.session_state.get("broker")
            if not broker or not broker.is_connected():
                st.warning("Connect a broker first (Broker Connect page)")
            else:
                with st.spinner("Executing single trade cycle (buy + sell)..."):
                    from auto_trader_daemon import execute_trade_cycle
                    cfg = {
                        "strategy_name": at_strategy,
                        "symbols": resolved_syms,
                        "max_position_pct": at_max_pos / 100,
                        "stop_loss_pct": at_stop_loss,
                        "take_profit_pct": at_take_profit,
                    }
                    result = execute_trade_cycle(db, fetcher, broker, user_id, cfg)
                    # Persist broker after trade
                    _persist_broker_to_db()
                st.success(f"Done! {result['trades']} trades executed, {result['errors']} errors")

    # Current config display
    if at_active and db_at_cfg:
        st.markdown('<div class="section-title"><span class="dot"></span>Active Configuration</div>', unsafe_allow_html=True)
        c1,c2,c3,c4,c5 = st.columns(5)
        with c1: metric_card("Strategy", db_at_cfg["strategy_name"], accent="green")
        with c2: metric_card("Stocks", len(db_at_cfg["symbols"]), accent="blue")
        with c3: metric_card("Interval", f"{db_at_cfg['interval_minutes']}m", accent="amber")
        with c4: metric_card("Max Position", f"{db_at_cfg['max_position_pct']*100:.0f}%", accent="")
        with c5: metric_card("Auto-Sell", "Active", accent="green", sub="SL + TP + Signals")

    # Recent activity
    st.markdown('<div class="section-title"><span class="dot"></span>Recent Auto-Trade Activity</div>', unsafe_allow_html=True)
    recent_trades = db.get_trades(limit=15)
    auto_trades = [t for t in recent_trades if t.strategy_name and "AutoTrade" in t.strategy_name]
    if auto_trades:
        cs_at = config.CURRENCY_SYMBOL
        td = pd.DataFrame([{"Time":t.timestamp,"Symbol":t.symbol,"Company":config.get_symbol_name(t.symbol),
            "Side":t.side,"Qty":t.quantity,"Price":f"{cs_at}{t.price:.2f}",
            "P&L":f"{cs_at}{t.pnl:.2f}" if t.pnl else "-","Strategy":t.strategy_name} for t in auto_trades])
        st.dataframe(td, use_container_width=True)
    elif recent_trades:
        cs_at = config.CURRENCY_SYMBOL
        td = pd.DataFrame([{"Time":t.timestamp,"Symbol":t.symbol,"Company":config.get_symbol_name(t.symbol),
            "Side":t.side,"Qty":t.quantity,"Price":f"{cs_at}{t.price:.2f}",
            "P&L":f"{cs_at}{t.pnl:.2f}" if t.pnl else "-","Strategy":t.strategy_name} for t in recent_trades])
        st.dataframe(td, use_container_width=True)
    else:
        st.info("No trading activity yet. Start auto-trade or run once to begin.")

    # Risk events
    risk_events = db.get_risk_events(limit=5)
    if risk_events:
        st.markdown('<div class="section-title"><span class="dot"></span>Recent Risk Events (Auto-Sell Triggers)</div>', unsafe_allow_html=True)
        edf = pd.DataFrame([{
            "Time": e.timestamp.strftime("%m-%d %H:%M") if e.timestamp else "",
            "Stock": config.get_clean_ticker(e.symbol),
            "Event": e.event_type, "Action": e.action_taken or "-",
            "Message": e.message[:60],
        } for e in risk_events])
        st.dataframe(edf, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════
#  PAGE: Trade History
# ══════════════════════════════════════════════
elif active_page == "📜 Trade History":
    st.markdown('<div class="page-header"><h1>Trade History</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Complete log of all paper trading executions</div>', unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        td = st.selectbox("STOCK", ["All"]+SYMBOL_OPTIONS)
        ts = resolve_symbol(td) if td!="All" else None
    with c2:
        tf = st.selectbox("STRATEGY", ["All"]+list(STRATEGIES.keys()))

    trades = db.get_trades(symbol=ts, strategy_name=STRATEGIES[tf]().name if tf!="All" else None)
    if trades:
        perf = db.get_performance_summary()
        c1,c2,c3,c4 = st.columns(4)
        with c1: metric_card("Trades", perf['total_trades'], accent="blue")
        with c2:
            pc = "green" if perf["total_pnl"]>=0 else "red"
            metric_card("Total P&L", f"{config.CURRENCY_SYMBOL}{perf['total_pnl']:,.2f}", accent=pc, val_class=pc)
        with c3: metric_card("Win Rate", f"{perf['win_rate']:.0f}%", accent="green", sub=f"{perf['winning_trades']}W/{perf['losing_trades']}L")
        with c4: metric_card("Avg P&L", f"{config.CURRENCY_SYMBOL}{perf['avg_pnl_per_trade']:.2f}", accent="amber")
        st.markdown("<br>", unsafe_allow_html=True)
        df = pd.DataFrame([{"Time":t.timestamp,"Symbol":t.symbol,"Company":config.get_symbol_name(t.symbol),
            "Side":t.side,"Qty":t.quantity,"Price":f"{config.CURRENCY_SYMBOL}{t.price:.2f}","Commission":f"{config.CURRENCY_SYMBOL}{t.commission:.2f}",
            "P&L":f"{config.CURRENCY_SYMBOL}{t.pnl:.2f}" if t.pnl else "-","Strategy":t.strategy_name} for t in trades])
        st.dataframe(df, use_container_width=True, height=600)
    else:
        st.markdown('<div class="empty-state"><div class="empty-text">No trades yet</div><div class="empty-hint">Run <code>python main.py run</code></div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════
#  PAGE: Portfolio
# ══════════════════════════════════════════════
elif active_page == "📁 Portfolio":
    st.markdown('<div class="page-header"><h1>Portfolio</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Current holdings, allocation, and performance</div>', unsafe_allow_html=True)

    positions = db.get_portfolio()
    perf = db.get_performance_summary()
    tv = sum(p.current_value or 0 for p in positions)
    tp = sum(p.unrealized_pnl or 0 for p in positions)

    c1,c2,c3,c4 = st.columns(4)
    cs_p = config.CURRENCY_SYMBOL
    with c1: metric_card("Portfolio Value", f"{cs_p}{tv:,.2f}", accent="blue")
    with c2:
        pc = "green" if tp>=0 else "red"
        metric_card("Unrealized P&L", f"{cs_p}{tp:,.2f}", accent=pc, val_class=pc)
    with c3: metric_card("Positions", len(positions), accent="amber")
    with c4: metric_card("Signals", perf['total_signals'])

    if positions:
        st.markdown('<div class="section-title"><span class="dot"></span>Holdings</div>', unsafe_allow_html=True)
        cs_p = config.CURRENCY_SYMBOL
        df = pd.DataFrame([{"Symbol":p.symbol,"Company":config.get_symbol_name(p.symbol),"Qty":p.quantity,
            "Avg Cost":f"{cs_p}{p.avg_cost:.2f}","Price":f"{cs_p}{p.current_price:.2f}" if p.current_price else "N/A",
            "Value":f"{cs_p}{p.current_value:,.2f}" if p.current_value else "N/A",
            "P&L":f"{cs_p}{p.unrealized_pnl:,.2f}" if p.unrealized_pnl else f"{cs_p}0.00"} for p in positions])
        st.dataframe(df, use_container_width=True)

        if len(positions)>1:
            fig = px.pie(names=[p.symbol for p in positions], values=[p.current_value or 0 for p in positions],
                color_discrete_sequence=["#00d4aa","#6c5ce7","#ffa502","#ff4757","#00cec9"], hole=0.55)
            fig.update_layout(**PLOTLY_LAYOUT, height=350)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div class="empty-state"><div class="empty-text">No positions</div><div class="empty-hint">Run <code>python main.py run</code></div></div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title"><span class="dot"></span>Lifetime Performance</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame([{"Trades":perf["total_trades"],"Wins":perf["winning_trades"],
        "Losses":perf["losing_trades"],"Win Rate":f"{perf['win_rate']:.1f}%",
        "Total P&L":f"{config.CURRENCY_SYMBOL}{perf['total_pnl']:,.2f}","Avg P&L":f"{config.CURRENCY_SYMBOL}{perf['avg_pnl_per_trade']:.2f}"}]), use_container_width=True)

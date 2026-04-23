"""Market Watchlist page — heatmap, gainers/losers, sector view."""
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import config
from data.indicators import TechnicalIndicators
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import yfinance as yf
import pytz
import logging

log = logging.getLogger(__name__)

_COMMODITY_TICKERS = {"GC=F", "SI=F", "GOLDBEES.NS", "SILVERBEES.NS"}


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
    margin=dict(l=50, r=20, t=40, b=20),
    xaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.04)"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, font=dict(size=11), bgcolor="rgba(0,0,0,0)"),
)

IST = pytz.timezone("Asia/Kolkata")


# ── Data fetching helpers (no show_spinner to avoid flash) ──

@st.cache_data(ttl=3600, show_spinner=False)  # prev close only changes once per day
def _get_prev_close(sym):
    """Get previous close — cached 1hr since it doesn't change intraday."""
    try:
        d = yf.download(sym, period="2d", interval="1d", progress=False, timeout=5)
        if len(d) > 1:
            return float(d["Close"].iloc[-2])
        elif not d.empty:
            return float(d["Close"].iloc[0])
    except Exception:
        pass
    return 0.0


def _fetch_live_price(sym):
    """Get near real-time price using yf.download (bypasses Ticker cache).

    Downloads latest 1-min candle — at most ~60s old during market hours.
    """
    try:
        df = yf.download(sym, period="1d", interval="1m", progress=False,
                         prepost=True, timeout=5)
        if not df.empty:
            price = float(df["Close"].iloc[-1])
            prev = _get_prev_close(sym)
            return price, prev
    except Exception:
        pass

    # Fallback to Ticker.info
    try:
        t = yf.Ticker(sym)
        info = t.info
        price = info.get("regularMarketPrice", 0) or 0
        prev = info.get("regularMarketPreviousClose",
                 info.get("previousClose", 0)) or 0
        if price and price > 0:
            return float(price), float(prev)
        fi = t.fast_info
        price = fi.get("lastPrice", 0) or fi.get("last_price", 0)
        prev = fi.get("previousClose", 0) or fi.get("previous_close", 0)
        return float(price), float(prev)
    except Exception:
        return 0.0, 0.0


def _fetch_intraday_fresh(sym, hours=4):
    """
    Fetch intraday candle data with forced fresh download.

    For commodity futures we use 2-min candles because yfinance's 1-min
    pipeline for futures is often delayed ~15 min, whereas 2-min candles
    arrive much closer to real-time.
    """
    is_commodity = sym in _COMMODITY_TICKERS
    interval = "2m" if is_commodity else "1m"
    try:
        t = yf.Ticker(sym)
        df = t.history(period="1d", interval=interval, prepost=True, raise_errors=False)
        if df.empty:
            df = t.history(period="2d", interval=interval, prepost=True, raise_errors=False)
        if not df.empty:
            # Convert to IST
            if df.index.tz is not None:
                df.index = df.index.tz_convert(IST)
            else:
                df.index = df.index.tz_localize("UTC").tz_convert(IST)
            df.index.name = "Time"
            return df[["Open", "High", "Low", "Close", "Volume"]]
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def _get_ticker_prices_fresh(symbols):
    """Get ticker bar prices — batch download for speed."""
    results = []
    try:
        # Batch download — much faster than individual Ticker.fast_info calls
        data = yf.download(symbols, period="2d", interval="1d", progress=False, threads=True)
        if data.empty:
            return results
        for sym in symbols:
            try:
                if len(symbols) > 1:
                    close = data["Close"][sym]
                else:
                    close = data["Close"]
                if close.empty or len(close) < 1:
                    continue
                price = float(close.iloc[-1])
                prev = float(close.iloc[-2]) if len(close) > 1 else price
                chg = price - prev
                pct = (chg / prev * 100) if prev else 0
                results.append((sym, price, chg, pct))
            except Exception:
                pass
    except Exception:
        pass
    return results


def render(db, fetcher):
    cs = config.CURRENCY_SYMBOL
    now = datetime.now()
    st.markdown('<div class="page-header"><h1>Market Watchlist</h1></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-subtitle">Real-time market data, charts, and sector performance &nbsp;·&nbsp; <span style="color:#00d4aa;"><span class="live-dot"></span>Live</span> &nbsp;·&nbsp; Updated {now.strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

    # Symbol options
    SYMBOL_OPTIONS = [config.get_symbol_display(s) for s in config.DEFAULT_SYMBOLS]
    SYMBOL_MAP = {config.get_symbol_display(s): s for s in config.DEFAULT_SYMBOLS}

    # ── Controls row ──
    c1, c2, c3, c4, c5 = st.columns([2, 0.8, 0.8, 1, 1.5])
    with c1:
        sym_d = st.selectbox("STOCK", SYMBOL_OPTIONS, index=0, key="mw_stock")
        symbol = SYMBOL_MAP.get(sym_d, sym_d.split(' - ')[0].strip())
    with c2:
        # Real-time chart time window
        rt_window_opts = {"1 Hour": 1, "2 Hours": 2, "3 Hours": 3, "4 Hours": 4}
        rt_window_label = st.selectbox("REAL-TIME WINDOW", list(rt_window_opts.keys()), index=3, key="mw_rt_window")
        rt_hours = rt_window_opts[rt_window_label]
    with c3:
        # Historical chart period
        period_opts = {"3 Months": 90, "6 Months": 180, "8 Months": 240, "10 Months": 300, "1 Year": 365}
        period_label = st.selectbox("HISTORY PERIOD", list(period_opts.keys()), index=4, key="mw_period")
    with c4:
        indicators = st.multiselect("INDICATORS", ["SMA 20", "SMA 50", "EMA 20", "Bollinger Bands", "RSI", "MACD", "SuperTrend"], default=["SMA 20", "SMA 50"], key="mw_ind")

    # Detect market status (inlined to avoid stale module cache issues)
    _COMMODITY_SYMS = {"GC=F", "SI=F", "GOLDBEES.NS", "SILVERBEES.NS"}
    _INDEX_SYMS = {"^NSEI", "^NSMIDCP", "NIFTY500MULTICAP5025.NS"}
    is_indian = symbol.endswith(".NS")
    is_commodity = symbol in _COMMODITY_SYMS
    is_index = symbol in _INDEX_SYMS or symbol.startswith("^")

    if is_commodity and not is_indian:
        market_name = "COMEX"
        # Commodities trade nearly 24h
        mkt_open_h, mkt_open_m = 0, 0
        mkt_close_h, mkt_close_m = 23, 59
    elif is_index:
        market_name = "NSE" if is_indian or symbol.startswith("^N") else "Index"
        mkt_open_h, mkt_open_m = 9, 15
        mkt_close_h, mkt_close_m = 15, 30
    elif is_indian:
        market_name = "NSE"
        mkt_open_h, mkt_open_m = 9, 15
        mkt_close_h, mkt_close_m = 15, 30
    else:
        market_name = "NYSE"
        mkt_open_h, mkt_open_m = 19, 0
        mkt_close_h, mkt_close_m = 1, 30

    now_h, now_m = now.hour, now.minute
    now_mins = now_h * 60 + now_m
    open_mins = mkt_open_h * 60 + mkt_open_m
    close_mins = mkt_close_h * 60 + mkt_close_m

    if is_commodity and not is_indian:
        market_open = now.weekday() < 5  # Mon-Fri
    elif is_indian or is_index:
        market_open = open_mins <= now_mins <= close_mins and now.weekday() < 5
    else:
        market_open = (now_mins >= open_mins or now_mins <= close_mins) and now.weekday() < 5

    mkt_status = f"🟢 {market_name} Open" if market_open else f"🔴 {market_name} Closed"

    # ══════════════════════════════════════════════
    #  REAL-TIME FRAGMENT — only this section auto-refreshes (no full page flash)
    # ══════════════════════════════════════════════
    @st.fragment(run_every=3)
    def _live_section():
        """This fragment auto-reruns every 3s WITHOUT rerunning the whole page."""
        _now = datetime.now()

        # ── Live Ticker Bar ──
        ticker_syms = config.DEFAULT_SYMBOLS[:12]
        ticker_data = _get_ticker_prices_fresh(ticker_syms)

        if ticker_data:
            update_str = _now.strftime("%H:%M:%S")
            ticker_html = f'<div style="display:flex;gap:16px;overflow-x:auto;padding:8px 0 16px;scrollbar-width:thin;align-items:center;"><div style="flex:0 0 auto;font-size:10px;color:#00d4aa;font-weight:700;writing-mode:vertical-lr;text-orientation:mixed;letter-spacing:1px;">{update_str}</div>'
            for sym, price, chg, pct in ticker_data:
                color = "#00d4aa" if chg >= 0 else "#ff4757"
                arrow = "▲" if chg >= 0 else "▼"
                name = config.get_clean_ticker(sym)
                # Use $ for commodities/US, ₹ for Indian
                sym_cs = "$" if sym in ("GC=F", "SI=F") or not sym.endswith(".NS") else cs
                ticker_html += f'''
                <div style="flex:0 0 auto;background:rgba(17,24,39,0.85);border:1px solid rgba(255,255,255,0.06);
                    border-radius:10px;padding:10px 16px;min-width:140px;text-align:center;">
                    <div style="font-size:11px;color:#8492a6;font-weight:600;">{name}</div>
                    <div style="font-size:18px;font-weight:800;color:#e8ecf1;">{sym_cs}{price:.2f}</div>
                    <div style="font-size:12px;color:{color};font-weight:600;">{arrow} {chg:+.2f} ({pct:+.2f}%)</div>
                </div>'''
            ticker_html += '</div>'
            st.markdown(ticker_html, unsafe_allow_html=True)

        # ── Intraday Tab (real-time) ──
        live_price, prev_close = _fetch_live_price(symbol)
        intraday = _fetch_intraday_fresh(symbol, hours=rt_hours)

        st.markdown(f'<div style="text-align:right;font-size:12px;color:#8492a6;margin-bottom:-10px;">{mkt_status} &nbsp;·&nbsp; Times in IST &nbsp;·&nbsp; Last fetch: {_now.strftime("%H:%M:%S")}</div>', unsafe_allow_html=True)

        if not intraday.empty:
            idf = intraday.copy()

            # ── Filter to selected time window ──
            cutoff = _now - timedelta(hours=rt_hours)
            cutoff_aware = IST.localize(cutoff) if idf.index.tz else cutoff
            idf = idf[idf.index >= cutoff_aware]
            if idf.empty:
                # Fallback: show last N candles (N hours of 1-min data)
                idf = intraday.tail(rt_hours * 60).copy()

            prices = idf["Close"]
            open_price = float(idf["Open"].iloc[0])
            current = float(prices.iloc[-1]) if live_price <= 0 else live_price
            day_change = current - open_price
            day_pct = (day_change / open_price * 100) if open_price else 0

            # Y-axis: start from absolute lowest, tight to data
            y_min = float(idf["Low"].min())
            y_max = float(idf["High"].max())
            # Include live price in range calc
            if live_price > 0:
                y_min = min(y_min, live_price)
                y_max = max(y_max, live_price)
            y_pad = (y_max - y_min) * 0.02 if y_max > y_min else 0.5
            y_range = [y_min - y_pad, y_max + y_pad]

            # X-axis: extend to current time so live price line sits at right edge
            x_start = idf.index[0]
            x_end = max(idf.index[-1] + timedelta(minutes=2),
                        IST.localize(_now) if idf.index.tz else _now)

            rt_fig = go.Figure()
            rt_fig.add_trace(go.Candlestick(
                x=idf.index, open=idf["Open"], high=idf["High"],
                low=idf["Low"], close=idf["Close"], name="OHLC",
                increasing=dict(line=dict(color="#00d4aa"), fillcolor="rgba(0,212,170,0.4)"),
                decreasing=dict(line=dict(color="#ff4757"), fillcolor="rgba(255,71,87,0.4)"),
            ))
            # Previous close reference
            if prev_close > 0:
                rt_fig.add_hline(y=prev_close, line_dash="dot", line_color="rgba(132,146,166,0.4)",
                                 line_width=1, annotation_text=f"Prev Close {cs}{prev_close:.2f}",
                                 annotation_position="left",
                                 annotation_font=dict(color="#8492a6", size=10))
            # Live price marker
            if live_price > 0:
                live_color = "#00d4aa" if live_price >= prev_close else "#ff4757"
                rt_fig.add_hline(y=live_price, line_dash="dash", line_color=live_color,
                                 line_width=1.5,
                                 annotation_text=f"  ● LIVE {cs}{live_price:.2f}  ({day_pct:+.2f}%)",
                                 annotation_position="right",
                                 annotation_font=dict(color=live_color, size=12, family="Inter"))

            window_label = f"Last {rt_hours}h"
            rt_fig.update_layout(
                template="plotly_dark",
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter", color="#8492a6"),
                margin=dict(l=50, r=20, t=40, b=20),
                height=420, showlegend=False,
                yaxis=dict(gridcolor="rgba(255,255,255,0.04)", title=None, range=y_range),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", title=None,
                           rangeslider=dict(visible=False), range=[x_start, x_end]),
                title=dict(text=f"{config.get_symbol_name(symbol)} · {window_label} · {_now.strftime('%H:%M:%S')}", font=dict(size=14, color="#8492a6")),
            )
            st.plotly_chart(rt_fig, use_container_width=True, key=f"rt_chart_{_now.strftime('%H%M%S')}")

            # Intraday metrics
            ic1, ic2, ic3, ic4 = st.columns(4)
            with ic1: metric_card("Live", f"{cs}{current:.2f}", accent="green" if day_change >= 0 else "red")
            with ic2:
                vc = "green" if day_change >= 0 else "red"
                metric_card("Day Change", f"{day_change:+.2f}", accent=vc, val_class=vc, sub=f"{day_pct:+.2f}%")
            with ic3: metric_card("Day High", f"{cs}{float(idf['High'].max()):.2f}", accent="blue")
            with ic4: metric_card("Day Low", f"{cs}{float(idf['Low'].min()):.2f}", accent="amber")
        else:
            st.markdown("""<div class="empty-state">
                <div class="empty-icon">📈</div>
                <div class="empty-text">No intraday data available</div>
                <div class="empty-hint">Market may be closed. Check Historical tab below.</div>
            </div>""", unsafe_allow_html=True)

    # Render the live fragment
    _live_section()

    # ══════════════════════════════════════════════
    #  HISTORICAL TAB (static — no auto-refresh needed)
    # ══════════════════════════════════════════════
    st.markdown('<div class="section-title"><span class="dot"></span>Historical Chart</div>', unsafe_allow_html=True)

    days = period_opts[period_label]
    end_d = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    start_d = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    @st.cache_data(ttl=300, show_spinner=False)
    def _fetch_chart_data(sym, start, end):
        return fetcher.fetch_historical_data(sym, start=start, end=end, save_to_db=True)

    data = _fetch_chart_data(symbol, start_d, end_d)

    if not data.empty:
        enriched = TechnicalIndicators.add_all_indicators(data)
        num_rows = 1
        rh = [0.7]
        if "RSI" in indicators:
            num_rows += 1; rh.append(0.15)
        if "MACD" in indicators:
            num_rows += 1; rh.append(0.15)

        fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=rh)
        fig.add_trace(go.Candlestick(x=enriched.index, open=enriched["Open"], high=enriched["High"],
            low=enriched["Low"], close=enriched["Close"], name="OHLC",
            increasing=dict(line=dict(color="#00d4aa"), fillcolor="rgba(0,212,170,0.3)"),
            decreasing=dict(line=dict(color="#ff4757"), fillcolor="rgba(255,71,87,0.3)")), row=1, col=1)

        if "SMA 20" in indicators:
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["SMA_20"], name="SMA 20", line=dict(color="#ffa502", width=1.5, dash="dot")), row=1, col=1)
        if "SMA 50" in indicators:
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["SMA_50"], name="SMA 50", line=dict(color="#6c5ce7", width=1.5, dash="dot")), row=1, col=1)
        if "EMA 20" in indicators:
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["EMA_20"], name="EMA 20", line=dict(color="#e056fd", width=1.5)), row=1, col=1)
        if "Bollinger Bands" in indicators:
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["BB_Upper"], name="BB Upper", line=dict(color="rgba(108,92,231,0.5)", width=1, dash="dash")), row=1, col=1)
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["BB_Lower"], name="BB Lower", line=dict(color="rgba(108,92,231,0.5)", width=1, dash="dash"), fill="tonexty", fillcolor="rgba(108,92,231,0.06)"), row=1, col=1)
        if "SuperTrend" in indicators and "SuperTrend" in enriched.columns:
            colors = ["#00d4aa" if d == 1 else "#ff4757" for d in enriched["ST_Direction"].fillna(1)]
            for i in range(1, len(enriched)):
                fig.add_trace(go.Scatter(x=[enriched.index[i-1], enriched.index[i]], y=[enriched["SuperTrend"].iloc[i-1], enriched["SuperTrend"].iloc[i]], mode="lines", line=dict(color=colors[i], width=2), showlegend=(i==1), name="SuperTrend" if i==1 else None), row=1, col=1)

        cr = 2
        if "RSI" in indicators:
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["RSI"], name="RSI", line=dict(color="#ffa502", width=1.5)), row=cr, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="rgba(255,71,87,0.4)", row=cr, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="rgba(0,212,170,0.4)", row=cr, col=1)
            cr += 1
        if "MACD" in indicators:
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["MACD"], name="MACD", line=dict(color="#6c5ce7", width=1.5)), row=cr, col=1)
            fig.add_trace(go.Scatter(x=enriched.index, y=enriched["MACD_Signal"], name="Signal", line=dict(color="#ff6348", width=1.5)), row=cr, col=1)
            mc = ["rgba(0,212,170,0.6)" if v >= 0 else "rgba(255,71,87,0.6)" for v in enriched["MACD_Histogram"].fillna(0)]
            fig.add_trace(go.Bar(x=enriched.index, y=enriched["MACD_Histogram"], name="Histogram", marker_color=mc), row=cr, col=1)

        # Live price line on historical chart (fetch once, cached)
        @st.cache_data(ttl=10, show_spinner=False)
        def _hist_live(sym):
            return _fetch_live_price(sym)

        h_live, h_prev = _hist_live(symbol)
        if h_live > 0:
            live_color = "#00d4aa" if h_live >= h_prev else "#ff4757"
            fig.add_hline(y=h_live, line_dash="dash", line_color=live_color,
                          line_width=1.5, row=1, col=1,
                          annotation_text=f"  LIVE {cs}{h_live:.2f}",
                          annotation_position="right",
                          annotation_font=dict(color=live_color, size=11, family="Inter"))

        chart_title = f"{config.get_symbol_name(symbol)} · {period_label} · {now.strftime('%H:%M:%S')}"
        fig.update_layout(**PLOTLY_LAYOUT, height=560 + (num_rows - 1) * 130, xaxis_rangeslider_visible=False, title=dict(text=chart_title, font=dict(size=14, color="#8492a6")))
        st.plotly_chart(fig, use_container_width=True)

        latest = enriched.iloc[-1]
        prev = enriched.iloc[-2] if len(enriched) > 1 else latest
        display_price = h_live if h_live > 0 else latest["Close"]
        change = display_price - h_prev if h_live > 0 else (latest["Close"] - prev["Close"])
        change_pct = (change / (h_prev if h_prev else prev["Close"])) * 100 if (h_prev or prev["Close"]) else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        price_label = "Live Price" if h_live > 0 else "Last Close"
        with c1: metric_card(price_label, f"{cs}{display_price:.2f}", accent="green" if change >= 0 else "red")
        with c2:
            vc = "green" if change >= 0 else "red"
            metric_card("Change", f"{change:+.2f}", accent=vc, val_class=vc, sub=f"{change_pct:+.2f}%")
        with c3:
            rsi = latest.get('RSI', 0)
            metric_card("RSI", f"{rsi:.1f}", accent="amber", sub="Overbought" if rsi > 70 else ("Oversold" if rsi < 30 else "Neutral"))
        with c4: metric_card("High", f"{cs}{enriched['High'].max():.2f}", accent="blue")
        with c5:
            v = latest['Volume']
            vs = f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}K"
            metric_card("Volume", vs, sub="shares")

    # Top Gainers / Losers
    st.markdown('<div class="section-title"><span class="dot"></span>Top Movers Today</div>', unsafe_allow_html=True)
    summaries = fetcher.get_market_summary()
    if summaries:
        sorted_s = sorted(summaries, key=lambda x: x["change_pct"], reverse=True)
        gc, lc = st.columns(2)
        with gc:
            st.markdown("**Top Gainers**")
            gainers = [s for s in sorted_s if s["change_pct"] > 0][:5]
            if gainers:
                gdf = pd.DataFrame([{"Stock": config.get_clean_ticker(g["symbol"]), "Price": f"{cs}{g['price']:.2f}", "Change": f"{g['change_pct']:+.2f}%"} for g in gainers])
                st.dataframe(gdf, use_container_width=True, hide_index=True)
        with lc:
            st.markdown("**Top Losers**")
            losers = [s for s in reversed(sorted_s) if s["change_pct"] < 0][:5]
            if losers:
                ldf = pd.DataFrame([{"Stock": config.get_clean_ticker(l["symbol"]), "Price": f"{cs}{l['price']:.2f}", "Change": f"{l['change_pct']:+.2f}%"} for l in losers])
                st.dataframe(ldf, use_container_width=True, hide_index=True)

    # Sector heatmap
    if summaries:
        st.markdown('<div class="section-title"><span class="dot"></span>Sector Performance</div>', unsafe_allow_html=True)
        sector_data = {}
        for s in summaries:
            sec = s["sector"]
            if sec not in sector_data:
                sector_data[sec] = []
            sector_data[sec].append(s["change_pct"])
        sector_avg = {k: round(sum(v)/len(v), 2) for k, v in sector_data.items()}
        sdf = pd.DataFrame(list(sector_avg.items()), columns=["Sector", "Avg Change %"])
        sdf = sdf.sort_values("Avg Change %", ascending=False)
        fig = px.bar(sdf, x="Sector", y="Avg Change %",
                     color="Avg Change %", color_continuous_scale=["#ff4757", "#ffa502", "#00d4aa"])
        fig.update_layout(**PLOTLY_LAYOUT, height=300, coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

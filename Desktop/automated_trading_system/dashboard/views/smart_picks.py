"""Smart Picks page — AI-curated recommendations for beginners."""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import config
from strategy import STRATEGIES
from data.indicators import TechnicalIndicators


def metric_card(label, value, accent="", sub="", val_class=""):
    ac = f"accent-{accent}" if accent else ""
    vc = f"val-{val_class}" if val_class else ""
    st.markdown(f"""<div class="glass-card {ac}">
        <div class="card-label">{label}</div>
        <div class="card-value {vc}">{value}</div>
        <div class="card-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


def render(db, fetcher):
    cs = config.CURRENCY_SYMBOL
    st.markdown('<div class="page-header"><h1>Smart Picks</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">AI-powered stock recommendations — no expertise needed</div>', unsafe_allow_html=True)

    # Controls
    c1, c2 = st.columns(2)
    with c1:
        market = st.selectbox("MARKET", ["Nifty 50", "US Stocks", "All"], key="sp_mkt")
    with c2:
        risk_pref = st.selectbox("RISK APPETITE", ["Conservative", "Moderate", "Aggressive"], index=1, key="sp_risk")

    if market == "Nifty 50":
        symbols = config.NIFTY50_SYMBOLS[:20]  # Top 20 for speed
    elif market == "US Stocks":
        symbols = config.US_SYMBOLS
    else:
        symbols = config.US_SYMBOLS + config.NIFTY50_SYMBOLS[:15]

    if st.button("Generate Smart Picks", use_container_width=True, type="primary"):
        smart_auto = STRATEGIES["smart_auto"]()
        recommendations = []

        progress = st.progress(0)
        status = st.empty()

        for idx, sym in enumerate(symbols):
            progress.progress((idx + 1) / len(symbols))
            status.text(f"Analyzing {config.get_symbol_name(sym)}...")

            data = fetcher.get_data_from_db(sym)
            if data.empty or len(data) < 60:
                # Try fetching
                data = fetcher.fetch_historical_data(sym, save_to_db=True)
            if data.empty or len(data) < 60:
                continue

            try:
                signals_df = smart_auto.generate_signals(data)
                latest = signals_df.iloc[-1]

                if latest.get("Signal", 0) != 0:
                    confidence = latest.get("Confidence", 0)
                    recommendation = latest.get("Recommendation", "Hold")
                    reason = latest.get("Reason", "")

                    # Risk filter
                    rsi = latest.get("RSI", 50)
                    if risk_pref == "Conservative" and confidence < 60:
                        continue
                    if risk_pref == "Moderate" and confidence < 40:
                        continue

                    # Determine risk level
                    if rsi < 25 or rsi > 75:
                        risk_level = "High"
                    elif rsi < 35 or rsi > 65:
                        risk_level = "Medium"
                    else:
                        risk_level = "Low"

                    recommendations.append({
                        "symbol": sym,
                        "name": config.get_symbol_name(sym),
                        "sector": config.get_symbol_sector(sym),
                        "price": round(latest["Close"], 2),
                        "signal": recommendation,
                        "confidence": round(confidence, 1),
                        "reason": reason,
                        "risk_level": risk_level,
                        "rsi": round(rsi, 1),
                    })

                    # Save to DB
                    db.save_recommendation(
                        symbol=sym, signal_type=recommendation,
                        confidence=confidence, reason=reason,
                        strategy_name="Smart_Auto",
                        price_at_signal=round(latest["Close"], 2),
                        risk_level=risk_level,
                    )
            except Exception:
                continue

        progress.empty()
        status.empty()
        st.session_state["smart_picks"] = recommendations

    # Display recommendations
    picks = st.session_state.get("smart_picks", [])
    if picks:
        buys = [p for p in picks if "Buy" in p["signal"]]
        sells = [p for p in picks if "Sell" in p["signal"]]

        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Total Picks", len(picks), accent="blue")
        with c2: metric_card("Buy Signals", len(buys), accent="green", val_class="green")
        with c3: metric_card("Sell Signals", len(sells), accent="red", val_class="red")
        with c4:
            avg_conf = sum(p["confidence"] for p in picks) / len(picks) if picks else 0
            metric_card("Avg Confidence", f"{avg_conf:.0f}%", accent="amber")

        # Render each pick as a card
        st.markdown('<div class="section-title"><span class="dot"></span>Recommendations</div>', unsafe_allow_html=True)

        for pick in sorted(picks, key=lambda x: x["confidence"], reverse=True):
            signal = pick["signal"]
            if "Strong Buy" in signal:
                emoji, color = "🟢", "#00d4aa"
            elif "Buy" in signal:
                emoji, color = "🟢", "#00d4aa"
            elif "Strong Sell" in signal:
                emoji, color = "🔴", "#ff4757"
            else:
                emoji, color = "🔴", "#ff4757"

            risk_emoji = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(pick["risk_level"], "🟡")
            ticker = config.get_clean_ticker(pick["symbol"])

            st.markdown(f"""
            <div style="background:rgba(17,24,39,0.85); border:1px solid rgba(255,255,255,0.06);
                border-radius:14px; padding:18px 20px; margin-bottom:10px;
                border-left:4px solid {color};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:18px; font-weight:700; color:#e8ecf1;">{ticker}</span>
                        <span style="font-size:12px; color:#8492a6; margin-left:8px;">{pick['name']}</span>
                        <span style="font-size:10px; color:#5a6577; margin-left:8px;">({pick['sector']})</span>
                    </div>
                    <div>
                        <span style="font-size:16px; font-weight:700; color:{color};">{emoji} {signal}</span>
                        <span style="font-size:13px; color:#8492a6; margin-left:12px;">{pick['confidence']:.0f}% confidence</span>
                    </div>
                </div>
                <div style="margin-top:8px; font-size:12px; color:#8492a6;">
                    {cs}{pick['price']:.2f} &nbsp;|&nbsp; RSI: {pick['rsi']:.0f} &nbsp;|&nbsp;
                    Risk: {risk_emoji} {pick['risk_level']}
                </div>
                <div style="margin-top:6px; font-size:11px; color:#6c5ce7; font-style:italic;">
                    Why: {pick['reason']}
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        # Show recent recommendations from DB
        recent = db.get_recommendations(limit=10)
        if recent:
            st.markdown('<div class="section-title"><span class="dot"></span>Recent Picks</div>', unsafe_allow_html=True)
            df = pd.DataFrame([{
                "Time": r.timestamp.strftime("%Y-%m-%d %H:%M") if r.timestamp else "",
                "Stock": config.get_clean_ticker(r.symbol),
                "Signal": r.signal_type,
                "Confidence": f"{r.confidence:.0f}%",
                "Price": f"{cs}{r.price_at_signal:.2f}" if r.price_at_signal else "-",
                "Risk": r.risk_level or "-",
            } for r in recent])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.markdown("""<div class="empty-state">
                <div class="empty-icon">🧠</div>
                <div class="empty-text">Click "Generate Smart Picks" to get AI recommendations</div>
                <div class="empty-hint">The system analyzes all stocks using 5 strategies simultaneously</div>
            </div>""", unsafe_allow_html=True)

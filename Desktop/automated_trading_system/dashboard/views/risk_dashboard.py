"""Risk Dashboard page — portfolio health, per-position risk, alerts."""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import config


def metric_card(label, value, accent="", sub="", val_class=""):
    ac = f"accent-{accent}" if accent else ""
    vc = f"val-{val_class}" if val_class else ""
    st.markdown(f"""<div class="glass-card {ac}">
        <div class="card-label">{label}</div>
        <div class="card-value {vc}">{value}</div>
        <div class="card-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)


PLOTLY_LAYOUT = dict(
    template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#8492a6"), margin=dict(l=50, r=20, t=40, b=20),
)


def render(db, fetcher):
    cs = config.CURRENCY_SYMBOL
    st.markdown('<div class="page-header"><h1>Risk Dashboard</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Portfolio health monitoring and risk management</div>', unsafe_allow_html=True)

    # Risk settings display
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Stop Loss", f"{config.RISK_STOP_LOSS_PCT}%", accent="red", sub="Per position")
    with c2: metric_card("Trailing Stop", f"{config.RISK_TRAILING_STOP_PCT}%", accent="amber", sub="From peak")
    with c3: metric_card("Take Profit", f"{config.RISK_TAKE_PROFIT_PCT}%", accent="green", sub="Auto-exit")
    with c4: metric_card("Max Daily Loss", f"{config.RISK_MAX_DAILY_LOSS_PCT}%", accent="red", sub="Halt trading")

    # Portfolio risk score gauge
    st.markdown('<div class="section-title"><span class="dot"></span>Portfolio Health</div>', unsafe_allow_html=True)

    positions = db.get_portfolio()
    perf = db.get_performance_summary()

    if positions:
        total_value = sum(p.current_value or 0 for p in positions)
        total_pnl = sum(p.unrealized_pnl or 0 for p in positions)

        # Simple risk score
        risk_score = 75  # Base
        if total_pnl < 0:
            risk_score -= min(40, abs(total_pnl / total_value * 100) * 5) if total_value > 0 else 0
        if len(positions) >= config.RISK_MAX_OPEN_POSITIONS:
            risk_score -= 10
        risk_score = max(0, min(100, int(risk_score)))

        score_color = "#00d4aa" if risk_score >= 70 else ("#ffa502" if risk_score >= 40 else "#ff4757")
        score_label = "Healthy" if risk_score >= 70 else ("Caution" if risk_score >= 40 else "At Risk")

        gc, gc2 = st.columns([1, 2])
        with gc:
            fig = go.Figure(go.Indicator(
                mode="gauge+number", value=risk_score,
                title={"text": "Risk Score", "font": {"size": 14, "color": "#8492a6"}},
                gauge={
                    "axis": {"range": [0, 100], "tickcolor": "#5a6577"},
                    "bar": {"color": score_color},
                    "bgcolor": "rgba(17,24,39,0.8)",
                    "steps": [
                        {"range": [0, 40], "color": "rgba(255,71,87,0.15)"},
                        {"range": [40, 70], "color": "rgba(255,165,2,0.15)"},
                        {"range": [70, 100], "color": "rgba(0,212,170,0.15)"},
                    ],
                },
                number={"suffix": "%", "font": {"color": score_color}},
            ))
            fig.update_layout(**PLOTLY_LAYOUT, height=250)
            st.plotly_chart(fig, use_container_width=True)

        with gc2:
            c1, c2, c3 = st.columns(3)
            with c1:
                pnl_c = "green" if total_pnl >= 0 else "red"
                metric_card("Unrealized P&L", f"{cs}{total_pnl:,.2f}", accent=pnl_c, val_class=pnl_c)
            with c2: metric_card("Open Positions", f"{len(positions)}/{config.RISK_MAX_OPEN_POSITIONS}", accent="blue")
            with c3: metric_card("Status", score_label, accent="green" if risk_score >= 70 else "red")

        # Per-position risk table
        st.markdown('<div class="section-title"><span class="dot"></span>Position Risk Monitor</div>', unsafe_allow_html=True)
        pos_data = []
        for p in positions:
            pnl_pct = ((p.current_price - p.avg_cost) / p.avg_cost * 100) if p.avg_cost and p.current_price else 0
            sl = p.avg_cost * (1 - config.RISK_STOP_LOSS_PCT / 100)
            tp = p.avg_cost * (1 + config.RISK_TAKE_PROFIT_PCT / 100)
            risk = "🟢 Low" if pnl_pct > 0 else ("🟡 Med" if pnl_pct > -config.RISK_STOP_LOSS_PCT/2 else "🔴 High")
            pos_data.append({
                "Stock": config.get_clean_ticker(p.symbol),
                "Qty": p.quantity,
                "Entry": f"{cs}{p.avg_cost:.2f}",
                "Current": f"{cs}{p.current_price:.2f}" if p.current_price else "-",
                "P&L %": f"{pnl_pct:+.2f}%",
                "Stop Loss": f"{cs}{sl:.2f}",
                "Take Profit": f"{cs}{tp:.2f}",
                "Risk": risk,
            })
        st.dataframe(pd.DataFrame(pos_data), use_container_width=True, hide_index=True)
    else:
        st.markdown("""<div class="empty-state">
            <div class="empty-icon">🛡️</div>
            <div class="empty-text">No open positions</div>
            <div class="empty-hint">Risk monitoring activates when you have active trades</div>
        </div>""", unsafe_allow_html=True)

    # Risk events log
    st.markdown('<div class="section-title"><span class="dot"></span>Risk Events Log</div>', unsafe_allow_html=True)
    events = db.get_risk_events(limit=20)
    if events:
        edf = pd.DataFrame([{
            "Time": e.timestamp.strftime("%m-%d %H:%M") if e.timestamp else "",
            "Stock": config.get_clean_ticker(e.symbol),
            "Event": e.event_type,
            "Severity": {"danger": "🔴", "warning": "🟡", "info": "🟢"}.get(e.severity, "⚪") + f" {e.severity.title()}",
            "Message": e.message[:60],
            "Action": e.action_taken or "-",
        } for e in events])
        st.dataframe(edf, use_container_width=True, hide_index=True)
    else:
        st.info("No risk events recorded yet.")

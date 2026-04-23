"""Broker Connect page — link demat account, manage connection."""
import streamlit as st
import config
from broker import get_broker


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
    st.markdown('<div class="page-header"><h1>Broker Connect</h1></div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Link your demat account for live trading</div>', unsafe_allow_html=True)

    # Current connection status
    broker = st.session_state.get("broker")
    if broker and broker.is_connected():
        info = broker.get_account_info()
        st.markdown(f"""
        <div style="background:rgba(0,212,170,0.08); border:1px solid rgba(0,212,170,0.25);
            border-radius:14px; padding:16px 20px; margin-bottom:20px;">
            <span class="live-dot"></span>
            <span style="font-size:14px; font-weight:600; color:#00d4aa;">
                Connected to {info.broker_name}
            </span>
            <span style="font-size:12px; color:#8492a6; margin-left:12px;">
                {"LIVE" if broker.is_live else "PAPER"} Mode
            </span>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns(4)
        with c1: metric_card("Available Cash", f"{cs}{info.available_cash:,.2f}", accent="green")
        with c2: metric_card("Total Value", f"{cs}{info.total_value:,.2f}", accent="blue")
        with c3: metric_card("Positions", info.positions_count, accent="amber")
        with c4:
            mode = "LIVE" if broker.is_live else "PAPER"
            metric_card("Mode", mode, accent="red" if broker.is_live else "green")

        # Holdings from broker
        positions = broker.get_positions()
        if positions:
            st.markdown('<div class="section-title"><span class="dot"></span>Demat Holdings</div>', unsafe_allow_html=True)
            import pandas as pd
            pdf = pd.DataFrame([{
                "Stock": config.get_clean_ticker(p.symbol),
                "Qty": p.quantity,
                "Avg Cost": f"{cs}{p.avg_cost:.2f}",
                "Current": f"{cs}{p.current_price:.2f}" if p.current_price else "-",
                "P&L": f"{cs}{p.pnl:.2f}" if p.pnl else "-",
            } for p in positions])
            st.dataframe(pdf, use_container_width=True, hide_index=True)

        if st.button("Disconnect", use_container_width=True, type="secondary"):
            broker.disconnect()
            st.session_state["broker"] = None
            # Clear persisted broker state
            user = st.session_state.get("user")
            if user:
                db.clear_broker_state(user.get("user_id", 0))
            st.rerun()
        return

    # Connection form
    st.markdown('<div class="section-title"><span class="dot"></span>Select Broker</div>', unsafe_allow_html=True)

    broker_type = st.radio("Broker", ["Paper Trading (Free)", "Zerodha Kite", "Angel One"],
                           horizontal=True, label_visibility="collapsed")

    if broker_type == "Paper Trading (Free)":
        st.info("Paper trading uses virtual money. No demat account needed.")
        capital = st.number_input("Starting Capital", value=100000.0, step=10000.0, min_value=1000.0)
        if st.button("Start Paper Trading", use_container_width=True, type="primary"):
            from broker.paper import PaperBroker
            b = PaperBroker(initial_capital=capital)
            b.connect()
            st.session_state["broker"] = b
            # Persist broker state
            user = st.session_state.get("user")
            if user:
                db.save_broker_state(
                    user_id=user.get("user_id", 0),
                    broker_type="paper", is_connected=True,
                    cash=capital, initial_capital=capital,
                    positions={}, daily_pnl=0.0,
                )
            st.success("Paper trading started!")
            st.rerun()

    elif broker_type == "Zerodha Kite":
        st.warning("Requires Zerodha account + Kite Connect API subscription")
        with st.form("zerodha_form"):
            api_key = st.text_input("API Key", value=config.ZERODHA_API_KEY)
            api_secret = st.text_input("API Secret", type="password", value=config.ZERODHA_API_SECRET)
            request_token = st.text_input("Request Token (from Kite login)")
            st.markdown("Get request token: login at [kite.trade](https://kite.trade/)")
            submitted = st.form_submit_button("Connect", use_container_width=True, type="primary")
            if submitted:
                from broker.zerodha import ZerodhaBroker
                b = ZerodhaBroker()
                if b.connect(api_key=api_key, api_secret=api_secret, request_token=request_token):
                    st.session_state["broker"] = b
                    st.success("Connected to Zerodha!")
                    st.rerun()
                else:
                    st.error("Connection failed. Check credentials.")

    elif broker_type == "Angel One":
        st.warning("Requires Angel One demat account + SmartAPI app")
        with st.form("angel_form"):
            api_key = st.text_input("API Key", value=config.ANGEL_API_KEY)
            client_id = st.text_input("Client ID", value=config.ANGEL_CLIENT_ID)
            password = st.text_input("Password", type="password")
            totp_secret = st.text_input("TOTP Secret", type="password", value=config.ANGEL_TOTP_SECRET)
            submitted = st.form_submit_button("Connect", use_container_width=True, type="primary")
            if submitted:
                from broker.angel import AngelBroker
                b = AngelBroker()
                if b.connect(api_key=api_key, client_id=client_id, password=password, totp_secret=totp_secret):
                    st.session_state["broker"] = b
                    st.success("Connected to Angel One!")
                    st.rerun()
                else:
                    st.error("Connection failed. Check credentials.")

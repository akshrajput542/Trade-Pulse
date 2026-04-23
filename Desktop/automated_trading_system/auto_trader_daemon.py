"""
Auto-Trader Daemon — Background process for automated trading.

Runs independently of the browser. Reads config from DB, executes trades,
persists state. Survives browser close.

Usage:
    python auto_trader_daemon.py --user-id 1
    python auto_trader_daemon.py --user-id 1 --once
"""

import sys
import os
import time
import json
import argparse
import logging
from datetime import datetime, timedelta

# Fix Windows encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from database.db_manager import DatabaseManager
from data.fetcher import DataFetcher
from strategy import STRATEGIES
from risk.manager import RiskManager
from broker.paper import PaperBroker


# ──────────────────────────────────────────────
#  Logger
# ──────────────────────────────────────────────
LOG_FILE = os.path.join(config.BASE_DIR, "auto_trade.log")

def setup_logger():
    logger = logging.getLogger("AutoTrader")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)-7s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    try:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass

    return logger

log = setup_logger()


# ──────────────────────────────────────────────
#  Broker State Persistence
# ──────────────────────────────────────────────
def restore_broker(db: DatabaseManager, user_id: int) -> PaperBroker:
    """Restore paper broker from DB state, or create new one."""
    state = db.get_broker_state(user_id)
    if state and state["broker_type"] == "paper" and state["is_connected"]:
        broker = PaperBroker(
            initial_capital=state["initial_capital"],
        )
        broker.connect()
        broker.cash = state["cash"]
        broker._daily_pnl = state.get("daily_pnl", 0.0)
        # Restore positions
        for sym, pos_data in state.get("positions", {}).items():
            broker._positions[sym] = {
                "quantity": pos_data["quantity"],
                "avg_cost": pos_data["avg_cost"],
            }
        log.info(f"  Restored broker: cash={config.CURRENCY_SYMBOL}{broker.cash:,.2f}, "
                 f"positions={len(broker._positions)}")
        return broker
    else:
        broker = PaperBroker(initial_capital=config.INITIAL_CAPITAL)
        broker.connect()
        log.info(f"  New paper broker: cash={config.CURRENCY_SYMBOL}{broker.cash:,.2f}")
        return broker


def persist_broker(db: DatabaseManager, user_id: int, broker: PaperBroker):
    """Save broker state to DB."""
    positions = {}
    for sym, data in broker._positions.items():
        positions[sym] = {
            "quantity": data["quantity"],
            "avg_cost": data["avg_cost"],
        }
    db.save_broker_state(
        user_id=user_id,
        broker_type="paper",
        is_connected=broker.is_connected(),
        cash=broker.cash,
        initial_capital=broker.initial_capital,
        positions=positions,
        daily_pnl=broker._daily_pnl,
    )


# ──────────────────────────────────────────────
#  Auto-Trade Execution Cycle
# ──────────────────────────────────────────────
def execute_trade_cycle(db: DatabaseManager, fetcher: DataFetcher,
                        broker: PaperBroker, user_id: int,
                        cfg: dict) -> dict:
    """
    Single auto-trade cycle:
    1. Fetch latest data
    2. Generate signals
    3. Execute BUY on buy signals
    4. Execute SELL on sell signals + risk-based exits
    5. Persist state
    """
    cs = config.CURRENCY_SYMBOL
    strategy_name = cfg["strategy_name"]
    symbols = cfg["symbols"]
    max_pos_pct = cfg.get("max_position_pct", 0.2)
    stop_loss_pct = cfg.get("stop_loss_pct", config.RISK_STOP_LOSS_PCT)
    take_profit_pct = cfg.get("take_profit_pct", config.RISK_TAKE_PROFIT_PCT)

    if strategy_name not in STRATEGIES:
        log.error(f"  Unknown strategy: {strategy_name}")
        return {"trades": 0, "errors": 1}

    strategy = STRATEGIES[strategy_name]()
    risk_mgr = RiskManager(
        stop_loss_pct=stop_loss_pct,
        take_profit_pct=take_profit_pct,
        initial_capital=broker.initial_capital,
    )

    # Register existing positions with risk manager
    for sym, pos_data in broker._positions.items():
        risk_mgr.register_position(sym, pos_data["avg_cost"], int(pos_data["quantity"]))

    trades_executed = 0
    errors = 0

    for symbol in symbols:
        try:
            # Fetch latest data
            df = fetcher.fetch_latest_data(symbol, period="5d")
            data = fetcher.get_data_from_db(symbol)
            if data.empty or len(data) < 50:
                continue

            # Generate signals
            signals_df = strategy.generate_signals(data)
            if signals_df.empty:
                continue

            latest = signals_df.iloc[-1]
            latest_price = float(latest["Close"])
            signal = int(latest.get("Signal", 0))

            # ── Risk-based auto-sell (check existing positions) ──
            if symbol in broker._positions:
                triggers = risk_mgr.update_price(symbol, latest_price)
                pos = broker._positions[symbol]
                qty = int(pos["quantity"])

                for trigger in triggers:
                    if trigger in ("STOP_LOSS", "TRAILING_STOP", "TAKE_PROFIT"):
                        log.info(f"  🔴 RISK {trigger}: Selling {qty} {symbol} @ {cs}{latest_price:.2f}")
                        result = broker.place_order(symbol, "SELL", qty, "MARKET", latest_price)
                        if result.success:
                            db.save_trade(
                                symbol=symbol, side="SELL", quantity=result.quantity,
                                price=result.price, commission=result.commission,
                                slippage=0.0, total_cost=result.price * result.quantity,
                                pnl=result.pnl, strategy_name=f"AutoTrade_{trigger}",
                            )
                            db.save_risk_event(
                                symbol=symbol, event_type=trigger, severity="warning",
                                message=f"Auto-sold {qty} shares at {cs}{latest_price:.2f}",
                                action_taken="SELL", price_at_event=latest_price,
                                pnl_at_event=result.pnl,
                            )
                            risk_mgr.record_exit(symbol, result.pnl)
                            trades_executed += 1
                            log.info(f"    P&L: {cs}{result.pnl:.2f}")
                        break  # Only execute one risk trigger per symbol

            # ── Strategy-based SELL ──
            if signal == -1 and symbol in broker._positions:
                pos = broker._positions[symbol]
                qty = int(pos["quantity"])
                log.info(f"  🔴 SELL signal: {qty} {symbol} @ {cs}{latest_price:.2f}")
                result = broker.place_order(symbol, "SELL", qty, "MARKET", latest_price)
                if result.success:
                    db.save_trade(
                        symbol=symbol, side="SELL", quantity=result.quantity,
                        price=result.price, commission=result.commission,
                        slippage=0.0, total_cost=result.price * result.quantity,
                        pnl=result.pnl, strategy_name=f"AutoTrade_{strategy.name}",
                    )
                    risk_mgr.record_exit(symbol, result.pnl)
                    trades_executed += 1
                    log.info(f"    P&L: {cs}{result.pnl:.2f}")

            # ── Strategy-based BUY ──
            elif signal == 1 and symbol not in broker._positions:
                # Check risk constraints
                portfolio_value = broker.cash + sum(
                    p["quantity"] * p["avg_cost"] for p in broker._positions.values()
                )
                max_invest = portfolio_value * max_pos_pct
                can_open, reason = risk_mgr.can_open_position(symbol, max_invest, portfolio_value)

                if can_open:
                    qty = int(max_invest / latest_price)
                    if qty > 0:
                        log.info(f"  🟢 BUY signal: {qty} {symbol} @ {cs}{latest_price:.2f}")
                        result = broker.place_order(symbol, "BUY", qty, "MARKET", latest_price)
                        if result.success:
                            db.save_trade(
                                symbol=symbol, side="BUY", quantity=result.quantity,
                                price=result.price, commission=result.commission,
                                slippage=0.0, total_cost=result.price * result.quantity + result.commission,
                                strategy_name=f"AutoTrade_{strategy.name}",
                            )
                            risk_mgr.register_position(symbol, result.price, result.quantity)
                            # Update portfolio in DB
                            db.update_portfolio(symbol, result.quantity, result.price, latest_price)
                            trades_executed += 1
                else:
                    log.info(f"  ⚠️ Skip BUY {symbol}: {reason}")

        except Exception as e:
            log.error(f"  ERR {symbol}: {e}")
            errors += 1

    # Persist broker state after cycle
    persist_broker(db, user_id, broker)
    db.update_auto_trade_last_run(user_id)

    return {"trades": trades_executed, "errors": errors}


# ──────────────────────────────────────────────
#  Daemon Loop
# ──────────────────────────────────────────────
def run_daemon(user_id: int, once: bool = False):
    """Main daemon loop. Reads config from DB, runs trade cycles."""
    db = DatabaseManager()
    db.init_db()
    fetcher = DataFetcher(db_manager=db)

    log.info("")
    log.info("=" * 55)
    log.info("  TRADEPULSE AUTO-TRADER DAEMON")
    log.info(f"  User ID: {user_id}")
    log.info(f"  Mode: {'Single run' if once else 'Continuous'}")
    log.info(f"  PID: {os.getpid()}")
    log.info("=" * 55)

    # Restore or create broker
    broker = restore_broker(db, user_id)

    cycle = 0
    while True:
        cycle += 1

        # Read config from DB (may have changed via dashboard)
        cfg = db.get_auto_trade_config(user_id)
        if not cfg:
            log.info(f"[Cycle {cycle}] No auto-trade config found. Waiting...")
            if once:
                break
            time.sleep(60)
            continue

        if not cfg["is_active"] and not once:
            log.info(f"[Cycle {cycle}] Auto-trade is STOPPED. Exiting daemon.")
            break

        interval = cfg.get("interval_minutes", 15)

        # Check market hours
        if cfg.get("market_hours_only", True):
            now = datetime.now()
            h, m = now.hour, now.minute
            now_mins = h * 60 + m
            # Indian market: 9:15 - 15:30
            if now.weekday() >= 5 or now_mins < 555 or now_mins > 930:
                log.info(f"[Cycle {cycle}] Market closed. Sleeping {interval} min...")
                if once:
                    break
                time.sleep(interval * 60)
                continue

        log.info(f"\n[Cycle {cycle}] Starting trade cycle...")
        log.info(f"  Strategy: {cfg['strategy_name']}")
        log.info(f"  Symbols: {len(cfg['symbols'])}")
        log.info(f"  Broker cash: {config.CURRENCY_SYMBOL}{broker.cash:,.2f}")

        try:
            result = execute_trade_cycle(db, fetcher, broker, user_id, cfg)
            log.info(f"[Cycle {cycle}] Done: {result['trades']} trades, {result['errors']} errors")
        except Exception as e:
            log.error(f"[Cycle {cycle}] FAILED: {e}")

        if once:
            break

        log.info(f"  Next cycle in {interval} minutes...\n")
        time.sleep(interval * 60)

    log.info("Daemon stopped.")


# ──────────────────────────────────────────────
#  CLI Entry Point
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="TradePulse Auto-Trader Daemon")
    parser.add_argument("--user-id", type=int, required=True, help="User ID to trade for")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    args = parser.parse_args()

    try:
        run_daemon(user_id=args.user_id, once=args.once)
    except KeyboardInterrupt:
        log.info("\nDaemon stopped by user.")


if __name__ == "__main__":
    main()

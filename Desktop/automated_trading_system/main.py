"""
Automated Trading System - CLI Entry Point

Commands:
    python main.py fetch       - Download market data for all default symbols
    python main.py analyze     - Run all strategies and generate signals
    python main.py backtest    - Run backtest (use --strategy and --symbol flags)
    python main.py run         - Full pipeline: fetch -> analyze -> simulate trades
    python main.py dashboard   - Launch the Streamlit dashboard
    python main.py status      - Show system status and recent activity
    python main.py auto-update - Start auto-update scheduler for live data
"""

import sys
import os

# Fix Windows console encoding for unicode output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import argparse
from datetime import datetime

import pandas as pd

import config
from database.db_manager import DatabaseManager
from data.fetcher import DataFetcher
from data.indicators import TechnicalIndicators
from strategy import STRATEGIES
from backtest.engine import BacktestEngine
from execution.simulator import PaperTrader


def init_system():
    """Initialize database and core services."""
    db = DatabaseManager()
    db.init_db()
    fetcher = DataFetcher(db_manager=db)
    return db, fetcher


def cmd_fetch(args):
    """Fetch market data for configured symbols."""
    db, fetcher = init_system()

    symbols = args.symbols.split(",") if args.symbols else config.DEFAULT_SYMBOLS
    start = args.start or config.DEFAULT_START_DATE
    end = args.end or config.DEFAULT_END_DATE

    print(f"\n{'='*60}")
    print(f"  Fetching real-time data for {len(symbols)} stocks")
    print(f"  Period: {start} -> {end}")
    print(f"{'='*60}")
    for sym in symbols:
        print(f"    {sym:>5s}  {config.get_symbol_name(sym)}")
    print()

    fetcher.fetch_multiple_symbols(symbols=symbols, start=start, end=end)


def cmd_analyze(args):
    """Run all strategies on all symbols and save signals."""
    db, fetcher = init_system()

    symbols = args.symbols.split(",") if args.symbols else config.DEFAULT_SYMBOLS
    strategy_names = args.strategies.split(",") if args.strategies else list(STRATEGIES.keys())

    print(f"\n{'='*60}")
    print(f"  Analyzing {len(symbols)} stocks with {len(strategy_names)} strategies")
    print(f"{'='*60}\n")

    all_signals = []

    for symbol in symbols:
        name = config.get_symbol_name(symbol)
        print(f"\n  Analyzing {symbol} ({name})...")
        data = fetcher.get_data_from_db(symbol)

        if data.empty:
            print(f"   [WARN] No data for {symbol}. Run 'fetch' first.")
            continue

        for strat_name in strategy_names:
            if strat_name not in STRATEGIES:
                print(f"   [WARN] Unknown strategy: {strat_name}")
                continue

            strategy = STRATEGIES[strat_name]()
            signals_df = strategy.generate_signals(data)

            # Extract actionable signals (BUY/SELL only)
            actionable = signals_df[signals_df["Signal"] != 0]

            for idx, row in actionable.iterrows():
                signal_type = "BUY" if row["Signal"] == 1 else "SELL"
                signal_record = {
                    "symbol": symbol,
                    "strategy_name": strategy.name,
                    "signal_type": signal_type,
                    "price": float(row["Close"]),
                    "timestamp": idx,
                }
                all_signals.append(signal_record)

            buy_count = len(actionable[actionable["Signal"] == 1])
            sell_count = len(actionable[actionable["Signal"] == -1])
            print(f"   {strategy.name}: {buy_count} BUY, {sell_count} SELL signals")

    if all_signals:
        db.save_signals_bulk(all_signals)
        print(f"\n[OK] Total: {len(all_signals)} signals generated and saved.\n")
    else:
        print("\n[WARN] No actionable signals generated.\n")


def cmd_backtest(args):
    """Run backtest for a specific strategy and symbol."""
    db, fetcher = init_system()

    strat_name = args.strategy or "sma"
    symbol = args.symbol or "AAPL"
    start = args.start or config.DEFAULT_START_DATE
    end = args.end or config.DEFAULT_END_DATE

    if strat_name not in STRATEGIES:
        print(f"[ERROR] Unknown strategy: {strat_name}")
        print(f"   Available: {', '.join(STRATEGIES.keys())}")
        return

    name = config.get_symbol_name(symbol)
    print(f"\n  Backtesting {strat_name} on {symbol} ({name})")

    strategy = STRATEGIES[strat_name]()
    engine = BacktestEngine(strategy=strategy, db_manager=db)
    result = engine.run(symbol=symbol, start=start, end=end)


def cmd_run(args):
    """Full pipeline: fetch -> analyze -> simulate trades on latest signals."""
    db, fetcher = init_system()

    symbols = args.symbols.split(",") if args.symbols else config.DEFAULT_SYMBOLS
    strat_name = args.strategy or "sma"

    if strat_name not in STRATEGIES:
        print(f"[ERROR] Unknown strategy: {strat_name}")
        return

    strategy = STRATEGIES[strat_name]()

    print(f"\n{'='*60}")
    print(f"  Full Pipeline: {strategy.name}")
    print(f"  Stocks:")
    for s in symbols:
        print(f"    {s:>5s}  {config.get_symbol_name(s)}")
    print(f"{'='*60}")

    # Step 1: Fetch data
    print("\n-- Step 1: Fetching Data --")
    fetcher.fetch_multiple_symbols(symbols=symbols)

    # Step 2: Generate signals & execute trades
    print("\n-- Step 2: Analyzing & Trading --")
    trader = PaperTrader(strategy_name=strategy.name, db_manager=db)

    for symbol in symbols:
        data = fetcher.get_data_from_db(symbol)
        if data.empty:
            continue

        signals_df = strategy.generate_signals(data)

        # Save signals to DB
        actionable = signals_df[signals_df["Signal"] != 0]
        signal_records = []
        for idx, row in actionable.iterrows():
            signal_type = "BUY" if row["Signal"] == 1 else "SELL"
            signal_records.append({
                "symbol": symbol,
                "strategy_name": strategy.name,
                "signal_type": signal_type,
                "price": float(row["Close"]),
                "timestamp": idx,
            })

        if signal_records:
            db.save_signals_bulk(signal_records)

        # Execute on the latest signal
        if not actionable.empty:
            latest_signal = actionable.iloc[-1]
            latest_price = latest_signal["Close"]

            if latest_signal["Signal"] == 1:
                # BUY signal - invest up to 20% of capital per position
                max_invest = trader.cash * 0.2
                quantity = int(max_invest / latest_price)
                if quantity > 0:
                    trader.execute_buy(symbol, quantity, latest_price)
            elif latest_signal["Signal"] == -1:
                # SELL signal - sell all shares
                pos = trader.get_position(symbol)
                if pos:
                    trader.execute_sell(symbol, int(pos["quantity"]), latest_price)

    # Status
    status = trader.get_status()
    cs = config.CURRENCY_SYMBOL
    print(f"\n{'='*60}")
    print(f"  Paper Trading Status")
    print(f"{'='*60}")
    print(f"  Cash:             {cs}{status['cash']:>12,.2f}")
    print(f"  Positions Value:  {cs}{status['positions_value']:>12,.2f}")
    print(f"  Total Value:      {cs}{status['total_value']:>12,.2f}")
    print(f"  Return:           {status['return_pct']:>11.2f}%")
    print(f"  Active Positions: {status['num_positions']}")
    for sym, pos in status['positions'].items():
        name = config.get_symbol_name(sym)
        print(f"    {sym} ({name}): {pos['quantity']} shares @ {cs}{pos['avg_cost']:.2f}")
    print(f"{'='*60}\n")


def cmd_dashboard(args):
    """Launch the Streamlit dashboard."""
    import subprocess
    dashboard_path = "dashboard/app.py"
    print(f"\nLaunching TradePulse dashboard at http://localhost:{config.DASHBOARD_PORT}")
    print("   Press Ctrl+C to stop.\n")
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", dashboard_path,
        "--server.port", str(config.DASHBOARD_PORT),
        "--theme.base", "dark",
        "--theme.primaryColor", "#00d4aa",
        "--theme.backgroundColor", "#06080d",
        "--theme.secondaryBackgroundColor", "#0c1018",
        "--theme.textColor", "#e8ecf1",
    ])


def cmd_status(args):
    """Show system status and recent activity."""
    db, _ = init_system()

    perf = db.get_performance_summary()
    recent_signals = db.get_signals(limit=10)
    recent_trades = db.get_trades(limit=10)
    positions = db.get_portfolio()

    print(f"\n{'='*60}")
    print(f"  TradePulse System Status")
    print(f"{'='*60}")
    print(f"  Tracked Stocks ({len(config.DEFAULT_SYMBOLS)}):")
    for sym in config.DEFAULT_SYMBOLS:
        print(f"    {sym:>5s}  {config.get_symbol_name(sym)}")
    cs = config.CURRENCY_SYMBOL
    print(f"  Total Signals:     {perf['total_signals']}")
    print(f"  Total Trades:      {perf['total_trades']}")
    print(f"  Total P&L:         {cs}{perf['total_pnl']:,.2f}")
    print(f"  Win Rate:          {perf['win_rate']:.1f}%")
    print(f"  Active Positions:  {len(positions)}")

    if recent_signals:
        print(f"\n-- Recent Signals (last {len(recent_signals)}) --")
        for s in recent_signals[:5]:
            name = config.get_symbol_name(s.symbol)
            print(f"  {s.timestamp} | {s.signal_type:4s} | {s.symbol:5s} ({name}) | "
                  f"{cs}{s.price:.2f} | {s.strategy_name}")

    if recent_trades:
        print(f"\n-- Recent Trades (last {len(recent_trades)}) --")
        for t in recent_trades[:5]:
            name = config.get_symbol_name(t.symbol)
            pnl_str = f"P&L: {cs}{t.pnl:.2f}" if t.pnl else ""
            print(f"  {t.timestamp} | {t.side:4s} | {t.symbol:5s} ({name}) | "
                  f"{t.quantity} @ {cs}{t.price:.2f} {pnl_str}")

    print(f"{'='*60}\n")


def cmd_auto_update(args):
    """Start the auto-update scheduler."""
    from scheduler import run_update, run_scheduler
    db, fetcher = init_system()

    if args.once:
        print("\n[AUTO-UPDATE] Running single update cycle...\n")
        run_update(db, fetcher)
    else:
        interval = args.interval
        market_hours = args.market_hours
        print(f"\n[AUTO-UPDATE] Starting scheduler (every {interval} min)")
        print(f"  Market hours only: {market_hours}")
        print("  Press Ctrl+C to stop.\n")
        try:
            run_scheduler(
                interval_minutes=interval,
                market_hours_only=market_hours,
            )
        except KeyboardInterrupt:
            print("\nScheduler stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="TradePulse - Automated Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Download market data")
    fetch_parser.add_argument("--symbols", type=str, help="Comma-separated symbols (e.g. AAPL,MSFT)")
    fetch_parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    fetch_parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")

    # analyze
    analyze_parser = subparsers.add_parser("analyze", help="Generate trading signals")
    analyze_parser.add_argument("--symbols", type=str, help="Comma-separated symbols")
    analyze_parser.add_argument("--strategies", type=str, help="Comma-separated strategies (sma,rsi,macd)")

    # backtest
    bt_parser = subparsers.add_parser("backtest", help="Run backtest")
    bt_parser.add_argument("--strategy", type=str, default="sma", help="Strategy name (sma, rsi, macd)")
    bt_parser.add_argument("--symbol", type=str, default="AAPL", help="Symbol to backtest")
    bt_parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    bt_parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")

    # run
    run_parser = subparsers.add_parser("run", help="Full pipeline: fetch -> analyze -> trade")
    run_parser.add_argument("--symbols", type=str, help="Comma-separated symbols")
    run_parser.add_argument("--strategy", type=str, default="sma", help="Strategy to use")

    # dashboard
    subparsers.add_parser("dashboard", help="Launch Streamlit dashboard")

    # status
    subparsers.add_parser("status", help="Show system status")

    # auto-update
    auto_parser = subparsers.add_parser("auto-update", help="Start auto-update scheduler")
    auto_parser.add_argument("--interval", type=int, default=config.AUTO_UPDATE_INTERVAL_MINUTES,
                             help=f"Update interval in minutes (default: {config.AUTO_UPDATE_INTERVAL_MINUTES})")
    auto_parser.add_argument("--once", action="store_true", help="Run once and exit")
    auto_parser.add_argument("--market-hours", action="store_true",
                             help="Only update during US market hours")

    args = parser.parse_args()

    commands = {
        "fetch": cmd_fetch,
        "analyze": cmd_analyze,
        "backtest": cmd_backtest,
        "run": cmd_run,
        "dashboard": cmd_dashboard,
        "status": cmd_status,
        "auto-update": cmd_auto_update,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

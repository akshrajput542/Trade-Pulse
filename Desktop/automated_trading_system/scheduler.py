"""
Auto-Update Scheduler — Continuously refreshes market data and generates signals.

Features:
    - Fetches latest market data at configurable intervals
    - Runs all strategies on fresh data to generate new signals
    - Logs all activity with timestamps
    - Respects market hours (only updates during trading hours)
    - Can run as a background process or daemon

Usage:
    python scheduler.py                  # Run with default 15-min interval
    python scheduler.py --interval 5     # Run every 5 minutes
    python scheduler.py --once           # Run once and exit
"""

import sys
import os
import time
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

# Ensure project root on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from database.db_manager import DatabaseManager
from data.fetcher import DataFetcher
from strategy import STRATEGIES


# ──────────────────────────────────────────────
#  Logger Setup
# ──────────────────────────────────────────────
def setup_logger():
    logger = logging.getLogger("AutoUpdate")
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    try:
        fh = logging.FileHandler(config.AUTO_UPDATE_LOG_FILE, encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        pass

    return logger


logger = setup_logger()


# ──────────────────────────────────────────────
#  Market Hours Check
# ──────────────────────────────────────────────
def is_market_hours() -> bool:
    """
    Check if US stock market is currently open (rough estimate).
    Market hours: Mon-Fri, 9:30 AM - 4:00 PM Eastern Time.
    This uses a rough UTC offset; for production, use pytz.
    """
    now = datetime.utcnow()
    # Convert UTC to ET (approximate: UTC-4 during EDT, UTC-5 during EST)
    et_hour = (now.hour - 4) % 24  # Rough EDT offset
    weekday = now.weekday()  # 0=Mon, 6=Sun

    if weekday >= 5:  # Weekend
        return False
    if et_hour < config.MARKET_OPEN_HOUR or et_hour >= config.MARKET_CLOSE_HOUR:
        return False
    return True


# ──────────────────────────────────────────────
#  Core Update Logic
# ──────────────────────────────────────────────
def run_update(db: DatabaseManager, fetcher: DataFetcher,
               symbols: list = None, run_signals: bool = True):
    """
    Execute a single update cycle:
    1. Fetch latest market data for all symbols
    2. Generate trading signals with all strategies
    3. Log results

    Returns:
        dict with update summary
    """
    symbols = symbols or config.DEFAULT_SYMBOLS
    timestamp = datetime.now()

    logger.info("=" * 55)
    logger.info("  AUTO-UPDATE CYCLE STARTED")
    logger.info(f"  Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Symbols: {len(symbols)} | Strategies: {len(STRATEGIES)}")
    logger.info("=" * 55)

    # ── Step 1: Fetch latest data ──
    logger.info("[1/2] Fetching latest market data...")
    fetch_results = {}
    for symbol in symbols:
        try:
            name = config.get_symbol_name(symbol)
            df = fetcher.fetch_latest_data(symbol, period="5d")
            if not df.empty:
                fetch_results[symbol] = len(df)
                logger.info(f"  OK  {symbol:>5s} ({name}): {len(df)} records")
            else:
                logger.warning(f"  WARN {symbol:>5s}: No data returned")
        except Exception as e:
            logger.error(f"  ERR  {symbol:>5s}: {e}")

    # Also fetch/update historical data (last 30 days to fill gaps)
    start_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end_today = datetime.now().strftime("%Y-%m-%d")
    for symbol in symbols:
        try:
            fetcher.fetch_historical_data(
                symbol, start=start_30d, end=end_today, save_to_db=True
            )
        except Exception:
            pass

    # ── Step 2: Generate signals ──
    total_signals = 0
    if run_signals:
        logger.info("[2/2] Generating trading signals...")
        all_signals = []

        for symbol in symbols:
            data = fetcher.get_data_from_db(symbol)
            if data.empty or len(data) < 50:
                continue

            for strat_name, strat_cls in STRATEGIES.items():
                try:
                    strategy = strat_cls()
                    signals_df = strategy.generate_signals(data)
                    actionable = signals_df[signals_df["Signal"] != 0]

                    # Only save signals from the last 5 days (avoid duplicates)
                    cutoff = datetime.now() - timedelta(days=5)
                    recent = actionable[actionable.index >= cutoff]

                    for idx, row in recent.iterrows():
                        signal_type = "BUY" if row["Signal"] == 1 else "SELL"
                        all_signals.append({
                            "symbol": symbol,
                            "strategy_name": strategy.name,
                            "signal_type": signal_type,
                            "price": float(row["Close"]),
                            "timestamp": idx,
                        })
                except Exception as e:
                    logger.error(f"  ERR  {symbol}/{strat_name}: {e}")

        if all_signals:
            db.save_signals_bulk(all_signals)
            total_signals = len(all_signals)
            logger.info(f"  Saved {total_signals} new signals")
    else:
        logger.info("[2/2] Signal generation skipped")

    # ── Summary ──
    duration = (datetime.now() - timestamp).total_seconds()
    summary = {
        "timestamp": timestamp.isoformat(),
        "symbols_updated": len(fetch_results),
        "symbols_total": len(symbols),
        "signals_generated": total_signals,
        "duration_seconds": round(duration, 1),
        "market_open": is_market_hours(),
    }

    logger.info("-" * 55)
    logger.info(f"  COMPLETED in {duration:.1f}s")
    logger.info(f"  Data: {len(fetch_results)}/{len(symbols)} symbols updated")
    logger.info(f"  Signals: {total_signals} generated")
    logger.info(f"  Market Open: {'Yes' if summary['market_open'] else 'No'}")
    logger.info("=" * 55 + "\n")

    return summary


# ──────────────────────────────────────────────
#  Scheduler Loop
# ──────────────────────────────────────────────
def run_scheduler(interval_minutes: int = None, market_hours_only: bool = False,
                  symbols: list = None):
    """
    Run the auto-update scheduler in a continuous loop.

    Args:
        interval_minutes: Minutes between update cycles
        market_hours_only: If True, skip updates outside market hours
        symbols: List of symbols to track (default: config.DEFAULT_SYMBOLS)
    """
    interval = interval_minutes or config.AUTO_UPDATE_INTERVAL_MINUTES
    symbols = symbols or config.DEFAULT_SYMBOLS

    db = DatabaseManager()
    db.init_db()
    fetcher = DataFetcher(db_manager=db)

    logger.info("")
    logger.info("*" * 55)
    logger.info("  TRADEPULSE AUTO-UPDATE SCHEDULER")
    logger.info(f"  Interval: Every {interval} minutes")
    logger.info(f"  Symbols: {', '.join(symbols)}")
    logger.info(f"  Market Hours Only: {market_hours_only}")
    logger.info("  Press Ctrl+C to stop")
    logger.info("*" * 55)
    logger.info("")

    cycle = 0
    while True:
        cycle += 1

        # Check market hours
        if market_hours_only and not is_market_hours():
            logger.info(f"[Cycle {cycle}] Market closed. Sleeping {interval} min...")
            time.sleep(interval * 60)
            continue

        logger.info(f"[Cycle {cycle}] Starting update...")
        try:
            run_update(db, fetcher, symbols=symbols, run_signals=True)
        except Exception as e:
            logger.error(f"[Cycle {cycle}] Update failed: {e}")

        # Wait for next cycle
        logger.info(f"Next update in {interval} minutes...\n")
        time.sleep(interval * 60)


# ──────────────────────────────────────────────
#  CLI Entry Point
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="TradePulse Auto-Update Scheduler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--interval", type=int, default=config.AUTO_UPDATE_INTERVAL_MINUTES,
        help=f"Update interval in minutes (default: {config.AUTO_UPDATE_INTERVAL_MINUTES})"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run one update cycle and exit"
    )
    parser.add_argument(
        "--market-hours", action="store_true",
        help="Only update during US market hours"
    )
    parser.add_argument(
        "--symbols", type=str, default=None,
        help="Comma-separated symbols (default: all configured)"
    )

    args = parser.parse_args()
    symbols = args.symbols.split(",") if args.symbols else None

    if args.once:
        # Single run mode
        db = DatabaseManager()
        db.init_db()
        fetcher = DataFetcher(db_manager=db)
        run_update(db, fetcher, symbols=symbols)
    else:
        # Continuous scheduler
        try:
            run_scheduler(
                interval_minutes=args.interval,
                market_hours_only=args.market_hours,
                symbols=symbols,
            )
        except KeyboardInterrupt:
            logger.info("\nScheduler stopped by user.")


if __name__ == "__main__":
    main()

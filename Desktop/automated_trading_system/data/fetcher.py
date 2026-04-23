"""
Data fetcher — downloads historical and latest market data via yfinance.
Supports US stocks and Indian NSE stocks (Nifty 50 with .NS suffix).
"""

from datetime import datetime, date
from typing import List, Dict, Optional

import pandas as pd
import yfinance as yf

import config
from database.db_manager import DatabaseManager


def _safe_print(msg: str):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"))


class DataFetcher:
    """Fetches market data from Yahoo Finance and caches to database."""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()

    def fetch_historical_data(self, symbol: str, start: str = None,
                              end: str = None, interval: str = None,
                              save_to_db: bool = True) -> pd.DataFrame:
        """Download historical OHLCV data for a single symbol."""
        start = start or config.DEFAULT_START_DATE
        end = end or config.DEFAULT_END_DATE
        interval = interval or config.DEFAULT_INTERVAL

        name = config.get_symbol_name(symbol)
        _safe_print(f"[FETCH] {symbol} ({name}) ({start} -> {end})...")

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval)

            if df.empty:
                _safe_print(f"   [WARN] No data returned for {symbol}.")
                return pd.DataFrame()

            df.index.name = "Date"
            ohlcv_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[ohlcv_cols]

            if save_to_db:
                self.db.save_market_data(df, symbol)

            _safe_print(f"   [OK] {symbol}: {len(df)} records fetched.")
            return df

        except Exception as e:
            _safe_print(f"   [ERROR] Error fetching {symbol}: {e}")
            return pd.DataFrame()

    def fetch_multiple_symbols(self, symbols: List[str] = None,
                               start: str = None, end: str = None,
                               interval: str = None) -> Dict[str, pd.DataFrame]:
        """Fetch data for multiple symbols."""
        symbols = symbols or config.DEFAULT_SYMBOLS
        results = {}

        _safe_print(f"\n{'='*60}")
        _safe_print(f"  [DATA] Fetching market data for {len(symbols)} symbols")
        _safe_print(f"{'='*60}\n")

        for symbol in symbols:
            df = self.fetch_historical_data(symbol, start=start, end=end, interval=interval)
            if not df.empty:
                results[symbol] = df

        _safe_print(f"\n[OK] Fetched data for {len(results)}/{len(symbols)} symbols.\n")
        return results

    def fetch_latest_data(self, symbol: str, period: str = "5d") -> pd.DataFrame:
        """Fetch the latest few days of data for a symbol."""
        _safe_print(f"[FETCH] Latest data for {symbol} (period={period})...")
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if df.empty:
                return pd.DataFrame()

            df.index.name = "Date"
            ohlcv_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
            df = df[ohlcv_cols]
            self.db.save_market_data(df, symbol)
            _safe_print(f"   [OK] {symbol}: {len(df)} recent records.")
            return df
        except Exception as e:
            _safe_print(f"   [ERROR] {symbol}: {e}")
            return pd.DataFrame()

    def get_data_from_db(self, symbol: str, start_date: date = None,
                         end_date: date = None) -> pd.DataFrame:
        """Retrieve cached market data from the database."""
        return self.db.get_market_data(symbol, start_date, end_date)

    def get_stock_info(self, symbol: str) -> dict:
        """Get basic info about a stock."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "symbol": symbol,
                "name": info.get("longName", config.get_symbol_name(symbol)),
                "sector": info.get("sector", config.get_symbol_sector(symbol)),
                "industry": info.get("industry", "N/A"),
                "market_cap": info.get("marketCap", "N/A"),
                "pe_ratio": info.get("trailingPE", "N/A"),
                "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
                "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
            }
        except Exception:
            return {"symbol": symbol, "name": config.get_symbol_name(symbol),
                    "sector": config.get_symbol_sector(symbol)}

    def get_market_summary(self, symbols: List[str] = None) -> List[dict]:
        """Get summary data for multiple symbols (for heatmap/watchlist)."""
        symbols = symbols or config.DEFAULT_SYMBOLS
        summaries = []
        for sym in symbols:
            data = self.get_data_from_db(sym)
            if data.empty or len(data) < 2:
                continue
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            change = latest["Close"] - prev["Close"]
            change_pct = (change / prev["Close"]) * 100 if prev["Close"] > 0 else 0
            summaries.append({
                "symbol": sym,
                "name": config.get_symbol_name(sym),
                "sector": config.get_symbol_sector(sym),
                "price": round(latest["Close"], 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": latest.get("Volume", 0),
                "high": round(latest["High"], 2),
                "low": round(latest["Low"], 2),
            })
        return summaries

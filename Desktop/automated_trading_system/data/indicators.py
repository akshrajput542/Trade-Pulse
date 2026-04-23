"""
Technical indicators — compute common trading indicators using the `ta` library.
Enhanced with SuperTrend and VWAP for Indian market support.
"""

import pandas as pd
import numpy as np
from ta.trend import SMAIndicator, EMAIndicator, MACD
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.volatility import BollingerBands, AverageTrueRange

import config


class TechnicalIndicators:
    """Utility class to compute technical indicators on OHLCV DataFrames."""

    @staticmethod
    def compute_sma(df: pd.DataFrame, window: int = None, column: str = "Close") -> pd.Series:
        """Simple Moving Average."""
        window = window or config.SMA_SHORT_WINDOW
        indicator = SMAIndicator(close=df[column], window=window)
        return indicator.sma_indicator()

    @staticmethod
    def compute_ema(df: pd.DataFrame, window: int = 20, column: str = "Close") -> pd.Series:
        """Exponential Moving Average."""
        indicator = EMAIndicator(close=df[column], window=window)
        return indicator.ema_indicator()

    @staticmethod
    def compute_rsi(df: pd.DataFrame, period: int = None, column: str = "Close") -> pd.Series:
        """Relative Strength Index."""
        period = period or config.RSI_PERIOD
        indicator = RSIIndicator(close=df[column], window=period)
        return indicator.rsi()

    @staticmethod
    def compute_macd(df: pd.DataFrame, column: str = "Close") -> pd.DataFrame:
        """
        MACD — returns DataFrame with columns:
            - MACD: MACD line
            - MACD_Signal: Signal line
            - MACD_Histogram: Histogram (MACD - Signal)
        """
        indicator = MACD(
            close=df[column],
            window_slow=config.MACD_SLOW_PERIOD,
            window_fast=config.MACD_FAST_PERIOD,
            window_sign=config.MACD_SIGNAL_PERIOD,
        )
        return pd.DataFrame({
            "MACD": indicator.macd(),
            "MACD_Signal": indicator.macd_signal(),
            "MACD_Histogram": indicator.macd_diff(),
        })

    @staticmethod
    def compute_bollinger_bands(df: pd.DataFrame, window: int = None,
                                 std_dev: int = None, column: str = "Close") -> pd.DataFrame:
        """
        Bollinger Bands — returns DataFrame with columns:
            - BB_Upper, BB_Middle, BB_Lower, BB_Width
        """
        window = window or config.BOLLINGER_WINDOW
        std_dev = std_dev or config.BOLLINGER_STD_DEV
        indicator = BollingerBands(close=df[column], window=window, window_dev=std_dev)
        return pd.DataFrame({
            "BB_Upper": indicator.bollinger_hband(),
            "BB_Middle": indicator.bollinger_mavg(),
            "BB_Lower": indicator.bollinger_lband(),
            "BB_Width": indicator.bollinger_wband(),
        })

    @staticmethod
    def compute_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
        """Average True Range — measures volatility."""
        indicator = AverageTrueRange(
            high=df["High"], low=df["Low"], close=df["Close"], window=window
        )
        return indicator.average_true_range()

    @staticmethod
    def compute_stochastic(df: pd.DataFrame, window: int = 14,
                            smooth_window: int = 3) -> pd.DataFrame:
        """
        Stochastic Oscillator — returns DataFrame with:
            - Stoch_K: %K line
            - Stoch_D: %D line (smoothed)
        """
        indicator = StochasticOscillator(
            high=df["High"], low=df["Low"], close=df["Close"],
            window=window, smooth_window=smooth_window,
        )
        return pd.DataFrame({
            "Stoch_K": indicator.stoch(),
            "Stoch_D": indicator.stoch_signal(),
        })

    @staticmethod
    def compute_supertrend(df: pd.DataFrame, period: int = None,
                            multiplier: float = None) -> pd.DataFrame:
        """
        SuperTrend indicator — popular trend indicator in Indian markets.

        Returns DataFrame with:
            - SuperTrend: the SuperTrend line value
            - Direction: 1 (bullish/up) or -1 (bearish/down)
        """
        period = period or config.SUPERTREND_PERIOD
        multiplier = multiplier or config.SUPERTREND_MULTIPLIER

        high = df["High"].values
        low = df["Low"].values
        close = df["Close"].values
        n = len(close)

        # Compute ATR manually for flexibility
        tr = np.zeros(n)
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1])
            )
        # Smoothed ATR using Wilder's method
        atr = np.zeros(n)
        atr[period] = np.mean(tr[1:period + 1])
        for i in range(period + 1, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        # Basic upper and lower bands
        hl2 = (high + low) / 2
        basic_upper = hl2 + multiplier * atr
        basic_lower = hl2 - multiplier * atr

        # Final bands
        final_upper = np.zeros(n)
        final_lower = np.zeros(n)
        supertrend = np.zeros(n)
        direction = np.ones(n)  # 1 = bullish, -1 = bearish

        final_upper[0] = basic_upper[0]
        final_lower[0] = basic_lower[0]

        for i in range(1, n):
            # Upper band
            if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i - 1]

            # Lower band
            if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i - 1]

            # Direction and SuperTrend value
            if i == 0:
                direction[i] = 1
            elif supertrend[i - 1] == final_upper[i - 1]:
                direction[i] = -1 if close[i] <= final_upper[i] else 1
            else:
                direction[i] = 1 if close[i] >= final_lower[i] else -1

            supertrend[i] = final_lower[i] if direction[i] == 1 else final_upper[i]

        return pd.DataFrame({
            "SuperTrend": supertrend,
            "Direction": direction,
        }, index=df.index)

    @staticmethod
    def compute_vwap(df: pd.DataFrame) -> pd.Series:
        """
        Volume Weighted Average Price.
        Useful for intraday trading — shows fair value.
        """
        typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
        vwap = (typical_price * df["Volume"]).cumsum() / df["Volume"].cumsum()
        return vwap

    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute and attach all common indicators to a copy of the DataFrame.
        Useful for dashboard visualization and comprehensive analysis.
        """
        result = df.copy()

        # Moving averages
        result["SMA_20"] = TechnicalIndicators.compute_sma(df, window=20)
        result["SMA_50"] = TechnicalIndicators.compute_sma(df, window=50)
        result["EMA_20"] = TechnicalIndicators.compute_ema(df, window=20)

        # RSI
        result["RSI"] = TechnicalIndicators.compute_rsi(df)

        # MACD
        macd = TechnicalIndicators.compute_macd(df)
        result = pd.concat([result, macd], axis=1)

        # Bollinger Bands
        bb = TechnicalIndicators.compute_bollinger_bands(df)
        result = pd.concat([result, bb], axis=1)

        # ATR
        result["ATR"] = TechnicalIndicators.compute_atr(df)

        # SuperTrend
        st = TechnicalIndicators.compute_supertrend(df)
        result["SuperTrend"] = st["SuperTrend"]
        result["ST_Direction"] = st["Direction"]

        # VWAP (only if Volume exists and is non-zero)
        if "Volume" in df.columns and df["Volume"].sum() > 0:
            result["VWAP"] = TechnicalIndicators.compute_vwap(df)

        return result

"""
MACD (Moving Average Convergence Divergence) Strategy.

BUY  when MACD line crosses ABOVE the signal line.
SELL when MACD line crosses BELOW the signal line.
"""

import pandas as pd
from typing import Dict, Any

from .base import Strategy
from data.indicators import TechnicalIndicators
import config


class MACDStrategy(Strategy):
    """MACD signal line crossover strategy."""

    def __init__(self, fast: int = None, slow: int = None, signal: int = None):
        self.fast = fast or config.MACD_FAST_PERIOD
        self.slow = slow or config.MACD_SLOW_PERIOD
        self.signal_period = signal or config.MACD_SIGNAL_PERIOD

    @property
    def name(self) -> str:
        return f"MACD_{self.fast}_{self.slow}_{self.signal_period}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "fast_period": self.fast,
            "slow_period": self.slow,
            "signal_period": self.signal_period,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate MACD crossover signals.

        Returns DataFrame with columns:
            MACD, MACD_Signal, MACD_Histogram, Signal
        """
        result = df.copy()

        # Compute MACD
        macd_df = TechnicalIndicators.compute_macd(df)
        result["MACD"] = macd_df["MACD"]
        result["MACD_Signal_Line"] = macd_df["MACD_Signal"]
        result["MACD_Histogram"] = macd_df["MACD_Histogram"]

        result["Signal"] = 0

        # BUY when MACD crosses above signal line
        result.loc[
            (result["MACD"] > result["MACD_Signal_Line"]) &
            (result["MACD"].shift(1) <= result["MACD_Signal_Line"].shift(1)),
            "Signal"
        ] = 1  # BUY

        # SELL when MACD crosses below signal line
        result.loc[
            (result["MACD"] < result["MACD_Signal_Line"]) &
            (result["MACD"].shift(1) >= result["MACD_Signal_Line"].shift(1)),
            "Signal"
        ] = -1  # SELL

        return result

"""
SMA Crossover Strategy.

BUY  when short-term SMA crosses ABOVE long-term SMA (golden cross).
SELL when short-term SMA crosses BELOW long-term SMA (death cross).
"""

import pandas as pd
from typing import Dict, Any

from .base import Strategy
from data.indicators import TechnicalIndicators
import config


class SMACrossoverStrategy(Strategy):
    """Simple Moving Average Crossover strategy."""

    def __init__(self, short_window: int = None, long_window: int = None):
        self.short_window = short_window or config.SMA_SHORT_WINDOW
        self.long_window = long_window or config.SMA_LONG_WINDOW

    @property
    def name(self) -> str:
        return f"SMA_Crossover_{self.short_window}_{self.long_window}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "short_window": self.short_window,
            "long_window": self.long_window,
        }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate SMA crossover signals.

        Returns DataFrame with columns:
            SMA_Short, SMA_Long, Signal, Position
        """
        result = df.copy()

        # Compute SMAs
        result["SMA_Short"] = TechnicalIndicators.compute_sma(df, window=self.short_window)
        result["SMA_Long"] = TechnicalIndicators.compute_sma(df, window=self.long_window)

        # Initialize signal column
        result["Signal"] = 0

        # Generate crossover signals
        # BUY when short crosses above long
        # SELL when short crosses below long
        result.loc[
            (result["SMA_Short"] > result["SMA_Long"]) &
            (result["SMA_Short"].shift(1) <= result["SMA_Long"].shift(1)),
            "Signal"
        ] = 1  # BUY

        result.loc[
            (result["SMA_Short"] < result["SMA_Long"]) &
            (result["SMA_Short"].shift(1) >= result["SMA_Long"].shift(1)),
            "Signal"
        ] = -1  # SELL

        # Position: 1 when short > long, 0 otherwise
        result["Position"] = (result["SMA_Short"] > result["SMA_Long"]).astype(int)

        return result

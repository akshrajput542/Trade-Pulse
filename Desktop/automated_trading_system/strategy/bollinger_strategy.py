"""
Bollinger Bands Mean-Reversion Strategy.

BUY  when price touches/crosses below lower Bollinger Band (oversold).
SELL when price touches/crosses above upper Bollinger Band (overbought).

Good for range-bound, sideways markets. Beginner-friendly.
"""

import pandas as pd
from typing import Dict, Any

from .base import Strategy
from data.indicators import TechnicalIndicators
import config


class BollingerStrategy(Strategy):
    """Bollinger Bands mean-reversion strategy."""

    def __init__(self, window: int = None, std_dev: int = None):
        self.window = window or config.BOLLINGER_WINDOW
        self.std_dev = std_dev or config.BOLLINGER_STD_DEV

    @property
    def name(self) -> str:
        return f"Bollinger_{self.window}_{self.std_dev}"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"window": self.window, "std_dev": self.std_dev}

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        bb = TechnicalIndicators.compute_bollinger_bands(
            df, window=self.window, std_dev=self.std_dev
        )
        result["BB_Upper"] = bb["BB_Upper"]
        result["BB_Lower"] = bb["BB_Lower"]
        result["BB_Middle"] = bb["BB_Middle"]

        result["Signal"] = 0

        # BUY when price crosses below lower band
        result.loc[
            (result["Close"] < result["BB_Lower"]) &
            (result["Close"].shift(1) >= result["BB_Lower"].shift(1)),
            "Signal"
        ] = 1

        # SELL when price crosses above upper band
        result.loc[
            (result["Close"] > result["BB_Upper"]) &
            (result["Close"].shift(1) <= result["BB_Upper"].shift(1)),
            "Signal"
        ] = -1

        return result

"""
Smart Auto Combined Strategy — THE beginner USP.

Combines multiple strategies (SMA, RSI, MACD, Bollinger, SuperTrend)
with weighted voting. Only triggers when multiple strategies agree,
dramatically reducing false signals.

Features:
    - Weighted multi-strategy consensus
    - Confidence score (0-100%)
    - Human-readable recommendation: Strong Buy / Buy / Hold / Sell / Strong Sell
    - Reason explanation in plain English
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple

from .base import Strategy
from data.indicators import TechnicalIndicators
import config


class CombinedStrategy(Strategy):
    """Smart Auto strategy — multi-indicator consensus with confidence scoring."""

    def __init__(self, min_agreement: int = None):
        self.min_agreement = min_agreement or config.SMART_AUTO_MIN_AGREEMENT

    @property
    def name(self) -> str:
        return "Smart_Auto"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {"min_agreement": self.min_agreement}

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()

        # Compute all indicators
        sma_short = TechnicalIndicators.compute_sma(df, window=config.SMA_SHORT_WINDOW)
        sma_long = TechnicalIndicators.compute_sma(df, window=config.SMA_LONG_WINDOW)
        rsi = TechnicalIndicators.compute_rsi(df)
        macd_df = TechnicalIndicators.compute_macd(df)
        bb = TechnicalIndicators.compute_bollinger_bands(df)

        result["RSI"] = rsi
        result["Signal"] = 0
        result["Confidence"] = 0.0
        result["Recommendation"] = "Hold"
        result["Reason"] = ""

        for i in range(1, len(result)):
            votes = []  # (signal, weight, reason)

            # SMA Crossover vote (weight: 1.0)
            if pd.notna(sma_short.iloc[i]) and pd.notna(sma_long.iloc[i]):
                if (sma_short.iloc[i] > sma_long.iloc[i] and
                    sma_short.iloc[i-1] <= sma_long.iloc[i-1]):
                    votes.append((1, 1.0, "SMA golden cross"))
                elif (sma_short.iloc[i] < sma_long.iloc[i] and
                      sma_short.iloc[i-1] >= sma_long.iloc[i-1]):
                    votes.append((-1, 1.0, "SMA death cross"))

            # RSI vote (weight: 0.8)
            if pd.notna(rsi.iloc[i]):
                if rsi.iloc[i] < config.RSI_OVERSOLD:
                    votes.append((1, 0.8, f"RSI oversold ({rsi.iloc[i]:.0f})"))
                elif rsi.iloc[i] > config.RSI_OVERBOUGHT:
                    votes.append((-1, 0.8, f"RSI overbought ({rsi.iloc[i]:.0f})"))

            # MACD vote (weight: 1.0)
            macd_val = macd_df["MACD"].iloc[i]
            macd_sig = macd_df["MACD_Signal"].iloc[i]
            if pd.notna(macd_val) and pd.notna(macd_sig) and i > 0:
                prev_macd = macd_df["MACD"].iloc[i-1]
                prev_sig = macd_df["MACD_Signal"].iloc[i-1]
                if pd.notna(prev_macd) and pd.notna(prev_sig):
                    if macd_val > macd_sig and prev_macd <= prev_sig:
                        votes.append((1, 1.0, "MACD bullish crossover"))
                    elif macd_val < macd_sig and prev_macd >= prev_sig:
                        votes.append((-1, 1.0, "MACD bearish crossover"))

            # Bollinger vote (weight: 0.7)
            close = result["Close"].iloc[i]
            if pd.notna(bb["BB_Lower"].iloc[i]) and pd.notna(bb["BB_Upper"].iloc[i]):
                if close < bb["BB_Lower"].iloc[i]:
                    votes.append((1, 0.7, "Price below Bollinger lower band"))
                elif close > bb["BB_Upper"].iloc[i]:
                    votes.append((-1, 0.7, "Price above Bollinger upper band"))

            # Tally votes
            if votes:
                buy_score = sum(w for s, w, _ in votes if s == 1)
                sell_score = sum(w for s, w, _ in votes if s == -1)
                buy_count = sum(1 for s, _, _ in votes if s == 1)
                sell_count = sum(1 for s, _, _ in votes if s == -1)
                total_weight = buy_score + sell_score
                reasons = [r for _, _, r in votes]

                if buy_count >= self.min_agreement and buy_score > sell_score:
                    confidence = min(100, (buy_score / 3.5) * 100)
                    result.iloc[i, result.columns.get_loc("Signal")] = 1
                    result.iloc[i, result.columns.get_loc("Confidence")] = round(confidence, 1)
                    rec = "Strong Buy" if confidence >= 70 else "Buy"
                    result.iloc[i, result.columns.get_loc("Recommendation")] = rec
                    result.iloc[i, result.columns.get_loc("Reason")] = " + ".join(reasons)

                elif sell_count >= self.min_agreement and sell_score > buy_score:
                    confidence = min(100, (sell_score / 3.5) * 100)
                    result.iloc[i, result.columns.get_loc("Signal")] = -1
                    result.iloc[i, result.columns.get_loc("Confidence")] = round(confidence, 1)
                    rec = "Strong Sell" if confidence >= 70 else "Sell"
                    result.iloc[i, result.columns.get_loc("Recommendation")] = rec
                    result.iloc[i, result.columns.get_loc("Reason")] = " + ".join(reasons)

        return result

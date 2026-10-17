"""The strategy. A pure function: prices in, signal out.

No network calls, no broker, no clock. This is what makes the backtest and
the live run provably identical — they call this same function on the same
shape of data. If you ever find yourself adding an API call here, stop.
"""

from __future__ import annotations

from enum import Enum

import pandas as pd


class Signal(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


def moving_averages(closes: pd.Series, fast: int, slow: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": closes,
            "fast": closes.rolling(fast).mean(),
            "slow": closes.rolling(slow).mean(),
        }
    )


def signal_at(mas: pd.DataFrame, i: int) -> Signal:
    """Signal produced by the bar at integer position ``i``.

    A crossover means the sign of (fast - slow) changed between bar i-1 and
    bar i. Simply testing ``fast > slow`` is not a crossover — it is true on
    every day of an uptrend and would re-buy forever.
    """
    if i < 1:
        return Signal.HOLD

    prev, curr = mas.iloc[i - 1], mas.iloc[i]
    if pd.isna(prev["slow"]) or pd.isna(curr["slow"]):
        return Signal.HOLD  # not enough history yet

    prev_diff = prev["fast"] - prev["slow"]
    curr_diff = curr["fast"] - curr["slow"]

    if prev_diff <= 0 < curr_diff:
        return Signal.BUY
    if prev_diff >= 0 > curr_diff:
        return Signal.SELL
    return Signal.HOLD


def latest_signal(closes: pd.Series, fast: int, slow: int) -> Signal:
    mas = moving_averages(closes, fast, slow)
    return signal_at(mas, len(mas) - 1)

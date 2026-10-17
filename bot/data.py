"""Market data from Alpaca.

Deliberately NOT yfinance. Signal and execution should come from the same
venue, otherwise you compute a crossover on prices you cannot trade at.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from .config import Config


def _client(cfg: Config) -> StockHistoricalDataClient:
    return StockHistoricalDataClient(cfg.api_key, cfg.secret_key)


def fetch_daily_bars(cfg: Config, lookback_days: int | None = None) -> pd.DataFrame:
    """Return completed daily bars, oldest first, indexed by date.

    THE IMPORTANT PART: today's bar is dropped. If you run this at 09:30 ET
    the API may hand back a bar for today containing about one second of
    trading. Feeding that into a 20-day average produces a crossover driven
    by noise, and the backtest will never reproduce it because in history
    that same bar was a full session. Only completed sessions are returned.
    """
    days = lookback_days or cfg.lookback_days
    # Calendar days, padded generously for weekends and holidays.
    start = datetime.now(timezone.utc) - timedelta(days=int(days * 1.7) + 10)

    request = StockBarsRequest(
        symbol_or_symbols=cfg.symbol,
        timeframe=TimeFrame.Day,
        start=start,
        adjustment=Adjustment.ALL,  # split- and dividend-adjusted
        feed=DataFeed.IEX,  # free tier; switch to SIP if you subscribe
    )
    bars = _client(cfg).get_stock_bars(request)
    df = bars.df

    if df.empty:
        raise RuntimeError(f"No bars returned for {cfg.symbol}")

    # alpaca-py returns a MultiIndex of (symbol, timestamp) for one symbol too.
    if isinstance(df.index, pd.MultiIndex):
        df = df.xs(cfg.symbol, level="symbol")

    df = df.sort_index()
    df.index = pd.to_datetime(df.index).tz_convert("America/New_York")

    today_et = pd.Timestamp.now(tz="America/New_York").date()
    df = df[df.index.date < today_et]

    if df.empty:
        raise RuntimeError("All bars were dropped as incomplete — check the clock")

    return df.tail(days)

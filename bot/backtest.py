"""Backtest the same strategy function the live bot uses.

Fill model: a signal computed from bar N's close is acted on at bar N+1's
open. This is what actually happens live — you see yesterday's close, you
trade this morning. Filling at bar N's close instead is lookahead bias and
is the single most common way a backtest lies to you.

The browser version in docs/index.html mirrors this file line for line.
If you change the rules here, change them there too; the site checks that
both give the same answer for the configured pair.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .strategy import Signal, moving_averages, signal_at

# Parameter grid used by `backtest --sweep` and by the site export.
FAST_GRID = (5, 10, 15, 20, 25, 30)
SLOW_GRID = (30, 50, 75, 100, 150, 200)


def max_drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    return round(float(((equity - peak) / peak).min()) * 100, 2)


def sharpe_ratio(equity: pd.Series) -> float:
    returns = equity.pct_change().dropna()
    if len(returns) < 2 or returns.std() == 0:
        return 0.0
    return round(float(returns.mean() / returns.std()) * (252**0.5), 2)


def total_return_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    return round(float(equity.iloc[-1] / equity.iloc[0] - 1) * 100, 2)


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None

    @property
    def pnl_pct(self) -> float | None:
        if self.exit_price is None:
            return None
        return (self.exit_price / self.entry_price - 1) * 100


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity: pd.Series = field(default_factory=pd.Series)
    buy_hold: pd.Series = field(default_factory=pd.Series)

    def summary(self) -> dict:
        closed = [t for t in self.trades if t.exit_price is not None]
        wins = [t for t in closed if t.pnl_pct and t.pnl_pct > 0]

        return {
            "trades": len(closed),
            "win_rate_pct": round(100 * len(wins) / len(closed), 1) if closed else 0.0,
            "strategy_return_pct": total_return_pct(self.equity),
            "buy_hold_return_pct": total_return_pct(self.buy_hold),
            "max_drawdown_pct": max_drawdown_pct(self.equity),
            "buy_hold_max_drawdown_pct": max_drawdown_pct(self.buy_hold),
            "sharpe": sharpe_ratio(self.equity),
            "buy_hold_sharpe": sharpe_ratio(self.buy_hold),
            "avg_trade_pct": round(
                float(sum(t.pnl_pct for t in closed) / len(closed)), 2
            )
            if closed
            else 0.0,
        }


def run_backtest(
    bars: pd.DataFrame,
    fast: int,
    slow: int,
    slippage_bps: float = 2.0,
    starting_cash: float = 10_000.0,
) -> BacktestResult:
    mas = moving_averages(bars["close"], fast, slow)
    slip = slippage_bps / 10_000.0

    cash = starting_cash
    shares = 0.0
    trades: list[Trade] = []
    equity_points: list[float] = []

    for i in range(len(bars)):
        # Act on the PREVIOUS bar's signal at THIS bar's open.
        sig = signal_at(mas, i - 1) if i >= 1 else Signal.HOLD
        px_open = float(bars["open"].iloc[i])
        date = bars.index[i]

        if sig is Signal.BUY and shares == 0:
            fill = px_open * (1 + slip)
            shares = cash / fill
            cash = 0.0
            trades.append(Trade(entry_date=date, entry_price=fill))
        elif sig is Signal.SELL and shares > 0:
            fill = px_open * (1 - slip)
            cash = shares * fill
            shares = 0.0
            trades[-1].exit_date = date
            trades[-1].exit_price = fill

        equity_points.append(cash + shares * float(bars["close"].iloc[i]))

    equity = pd.Series(equity_points, index=bars.index)
    bh = starting_cash * bars["close"] / float(bars["close"].iloc[0])

    return BacktestResult(trades=trades, equity=equity, buy_hold=bh)

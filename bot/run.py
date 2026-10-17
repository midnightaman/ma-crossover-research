"""Entry point.

    python -m bot.run check              account + latest signal, places nothing
    python -m bot.run backtest           measure the strategy on history
    python -m bot.run backtest --sweep   grid over fast/slow pairs
    python -m bot.run trade --dry-run    full live path, order suppressed
    python -m bot.run trade --live       actually submits to the paper account
    python -m bot.run export             write docs/data.js for the results site
    python -m bot.run export --symbols AAPL SPY QQQ

Note that --live still means PAPER. config.yaml guards against real money.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from .backtest import FAST_GRID, SLOW_GRID, run_backtest
from .broker import AlpacaBroker
from .config import ROOT, load_config
from .data import fetch_daily_bars
from .export import export_site
from .strategy import Signal, latest_signal

LOG_DIR = ROOT / "logs"


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        handlers=[
            logging.FileHandler(LOG_DIR / "bot.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def journal(entry: dict) -> None:
    """One JSON object per line. Greppable, and loadable into pandas later."""
    LOG_DIR.mkdir(exist_ok=True)
    entry["ts"] = datetime.now().astimezone().isoformat()
    with (LOG_DIR / "journal.jsonl").open("a") as fh:
        fh.write(json.dumps(entry) + "\n")


def cmd_check(cfg) -> None:
    broker = AlpacaBroker(cfg)
    bars = fetch_daily_bars(cfg)
    sig = latest_signal(bars["close"], cfg.fast_period, cfg.slow_period)

    acct = broker.account_summary()
    held = broker.position_qty(cfg.symbol)

    logging.info("Account equity $%.2f, cash $%.2f", acct["equity"], acct["cash"])
    logging.info("Market open: %s", broker.market_is_open())
    logging.info(
        "Latest completed bar: %s close %.2f",
        bars.index[-1].date(),
        bars["close"].iloc[-1],
    )
    logging.info("Holding %d shares of %s", held, cfg.symbol)
    logging.info("Signal: %s", sig.value)


def cmd_backtest(cfg, sweep: bool) -> None:
    bars = fetch_daily_bars(cfg, lookback_days=1500)
    logging.info(
        "Backtesting %s on %d bars (%s to %s)",
        cfg.symbol,
        len(bars),
        bars.index[0].date(),
        bars.index[-1].date(),
    )

    if not sweep:
        res = run_backtest(bars, cfg.fast_period, cfg.slow_period, cfg.slippage_bps)
        s = res.summary()
        logging.info("--- %d/%d crossover ---", cfg.fast_period, cfg.slow_period)
        for k, v in s.items():
            logging.info("  %-22s %s", k, v)
        if s["strategy_return_pct"] < s["buy_hold_return_pct"]:
            logging.warning(
                "Strategy underperformed buy-and-hold by %.2f points. "
                "This is the normal result. Do not automate it yet.",
                s["buy_hold_return_pct"] - s["strategy_return_pct"],
            )
        return

    # Parameter sweep. Read the spread, not the best cell: if 20/50 is the
    # only pair that works and 19/50 and 21/50 are terrible, you found noise.
    rows = []
    for fast in FAST_GRID:
        for slow in SLOW_GRID:
            if fast >= slow:
                continue
            s = run_backtest(bars, fast, slow, cfg.slippage_bps).summary()
            rows.append((fast, slow, s["strategy_return_pct"], s["trades"], s["sharpe"]))

    rows.sort(key=lambda r: r[2], reverse=True)
    bh = run_backtest(bars, 20, 50, cfg.slippage_bps).summary()["buy_hold_return_pct"]
    logging.info("Buy and hold over the same window: %.2f%%", bh)
    logging.info("%-6s %-6s %-12s %-8s %s", "fast", "slow", "return%", "trades", "sharpe")
    for fast, slow, ret, n, sharpe in rows:
        logging.info("%-6d %-6d %-12.2f %-8d %.2f", fast, slow, ret, n, sharpe)


def cmd_trade(cfg, live: bool) -> None:
    broker = AlpacaBroker(cfg)
    acct = broker.account_summary()
    if acct["blocked"]:
        logging.error("Account is blocked from trading. Aborting.")
        return

    bars = fetch_daily_bars(cfg)
    sig = latest_signal(bars["close"], cfg.fast_period, cfg.slow_period)
    held = broker.position_qty(cfg.symbol)
    bar_date = str(bars.index[-1].date())

    record = {
        "symbol": cfg.symbol,
        "signal": sig.value,
        "bar_date": bar_date,
        "held": held,
        "equity": acct["equity"],
        "mode": "live" if live else "dry-run",
        "action": "none",
    }

    if sig is Signal.HOLD:
        logging.info("No crossover on %s. Nothing to do.", bar_date)
    elif sig is Signal.BUY and held > 0:
        logging.info("BUY signal but already long %d shares. Skipping.", held)
        record["action"] = "skipped_already_long"
    elif sig is Signal.SELL and held == 0:
        logging.info("SELL signal but flat. Skipping. (Long-only strategy.)")
        record["action"] = "skipped_already_flat"
    elif sig is Signal.BUY:
        if live:
            record["order_id"] = broker.buy(cfg.symbol, cfg.qty)
        record["action"] = "buy"
        logging.info("%s BUY %d %s", "SUBMITTED" if live else "WOULD", cfg.qty, cfg.symbol)
    elif sig is Signal.SELL:
        qty = min(cfg.qty, held)
        if live:
            record["order_id"] = broker.sell(cfg.symbol, qty)
        record["action"] = "sell"
        logging.info("%s SELL %d %s", "SUBMITTED" if live else "WOULD", qty, cfg.symbol)

    journal(record)


def cmd_export(cfg, symbols: list[str] | None) -> None:
    path = export_site(cfg, symbols or [cfg.symbol])
    logging.info("Wrote %s", path.relative_to(ROOT))
    logging.info("Open docs/index.html in a browser to view the results.")


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(prog="bot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check")

    bt = sub.add_parser("backtest")
    bt.add_argument("--sweep", action="store_true")

    tr = sub.add_parser("trade")
    group = tr.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--live", action="store_true")

    ex = sub.add_parser("export")
    ex.add_argument("--symbols", nargs="+", metavar="SYMBOL")

    args = parser.parse_args()
    cfg = load_config()

    if args.cmd == "check":
        cmd_check(cfg)
    elif args.cmd == "backtest":
        cmd_backtest(cfg, args.sweep)
    elif args.cmd == "trade":
        cmd_trade(cfg, live=args.live)
    elif args.cmd == "export":
        cmd_export(cfg, args.symbols)


if __name__ == "__main__":
    main()

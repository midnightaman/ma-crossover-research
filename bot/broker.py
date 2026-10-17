"""Alpaca execution adapter.

Keep this the only file that knows about Alpaca orders. Swap this class for
another broker and the strategy, backtest and runner are untouched.
"""

from __future__ import annotations

import logging

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from .config import Config

log = logging.getLogger(__name__)


class AlpacaBroker:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = TradingClient(cfg.api_key, cfg.secret_key, paper=cfg.paper)

    def account_summary(self) -> dict:
        acct = self.client.get_account()
        return {
            "cash": float(acct.cash),
            "equity": float(acct.equity),
            "buying_power": float(acct.buying_power),
            "blocked": acct.trading_blocked or acct.account_blocked,
        }

    def position_qty(self, symbol: str) -> int:
        """Shares currently held. Zero if flat.

        This is the idempotency guard. The bot never tracks its own position
        in a local file — the broker is the source of truth. Run the script
        five times in a morning and it still ends up with one position.
        """
        try:
            pos = self.client.get_open_position(symbol)
            return int(float(pos.qty))
        except Exception:
            return 0

    def market_is_open(self) -> bool:
        return bool(self.client.get_clock().is_open)

    def submit(self, symbol: str, qty: int, side: OrderSide) -> str:
        order = self.client.submit_order(
            MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                client_order_id=None,
            )
        )
        log.info("Submitted %s %s x%d -> order %s", side.value, symbol, qty, order.id)
        return str(order.id)

    def buy(self, symbol: str, qty: int) -> str:
        return self.submit(symbol, qty, OrderSide.BUY)

    def sell(self, symbol: str, qty: int) -> str:
        return self.submit(symbol, qty, OrderSide.SELL)

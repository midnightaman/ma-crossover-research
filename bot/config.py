"""Configuration loading. Everything tunable lives in config.yaml;
secrets live in .env and never touch the repo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    symbol: str
    fast_period: int
    slow_period: int
    qty: int
    lookback_days: int
    slippage_bps: float
    paper: bool
    api_key: str
    secret_key: str

    def validate(self) -> None:
        if self.fast_period >= self.slow_period:
            raise ValueError(
                f"fast_period ({self.fast_period}) must be less than "
                f"slow_period ({self.slow_period})"
            )
        if self.lookback_days < self.slow_period + 5:
            raise ValueError(
                "lookback_days must exceed slow_period by a margin so there is "
                "enough history to compute the slow average plus one prior day"
            )
        if self.qty < 1:
            raise ValueError("qty must be at least 1")
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env"
            )
        if not self.paper:
            raise ValueError(
                "paper is False. This project is built for paper trading. "
                "If you really intend to trade real money, remove this guard "
                "deliberately and re-read run.py first."
            )


def load_config(path: Path | None = None) -> Config:
    load_dotenv(ROOT / ".env")
    cfg_path = path or (ROOT / "config.yaml")
    raw = yaml.safe_load(cfg_path.read_text())

    cfg = Config(
        symbol=raw["symbol"].upper(),
        fast_period=int(raw["fast_period"]),
        slow_period=int(raw["slow_period"]),
        qty=int(raw["qty"]),
        lookback_days=int(raw["lookback_days"]),
        slippage_bps=float(raw.get("slippage_bps", 2.0)),
        paper=bool(raw.get("paper", True)),
        api_key=os.getenv("ALPACA_API_KEY", ""),
        secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
    )
    cfg.validate()
    return cfg

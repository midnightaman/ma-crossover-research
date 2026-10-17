# MA Crossover Paper Trading Bot (Alpaca, US equities)

A 20/50 moving-average crossover bot for Alpaca paper trading. Same strategy as
the video, built so the backtest and the live run are provably the same code.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# paste your PAPER keys from app.alpaca.markets -> API Keys
```

Edit `config.yaml` for symbol and parameters.

## Use it in this order

```bash
python -m bot.run check              # account + today's signal, places nothing
python -m bot.run backtest           # measure it on ~6 years of history
python -m bot.run backtest --sweep   # grid over fast/slow pairs
python -m bot.run export --symbols AAPL SPY QQQ   # build the results site
python -m bot.run trade --dry-run    # full live path, order suppressed
python -m bot.run trade --live       # submits to the PAPER account
```

## Results site

`docs/index.html` is a static page showing the backtest: an interactive chart
where you drag the two averages and watch the buy and sell points move, a
comparison against buy-and-hold, the full parameter grid, and every trade.

```bash
python -m bot.run export --symbols AAPL SPY QQQ
open docs/index.html          # macOS; or double-click the file
```

`export` writes `docs/data.js` with prices and results only, with no keys or
account data. The page recomputes the strategy in the browser and checks that it
matches the Python backtest for the configured pair; the result of that check
is printed in the footer.

To show a "Code on GitHub" link, set `REPO_URL` near the top of the script in
`docs/index.html`.

The exported prices come from Alpaca's market data. If you publish the site,
check Alpaca's market data terms on redistribution.

## Publish on GitHub

Check that `.gitignore` exists and lists `.env` before your first commit:

```bash
cat .gitignore
git init
git add .
git status        # .env and .venv must NOT appear in this list
git commit -m "Moving-average crossover backtester and results site"
```

Create an empty repository on github.com (no README, no .gitignore), then:

```bash
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git
git push -u origin main
```

Turn on the site: repository **Settings > Pages > Build and deployment >
Source: Deploy from a branch > Branch: main, folder: /docs > Save**. After a
minute it's live at `https://YOUR_USERNAME.github.io/trading-bot/`.

To update the site later, rerun `export`, then commit and push `docs/data.js`.

If `.env` ever gets committed, deleting it in a later commit is not enough,
because it stays in the history. Regenerate your Alpaca keys immediately.

Do not skip `backtest`. On most large-caps a 20/50 crossover underperforms
simply holding the stock, and you want to see that number yourself before you
schedule anything.

## Reading the backtest honestly

- **Compare against `buy_hold_return_pct`, not against zero.** A strategy that
  made 30% while the stock made 60% lost you money in the only sense that counts.
- **On `--sweep`, read the neighbourhood, not the winner.** If 20/50 looks great
  but 15/50 and 25/50 are losses, you found a quirk of this particular history,
  not an edge. A real edge degrades smoothly as you nudge parameters.
- **Nine trades is not evidence.** Crossover on daily bars fires a handful of
  times a year. A 70% win rate over 9 trades is statistically nothing.
- **Alpaca is commission-free, but slippage is real.** `slippage_bps` defaults
  to a conservative 2bps per side.

## Deployment

The video has you leave your laptop on. Don't. A missed exit because the lid was
closed is a real loss. You already run things on AWS — this is a t4g.nano and a
cron entry:

```cron
# 09:35 ET, weekdays. Run after the open, not at it: the 09:30 bar is garbage.
35 13 * * 1-5 cd /home/ubuntu/trading-bot && .venv/bin/python -m bot.run trade --live >> logs/cron.log 2>&1
```

Set the instance to UTC and adjust for DST, or set `CRON_TZ=America/New_York`
at the top of the crontab if your cron supports it. Put the keys in SSM
Parameter Store rather than a `.env` on disk once you're past testing.

## How this differs from the video, and why

| Video | Here | Reason |
|---|---|---|
| Claude MCP places the orders | Plain Python script | An LLM in the order path is non-deterministic. It can misread a quantity or retry an order it already sent. Use the MCP to *inspect* your account, never to execute. |
| yfinance for prices, Alpaca for orders | Alpaca for both | Two sources means you compute signals on prices you can't trade at. yfinance is also an unofficial scraper that breaks without notice. |
| Fetches bars at 09:30 ET | Drops today's bar, runs 09:35 | At 09:30 the API may return a partial bar for today. A 20-day average containing a two-second "day" fires crossovers on noise that the backtest can never reproduce. |
| No backtest | `backtest` + `--sweep` | The video automates a strategy nobody measured. |
| Keys in Claude's config file | `.env`, gitignored | Config files get screenshotted, synced and shared. |
| No position check | Broker is source of truth | Run the script twice in a morning and you'd buy twice. `position_qty()` makes every run idempotent. |
| Laptop stays on | EC2 + cron | Reliability. |

## Structure

```
config.yaml      symbol, periods, size
.env             credentials (gitignored)
bot/config.py    typed config + validation
bot/data.py      Alpaca bars, incomplete sessions dropped
bot/strategy.py  pure function: prices in, signal out
bot/broker.py    Alpaca adapter — the only file that knows about orders
bot/backtest.py  next-bar-open fills, slippage, buy-hold benchmark
bot/run.py       CLI
bot/export.py    writes docs/data.js for the site
docs/index.html  the results site (static, no build step)
logs/            bot.log (human) + journal.jsonl (machine)
```

`strategy.py` imports nothing but pandas. That's deliberate: it's why the
backtest and the live run cannot silently diverge. If you add a second strategy,
add it there with the same signature and everything else keeps working.

## Where to take it next

1. Run it in paper for 2–3 months and compare the journal against the backtest.
   If live results differ materially from backtested ones over the same window,
   you have a bug, not bad luck. Find it before adding anything.
2. Add a stop-loss. Crossover has no risk control — it rides a position all the
   way down until the slow average catches up.
3. Test on a basket, not one symbol. Single-stock results are mostly luck.
4. Only then consider ML, and use walk-forward validation when you do.

Not financial advice. Paper results do not transfer to live trading: real fills
slip, liquidity disappears exactly when you want it, and a strategy that worked
for six months can stop working permanently.

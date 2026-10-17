Moving-average crossover, tested

A backtester and paper trading bot for the moving-average crossover strategy on US stocks, with an interactive site that compares it against simply buying and holding.

Live results: https://midnightaman.github.io/trading-bot/

The result

From October 2020 to October 2026, buying AAPL once and holding it returned +203.9%. None of the 35 crossover settings tested beat that. The common 20/50 setting trailed it by more than 150 percentage points.

The site lets you drag the two averages and watch where the rule would have bought and sold, so you can see why: in a stock that mostly rises, the rule keeps selling dips and buying back higher.

How the strategy works

Every day, average the last 20 closing prices (the fast line) and the last 50 (the slow line). When the fast line crosses above the slow one, buy. When it crosses back below, sell and wait in cash. "30/75" means the same rule with a 30-day and a 75-day line.

It's a trend-following rule. It is meant to get you out of long declines, and it pays for that by missing part of every recovery.

Run it yourself

Requires Python 3.10+ and a free Alpaca paper trading account (email signup, no funding needed).

bash
git clone https://github.com/midnightaman/trading-bot.git
cd trading-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# add your Alpaca PAPER keys to .env

Set the symbol and parameters in config.yaml, then:

bash
python -m bot.run check                          # account and today's signal, places nothing
python -m bot.run backtest                       # about six years of history
python -m bot.run backtest --sweep               # every fast/slow pair in the grid
python -m bot.run export --symbols AAPL SPY QQQ  # build the results site
python -m bot.run trade --dry-run                # full live path, order suppressed
python -m bot.run trade --live                   # submits to the PAPER account

config.yaml refuses to run with paper: false. Real-money trading is deliberately not supported.

The results site

docs/index.html is a static page with no build step, served by GitHub Pages. export writes docs/data.js containing prices and results only, with no keys or account data. The page loads it with a plain <script> tag, so it also works when opened straight from disk.

The page reruns the strategy in JavaScript and checks that it matches the Python backtest for the configured pair. The outcome of that check is shown in the footer, so the two implementations can't drift apart unnoticed.

Reading a backtest honestly
Compare against buy-and-hold, not against zero. A strategy that made 30% while the stock made 60% cost you money.
In the sweep, look at the neighbours, not the winner. If 20/50 looks great but 15/50 and 25/50 are losses, that's a quirk of this particular history, not an edge. A real edge fades gradually as the parameters change.
A handful of trades is not evidence. On daily bars the crossover fires a few times a year, so a high win rate over nine trades means very little.
Commission-free is not cost-free. The backtest assumes 2 basis points of slippage on each side of every trade.
Design decisions
Common shortcut	Here	Why
An AI assistant places the orders	A plain Python script	Order placement must be deterministic. An LLM can misread a quantity or retry an order it already sent.
One data source for signals, another for orders	Alpaca for both	Signals should be computed on the prices you can actually trade at.
Run at the 09:30 open with today's bar	Drop the incomplete bar, run at 09:35	A bar a few seconds old makes the averages fire on noise the backtest never sees.
Fill at the signal day's close	Fill at the next day's open	Filling at the close you just used to decide is lookahead bias.
Track the position in a local file	Ask the broker every run	Running twice in a morning can't buy twice.
Raw prices	Split- and dividend-adjusted	A stock split would otherwise look like a 75% crash and trigger a sale.

strategy.py imports nothing but pandas and does no I/O. The backtest and the live runner call the same function on the same shape of data, which is what keeps them from silently diverging.

Project structure
config.yaml      symbol, periods, trade size
.env             Alpaca credentials (gitignored)
bot/strategy.py  pure function: prices in, signal out
bot/backtest.py  next-bar-open fills, slippage, buy-and-hold benchmark
bot/data.py      Alpaca daily bars, adjusted, incomplete sessions dropped
bot/broker.py    Alpaca adapter, the only file that places orders
bot/config.py    typed config and validation
bot/export.py    writes docs/data.js for the site
bot/run.py       command-line entry point
docs/index.html  the results site
Running it on a schedule

The bot is meant to run once each weekday morning after the US market opens. It should run on a server rather than a laptop, since a missed exit because the lid was closed is a real loss. A small cloud VM with a cron entry works:

cron
# 09:35 New York time, weekdays (13:35 UTC during US daylight saving time)
35 13 * * 1-5 cd ~/trading-bot && .venv/bin/python -m bot.run trade --live >> logs/cron.log 2>&1
Roadmap
 Backtester, parameter sweep and paper trading runner
 Interactive results site on GitHub Pages
 Compare stocks that had large declines, where trend following should help
 Automated tests and CI
 Out-of-sample testing: choose parameters on 2020–2023, evaluate on 2024–2026
 A mean-reversion strategy (RSI) for comparison
 Daily paper trading through GitHub Actions, with live results next to the backtest
Notes

Prices come from Alpaca's IEX market data feed. Check Alpaca's market data terms before redistributing the exported data.

This is a personal research project using a paper trading account. It is not financial advice.

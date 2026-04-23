# 📈 Automated Trading System

A fully automated, modular Python trading system for analyzing market data, generating trading signals, backtesting strategies, and paper trading.

## Features

- **Market Data Ingestion** — Download historical OHLCV data via Yahoo Finance (yfinance)
- **Technical Indicators** — SMA, EMA, RSI, MACD, Bollinger Bands, ATR, Stochastic Oscillator
- **Rule-Based Strategies** — SMA Crossover, RSI Overbought/Oversold, MACD Signal Crossover
- **Backtesting Engine** — Full simulation with Sharpe ratio, max drawdown, win rate, equity curves
- **Paper Trading** — Simulated order execution with commission & slippage modeling
- **Database Integration** — SQLite via SQLAlchemy for persistent storage of all data
- **Interactive Dashboard** — Streamlit + Plotly for real-time visualization and analysis

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Fetch Market Data
```bash
python main.py fetch
```

### 3. Generate Trading Signals
```bash
python main.py analyze
```

### 4. Run Backtest
```bash
python main.py backtest --strategy sma --symbol AAPL
python main.py backtest --strategy rsi --symbol MSFT
python main.py backtest --strategy macd --symbol GOOGL
```

### 5. Full Pipeline (Fetch → Analyze → Trade)
```bash
python main.py run
```

### 6. Launch Dashboard
```bash
python main.py dashboard
```

## Architecture

```
automated_trading_system/
├── config.py               # Central configuration
├── main.py                 # CLI entry point
├── data/                   # Data ingestion layer
│   ├── fetcher.py          # yfinance data downloader
│   └── indicators.py       # Technical indicator calculations
├── strategy/               # Signal generation layer
│   ├── base.py             # Abstract strategy base class
│   ├── sma_crossover.py    # SMA crossover strategy
│   ├── rsi_strategy.py     # RSI strategy
│   └── macd_strategy.py    # MACD strategy
├── backtest/               # Backtesting engine
│   └── engine.py           # Simulation & metrics
├── execution/              # Execution layer
│   └── simulator.py        # Paper trading simulator
├── database/               # Database layer
│   ├── models.py           # SQLAlchemy ORM models
│   └── db_manager.py       # CRUD operations
└── dashboard/              # Visualization
    └── app.py              # Streamlit dashboard
```

## Available Strategies

| Strategy | Logic | Parameters |
|----------|-------|-----------|
| **SMA Crossover** | BUY on golden cross, SELL on death cross | Short: 20, Long: 50 |
| **RSI** | BUY when RSI < 30, SELL when RSI > 70 | Period: 14 |
| **MACD** | BUY/SELL on MACD-Signal line crossover | Fast: 12, Slow: 26, Signal: 9 |

## CLI Commands

| Command | Description |
|---------|-------------|
| `fetch` | Download market data for configured symbols |
| `analyze` | Run all strategies and generate signals |
| `backtest` | Run backtest with `--strategy` and `--symbol` flags |
| `run` | Full pipeline: fetch → analyze → simulate trades |
| `dashboard` | Launch interactive Streamlit dashboard |
| `status` | Show system status and recent activity |

## Configuration

Edit `config.py` to customize:
- Default symbols and date ranges
- Initial capital and commission rates
- Strategy parameters (SMA windows, RSI thresholds, MACD periods)
- Dashboard settings

## Tech Stack

- **Python 3.9+**
- **yfinance** — Market data API
- **pandas / numpy** — Data processing
- **ta** — Technical analysis library
- **SQLAlchemy** — ORM / Database
- **Streamlit** — Dashboard framework
- **Plotly** — Interactive charts

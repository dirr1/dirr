# Polymarket Insider Activity Tracker 🚨

High-performance async bot that detects potential insider trading activity on Polymarket by monitoring suspicious patterns. Get alerts before markets move.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

PS. Code is 100% written by AI. I was supervising & prompting :)

## Features

🚀 **Performance**
- Fully async with `aiohttp` - blazing fast concurrent processing
- SQLite database with indexed queries
- Connection pooling & intelligent caching
- Automatic retry with exponential backoff
- Processes 30+ markets simultaneously

🔍 **Detection Signals**
- Fresh wallets making large bets (< 30 days old)
- Unusual bet sizing vs market average (3x+ larger)
- High concentration in single markets (60%+)
- Activity in low-liquidity niche markets
- Coordinated wallet behavior patterns

🎨 **Beautiful CLI**
- Rich terminal UI with real-time progress bars
- Color-coded alerts by severity
- Live statistics dashboard
- Structured logging (console + file)

🔔 **Slack Integration**
- Real-time alerts pushed to Slack channels
- Formatted messages with action buttons
- Direct links to Polymarket markets
- Severity-based color coding

## Quick Start

```bash
# Clone the repo
git clone https://github.com/yourusername/polymarket-insider-bot.git
cd polymarket-insider-bot

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings (Slack webhook optional)

# Run
python run.py

# Or for a single scan
python run.py --mode scan

# View statistics
python run.py --mode stats
```

## Installation

### Option 1: Quick Install Script

```bash
chmod +x install.sh
./install.sh
source venv/bin/activate
```

### Option 2: Manual Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure .env
cp .env.example .env
```

## Configuration

Edit `.env` file:

```bash
# Slack (optional but recommended)
SLACK_ENABLED=true
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Detection sensitivity (lower = more alerts)
SUSPICIOUS_SCORE_THRESHOLD=7

# Performance tuning
CONCURRENT_BATCH_SIZE=30
POLL_INTERVAL=60
```

### Slack Setup

1. Create Slack app at https://api.slack.com/apps
2. Enable "Incoming Webhooks"
3. Add webhook to workspace
4. Copy webhook URL to `.env`

Detailed guide: See included Slack setup documentation

## Usage

### Continuous Monitoring (Default)
```bash
python run.py
```
Runs forever, scanning markets every 60 seconds (configurable).

### Single Scan
```bash
python run.py --mode scan
```
Run once and exit. Perfect for cron jobs.

### View Statistics
```bash
python run.py --mode stats
```
Display historical alert statistics and recent activity.

### Debug Mode
```bash
python run.py --debug
```
Enable verbose logging for troubleshooting.

## How It Works

1. **Market Scanning**: Fetches active markets from Polymarket API concurrently
2. **Trade Analysis**: Analyzes recent trades and calculates market statistics
3. **Wallet Tracking**: Maintains SQLite database of wallet behavior over time
4. **Anomaly Detection**: Scores each trade 0-10 based on suspicious patterns
5. **Alerting**: Triggers alerts for high-score trades (console + Slack)

## Scoring System

The bot assigns suspicion points (0-10 scale):

| Pattern | Points | Description |
|---------|--------|-------------|
| **Fresh Wallet** | 0-2 | Brand new wallets (< 1 day = 2pts, < 30 days = 1pt) |
| **Unusual Sizing** | 0-3 | Bets much larger than market average |
| **Market Concentration** | 0-2 | Wallet focused heavily on single market |
| **Niche Markets** | 0-2 | Activity in low-volume markets |
| **Repeated Entries** | 0-1 | Multiple trades in few markets |

**Alert threshold**: 7+ points (configurable)

## Example Output

```
🤖 Polymarket Insider Activity Tracker

Mode: ASYNC + OPTIMIZED + SQLite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⠋ Scanning 156 markets... ████████░ 75%

╭────────────────────────────────────────────╮
│ 🚨 SUSPICIOUS ACTIVITY (Score: 8.5/10)    │
├────────────────────────────────────────────┤
│ Market:     Will Donald Trump win 2024?   │
│ Wallet:     0x1234abcd...5678ef           │
│ Trade:      BUY $3,750.00 @ $0.075        │
│                                            │
│ Wallet Stats                               │
│   Age:              0.3 days              │
│   Total Trades:     2                     │
│   Unique Markets:   1                     │
│                                            │
│ Red Flags                                  │
│   • Brand new wallet (< 1 day old)        │
│   • Unusually large bet: $3750 vs $450 avg│
│   • 100% market concentration             │
│                                            │
│ Link: polymarket.com/event/trump-2024     │
╰────────────────────────────────────────────╯
```

## Project Structure

```
polymarket-insider-bot/
├── src/                      # Source code
│   ├── main.py              # CLI entry point
│   ├── tracker.py           # Main tracking logic
│   ├── database.py          # SQLite operations
│   ├── polymarket_api.py    # API client
│   ├── wallet_tracker.py    # Wallet behavior tracking
│   ├── anomaly_detector.py  # Pattern detection
│   ├── alert_system.py      # Alert management
│   ├── slack_notifier.py    # Slack integration
│   ├── logger.py            # Logging setup
│   └── config.py            # Configuration
├── run.py                    # Entry point script
├── requirements.txt          # Dependencies
├── requirements-dev.txt      # Dev dependencies
├── .env.example             # Config template
├── pyproject.toml           # Ruff config
└── README.md
```

## Development

### Install dev dependencies
```bash
pip install -r requirements-dev.txt
```

### Linting & Formatting
```bash
# Check code
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Format code
ruff format src/
```

### Testing
```bash
pytest tests/
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `FRESH_WALLET_DAYS` | 30 | Days threshold for "fresh" wallet |
| `MIN_BET_SIZE` | 1000 | Minimum bet size (USD) to track |
| `SUSPICIOUS_SCORE_THRESHOLD` | 7 | Score to trigger alerts (0-10) |
| `CONCURRENT_BATCH_SIZE` | 30 | Markets processed concurrently |
| `MAX_CONNECTIONS` | 50 | HTTP connection pool size |
| `POLL_INTERVAL` | 60 | Seconds between scans |
| `LOG_LEVEL` | INFO | Logging verbosity |

## Performance Tips

**Maximum Speed**
```bash
CONCURRENT_BATCH_SIZE=50
MAX_CONNECTIONS=100
POLL_INTERVAL=30
```

**More Sensitive Detection**
```bash
SUSPICIOUS_SCORE_THRESHOLD=5
FRESH_WALLET_DAYS=14
MIN_BET_SIZE=500
```

**Production Monitoring**
Run in `tmux` or `screen` for 24/7 monitoring:
```bash
tmux new -s polymarket
python run.py
# Ctrl+B, D to detach
```

## Data Storage

- `polymarket_tracker.db` - SQLite database
  - `wallets` - Wallet addresses and stats
  - `trades` - All trades indexed by wallet
  - `alerts` - Historical alerts with full context
- `tracker.log` - Detailed application logs

## Troubleshooting

**Rate limits?**
- Increase delays: reduce `CONCURRENT_BATCH_SIZE`
- Check `tracker.log` for errors

**Missing alerts?**
- Lower `SUSPICIOUS_SCORE_THRESHOLD`
- Adjust detection thresholds in `.env`

**Slow performance?**
- Increase `CONCURRENT_BATCH_SIZE`
- Check network connection
- Enable `--debug` mode to identify bottlenecks

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Run `ruff check` and `ruff format`
4. Submit a pull request

## Disclaimer

This tool is for educational and research purposes. Trading cryptocurrencies and prediction markets involves risk. Always do your own research.

## License

MIT License - see [LICENSE](LICENSE) file

## Acknowledgments

- Built for the Polymarket community
- Inspired by on-chain analysis techniques
- Powered by Python's async ecosystem

---

**Star this repo if you find it useful!** ⭐

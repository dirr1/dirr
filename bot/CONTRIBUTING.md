# Contributing to Polymarket Insider Tracker

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone and setup
git clone https://github.com/yourusername/polymarket-insider-bot.git
cd polymarket-insider-bot

# Install dev dependencies
pip install -r requirements-dev.txt

# Copy env template
cp .env.example .env
```

## Code Style

We use `ruff` for linting and formatting:

```bash
# Check code
ruff check src/

# Auto-fix issues
ruff check --fix src/

# Format code
ruff format src/
```

Or use the Makefile:
```bash
make lint    # Check code
make format  # Format and fix
```

## Pull Request Process

1. Fork the repo and create your branch from `main`
2. Make your changes
3. Run `make format` to ensure code style
4. Test your changes thoroughly
5. Update documentation if needed
6. Submit a pull request

## Code Guidelines

- Keep functions focused and single-purpose
- Add type hints to function signatures
- Use descriptive variable names
- Add docstrings to public functions
- Keep lines under 100 characters
- Use async/await for I/O operations

## Project Structure

```
src/
├── main.py              # CLI entry point
├── tracker.py           # Main tracking logic
├── database.py          # SQLite operations
├── polymarket_api.py    # API client
├── wallet_tracker.py    # Wallet tracking
├── anomaly_detector.py  # Pattern detection
├── alert_system.py      # Alert management
├── slack_notifier.py    # Slack integration
├── logger.py            # Logging setup
└── config.py            # Configuration
```

## Adding New Features

### New Detection Pattern

Add to `src/anomaly_detector.py`:
```python
def score_wallet_suspiciousness(self, ...):
    # Add your pattern detection
    if your_condition:
        score += points
        reasons.append("Your reason")
```

### New Alert Channel

Create new file like `src/discord_notifier.py`:
```python
class DiscordNotifier:
    async def send_alert(self, alert: Dict):
        # Your implementation
```

Add to `src/alert_system.py`:
```python
from src.discord_notifier import DiscordNotifier

class AlertSystem:
    def __init__(self, db: Database):
        self.discord = DiscordNotifier()
```

## Testing

```bash
pytest tests/ -v
```

## Questions?

Open an issue for discussion before starting major changes.


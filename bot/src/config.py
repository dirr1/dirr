"""Configuration - loads from .env file"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# API endpoints
BASE_DATA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

# Tracking parameters
TRACKED_TAG_IDS = [
    2,  # Politics
]

# Insider detection thresholds
FRESH_WALLET_DAYS = int(os.getenv("FRESH_WALLET_DAYS", "30"))
MIN_BET_SIZE = int(os.getenv("MIN_BET_SIZE", "1000"))
LARGE_BET_MULTIPLIER = 3
MIN_WALLET_CONCENTRATION = 0.6
NICHE_MARKET_VOLUME_THRESHOLD = 50000
SUSPICIOUS_SCORE_THRESHOLD = float(os.getenv("SUSPICIOUS_SCORE_THRESHOLD", "7"))

# Polling settings
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))
LOOKBACK_HOURS = 24

# Performance settings
CONCURRENT_BATCH_SIZE = int(os.getenv("CONCURRENT_BATCH_SIZE", "30"))
MAX_CONNECTIONS = int(os.getenv("MAX_CONNECTIONS", "50"))
CONNECTION_TIMEOUT = 30
REQUEST_RETRY_ATTEMPTS = 3
CACHE_TTL = 300

# Database
DATABASE_PATH = "polymarket_tracker.db"

# Slack notifications
SLACK_ENABLED = os.getenv("SLACK_ENABLED", "false").lower() == "true"
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "tracker.log"

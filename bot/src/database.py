"""SQLite database management"""

import json
from datetime import datetime

import aiosqlite

from src.logger import logger


class Database:
    def __init__(self, db_path: str = "polymarket_tracker.db"):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database schema"""
        async with aiosqlite.connect(self.db_path) as db:
            # Wallets table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    address TEXT PRIMARY KEY,
                    first_seen REAL NOT NULL,
                    last_seen REAL,
                    total_volume REAL DEFAULT 0,
                    total_trades INTEGER DEFAULT 0,
                    unique_markets INTEGER DEFAULT 0
                )
            """)

            # Trades table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    wallet_address TEXT NOT NULL,
                    market TEXT,
                    market_title TEXT,
                    timestamp REAL NOT NULL,
                    size REAL,
                    price REAL,
                    side TEXT,
                    FOREIGN KEY (wallet_address) REFERENCES wallets(address)
                )
            """)

            # Alerts table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    wallet TEXT NOT NULL,
                    market_title TEXT,
                    market_slug TEXT,
                    condition_id TEXT,
                    trade_data TEXT,
                    suspicion_score REAL,
                    reasons TEXT,
                    wallet_stats TEXT,
                    current_price TEXT
                )
            """)

            # Create indexes
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_wallet_address ON trades(wallet_address)"
            )
            await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON alerts(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_alert_wallet ON alerts(wallet)")

            await db.commit()
            logger.info("Database initialized")

    async def register_trade(self, address: str, trade: dict):
        """Register a trade for a wallet"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if wallet exists
            cursor = await db.execute(
                "SELECT first_seen FROM wallets WHERE address = ?", (address,)
            )
            result = await cursor.fetchone()

            timestamp = trade.get("timestamp", datetime.now().timestamp())

            if not result:
                # Insert new wallet
                await db.execute(
                    """INSERT INTO wallets (address, first_seen, last_seen, total_volume, total_trades)
                       VALUES (?, ?, ?, 0, 0)""",
                    (address, timestamp, timestamp),
                )

            # Insert trade
            trade_id = trade.get("id", f"{address}_{timestamp}")
            await db.execute(
                """INSERT OR IGNORE INTO trades
                   (id, wallet_address, market, market_title, timestamp, size, price, side)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade_id,
                    address,
                    trade.get("market"),
                    trade.get("market_title"),
                    timestamp,
                    trade.get("size"),
                    trade.get("price"),
                    trade.get("side"),
                ),
            )

            # Update wallet stats
            trade_value = float(trade.get("size", 0)) * float(trade.get("price", 0))
            await db.execute(
                """UPDATE wallets
                   SET last_seen = ?,
                       total_volume = total_volume + ?,
                       total_trades = total_trades + 1
                   WHERE address = ?""",
                (timestamp, trade_value, address),
            )

            # Update unique markets count
            await db.execute(
                """UPDATE wallets
                   SET unique_markets = (
                       SELECT COUNT(DISTINCT market) FROM trades WHERE wallet_address = ?
                   )
                   WHERE address = ?""",
                (address, address),
            )

            await db.commit()

    async def get_wallet_stats(self, address: str) -> dict:
        """Get comprehensive stats for a wallet"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get wallet info
            cursor = await db.execute("SELECT * FROM wallets WHERE address = ?", (address,))
            wallet = await cursor.fetchone()

            if not wallet:
                return {}

            # Get trades
            cursor = await db.execute(
                "SELECT * FROM trades WHERE wallet_address = ? ORDER BY timestamp DESC", (address,)
            )
            await cursor.fetchall()

            # Calculate stats
            age_days = (datetime.now().timestamp() - wallet["first_seen"]) / (24 * 3600)
            avg_bet_size = (
                wallet["total_volume"] / wallet["total_trades"] if wallet["total_trades"] > 0 else 0
            )

            # Market concentration
            cursor = await db.execute(
                """SELECT market, COUNT(*) as count
                   FROM trades
                   WHERE wallet_address = ?
                   GROUP BY market
                   ORDER BY count DESC
                   LIMIT 1""",
                (address,),
            )
            top_market = await cursor.fetchone()
            max_concentration = (
                (top_market["count"] / wallet["total_trades"])
                if top_market and wallet["total_trades"] > 0
                else 0
            )

            return {
                "address": address,
                "first_seen": wallet["first_seen"],
                "last_seen": wallet["last_seen"],
                "age_days": age_days,
                "total_trades": wallet["total_trades"],
                "total_volume": wallet["total_volume"],
                "unique_markets": wallet["unique_markets"],
                "avg_bet_size": avg_bet_size,
                "max_market_concentration": max_concentration,
            }

    async def save_alert(self, alert: dict):
        """Save an alert to database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO alerts
                   (timestamp, wallet, market_title, market_slug, condition_id,
                    trade_data, suspicion_score, reasons, wallet_stats, current_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    alert["timestamp"],
                    alert["wallet"],
                    alert["market_title"],
                    alert["market_slug"],
                    alert["condition_id"],
                    json.dumps(alert["trade"]),
                    alert["suspicion_score"],
                    json.dumps(alert["reasons"]),
                    json.dumps(alert["wallet_stats"]),
                    str(alert["current_price"]),
                ),
            )
            await db.commit()

    async def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        """Get alerts from last N hours"""
        cutoff = datetime.now().timestamp() - hours * 3600
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM alerts WHERE timestamp >= ? ORDER BY timestamp DESC", (cutoff_iso,)
            )
            rows = await cursor.fetchall()

            return [
                {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "wallet": row["wallet"],
                    "market_title": row["market_title"],
                    "market_slug": row["market_slug"],
                    "condition_id": row["condition_id"],
                    "trade": json.loads(row["trade_data"]),
                    "suspicion_score": row["suspicion_score"],
                    "reasons": json.loads(row["reasons"]),
                    "wallet_stats": json.loads(row["wallet_stats"]),
                    "current_price": row["current_price"],
                }
                for row in rows
            ]

    async def get_alert_stats(self) -> dict:
        """Get statistics about alerts"""
        async with aiosqlite.connect(self.db_path) as db:
            # Total alerts
            cursor = await db.execute("SELECT COUNT(*) as count FROM alerts")
            result = await cursor.fetchone()
            total_alerts = result[0]

            if total_alerts == 0:
                return {}

            # Average score
            cursor = await db.execute("SELECT AVG(suspicion_score) as avg FROM alerts")
            result = await cursor.fetchone()
            avg_score = result[0]

            # Unique wallets
            cursor = await db.execute("SELECT COUNT(DISTINCT wallet) as count FROM alerts")
            result = await cursor.fetchone()
            unique_wallets = result[0]

            # Most flagged wallet
            cursor = await db.execute(
                """SELECT wallet, COUNT(*) as count
                   FROM alerts
                   GROUP BY wallet
                   ORDER BY count DESC
                   LIMIT 1"""
            )
            result = await cursor.fetchone()
            most_flagged = result[0] if result else None

            # Recent 24h
            recent = await self.get_recent_alerts(24)

            return {
                "total_alerts": total_alerts,
                "avg_score": avg_score,
                "unique_wallets": unique_wallets,
                "most_flagged_wallet": most_flagged,
                "recent_24h": len(recent),
            }

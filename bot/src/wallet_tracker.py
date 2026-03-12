"""Wallet tracking with SQLite backend"""

from src.database import Database


class WalletTracker:
    def __init__(self, db: Database):
        self.db = db

    async def register_trade(self, address: str, trade: dict):
        """Register a trade for a wallet"""
        await self.db.register_trade(address, trade)

    async def get_wallet_stats(self, address: str) -> dict:
        """Get comprehensive stats for a wallet"""
        return await self.db.get_wallet_stats(address)

    def get_wallet_age_days(self, wallet_stats: dict) -> float:
        """Get wallet age in days from stats"""
        return wallet_stats.get("age_days", 0)

    def is_fresh_wallet(self, wallet_stats: dict, days_threshold: int = 30) -> bool:
        """Check if wallet is fresh (new)"""
        return self.get_wallet_age_days(wallet_stats) < days_threshold

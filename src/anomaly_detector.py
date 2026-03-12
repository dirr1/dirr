"""Detect anomalous/suspicious trading patterns"""

import statistics
from collections import defaultdict

from src.config import (
    FRESH_WALLET_DAYS,
    LARGE_BET_MULTIPLIER,
    MIN_BET_SIZE,
    MIN_WALLET_CONCENTRATION,
    NICHE_MARKET_VOLUME_THRESHOLD,
)


class AnomalyDetector:
    def calculate_market_stats(self, trades: list[dict]) -> dict:
        """Calculate statistics for a market"""
        if not trades:
            return {}

        sizes = [float(t.get("size", 0)) * float(t.get("price", 0)) for t in trades]

        return {
            "total_volume": sum(sizes),
            "avg_trade_size": statistics.mean(sizes) if sizes else 0,
            "median_trade_size": statistics.median(sizes) if sizes else 0,
            "std_trade_size": statistics.stdev(sizes) if len(sizes) > 1 else 0,
            "num_trades": len(trades),
            "unique_traders": len({t.get("maker", "") for t in trades}),
        }

    def score_wallet_suspiciousness(
        self, wallet_stats: dict, trade: dict, market_stats: dict
    ) -> tuple[float, list[str]]:
        """
        Score how suspicious a wallet/trade is (0-10 scale)
        Returns (score, list of reasons)
        """
        score = 0.0
        reasons = []

        # Fresh wallet check
        age_days = wallet_stats.get("age_days", 0)
        if age_days < 1:
            score += 2
            reasons.append("Brand new wallet (< 1 day old)")
        elif age_days < FRESH_WALLET_DAYS:
            score += 1
            reasons.append(f"Fresh wallet ({age_days:.1f} days old)")

        # Unusual bet sizing
        trade_size = float(trade.get("size", 0)) * float(trade.get("price", 0))
        avg_size = market_stats.get("avg_trade_size", 0)

        if trade_size > MIN_BET_SIZE:
            if avg_size > 0 and trade_size > avg_size * LARGE_BET_MULTIPLIER:
                score += 3
                reasons.append(f"Unusually large bet: ${trade_size:.0f} (avg: ${avg_size:.0f})")
            elif trade_size > MIN_BET_SIZE * 10:
                score += 2
                reasons.append(f"Very large bet: ${trade_size:.0f}")
            elif trade_size > MIN_BET_SIZE * 5:
                score += 1
                reasons.append(f"Large bet: ${trade_size:.0f}")

        # Market concentration
        concentration = wallet_stats.get("max_market_concentration", 0)
        if concentration >= MIN_WALLET_CONCENTRATION:
            score += 2
            reasons.append(
                f"High market concentration: {concentration * 100:.0f}% of trades in one market"
            )
        elif concentration >= MIN_WALLET_CONCENTRATION * 0.7:
            score += 1
            reasons.append(f"Moderate market concentration: {concentration * 100:.0f}%")

        # Niche market activity
        market_volume = market_stats.get("total_volume", float("inf"))
        if market_volume < NICHE_MARKET_VOLUME_THRESHOLD:
            if market_volume < NICHE_MARKET_VOLUME_THRESHOLD / 5:
                score += 2
                reasons.append(f"Very low liquidity market: ${market_volume:.0f} volume")
            else:
                score += 1
                reasons.append(f"Niche market: ${market_volume:.0f} volume")

        # Repeated aggressive entries
        total_trades = wallet_stats.get("total_trades", 0)
        unique_markets = wallet_stats.get("unique_markets", 1)
        if total_trades > 5 and unique_markets < 3:
            score += 1
            reasons.append(f"Repeated entries: {total_trades} trades in {unique_markets} markets")

        return min(score, 10), reasons

    def detect_coordinated_activity(self, trades: list[dict]) -> list[dict]:
        """Detect potential coordinated wallet activity"""
        time_windows = defaultdict(list)

        for trade in trades:
            ts = trade.get("timestamp", 0)
            window = int(ts / 300) * 300
            time_windows[window].append(trade)

        suspicious_groups = []

        for window, window_trades in time_windows.items():
            if len(window_trades) < 3:
                continue

            sizes = [float(t.get("size", 0)) for t in window_trades]
            avg_size = statistics.mean(sizes) if sizes else 0

            if avg_size > 0:
                similar_size_trades = [
                    t
                    for t in window_trades
                    if abs(float(t.get("size", 0)) - avg_size) / avg_size < 0.1
                ]

                if len(similar_size_trades) >= 3:
                    suspicious_groups.append(
                        {
                            "window": window,
                            "trades": similar_size_trades,
                            "pattern": "similar_sizing",
                            "count": len(similar_size_trades),
                        }
                    )

        return suspicious_groups

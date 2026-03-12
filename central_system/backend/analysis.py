import math
import statistics
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional
from collections import defaultdict
from scipy.stats import binom

class AnalysisEngine:
    """
    Unified analysis engine for detecting potential insider trading.
    Combines:
    1. Statistical p-value analysis (from /detector)
    2. Wallet clustering (from /terminal)
    3. Suspicion scoring logic (from /bot)
    """

    def __init__(self):
        pass

    @staticmethod
    def binomial_p_value(wins: int, total: int, p: float = 0.5) -> float:
        """
        Calculate binomial p-value for win rate.
        Probability of seeing 'wins' or more in 'total' trials if true prob is 'p'.
        """
        if total == 0:
            return 1.0
        # sf is 1 - cdf, which is P(X > k). We want P(X >= k), so we use k-1.
        return binom.sf(wins - 1, total, p)

    def calculate_cluster_score(self, wallet1_trades: List[Dict], wallet2_trades: List[Dict]) -> Dict[str, Any]:
        """
        Score 0-100 likelihood that two wallets are the same entity.
        Based on timing correlation, market overlap, and size patterns.
        """
        score = 0
        signals = []

        # 1. Timing Correlation (within 30s)
        w1_times = sorted([t['timestamp'] for t in wallet1_trades])
        w2_times = sorted([t['timestamp'] for t in wallet2_trades])

        correlated_count = 0
        for t1 in w1_times:
            for t2 in w2_times:
                if abs(t1 - t2) <= 30:
                    correlated_count += 1
                    break # Count each t1 at most once

        if correlated_count >= 3:
            score += min(correlated_count * 10, 40)
            signals.append(f"timing:{correlated_count}")

        # 2. Market Overlap (Jaccard Similarity)
        m1 = set(t['market_id'] for t in wallet1_trades)
        m2 = set(t['market_id'] for t in wallet2_trades)

        if m1 and m2:
            intersection = m1 & m2
            union = m1 | m2
            overlap = len(intersection) / len(union)
            overlap_score = int(overlap * 35)
            score += overlap_score
            if overlap > 0.5:
                signals.append(f"overlap:{overlap:.1%}")

        # 3. Size Pattern (identical position sizes)
        s1 = set(round(float(t.get('size', 0)), 2) for t in wallet1_trades if float(t.get('size', 0)) > 0)
        s2 = set(round(float(t.get('size', 0)), 2) for t in wallet2_trades if float(t.get('size', 0)) > 0)
        common_sizes = s1 & s2
        if len(common_sizes) >= 2:
            size_score = min(len(common_sizes) * 5, 25)
            score += size_score
            signals.append(f"sizes:{len(common_sizes)}")

        return {
            'score': min(score, 100),
            'signals': signals,
            'risk_level': 'high' if score >= 70 else 'medium' if score >= 40 else 'low'
        }

    def score_trade_suspiciousness(self, trade: Dict, wallet_stats: Dict, market_stats: Dict) -> Tuple[float, List[str]]:
        """
        Score how suspicious a trade is (0-10 scale).
        From bot/src/anomaly_detector.py
        """
        score = 0.0
        reasons = []

        # Fresh wallet check
        age_days = wallet_stats.get('age_days', 0)
        if age_days < 1:
            score += 2
            reasons.append("Brand new wallet (< 1 day old)")
        elif age_days < 7:
            score += 1
            reasons.append(f"Fresh wallet ({age_days:.1f} days old)")

        # Unusual bet sizing
        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        trade_value = size * price
        avg_market_size = market_stats.get('avg_trade_size', 0)

        if trade_value > 1000: # MIN_BET_SIZE equivalent
            if avg_market_size > 0 and trade_value > avg_market_size * 5: # LARGE_BET_MULTIPLIER
                score += 3
                reasons.append(f"Unusually large bet: ${trade_value:.0f} (avg: ${avg_market_size:.0f})")
            elif trade_value > 50000:
                score += 2
                reasons.append(f"Very large bet: ${trade_value:.0f}")

        # Market concentration
        concentration = wallet_stats.get('max_market_concentration', 0)
        if concentration >= 0.8:
            score += 2
            reasons.append(f"High market concentration: {concentration*100:.0f}%")

        # Low liquidity / Niche market
        market_vol = market_stats.get('total_volume', float('inf'))
        if market_vol < 10000:
            score += 2
            reasons.append(f"Low liquidity market: ${market_vol:.0f} vol")

        return min(score, 10), reasons

    def analyze_wallet(self, wallet_address: str, trades: List[Dict], markets: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Comprehensive wallet analysis.
        """
        wallet_trades = [t for t in trades if t['wallet_address'] == wallet_address]
        if not wallet_trades:
            return {}

        wins = 0
        total_pnl = 0.0
        total_stake = 0.0

        for t in wallet_trades:
            m = markets.get(t['market_id'])
            if not m or not m.get('outcome'): continue

            # Simplified win/loss calculation
            is_yes = t.get('outcome', '').upper() == 'YES' or t.get('side', '').upper() == 'BUY' # Heuristic
            market_won = m['outcome'].upper() == 'YES'

            won = is_yes == market_won
            price = float(t.get('price', 0))
            size = float(t.get('size', 0))

            if won:
                wins += 1
                total_pnl += size * (1 - price)
            else:
                total_pnl -= size * price
            total_stake += size * price

        total = len(wallet_trades)
        win_rate = wins / total if total > 0 else 0
        p_value = self.binomial_p_value(wins, total, 0.5)

        return {
            'address': wallet_address,
            'total_trades': total,
            'wins': wins,
            'win_rate': win_rate,
            'p_value': p_value,
            'total_pnl': total_pnl,
            'total_stake': total_stake,
            'suspicion_level': 'critical' if p_value < 0.01 and win_rate > 0.8 else 'high' if p_value < 0.05 else 'low'
        }

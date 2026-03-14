import unittest
import asyncio
from central_system.backend.analysis import AnalysisEngine
from central_system.backend.monitor import MonitorEngine
from central_system.backend.alerts import AlertManager
from unittest.mock import MagicMock, patch, AsyncMock

class TestUnifiedSystem(unittest.TestCase):
    def setUp(self):
        self.analysis = AnalysisEngine()
        self.alerts = MagicMock(spec=AlertManager)
        self.alerts.broadcast_alert = AsyncMock()
        self.monitor = MonitorEngine(self.analysis, self.alerts)

    def test_scoring_logic(self):
        trade = {'price': 0.5, 'size': 200000} # $100k trade
        wallet_stats = {'age_days': 0.5, 'max_market_concentration': 0.9}
        market_stats = {'avg_trade_size': 1000, 'total_volume': 5000}

        score, reasons = self.analysis.score_trade_suspiciousness(trade, wallet_stats, market_stats)
        self.assertGreaterEqual(score, 7)
        self.assertIn("Brand new wallet (< 1 day old)", reasons)

    def test_taker_aggregation(self):
        # A single $60k trade split into two $30k fills in one transaction hash
        tx_hash = '0x_aggregated'
        trade1 = {
            'transactionHash': tx_hash,
            'proxyWallet': '0xAgg',
            'price': '0.50',
            'size': '60000', # Value $30k
            'conditionId': 'cond1',
            'timestamp': 1000
        }
        trade2 = {
            'transactionHash': tx_hash,
            'proxyWallet': '0xAgg',
            'price': '0.50',
            'size': '60000', # Value $30k
            'conditionId': 'cond1',
            'timestamp': 1000
        }

        # Initial price baseline
        self.monitor.market_history['cond1'] = [(900, 0.40)]

        loop = asyncio.get_event_loop()
        self.monitor.get_market_info = AsyncMock(return_value={'question': 'Test'})

        # First fill doesn't trigger (only $30k)
        loop.run_until_complete(self.monitor.process_trade(trade1))
        self.alerts.broadcast_alert.assert_not_called()

        # Second fill triggers aggregation to $60k and detects 25% shift (0.40 -> 0.50)
        loop.run_until_complete(self.monitor.process_trade(trade2))
        self.alerts.broadcast_alert.assert_called_once()

        alert_data = self.alerts.broadcast_alert.call_args[0][0]
        self.assertEqual(alert_data['value_usd'], 60000.0)

    def test_memory_pruning(self):
        # Fill cache to limit
        self.monitor.CACHE_LIMIT = 10
        for i in range(15):
            asyncio.get_event_loop().run_until_complete(self.monitor.process_trade({
                'transactionHash': f'tx_{i}',
                'price': '0.5',
                'size': '10',
                'conditionId': 'c',
                'timestamp': 1000 + i
            }))
        self.assertEqual(len(self.monitor.processed_trades), 10)

if __name__ == '__main__':
    unittest.main()

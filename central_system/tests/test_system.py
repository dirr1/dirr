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

    def test_price_shift_detection(self):
        # 1. First trade sets baseline price
        trade1 = {
            'transactionHash': 'tx1',
            'proxyWallet': '0x1',
            'price': '0.50',
            'size': '10',
            'conditionId': 'cond1',
            'timestamp': 1000
        }

        # 2. Second trade causing 20% shift (0.50 -> 0.60)
        trade2 = {
            'transactionHash': 'tx2',
            'proxyWallet': '0x1',
            'price': '0.60',
            'size': '100000', # Value $60k
            'conditionId': 'cond1',
            'timestamp': 1100 # Within 5 mins
        }

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.monitor.process_trade(trade1))

        self.monitor.get_market_info = AsyncMock(return_value={'question': 'Test Market'})
        loop.run_until_complete(self.monitor.process_trade(trade2))

        # Verify alert was triggered
        self.alerts.broadcast_alert.assert_called_once()
        alert_arg = self.alerts.broadcast_alert.call_args[0][0]
        self.assertEqual(alert_arg['price_shift'], '20.00%')

if __name__ == '__main__':
    unittest.main()

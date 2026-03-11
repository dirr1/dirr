import unittest
import time
from unittest.mock import MagicMock, patch
from polymarket_monitor import PolymarketMonitorAgent

class TestPolymarketMonitorAgent(unittest.TestCase):
    def setUp(self):
        self.agent = PolymarketMonitorAgent()
        self.agent.trigger_alert = MagicMock()
        self.agent.get_market_info = MagicMock(return_value={
            'question': 'Test Market?',
            'daily_volume': 1000 # Low volume
        })

    def test_insider_trade_detected(self):
        # Trade > $50,000 in market with >10% price shift
        initial_price = 0.50
        current_price = 0.60 # 20% shift

        # Initial trade to set baseline
        self.agent.process_trade({
            'id': 'trade_base',
            'condition_id': 'cond1',
            'price': str(initial_price),
            'size': '10',
            'timestamp': str(time.time() - 60)
        })

        # Large trade causing shift
        trade = {
            'id': 'trade_large',
            'condition_id': 'cond1',
            'price': str(current_price),
            'size': '100000', # Value = 60,000 ( > $50k)
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }
        self.agent.process_trade(trade)
        self.agent.trigger_alert.assert_called_once()

    def test_small_trade_ignored(self):
        # Trade < $50,000
        trade = {
            'id': 'trade2',
            'condition_id': 'cond1',
            'price': '0.50',
            'size': '1000', # Value = 500
            'maker_address': '0xWallet'
        }
        self.agent.process_trade(trade)
        self.agent.trigger_alert.assert_not_called()

    def test_no_price_shift_ignored(self):
        # Large trade, but NO price shift
        initial_price = 0.50

        self.agent.process_trade({
            'id': 'trade_base',
            'condition_id': 'cond1',
            'price': str(initial_price),
            'size': '10',
            'timestamp': str(time.time() - 60)
        })

        trade = {
            'id': 'trade_large',
            'condition_id': 'cond1',
            'price': str(initial_price),
            'size': '200000', # Value = 100,000 ( > $50k)
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }
        self.agent.process_trade(trade)
        self.agent.trigger_alert.assert_not_called()

if __name__ == '__main__':
    unittest.main()

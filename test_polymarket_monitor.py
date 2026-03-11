import unittest
import time
from unittest.mock import MagicMock, patch
from polymarket_monitor import PolymarketInsiderAgent

class TestPolymarketInsiderAgent(unittest.TestCase):
    def setUp(self):
        # Mocking environment variable for Gemini API Key
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test_key'}):
            self.agent = PolymarketInsiderAgent()
            self.agent.get_market_info = MagicMock(return_value={
                'question': 'Will it rain?',
                'daily_volume': 1000
            })

    @patch('google.generativeai.GenerativeModel')
    def test_insider_detection_50k_10pct(self, mock_model_class):
        # Setup mock model instance
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        self.agent.model = mock_model

        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 90, "reasoning": "Highly suspicious.", "supporting_evidence": []}'
        mock_model.generate_content.return_value = mock_response

        # Setup baseline price 4 minutes ago
        self.agent.process_trade({
            'id': 'trade_baseline',
            'condition_id': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 240)
        })

        # Large trade ($60,000) causing 20% shift
        trade = {
            'id': 'trade_large',
            'condition_id': 'cond1',
            'price': '0.60', # 20% shift from 0.50
            'size': '100000', # Value = 60,000
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'analyze_with_gemini', wraps=self.agent.analyze_with_gemini) as mock_analyze:
            self.agent.process_trade(trade)
            mock_analyze.assert_called_once()

    def test_ignored_under_thresholds(self):
        # Case 1: Large trade ($60k) but small shift (2%)
        self.agent.process_trade({
            'id': 'trade_baseline',
            'condition_id': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 10)
        })

        trade_small_shift = {
            'id': 'trade_large_low_shift',
            'condition_id': 'cond1',
            'price': '0.51', # 2% shift
            'size': '120000', # Value = 61,200
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }

        # Case 2: Large shift (50%) but small trade ($5k)
        trade_small_value = {
            'id': 'trade_small_value_high_shift',
            'condition_id': 'cond1',
            'price': '0.75', # 50% shift
            'size': '6666', # Value approx 5,000
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'trigger_alert') as mock_alert:
            self.agent.process_trade(trade_small_shift)
            self.agent.process_trade(trade_small_value)
            mock_alert.assert_not_called()

if __name__ == '__main__':
    unittest.main()

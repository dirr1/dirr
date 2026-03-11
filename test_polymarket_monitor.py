import unittest
import time
from unittest.mock import MagicMock, patch
from polymarket_monitor import PolymarketInsiderAgent

class TestPolymarketInsiderAgent(unittest.TestCase):
    def setUp(self):
        # Mocking environment variables
        self.env_patcher = patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_key',
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test'
        })
        self.env_patcher.start()

        # Patching module level variables
        import polymarket_monitor
        polymarket_monitor.GEMINI_API_KEY = 'test_key'
        polymarket_monitor.DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/test'

        self.agent = PolymarketInsiderAgent()
        self.agent.get_market_info = MagicMock(return_value={
            'question': 'Test Question?',
            'daily_volume': 1000 # Low volume
        })

    def tearDown(self):
        self.env_patcher.stop()

    @patch('google.generativeai.GenerativeModel')
    @patch('requests.post')
    def test_insider_criteria_met(self, mock_post, mock_model_class):
        # Setup mock model
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        self.agent.model = mock_model

        # Setup mock high score response (95)
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 95, "reasoning": "No public news found.", "supporting_evidence": []}'
        mock_model.generate_content.return_value = mock_response

        # Baseline trade 4 mins ago
        self.agent.process_trade({
            'transactionHash': 'tx0',
            'conditionId': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 240)
        })

        # Large trade ($60,000) causing 20% shift
        trade = {
            'transactionHash': 'tx1',
            'conditionId': 'cond1',
            'price': '0.60',
            'size': '100000',
            'proxyWallet': '0xWallet',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'analyze_with_gemini', wraps=self.agent.analyze_with_gemini) as mock_analyze:
            self.agent.process_trade(trade)
            mock_analyze.assert_called_once()
            mock_post.assert_called_once()
            payload = mock_post.call_args[1]['json']
            self.assertIn("🚨 HIGH PROBABILITY INSIDER TRADE DETECTED 🚨", payload['embeds'][0]['title'])

    @patch('requests.post')
    def test_ignore_high_volume(self, mock_post):
        self.agent.get_market_info.return_value = {'question': 'High Vol', 'daily_volume': 100000}

        self.agent.process_trade({
            'transactionHash': 'tx_base',
            'conditionId': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 10)
        })

        trade = {
            'transactionHash': 'tx_large',
            'conditionId': 'cond1',
            'price': '0.60',
            'size': '100000',
            'proxyWallet': '0xWallet',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'trigger_alert') as mock_alert:
            self.agent.process_trade(trade)
            mock_alert.assert_not_called()

if __name__ == '__main__':
    unittest.main()

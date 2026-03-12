import unittest
import time
from unittest.mock import MagicMock, patch
from polymarket_monitor import PolymarketInsiderAgent

class TestPolymarketInsiderAgent(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_key',
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test'
        })
        self.env_patcher.start()

        # Patching module level variable for requests
        with patch('google.genai.Client') as mock_client_class:
            self.mock_client = MagicMock()
            mock_client_class.return_value = self.mock_client
            self.agent = PolymarketInsiderAgent()
            self.agent.client_ai = self.mock_client

        self.agent.get_market_info = MagicMock(return_value={
            'question': 'Will it rain?',
            'daily_volume': 1000 # Low volume
        })

    def tearDown(self):
        self.env_patcher.stop()

    @patch('requests.post')
    def test_insider_criteria_met(self, mock_post):
        # Setup mock high score response for Gemini
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 95, "reasoning": "Suspicious.", "supporting_evidence": []}'
        self.mock_client.models.generate_content.return_value = mock_response

        # 1. Baseline trade 4 mins ago
        self.agent.process_trade({
            'transactionHash': 'tx0',
            'conditionId': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 240)
        })

        # 2. Large trade ($60,000) causing 20% shift
        trade = {
            'transactionHash': 'tx1',
            'conditionId': 'cond1',
            'price': '0.60',
            'size': '100000', # Value 60,000
            'proxyWallet': '0xRealWallet',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'analyze_with_gemini', wraps=self.agent.analyze_with_gemini) as mock_analyze:
            self.agent.process_trade(trade)
            mock_analyze.assert_called_once()
            # Verify alerting
            mock_post.assert_called_once()

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

        with patch.object(self.agent, 'analyze_with_gemini') as mock_analyze:
            self.agent.process_trade(trade)
            mock_analyze.assert_not_called()

if __name__ == '__main__':
    unittest.main()

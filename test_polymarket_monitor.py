import unittest
import time
from unittest.mock import MagicMock, patch
from polymarket_monitor import PolymarketInsiderAgent

class TestPolymarketOptimizedAgent(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_key',
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test'
        })
        self.env_patcher.start()

        with patch('google.genai.Client') as mock_client_class:
            self.mock_client = MagicMock()
            mock_client_class.return_value = self.mock_client
            self.agent = PolymarketInsiderAgent()
            self.agent.client_ai = self.mock_client

        self.agent.get_market_info = MagicMock(return_value={
            'question': 'Will it rain?',
            'daily_volume': 1000
        })

    def tearDown(self):
        self.env_patcher.stop()

    @patch('requests.post')
    def test_detection_and_wallet_extraction(self, mock_post):
        # Baseline trade
        self.agent.process_trade({
            'transactionHash': 'tx0',
            'conditionId': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 10)
        })

        # Large trade ($60,000) causing 20% shift
        trade = {
            'transactionHash': 'tx1',
            'conditionId': 'cond1',
            'price': '0.60',
            'size': '100000',
            'proxyWallet': '0xRealWalletAddress',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'analyze_with_gemini', wraps=self.agent.analyze_with_gemini) as mock_analyze:
            # Setup mock response for Gemini
            mock_response = MagicMock()
            mock_response.text = '{"insider_probability_score": 95, "reasoning": "Suspicious."}'
            self.mock_client.models.generate_content.return_value = mock_response

            self.agent.process_trade(trade)
            mock_analyze.assert_called_once()
            # Check that wallet address was correctly passed
            self.assertEqual(mock_analyze.call_args[0][0]['wallet_address'], '0xRealWalletAddress')

if __name__ == '__main__':
    unittest.main()

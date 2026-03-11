import unittest
import time
import json
import os
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

        # Initialize agent (with mocked client)
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
        # Setup mock response from new SDK
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 95, "reasoning": "Highly suspicious.", "supporting_evidence": []}'
        self.mock_client.models.generate_content.return_value = mock_response

        # Setup mock Discord success
        mock_post.return_value.status_code = 204

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
            'size': '100000', # Value 60,000
            'proxyWallet': '0xWallet',
            'timestamp': str(time.time())
        }

        with patch.object(self.agent, 'analyze_with_gemini', wraps=self.agent.analyze_with_gemini) as mock_analyze:
            self.agent.process_trade(trade)
            mock_analyze.assert_called_once()

            # Verify Discord notification was sent with correct label
            mock_post.assert_called_once()
            payload = mock_post.call_args[1]['json']
            self.assertIn("🚨 HIGH PROBABILITY INSIDER TRADE DETECTED 🚨", payload['embeds'][0]['title'])
            self.assertIn("95/100", payload['embeds'][0]['fields'][0]['value'])

    @patch('requests.post')
    def test_low_score_label(self, mock_post):
        # Setup mock response with medium score
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 50, "reasoning": "Retail activity.", "supporting_evidence": []}'
        self.mock_client.models.generate_content.return_value = mock_response

        # Baseline trade
        self.agent.process_trade({
            'transactionHash': 'tx_base',
            'conditionId': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 10)
        })

        # Large trade causing 20% shift
        trade = {
            'transactionHash': 'tx2',
            'conditionId': 'cond1',
            'price': '0.60',
            'size': '100000',
            'proxyWallet': '0xWallet',
            'timestamp': str(time.time())
        }

        self.agent.process_trade(trade)

        # Verify Discord notification has potential label
        payload = mock_post.call_args[1]['json']
        self.assertIn("⚠️ POTENTIAL INSIDER TRADE", payload['embeds'][0]['title'])

if __name__ == '__main__':
    unittest.main()

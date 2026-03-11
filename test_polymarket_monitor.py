import unittest
import time
import json
import os
from unittest.mock import MagicMock, patch
from polymarket_monitor import PolymarketInsiderAgent

class TestPolymarketInsiderAgent(unittest.TestCase):
    def setUp(self):
        # Setup mocks for environment variables that will be used during __init__
        self.env_patcher = patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_key',
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test'
        })
        self.env_patcher.start()

        # We also need to patch GEMINI_API_KEY and DISCORD_WEBHOOK_URL at the module level
        # because polymarket_monitor.py reads them when imported.
        # However, for the class instance, we can set them directly.

        self.agent = PolymarketInsiderAgent()
        self.agent.get_market_info = MagicMock(return_value={
            'question': 'Will it rain?',
            'daily_volume': 1000
        })

    def tearDown(self):
        self.env_patcher.stop()

    @patch('google.generativeai.GenerativeModel')
    @patch('requests.post')
    def test_high_score_triggers_discord(self, mock_post, mock_model_class):
        # Ensure the agent has the webhook URL
        import polymarket_monitor
        polymarket_monitor.DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/test'
        polymarket_monitor.GEMINI_API_KEY = 'test_key'

        # Setup mock model
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        self.agent.model = mock_model

        # Setup mock high score response (95)
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 95, "reasoning": "Very suspicious.", "supporting_evidence": []}'
        mock_model.generate_content.return_value = mock_response

        # Setup mock Discord success
        mock_post.return_value.status_code = 204

        # Baseline trade
        self.agent.process_trade({
            'id': 'trade0',
            'condition_id': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 10)
        })

        # Large trade
        trade = {
            'id': 'trade1',
            'condition_id': 'cond1',
            'price': '0.60',
            'size': '100000', # Value 60,000
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }

        self.agent.process_trade(trade)

        # Verify Discord notification was sent
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        payload = kwargs['json']
        self.assertIn("🚨 HIGH CONFIDENCE INSIDER TRADE DETECTED 🚨", payload['embeds'][0]['title'])
        self.assertIn("95/100", payload['embeds'][0]['fields'][1]['value'])

    @patch('google.generativeai.GenerativeModel')
    @patch('requests.post')
    def test_low_score_no_discord(self, mock_post, mock_model_class):
        import polymarket_monitor
        polymarket_monitor.DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/test'

        # Setup mock model
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        self.agent.model = mock_model

        # Setup mock low score response (30)
        mock_response = MagicMock()
        mock_response.text = '{"insider_probability_score": 30, "reasoning": "Likely retail.", "supporting_evidence": []}'
        mock_model.generate_content.return_value = mock_response

        # Baseline trade
        self.agent.process_trade({
            'id': 'trade0',
            'condition_id': 'cond1',
            'price': '0.50',
            'size': '10',
            'timestamp': str(time.time() - 10)
        })

        # Large trade
        trade = {
            'id': 'trade2',
            'condition_id': 'cond1',
            'price': '0.60',
            'size': '100000',
            'maker_address': '0xWallet',
            'timestamp': str(time.time())
        }

        self.agent.process_trade(trade)

        # Verify Discord notification was NOT sent
        mock_post.assert_not_called()

if __name__ == '__main__':
    unittest.main()

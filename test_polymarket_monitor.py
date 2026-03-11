import unittest
import time
import json
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from polymarket_monitor import PolymarketRealtimeAgent

class TestPolymarketHybridAgent(unittest.TestCase):
    def setUp(self):
        self.env_patcher = patch.dict('os.environ', {
            'GEMINI_API_KEY': 'test_key',
            'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test'
        })
        self.env_patcher.start()

        with patch('google.genai.Client') as mock_client_class:
            self.mock_client = MagicMock()
            mock_client_class.return_value = self.mock_client
            self.agent = PolymarketRealtimeAgent()
            self.agent.client_ai = self.mock_client

        self.agent.market_cache = {
            'cond1': {'question': 'Will it rain?', 'daily_volume': 1000}
        }
        self.agent.asset_to_condition = {'asset1': 'cond1'}

    def tearDown(self):
        self.env_patcher.stop()

    @patch('requests.get')
    @patch('requests.post')
    def test_insider_criteria_met_hybrid(self, mock_post, mock_get):
        # Setup mock response for Data API wallet lookup
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'price': 0.60, 'proxyWallet': '0xRealWallet'}
        ]

        # Baseline trade event
        self.agent.process_trade_event({
            'asset_id': 'asset1',
            'price': '0.50',
            'size': '10',
            'event_type': 'last_trade_price'
        })

        # Large trade causing 20% shift
        trade_event = {
            'asset_id': 'asset1',
            'price': '0.60',
            'size': '100000', # Value 60,000
            'event_type': 'last_trade_price'
        }

        with patch('asyncio.create_task') as mock_task:
            self.agent.process_trade_event(trade_event)
            # Verify Data API was called for enrichment
            mock_get.assert_called_with("https://data-api.polymarket.com/trades?conditionId=cond1&limit=20")
            mock_task.assert_called_once()

    @patch('requests.get')
    def test_get_active_markets(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {
                'conditionId': 'c1',
                'question': 'Q1',
                'volume24hr': '100',
                'clobTokenIds': '["t1", "t2"]'
            }
        ]
        asset_ids = self.agent.get_active_markets()
        self.assertEqual(len(asset_ids), 2)
        self.assertIn('t1', asset_ids)

if __name__ == '__main__':
    unittest.main()

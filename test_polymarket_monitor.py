import unittest
import time
import json
import os
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from polymarket_monitor import PolymarketRealtimeAgent

class TestPolymarketHybridAgent(unittest.TestCase):
    def setUp(self):
        # Mocking environment variables
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
        # Setup Data API mock for wallet enrichment
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'price': 0.60, 'proxyWallet': '0xRealWallet', 'size': '100000'}
        ]

        # 1. Baseline trade event
        self.agent.process_ws_event({
            'asset_id': 'asset1',
            'price': '0.50',
            'size': '10',
            'event_type': 'last_trade_price'
        })

        # 2. Large event causing shift
        event = {
            'asset_id': 'asset1',
            'price': '0.60', # 20% shift
            'size': '100000',
            'event_type': 'last_trade_price'
        }

        with patch('asyncio.create_task') as mock_task:
            self.agent.process_ws_event(event)
            # Verify enrichment was attempted
            self.assertTrue(mock_get.called)
            mock_task.assert_called_once()

    @patch('requests.get')
    def test_get_active_tokens(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {
                'conditionId': 'c1',
                'question': 'Q1',
                'volume24hr': '100',
                'clobTokenIds': '["t1", "t2"]'
            }
        ]
        asset_ids = self.agent.discover_active_tokens()
        self.assertEqual(len(asset_ids), 2)
        self.assertIn('t1', asset_ids)

if __name__ == '__main__':
    unittest.main()

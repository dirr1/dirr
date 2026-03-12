import unittest
import time
import json
import os
import asyncio
import httpx
from unittest.mock import MagicMock, patch, AsyncMock
from polymarket_monitor import PolymarketRealtimeAgent

class TestPolymarketAsyncAgent(unittest.TestCase):
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

    async def async_test_insider_logic(self):
        # Setup mock client and response
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        # Mock Data API response for enrichment
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'price': 0.60, 'proxyWallet': '0xRealWallet', 'size': '100000'}]
        mock_client.get.return_value = mock_response

        # 1. First event
        await self.agent.process_ws_event(mock_client, {
            'asset_id': 'asset1', 'price': '0.50', 'size': '10', 'event_type': 'last_trade_price'
        })

        # 2. Large event
        event = {
            'asset_id': 'asset1', 'price': '0.60', 'size': '100000', 'event_type': 'last_trade_price'
        }

        with patch('asyncio.create_task') as mock_task:
            await self.agent.process_ws_event(mock_client, event)
            # Verify async enrichment call
            self.assertTrue(mock_client.get.called)
            # Verify AI analysis triggered
            mock_task.assert_called_once()

    def test_insider_logic(self):
        asyncio.run(self.async_test_insider_logic())

if __name__ == '__main__':
    unittest.main()

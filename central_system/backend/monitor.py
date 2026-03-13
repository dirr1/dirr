import asyncio
import time
import random
import aiohttp
import os
from typing import List, Dict, Any, Optional
from collections import deque
from central_system.backend.analysis import AnalysisEngine
from central_system.backend.alerts import AlertManager

class MonitorEngine:
    """
    Unified monitoring engine.
    Optimized for async I/O and specific price-shift detection.
    """

    DATA_API_URL = "https://data-api.polymarket.com"
    GAMMA_API_URL = "https://gamma-api.polymarket.com"

    WHALE_THRESHOLD = 10000
    PRICE_SHIFT_THRESHOLD = 0.10 # 10%
    WINDOW_SECONDS = 300 # 5 minutes

    def __init__(self, analysis_engine: AnalysisEngine, alert_manager: AlertManager):
        self.analysis_engine = analysis_engine
        self.alert_manager = alert_manager
        self.processed_trades = set()
        self.market_cache = {}
        self.wallets = {} # address -> {trades: [], total_volume: 0}
        self.market_history = {} # conditionId -> deque of (timestamp, price)
        self.running = False
        self.session = None

    async def get_market_info(self, condition_id: str) -> Dict[str, Any]:
        if condition_id in self.market_cache:
            return self.market_cache[condition_id]

        try:
            url = f"{self.GAMMA_API_URL}/markets?condition_id={condition_id}"
            async with self.session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        market = data[0]
                        info = {
                            'question': market.get('question', 'Unknown'),
                            'daily_volume': float(market.get('volume24hr', 0) or 0),
                            'slug': market.get('slug', '')
                        }
                        self.market_cache[condition_id] = info
                        return info
        except Exception as e:
            pass
        return {'question': 'Unknown', 'daily_volume': 0, 'slug': ''}

    async def process_trade(self, trade: Dict[str, Any]):
        tx_hash = trade.get('transactionHash')
        if not tx_hash or tx_hash in self.processed_trades:
            return

        self.processed_trades.add(tx_hash)

        wallet_address = trade.get('proxyWallet', trade.get('maker', 'Unknown'))
        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        value_usd = price * size
        condition_id = trade.get('conditionId')
        timestamp = float(trade.get('timestamp', time.time()))

        # 1. Update Market History for Price Shift Detection
        if condition_id not in self.market_history:
            self.market_history[condition_id] = deque()

        history = self.market_history[condition_id]
        history.append((timestamp, price))

        # Prune old history
        while history and history[0][0] < timestamp - self.WINDOW_SECONDS:
            history.popleft()

        # 2. Check for 10% Price Shift in 5 mins
        if len(history) > 1:
            initial_price = history[0][1]
            shift = abs(price - initial_price) / initial_price if initial_price else 0

            if shift >= self.PRICE_SHIFT_THRESHOLD and value_usd >= 50000:
                market_info = await self.get_market_info(condition_id)
                alert_data = {
                    'wallet_address': wallet_address,
                    'market_question': market_info['question'],
                    'value_usd': value_usd,
                    'price_shift': f"{shift*100:.2f}%",
                    'timestamp': timestamp,
                    'id': tx_hash
                }
                # Trigger Async Alert
                asyncio.create_task(self.alert_manager.broadcast_alert(alert_data))

        # 3. Update Wallet Stats
        if wallet_address not in self.wallets:
            self.wallets[wallet_address] = {'trades': [], 'total_volume': 0.0, 'first_seen': timestamp}

        wallet_data = self.wallets[wallet_address]
        wallet_data['trades'].append({
            'timestamp': timestamp,
            'market_id': condition_id,
            'size': size,
            'price': price,
            'value_usd': value_usd
        })
        wallet_data['total_volume'] += value_usd

    async def start_polling(self, poll_interval: int = 2):
        self.running = True
        self.session = aiohttp.ClientSession()
        print("Monitor Engine Started (Non-blocking I/O)...")
        while self.running:
            try:
                nonce = random.randint(1, 1000000)
                url = f"{self.DATA_API_URL}/trades?limit=200&nonce={nonce}"
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        trades = await response.json()
                        for trade in reversed(trades):
                            await self.process_trade(trade)

                await asyncio.sleep(poll_interval)
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()

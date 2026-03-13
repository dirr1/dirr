import asyncio
import time
import random
import aiohttp
import os
from typing import List, Dict, Any, Optional
from collections import deque, OrderedDict
from central_system.backend.analysis import AnalysisEngine
from central_system.backend.alerts import AlertManager

class MonitorEngine:
    """
    Unified monitoring engine.
    Optimized for async I/O, taker aggregation, and memory efficiency.
    """

    DATA_API_URL = "https://data-api.polymarket.com"
    GAMMA_API_URL = "https://gamma-api.polymarket.com"

    WHALE_THRESHOLD = 10000
    PRICE_SHIFT_THRESHOLD = 0.10 # 10%
    WINDOW_SECONDS = 300 # 5 minutes
    CACHE_LIMIT = 50000 # Max number of unique trade hashes to track

    def __init__(self, analysis_engine: AnalysisEngine, alert_manager: AlertManager):
        self.analysis_engine = analysis_engine
        self.alert_manager = alert_manager
        self.processed_trades = OrderedDict() # tx_hash -> aggregation_data
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
                            'slug': market.get('slug', ''),
                            'outcome': market.get('outcome', '')
                        }
                        self.market_cache[condition_id] = info
                        return info
        except Exception as e:
            pass
        return {'question': 'Unknown', 'daily_volume': 0, 'slug': '', 'outcome': ''}

    async def process_trade(self, trade: Dict[str, Any]):
        tx_hash = trade.get('transactionHash')
        if not tx_hash:
            return

        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        value_usd = price * size
        condition_id = trade.get('conditionId')
        timestamp = float(trade.get('timestamp', time.time()))
        wallet_address = trade.get('proxyWallet', trade.get('maker', 'Unknown'))

        # Aggregate fills by transactionHash (Taker-aware detection)
        if tx_hash in self.processed_trades:
            # We already processed one fill of this transaction
            # Check if this specific fill belongs to the same taker
            agg = self.processed_trades[tx_hash]
            if agg['wallet'] == wallet_address:
                agg['total_value'] += value_usd
                agg['total_size'] += size
                # Re-check threshold after aggregation
                if agg['total_value'] >= 50000 and not agg['alerted']:
                    await self._check_and_alert(tx_hash, agg, condition_id, timestamp)
            return

        # New transaction detected
        self.processed_trades[tx_hash] = {
            'wallet': wallet_address,
            'total_value': value_usd,
            'total_size': size,
            'price': price,
            'alerted': False
        }

        # Prune LRU Cache
        if len(self.processed_trades) > self.CACHE_LIMIT:
            self.processed_trades.popitem(last=False)

        # 1. Update Market History for Price Shift Detection
        if condition_id not in self.market_history:
            self.market_history[condition_id] = deque()

        history = self.market_history[condition_id]
        history.append((timestamp, price))
        while history and history[0][0] < timestamp - self.WINDOW_SECONDS:
            history.popleft()

        # 2. Check Detection Thresholds
        if self.processed_trades[tx_hash]['total_value'] >= 50000:
            await self._check_and_alert(tx_hash, self.processed_trades[tx_hash], condition_id, timestamp)

        # 3. Update Wallet Stats (Pruned every cycle or limit)
        if wallet_address not in self.wallets:
            self.wallets[wallet_address] = {'trades': [], 'total_volume': 0.0, 'first_seen': timestamp}

        w_data = self.wallets[wallet_address]
        w_data['trades'].append({'timestamp': timestamp, 'market_id': condition_id, 'size': size, 'price': price, 'value_usd': value_usd})
        w_data['total_volume'] += value_usd

        # Prune wallet history to avoid OOM (keep last 200 trades per wallet)
        if len(w_data['trades']) > 200:
            w_data['trades'] = w_data['trades'][-200:]

    async def _check_and_alert(self, tx_hash, agg_data, condition_id, timestamp):
        history = self.market_history.get(condition_id, [])
        if len(history) > 1:
            initial_price = history[0][1]
            shift = abs(agg_data['price'] - initial_price) / initial_price if initial_price else 0

            if shift >= self.PRICE_SHIFT_THRESHOLD:
                agg_data['alerted'] = True
                market_info = await self.get_market_info(condition_id)
                alert_data = {
                    'wallet_address': agg_data['wallet'],
                    'market_question': market_info['question'],
                    'value_usd': agg_data['total_value'],
                    'price_shift': f"{shift*100:.2f}%",
                    'timestamp': timestamp,
                    'id': tx_hash
                }
                asyncio.create_task(self.alert_manager.broadcast_alert(alert_data))

    async def start_polling(self, poll_interval: int = 1):
        self.running = True
        self.session = aiohttp.ClientSession()
        print("Monitor Engine Started (High-Capacity Mode)...")
        while self.running:
            try:
                nonce = random.randint(1, 1000000)
                url = f"{self.DATA_API_URL}/trades?limit=500&nonce={nonce}"
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        trades = await response.json()
                        for trade in reversed(trades):
                            await self.process_trade(trade)

                # Global Wallet Pruning: Remove inactive wallets if total > 20,000
                if len(self.wallets) > 20000:
                    sorted_wallets = sorted(self.wallets.items(), key=lambda x: x[1]['trades'][-1]['timestamp'] if x[1]['trades'] else 0)
                    for i in range(5000): # Remove 5000 oldest
                        self.wallets.pop(sorted_wallets[i][0])

                await asyncio.sleep(poll_interval)
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()

import asyncio
import time
import random
import aiohttp
import os
import dateutil.parser
from typing import List, Dict, Any, Optional
from collections import deque, OrderedDict
from central_system.backend.analysis import AnalysisEngine
from central_system.backend.alerts import AlertManager

class MonitorEngine:
    """
    Unified monitoring engine.
    Fixes: ID-based deduplication, ISO timestamp parsing, and memory management.
    """

    DATA_API_URL = "https://data-api.polymarket.com"
    GAMMA_API_URL = "https://gamma-api.polymarket.com"

    WHALE_THRESHOLD = 10000
    PRICE_SHIFT_THRESHOLD = 0.10 # 10%
    WINDOW_SECONDS = 300 # 5 minutes
    CACHE_LIMIT = 50000 # Max unique trade IDs
    TX_CACHE_LIMIT = 10000 # Max unique transaction hashes

    def __init__(self, analysis_engine: AnalysisEngine, alert_manager: AlertManager):
        self.analysis_engine = analysis_engine
        self.alert_manager = alert_manager
        self.processed_ids = OrderedDict() # trade_id -> timestamp (to deduplicate fills)
        self.processed_transactions = OrderedDict() # tx_hash -> aggregation_data
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
        except Exception:
            pass
        return {'question': 'Unknown', 'daily_volume': 0, 'slug': '', 'outcome': ''}

    def _parse_timestamp(self, ts_str: Any) -> float:
        """Parse ISO-8601 strings or numeric timestamps."""
        if isinstance(ts_str, (int, float)):
            return float(ts_str)
        try:
            # Polymarket Data API uses ISO strings
            dt = dateutil.parser.isoparse(str(ts_str))
            return dt.timestamp()
        except Exception:
            return time.time()

    async def process_trade(self, trade: Dict[str, Any]):
        trade_id = trade.get('id')
        tx_hash = trade.get('transactionHash')

        if not trade_id or not tx_hash:
            return

        # 1. Deduplicate by unique Trade ID (Prevent polling overlap duplication)
        if trade_id in self.processed_ids:
            return

        timestamp = self._parse_timestamp(trade.get('timestamp'))
        self.processed_ids[trade_id] = timestamp
        if len(self.processed_ids) > self.CACHE_LIMIT:
            self.processed_ids.popitem(last=False)

        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        value_usd = price * size
        condition_id = trade.get('conditionId')
        wallet_address = trade.get('proxyWallet', trade.get('maker', 'Unknown'))

        # 2. Update Market History for Price Shift Detection
        if condition_id not in self.market_history:
            self.market_history[condition_id] = deque()

        history = self.market_history[condition_id]
        history.append((timestamp, price))
        while history and history[0][0] < timestamp - self.WINDOW_SECONDS:
            history.popleft()

        # 3. Aggregate Taker executions (by Transaction Hash)
        if tx_hash not in self.processed_transactions:
            self.processed_transactions[tx_hash] = {
                'wallet': wallet_address,
                'total_value': 0.0,
                'total_size': 0.0,
                'initial_price': price,
                'alerted': False
            }
            if len(self.processed_transactions) > self.TX_CACHE_LIMIT:
                self.processed_transactions.popitem(last=False)

        agg = self.processed_transactions[tx_hash]
        agg['total_value'] += value_usd
        agg['total_size'] += size

        # 4. Check for Insider Criteria
        if agg['total_value'] >= 50000 and not agg['alerted']:
            if len(history) > 1:
                # Compare current price against price BEFORE this transaction sequence
                baseline_price = history[0][1]
                shift = abs(price - baseline_price) / baseline_price if baseline_price else 0

                if shift >= self.PRICE_SHIFT_THRESHOLD:
                    agg['alerted'] = True
                    market_info = await self.get_market_info(condition_id)
                    alert_data = {
                        'wallet_address': agg['wallet'],
                        'market_question': market_info['question'],
                        'value_usd': agg['total_value'],
                        'price_shift': f"{shift*100:.2f}%",
                        'timestamp': timestamp,
                        'id': tx_hash
                    }
                    asyncio.create_task(self.alert_manager.broadcast_alert(alert_data))

        # 5. Update Wallet Stats (limited storage)
        if wallet_address not in self.wallets:
            self.wallets[wallet_address] = {'trades': [], 'total_volume': 0.0, 'first_seen': timestamp}

        w_data = self.wallets[wallet_address]
        w_data['trades'].append({'timestamp': timestamp, 'market_id': condition_id, 'size': size, 'price': price, 'value_usd': value_usd})
        w_data['total_volume'] += value_usd
        if len(w_data['trades']) > 200:
            w_data['trades'] = w_data['trades'][-200:]

    async def start_polling(self, poll_interval: int = 1):
        self.running = True
        self.session = aiohttp.ClientSession()
        print("Monitor Engine Started (ID-aware Ingestion)...")
        while self.running:
            try:
                nonce = random.randint(1, 1000000)
                url = f"{self.DATA_API_URL}/trades?limit=500&nonce={nonce}"
                async with self.session.get(url, timeout=10) as response:
                    if response.status == 200:
                        trades = await response.json()
                        # Process chronological (API returns newest-first)
                        for trade in reversed(trades):
                            await self.process_trade(trade)

                # Cleanup inactive wallets
                if len(self.wallets) > 20000:
                    sorted_wallets = sorted(self.wallets.items(), key=lambda x: x[1]['trades'][-1]['timestamp'] if x[1]['trades'] else 0)
                    for i in range(5000):
                        self.wallets.pop(sorted_wallets[i][0])

                await asyncio.sleep(poll_interval)
            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        self.running = False
        if self.session:
            await self.session.close()

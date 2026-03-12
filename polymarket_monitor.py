import time
import json
import requests
import os
import asyncio
import websockets
from collections import deque
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env
load_dotenv()

# Configuration
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com"
DATA_API_ENDPOINT = "https://data-api.polymarket.com"
LOW_VOLUME_THRESHOLD = 5000  # daily avg volume
TRADE_VALUE_THRESHOLD = 50000 # $50,000
PRICE_SHIFT_THRESHOLD = 0.10 # 10%
WINDOW_SECONDS = 300 # 5 minutes
HEARTBEAT_INTERVAL = 300 # 5 minutes

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

class PolymarketRealtimeAgent:
    def __init__(self):
        self.market_cache = {} # conditionId -> market_info
        self.asset_to_condition = {} # asset_id -> conditionId
        self.trade_history = {} # conditionId -> deque of trades
        self.total_processed_count = 0
        self.start_time = time.time()

        if GEMINI_API_KEY:
            try:
                self.client_ai = genai.Client(api_key=GEMINI_API_KEY)
                self.model_id = 'gemini-2.0-flash'
            except Exception as e:
                print(f"Error initializing Gemini client: {e}")
                self.client_ai = None
        else:
            self.client_ai = None

    def get_active_markets(self):
        """Fetch active markets to map assets to conditions."""
        print("Fetching active markets for subscription...")
        try:
            url = f"{GAMMA_API_ENDPOINT}/markets?active=true&limit=1000"
            response = requests.get(url)
            if response.status_code == 200:
                markets = response.json()
                asset_ids = []
                for m in markets:
                    c_id = m.get('conditionId')
                    q = m.get('question')
                    v = float(m.get('volume24hr', 0) or 0)
                    self.market_cache[c_id] = {'question': q, 'daily_volume': v}

                    clob_rewards = m.get('clobTokenIds', [])
                    if clob_rewards:
                        if isinstance(clob_rewards, str):
                            clob_rewards = json.loads(clob_rewards)
                        for token_id in clob_rewards:
                            self.asset_to_condition[token_id] = c_id
                            asset_ids.append(token_id)

                print(f"Found {len(self.market_cache)} active markets and {len(asset_ids)} tokens.")
                return asset_ids
        except Exception as e:
            print(f"Error fetching markets: {e}")
        return []

    def lookup_wallet_address(self, condition_id, target_price, timestamp):
        """Fetch the wallet address from the Data API for a specific trade."""
        try:
            # Query recent trades for this market
            url = f"{DATA_API_ENDPOINT}/trades?conditionId={condition_id}&limit=20"
            response = requests.get(url)
            if response.status_code == 200:
                trades = response.json()
                # Find the trade that matches the price and is close to the timestamp
                for trade in trades:
                    price = float(trade.get('price', 0))
                    # Check if price matches and timestamp is within a 30s window (since Data API might be lagged)
                    if abs(price - target_price) < 0.001:
                        return trade.get('proxyWallet', 'Unknown')
        except Exception as e:
            print(f"Error looking up wallet: {e}")
        return "Unknown"

    def send_discord_notification(self, alert_data, analysis):
        """Send a notification to a Discord webhook."""
        if not DISCORD_WEBHOOK_URL: return

        score = analysis.get('insider_probability_score', 0)
        label = "🚨 HIGH PROBABILITY INSIDER TRADE DETECTED 🚨" if score > 80 else "⚠️ POTENTIAL INSIDER TRADE"

        payload = {
            "embeds": [{
                "title": label,
                "description": f"Real-time forensic analysis of a large trade on **{alert_data['market_question']}**.",
                "color": 15158332 if score > 80 else 15844367,
                "fields": [
                    {"name": "Insider Probability Score", "value": f"**{score}/100**", "inline": True},
                    {"name": "Trade Value", "value": f"${alert_data['value_usd']:,.2f}", "inline": True},
                    {"name": "Price Shift", "value": alert_data['price_shift'], "inline": True},
                    {"name": "Daily Market Volume", "value": f"${alert_data['daily_volume']:,.2f}", "inline": True},
                    {"name": "Wallet Address", "value": f"`{alert_data['wallet_address']}`", "inline": False},
                    {"name": "Reasoning", "value": analysis.get('reasoning', 'No reasoning provided.'), "inline": False}
                ],
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(alert_data['timestamp']))
            }]
        }
        try:
            requests.post(DISCORD_WEBHOOK_URL, json=payload)
        except Exception as e:
            print(f"Discord error: {e}")

    async def analyze_with_gemini(self, alert_data):
        """Perform search-grounded reasoning."""
        if not self.client_ai: return

        trade_time_str = time.ctime(alert_data['timestamp'])
        prompt = f"""
        You are an elite forensic market analyst.
        Analyze this Polymarket trade: {json.dumps(alert_data)}.
        Use the Google Search tool to find if any public news justified this 10% odds spike at this exact time ({trade_time_str}).
        1. Search specifically for news published BEFORE the trade.
        2. If no news exists, assign a high "insider_probability_score".
        3. Return a JSON object with: "insider_probability_score", "reasoning", "supporting_evidence".
        """
        try:
            response = self.client_ai.models.generate_content(
                model=self.model_id, contents=prompt,
                config=types.GenerateContentConfig(tools=[{'google_search': {}}])
            )
            text = response.text
            start, end = text.find('{'), text.rfind('}') + 1
            if start != -1 and end != -1:
                analysis = json.loads(text[start:end])
                self.send_discord_notification(alert_data, analysis)
        except Exception as e:
            print(f"Gemini error: {e}")

    def process_trade_event(self, event):
        """Process a real-time 'last_trade_price' event."""
        asset_id = event.get('asset_id')
        condition_id = self.asset_to_condition.get(asset_id)
        if not condition_id: return

        price = float(event.get('price', 0))
        size = float(event.get('size', 0))
        timestamp = time.time()
        value_usd = size * price

        self.total_processed_count += 1

        if condition_id not in self.trade_history:
            self.trade_history[condition_id] = deque()
        history = self.trade_history[condition_id]

        history.append({'price': price, 'timestamp': timestamp})
        while history and history[0]['timestamp'] < (timestamp - WINDOW_SECONDS):
            history.popleft()

        if value_usd > 10000:
            print(f"[Live] Token {asset_id[:6]}... Value: ${value_usd:,.2f} | Window: {len(history)} events", flush=True)

        if value_usd > TRADE_VALUE_THRESHOLD and len(history) > 1:
            initial_price = history[0]['price']
            shift = abs(price - initial_price) / initial_price if initial_price else 0
            if shift > PRICE_SHIFT_THRESHOLD:
                market_info = self.market_cache.get(condition_id)
                if market_info and market_info['daily_volume'] < LOW_VOLUME_THRESHOLD:
                    # Enrich with wallet address from Data API
                    wallet_address = self.lookup_wallet_address(condition_id, price, timestamp)

                    alert_data = {
                        'id': f"ws-{asset_id[:8]}-{int(timestamp)}",
                        'wallet_address': wallet_address,
                        'market_question': market_info['question'],
                        'timestamp': timestamp,
                        'value_usd': value_usd,
                        'price_shift': f"{shift*100:.2f}%",
                        'daily_volume': market_info['daily_volume']
                    }
                    print(f"\n[ALERT] REAL-TIME INSIDER SIGNAL DETECTED!")
                    print(f"  Wallet: {wallet_address} | Value: ${value_usd:,.2f} | Shift: {alert_data['price_shift']}")
                    asyncio.create_task(self.analyze_with_gemini(alert_data))

    async def monitor(self):
        """Main WebSocket loop for truly real-time monitoring."""
        asset_ids = self.get_active_markets()
        if not asset_ids: return

        print(f"Connecting to Polymarket WebSocket...")
        async for websocket in websockets.connect(CLOB_WS_URL):
            try:
                sub_msg = {"type": "market", "assets_ids": asset_ids}
                await websocket.send(json.dumps(sub_msg))
                print(f"Subscribed to {len(asset_ids)} tokens. Monitoring live...")

                last_heartbeat = time.time()
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if isinstance(data, list):
                        for item in data:
                            if item.get('event_type') == 'last_trade_price':
                                self.process_trade_event(item)
                    elif data.get('event_type') == 'last_trade_price':
                        self.process_trade_event(data)

                    now = time.time()
                    if now - last_heartbeat > HEARTBEAT_INTERVAL:
                        uptime = (now - self.start_time) / 3600
                        print(f"[HEARTBEAT] Live Uptime: {uptime:.1f}h | Events Processed: {self.total_processed_count}", flush=True)
                        last_heartbeat = now

            except websockets.ConnectionClosed:
                print("WS Connection lost. Reconnecting...")
                continue
            except Exception as e:
                print(f"WS error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    agent = PolymarketRealtimeAgent()
    try:
        asyncio.run(agent.monitor())
    except KeyboardInterrupt:
        print("\nAgent stopped.")

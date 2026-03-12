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
REPORT_INTERVAL = 5 # seconds
HEARTBEAT_INTERVAL = 300 # 5 minutes

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

class PolymarketRealtimeAgent:
    def __init__(self):
        self.market_cache = {} # conditionId -> info
        self.asset_to_condition = {} # asset_id -> conditionId
        self.trade_history = {} # conditionId -> deque of trades
        self.event_count = 0
        self.start_time = time.time()
        self.last_report_time = time.time()

        # Initialize Gemini 2.0 Client (Modern SDK)
        if GEMINI_API_KEY:
            try:
                self.client_ai = genai.Client(api_key=GEMINI_API_KEY)
                self.model_id = 'gemini-2.0-flash'
            except Exception as e:
                print(f"Error initializing Gemini: {e}")
                self.client_ai = None
        else:
            self.client_ai = None

    def discover_active_tokens(self):
        """Fetch active tokens from Gamma API for subscription."""
        print("Discovering active markets...")
        try:
            # Prioritize active markets with volume
            url = f"{GAMMA_API_ENDPOINT}/markets?active=true&limit=150"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                asset_ids = []
                for m in response.json():
                    c_id = m.get('conditionId')
                    q = m.get('question')
                    v = float(m.get('volume24hr', 0) or 0)
                    self.market_cache[c_id] = {'question': q, 'daily_volume': v}

                    ids = m.get('clobTokenIds', [])
                    if isinstance(ids, str): ids = json.loads(ids)
                    for t_id in ids:
                        self.asset_to_condition[t_id] = c_id
                        asset_ids.append(t_id)
                return asset_ids
        except Exception as e:
            print(f"Discovery error: {e}")
        return []

    def get_trade_details(self, condition_id, target_price, retries=3):
        """
        Enrich WebSocket event with size and wallet from Data API.
        Includes retry logic to account for indexing latency.
        """
        for attempt in range(retries):
            try:
                if attempt > 0: time.sleep(2) # Small delay for indexing
                url = f"{DATA_API_ENDPOINT}/trades?conditionId={condition_id}&limit=20"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    for t in response.json():
                        if abs(float(t.get('price', 0)) - target_price) < 0.001:
                            return float(t.get('size', 0)), t.get('proxyWallet', 'Unknown')
            except Exception: pass
        return 0, "Unknown"

    async def analyze_with_gemini(self, alert_data):
        """Forensic analysis with search grounding."""
        if not self.client_ai: return
        prompt = f"""
        You are an elite forensic market analyst.
        Analyze this Polymarket trade: {json.dumps(alert_data)}.
        Use the Google Search tool to find if any news justified this 10% odds spike at this time.
        Return a JSON object: "insider_probability_score" (0-100), "reasoning", "supporting_evidence".
        """
        try:
            resp = self.client_ai.models.generate_content(
                model=self.model_id, contents=prompt,
                config=types.GenerateContentConfig(tools=[{'google_search': {}}])
            )
            text = resp.text
            start, end = text.find('{'), text.rfind('}') + 1
            if start != -1 and end != -1:
                analysis = json.loads(text[start:end])
                self.send_discord_alert(alert_data, analysis)
        except Exception: pass

    def send_discord_alert(self, alert_data, analysis):
        """Send Discord alert."""
        if not DISCORD_WEBHOOK_URL: return
        score = analysis.get('insider_probability_score', 0)
        label = "🚨 HIGH PROBABILITY INSIDER 🚨" if score > 80 else "⚠️ POTENTIAL INSIDER"
        payload = {
            "embeds": [{
                "title": label,
                "color": 15158332 if score > 80 else 15844367,
                "fields": [
                    {"name": "Insider Score", "value": f"**{score}/100**", "inline": True},
                    {"name": "Trade Value", "value": f"${alert_data['value_usd']:,.2f}", "inline": True},
                    {"name": "Price Shift", "value": alert_data['price_shift'], "inline": True},
                    {"name": "Wallet", "value": f"`{alert_data['wallet_address']}`", "inline": False},
                    {"name": "Reasoning", "value": analysis.get('reasoning', '...'), "inline": False}
                ],
                "footer": {"text": f"Market: {alert_data['market_question']}"},
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(alert_data['timestamp']))
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

    def process_ws_event(self, event):
        """Handle real-time price update."""
        asset_id = event.get('asset_id')
        c_id = self.asset_to_condition.get(asset_id)
        if not c_id: return

        self.event_count += 1
        price = float(event.get('price', 0))
        timestamp = time.time()

        if c_id not in self.trade_history: self.trade_history[c_id] = deque()
        history = self.trade_history[c_id]

        history.append({'price': price, 'timestamp': timestamp})
        while history and history[0]['timestamp'] < (timestamp - WINDOW_SECONDS):
            history.popleft()

        if len(history) > 1:
            initial_price = history[0]['price']
            shift = abs(price - initial_price) / initial_price if initial_price else 0

            if shift > PRICE_SHIFT_THRESHOLD:
                # Potential high impact event - Enrich with size/wallet from Data API
                size, wallet = self.get_trade_details(c_id, price)
                value_usd = size * price

                if value_usd > TRADE_VALUE_THRESHOLD:
                    m_info = self.market_cache.get(c_id)
                    if m_info and m_info['daily_volume'] < LOW_VOLUME_THRESHOLD:
                        alert_data = {
                            'id': f"ws-{asset_id[:8]}", 'wallet_address': wallet,
                            'market_question': m_info['question'], 'timestamp': timestamp,
                            'value_usd': value_usd, 'price_shift': f"{shift*100:.2f}%",
                            'daily_volume': m_info['daily_volume']
                        }
                        print(f"\n[ALERT] INSIDER SIGNAL DETECTED! Value: ${value_usd:,.2f} | Shift: {alert_data['price_shift']}")
                        asyncio.create_task(self.analyze_with_gemini(alert_data))

    async def reporter(self, count):
        """Background task for live visibility."""
        while True:
            await asyncio.sleep(REPORT_INTERVAL)
            elapsed = time.time() - self.start_time
            print(f"[{time.strftime('%H:%M:%S')}] Monitoring {count} tokens | Live Events: {self.event_count} | Uptime: {elapsed/3600:.1f}h", end='\r', flush=True)

    async def monitor(self):
        """Main WebSocket loop with automatic reconnection."""
        tokens = self.discover_active_tokens()
        if not tokens: return

        print(f"Polymarket Real-time Monitoring Agent Started.")
        asyncio.create_task(self.reporter(len(tokens)))

        async for websocket in websockets.connect(CLOB_WS_URL):
            try:
                # Subscribe in chunks to avoid payload limits
                for i in range(0, len(tokens), 200):
                    await websocket.send(json.dumps({"type": "market", "assets_ids": tokens[i:i+200]}))

                print(f"Subscribed. Streaming live data...")
                while True:
                    msg = await websocket.recv()
                    data = json.loads(msg)
                    if isinstance(data, list):
                        for item in data:
                            if item.get('event_type') == 'last_trade_price': self.process_ws_event(item)
                    elif data.get('event_type') == 'last_trade_price':
                        self.process_ws_event(data)
            except websockets.ConnectionClosed:
                print("\nWS Connection lost. Reconnecting...")
                continue
            except Exception as e:
                print(f"\nWS Error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    agent = PolymarketRealtimeAgent()
    try: asyncio.run(agent.monitor())
    except KeyboardInterrupt: print("\nAgent stopped.")

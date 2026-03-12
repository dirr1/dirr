import time
import json
import os
import asyncio
import websockets
import httpx
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
REPORT_INTERVAL = 10 # seconds
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

    async def discover_active_tokens(self, client: httpx.AsyncClient):
        """Fetch active tokens from Gamma API for subscription."""
        print("Discovering active markets...")
        try:
            # Increase limit for better coverage
            url = f"{GAMMA_API_ENDPOINT}/markets?active=true&limit=250"
            response = await client.get(url, timeout=10)
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

    async def get_trade_details(self, client: httpx.AsyncClient, condition_id, target_price, retries=3):
        """
        Enrich WebSocket event with size and wallet from Data API.
        Asynchronous and non-blocking.
        """
        for attempt in range(retries):
            try:
                if attempt > 0: await asyncio.sleep(2) # Non-blocking delay
                url = f"{DATA_API_ENDPOINT}/trades?conditionId={condition_id}&limit=20"
                response = await client.get(url, timeout=5)
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
        Use the Google Search tool to find if any public news justified this 10% odds spike at this time.
        Return a JSON object: "insider_probability_score" (0-100), "reasoning", "supporting_evidence".
        """
        try:
            # Note: models.generate_content is currently synchronous in the SDK,
            # we run it in a thread to keep the event loop moving.
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: self.client_ai.models.generate_content(
                model=self.model_id, contents=prompt,
                config=types.GenerateContentConfig(tools=[{'google_search': {}}])
            ))

            text = resp.text
            start, end = text.find('{'), text.rfind('}') + 1
            if start != -1 and end != -1:
                analysis = json.loads(text[start:end])
                await self.send_discord_alert(alert_data, analysis)
        except Exception as e:
            print(f"Gemini analysis error: {e}")

    async def send_discord_alert(self, alert_data, analysis):
        """Send notification to Discord asynchronously."""
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
        try:
            async with httpx.AsyncClient() as client:
                await client.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        except Exception as e:
            print(f"Discord error: {e}")

    async def process_ws_event(self, client: httpx.AsyncClient, event):
        """Handle individual WebSocket message."""
        try:
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
                    # Enrich with size/wallet from Data API (asynchronous)
                    size, wallet = await self.get_trade_details(client, c_id, price)
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
        except Exception as e:
            print(f"Error processing event: {e}")

    async def reporter(self, count):
        """Background task for live visibility."""
        while True:
            await asyncio.sleep(REPORT_INTERVAL)
            elapsed = time.time() - self.start_time
            print(f"[{time.strftime('%H:%M:%S')}] Monitoring {count} tokens | Live Events: {self.event_count} | Uptime: {elapsed/3600:.1f}h", end='\r', flush=True)

    async def monitor(self):
        """Main WebSocket loop."""
        async with httpx.AsyncClient() as client:
            tokens = await self.discover_active_tokens(client)
            if not tokens: return

            print(f"Polymarket Real-time Monitoring Agent Started.")
            asyncio.create_task(self.reporter(len(tokens)))

            while True:
                try:
                    async with websockets.connect(CLOB_WS_URL) as ws:
                        # Subscribe in chunks to avoid payload limits
                        for i in range(0, len(tokens), 200):
                            chunk = tokens[i:i+200]
                            await ws.send(json.dumps({"type": "market", "assets_ids": chunk}))
                            print(f"Subscribed to chunk of {len(chunk)} tokens.")

                        print(f"Streaming live data...")
                        while True:
                            msg = await ws.recv()
                            if not msg: continue

                            try:
                                data = json.loads(msg)
                            except json.JSONDecodeError: continue

                            if isinstance(data, list):
                                for item in data:
                                    if item.get('event_type') == 'last_trade_price':
                                        await self.process_ws_event(client, item)
                            elif data.get('event_type') == 'last_trade_price':
                                await self.process_ws_event(client, data)
                except (websockets.ConnectionClosed, Exception) as e:
                    print(f"\nWS connection lost/error: {e}. Reconnecting in 5s...")
                    await asyncio.sleep(5)

if __name__ == "__main__":
    agent = PolymarketRealtimeAgent()
    try:
        asyncio.run(agent.monitor())
    except KeyboardInterrupt:
        print("\nAgent stopped.")

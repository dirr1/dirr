import time
import json
import requests
import os
from collections import deque, OrderedDict
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env
load_dotenv()

# Configuration - Optimized for max throughput and visibility
DATA_API_ENDPOINT = "https://data-api.polymarket.com"
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com"
LOW_VOLUME_THRESHOLD = 5000  # daily avg volume
TRADE_VALUE_THRESHOLD = 50000 # $50,000
PRICE_SHIFT_THRESHOLD = 0.10 # 10%
WINDOW_SECONDS = 300 # 5 minutes
POLL_INTERVAL = 1 # 1 second frequency for 100% coverage
HEARTBEAT_INTERVAL = 300 # 5 minutes stats report
HASH_RETENTION_LIMIT = 50000 # LRU cache size

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if GEMINI_API_KEY:
    # Google GenAI SDK (Modern Standard)
    pass

class PolymarketInsiderAgent:
    def __init__(self):
        self.processed_trade_hashes = OrderedDict()
        self.market_cache = {}
        self.trade_history = {} # conditionId -> deque of trades
        self.total_processed_count = 0
        self.last_minute_count = 0
        self.last_minute_time = time.time()
        self.start_time = time.time()

        if GEMINI_API_KEY:
            try:
                self.client_ai = genai.Client(api_key=GEMINI_API_KEY)
                self.model_id = 'gemini-2.0-flash'
            except Exception as e:
                print(f"Error initializing Gemini: {e}")
                self.client_ai = None
        else:
            self.client_ai = None

    def get_market_info(self, condition_id):
        """Fetch market question and volume from Gamma API."""
        if condition_id in self.market_cache:
            return self.market_cache[condition_id]

        try:
            url = f"{GAMMA_API_ENDPOINT}/markets?condition_id={condition_id}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data:
                    market = data[0]
                    daily_vol = float(market.get('volume24hr', 0) or 0)
                    info = {
                        'question': market.get('question', 'Unknown Question'),
                        'daily_volume': daily_vol
                    }
                    self.market_cache[condition_id] = info
                    return info
        except Exception:
            pass
        return None

    def send_discord_notification(self, alert_data, analysis):
        """Send a notification to a Discord webhook."""
        if not DISCORD_WEBHOOK_URL:
            print("[Discord] No webhook URL. Alert logged only.")
            return

        score = analysis.get('insider_probability_score', 0)
        label = "🚨 HIGH PROBABILITY INSIDER TRADE DETECTED 🚨" if score > 80 else "⚠️ POTENTIAL INSIDER TRADE"

        payload = {
            "embeds": [{
                "title": label,
                "description": f"Forensic analysis of a large trade on **{alert_data['market_question']}**.",
                "color": 15158332 if score > 80 else 15844367,
                "fields": [
                    {"name": "Insider Probability Score", "value": f"**{score}/100**", "inline": True},
                    {"name": "Trade Value", "value": f"${alert_data['value_usd']:,.2f}", "inline": True},
                    {"name": "Price Shift", "value": alert_data['price_shift'], "inline": True},
                    {"name": "Daily Market Volume", "value": f"${alert_data['daily_volume']:,.2f}", "inline": True},
                    {"name": "Wallet Address", "value": f"`{alert_data['wallet_address']}`", "inline": False},
                    {"name": "Reasoning", "value": analysis.get('reasoning', 'No reasoning provided.'), "inline": False}
                ],
                "footer": {"text": f"Transaction: {alert_data['id']}"},
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(float(alert_data['timestamp'])))
            }]
        }

        try:
            requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        except Exception as e:
            print(f"[Discord] Alert error: {e}")

    def analyze_with_gemini(self, alert_data):
        """Use Gemini 2.0 with search grounding for forensic analysis."""
        if not self.client_ai:
            return None

        trade_time_str = time.ctime(float(alert_data['timestamp']))
        prompt = f"""
        You are an elite forensic market analyst.
        Analyze this Polymarket trade: {json.dumps(alert_data)}.
        Use the Google Search tool to find if any public news justified this 10% odds spike at this exact time ({trade_time_str}).
        1. Search specifically for news published BEFORE the trade.
        2. If no news exists, assign a high "insider_probability_score".
        3. Return a JSON object with: "insider_probability_score" (int 0-100), "reasoning" (string), "supporting_evidence" (list).

        IMPORTANT: Your entire response must be a single valid JSON object.
        """

        print(f"[AI Analysis] Sending trade {alert_data['id'][:10]} to Gemini 2.0 for Reasoning...")

        try:
            response = self.client_ai.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[{'google_search': {}}])
            )

            text = response.text
            start, end = text.find('{'), text.rfind('}') + 1
            if start != -1 and end != -1:
                analysis = json.loads(text[start:end])
                print(f"Gemini Analysis for {alert_data['id'][:10]}: Score {analysis.get('insider_probability_score', 0)}/100")
                self.send_discord_notification(alert_data, analysis)
                return analysis
        except Exception as e:
            print(f"[AI Analysis] Gemini error: {e}")
        return None

    def process_trade(self, trade):
        """Analyze a single trade for thresholds and price impact."""
        tx_hash = trade.get('transactionHash')
        condition_id = trade.get('conditionId')
        timestamp = float(trade.get('timestamp', time.time()))
        price, size = float(trade.get('price', 0)), float(trade.get('size', 0))
        value_usd = size * price

        if not tx_hash or not condition_id: return
        if tx_hash in self.processed_trade_hashes: return

        # Track hash (LRU)
        self.processed_trade_hashes[tx_hash] = timestamp
        self.total_processed_count += 1
        self.last_minute_count += 1

        if len(self.processed_trade_hashes) > HASH_RETENTION_LIMIT:
            self.processed_trade_hashes.popitem(last=False)

        if condition_id not in self.trade_history:
            self.trade_history[condition_id] = deque()
        history = self.trade_history[condition_id]

        history.append({'price': price, 'timestamp': timestamp})
        while history and history[0]['timestamp'] < (timestamp - WINDOW_SECONDS):
            history.popleft()

        # Detection Logic
        if value_usd > TRADE_VALUE_THRESHOLD and len(history) > 1:
            initial_price = history[0]['price']
            shift = abs(price - initial_price) / initial_price if initial_price else 0

            if shift > PRICE_SHIFT_THRESHOLD:
                market_info = self.get_market_info(condition_id)
                if market_info and market_info['daily_volume'] < LOW_VOLUME_THRESHOLD:
                    alert_data = {
                        'id': tx_hash,
                        'wallet_address': trade.get('proxyWallet', 'Unknown'),
                        'market_question': market_info['question'],
                        'timestamp': timestamp,
                        'value_usd': value_usd,
                        'price_shift': f"{shift*100:.2f}%",
                        'daily_volume': market_info['daily_volume']
                    }
                    print(f"\n[ALERT] FLAGGED TRADE DETECTED! Value: ${value_usd:,.2f} | Shift: {alert_data['price_shift']}")
                    self.analyze_with_gemini(alert_data)

    def monitor(self):
        """Functional monitoring loop using Polymarket Data API with high-frequency polling."""
        print(f"Polymarket Monitoring Agent Started (Enhanced Visibility).")
        print(f"  Configuration: Trades > ${TRADE_VALUE_THRESHOLD:,.0f} | Shift > {PRICE_SHIFT_THRESHOLD*100}%")
        print(f"  Theoretical Capacity: ~1.8M trades/hr (Polling: {POLL_INTERVAL}s)")

        last_heartbeat = time.time()

        while True:
            try:
                # Capture all trades in the interval with limit=500
                response = requests.get(f"{DATA_API_ENDPOINT}/trades?limit=500", timeout=10)
                if response.status_code == 200:
                    trades = response.json()
                    new_count = 0
                    # Sort/Iterate chronologically (Data API is newest-first)
                    for trade in reversed(trades):
                        if trade.get('transactionHash') not in self.processed_trade_hashes:
                            self.process_trade(trade)
                            new_count += 1

                    # Real-time feedback ticker
                    t_str = time.strftime('%H:%M:%S')
                    print(f"[{t_str}] Polled: {len(trades)} | New: {new_count} | Total Analyzed: {self.total_processed_count}", end='\r', flush=True)

                now = time.time()
                # Rate summary every minute
                if now - self.last_minute_time > 60:
                    rate = self.last_minute_count / ((now - self.last_minute_time)/60)
                    print(f"\n[{time.strftime('%H:%M:%S')}] Throughput: {rate:.1f} trades/min")
                    self.last_minute_count = 0
                    self.last_minute_time = now

                if now - last_heartbeat > HEARTBEAT_INTERVAL:
                    uptime = (now - self.start_time) / 3600
                    print(f"\n[HEARTBEAT] Uptime: {uptime:.1f}h | Unique Hashes: {len(self.processed_trade_hashes)}", flush=True)
                    last_heartbeat = now

                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                print("\nAgent stopped.")
                break
            except Exception as e:
                print(f"\nMonitoring error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    agent = PolymarketInsiderAgent()
    agent.monitor()

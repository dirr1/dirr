import time
import json
import requests
import os
from collections import deque
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables from .env
load_dotenv()

# Configuration - Optimized for high throughput
DATA_API_ENDPOINT = "https://data-api.polymarket.com"
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com"
LOW_VOLUME_THRESHOLD = 5000  # daily avg volume
TRADE_VALUE_THRESHOLD = 50000 # $50,000
PRICE_SHIFT_THRESHOLD = 0.10 # 10%
WINDOW_SECONDS = 300 # 5 minutes
POLL_INTERVAL = 2 # Reduced to 2 seconds for high throughput (~180,000 trades/hr)
HEARTBEAT_INTERVAL = 300 # 5 minutes

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# In the new google-genai SDK, we don't call genai.configure()
# Configuration is passed directly to the Client.

class PolymarketInsiderAgent:
    def __init__(self):
        self.processed_trade_hashes = {} # map tx_hash -> timestamp for pruning
        self.market_cache = {}
        self.trade_history = {} # conditionId -> deque of trades within 5 min window
        self.total_processed_count = 0
        self.start_time = time.time()

        # Initialize the new Google GenAI SDK client
        if GEMINI_API_KEY:
            try:
                self.client_ai = genai.Client(api_key=GEMINI_API_KEY)
                self.model_id = 'gemini-2.0-flash'
            except Exception as e:
                print(f"Error initializing Gemini client: {e}")
                self.client_ai = None
        else:
            self.client_ai = None

    def get_market_info(self, condition_id):
        """Fetch market question and volume from Gamma API."""
        if condition_id in self.market_cache:
            return self.market_cache[condition_id]

        try:
            url = f"{GAMMA_API_ENDPOINT}/markets?condition_id={condition_id}"
            response = requests.get(url)
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
        """Send a notification to a Discord webhook if a trade is flagged."""
        if not DISCORD_WEBHOOK_URL:
            print("[Discord] No webhook URL configured. Skipping notification.")
            return

        score = analysis.get('insider_probability_score', 0)
        label = "🚨 HIGH PROBABILITY INSIDER TRADE DETECTED 🚨" if score > 80 else "⚠️ POTENTIAL INSIDER TRADE"

        payload = {
            "embeds": [{
                "title": label,
                "description": f"Forensic analysis of a large trade on **{alert_data['market_question']}**.",
                "color": 15158332 if score > 80 else 15844367, # Red or Yellow
                "fields": [
                    {"name": "Insider Probability Score", "value": f"**{score}/100**", "inline": True},
                    {"name": "Trade Value", "value": f"${alert_data['value_usd']:.2f}", "inline": True},
                    {"name": "Price Shift", "value": alert_data['price_shift'], "inline": True},
                    {"name": "Daily Market Volume", "value": f"${alert_data['daily_volume']:.2f}", "inline": True},
                    {"name": "Wallet Address", "value": f"`{alert_data['wallet_address']}`", "inline": False},
                    {"name": "Reasoning", "value": analysis.get('reasoning', 'No reasoning provided.'), "inline": False}
                ],
                "footer": {"text": f"Transaction: {alert_data['id']}"},
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(float(alert_data['timestamp'])))
            }]
        }

        try:
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print(f"[Discord] Notification sent for trade {alert_data['id']} (Score: {score}).")
            else:
                print(f"[Discord] Error sending notification: {response.status_code}")
        except Exception as e:
            print(f"[Discord] Error sending Discord notification: {e}")

    def analyze_with_gemini(self, alert_data, retries=2):
        """Use Gemini 2.0 with search grounding for forensic analysis."""
        if not self.client_ai:
            print("[AI Analysis] Gemini API Key not configured. Skipping.")
            return None

        trade_time_str = time.ctime(float(alert_data['timestamp']))
        prompt = f"""
        You are an elite forensic market analyst.
        Analyze this Polymarket trade: {json.dumps(alert_data)}.
        Use the Google Search tool to find if any public news justified this 10% odds spike at this exact time.

        Task:
        1. Search specifically for: "Was there any public news about [{alert_data['market_question']}] before this trade at {trade_time_str}?"
        2. Identify if any major announcements, leaks, or public statements were available to justify a ${alert_data['value_usd']:.2f} bet.
        3. If no matching news exists for this massive price-moving trade, assign a high "insider_probability_score".
        4. Return a JSON object with the fields: "insider_probability_score" (int 0-100), "reasoning" (string), "supporting_evidence" (list).

        IMPORTANT: Your entire response must be a single valid JSON object.
        """

        print(f"[AI Analysis] Sending trade {alert_data['id']} to Gemini 2.0 for Search Grounding...")

        # standalone tool declaration
        tools = [{'google_search': {}}]

        for attempt in range(retries + 1):
            try:
                response = self.client_ai.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(tools=tools)
                )

                text = response.text
                start, end = text.find('{'), text.rfind('}') + 1
                if start != -1 and end != -1:
                    analysis = json.loads(text[start:end])
                    print(f"Gemini Analysis for {alert_data['id']}: Score {analysis.get('insider_probability_score', 0)}/100")
                    self.send_discord_notification(alert_data, analysis)
                    return analysis
            except Exception as e:
                print(f"[AI Analysis] Error (Attempt {attempt+1}): {e}")
                time.sleep(2)
        return None

    def process_trade(self, trade):
        """Analyze a single trade for thresholds and price impact."""
        tx_hash = trade.get('transactionHash')
        condition_id = trade.get('conditionId')
        timestamp = float(trade.get('timestamp', time.time()))
        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        value_usd = size * price

        if not tx_hash or not condition_id: return
        if tx_hash in self.processed_trade_hashes: return
        self.processed_trade_hashes[tx_hash] = timestamp
        self.total_processed_count += 1

        if condition_id not in self.trade_history:
            self.trade_history[condition_id] = deque()

        history = self.trade_history[condition_id]
        history.append(trade)

        # Prune window
        while history and float(history[0].get('timestamp', 0)) < (timestamp - WINDOW_SECONDS):
            history.popleft()

        # Detection Logic: Value > $50k AND Price Shift > 10% in 5 mins AND <$5k low vol market
        if value_usd > 10000: # Log eval for trades > $10k
            print(f"[Evaluate] Trade {tx_hash[:10]}... Value: ${value_usd:,.2f} on {condition_id[:8]}", flush=True)

        if value_usd > TRADE_VALUE_THRESHOLD:
            if len(history) > 1:
                initial_price = float(history[0].get('price', 0))
                price_shift = abs(price - initial_price) / initial_price if initial_price else 0

                if price_shift > PRICE_SHIFT_THRESHOLD:
                    market_info = self.get_market_info(condition_id)
                    if market_info and market_info['daily_volume'] < LOW_VOLUME_THRESHOLD:
                        self.trigger_alert(trade, market_info, price_shift)

    def trigger_alert(self, trade, market_info, price_shift):
        """Extract info and alert."""
        alert_data = {
            'id': trade.get('transactionHash'),
            'wallet_address': trade.get('proxyWallet', 'Unknown'),
            'market_question': market_info['question'],
            'timestamp': trade.get('timestamp'),
            'value_usd': float(trade.get('size', 0)) * float(trade.get('price', 0)),
            'price_shift': f"{price_shift*100:.2f}%",
            'daily_volume': market_info['daily_volume']
        }
        print(f"\n[ALERT] FLAGGED TRADE DETECTED!")
        print(f"  Market: {alert_data['market_question']}")
        print(f"  Value: ${alert_data['value_usd']:,.2f}")
        print(f"  Shift: {alert_data['price_shift']}")
        print("-" * 30, flush=True)
        self.analyze_with_gemini(alert_data)

    def monitor(self):
        """Functional monitoring loop using Polymarket Data API."""
        print(f"Polymarket Monitoring Agent Started.")
        print(f"  Theoretical Capacity: ~180,000 trades/hr (Polling: {POLL_INTERVAL}s)")
        print(f"  Target: Trades > ${TRADE_VALUE_THRESHOLD:,.0f} | Vol < ${LOW_VOLUME_THRESHOLD:,.0f} | Shift > {PRICE_SHIFT_THRESHOLD*100}%", flush=True)

        last_heartbeat = time.time()

        while True:
            try:
                response = requests.get(f"{DATA_API_ENDPOINT}/trades")
                if response.status_code == 200:
                    trades = response.json()
                    new_count = 0
                    # Sort to process chronologically
                    trades.sort(key=lambda x: x.get('timestamp', 0))
                    for trade in trades:
                        if trade.get('transactionHash') not in self.processed_trade_hashes:
                            self.process_trade(trade)
                            new_count += 1

                    if new_count > 0:
                        print(f"[{time.strftime('%H:%M:%S')}] Ingested {new_count} new trades.", flush=True)

                # Heartbeat logging
                now = time.time()
                if now - last_heartbeat > HEARTBEAT_INTERVAL:
                    uptime = (now - self.start_time) / 3600
                    print(f"\n[HEARTBEAT] Agent Uptime: {uptime:.1f}h | Total Trades Analyzed: {self.total_processed_count:,}", flush=True)
                    last_heartbeat = now

                # Cleanup state
                now = time.time()
                stale_hashes = [h for h, ts in self.processed_trade_hashes.items() if ts < (now - 3600)]
                for h in stale_hashes: del self.processed_trade_hashes[h]

                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                print("\nAgent stopped by user.")
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    agent = PolymarketInsiderAgent()
    agent.monitor()

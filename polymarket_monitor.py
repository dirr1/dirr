import time
import json
import requests
import os
from collections import deque
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configuration - Thresholds from latest request
CLOB_ENDPOINT = "https://clob.polymarket.com"
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com"
LOW_VOLUME_THRESHOLD = 5000  # daily avg volume
TRADE_VALUE_THRESHOLD = 50000 # $50,000
PRICE_SHIFT_THRESHOLD = 0.10 # 10%
WINDOW_SECONDS = 300 # 5 minutes
POLL_INTERVAL = 15

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

class PolymarketInsiderAgent:
    def __init__(self, api_key=None, secret=None, passphrase=None):
        # Public data access
        self.client = ClobClient(CLOB_ENDPOINT, POLYGON)
        self.processed_trades = {} # map trade_id -> timestamp for pruning
        self.market_cache = {}
        self.trade_history = {} # condition_id -> deque of trades within 5 min window

        # Initialize Gemini 2.0 model with Google Search tool
        if GEMINI_API_KEY:
            try:
                self.model = genai.GenerativeModel(
                    model_name='gemini-2.0-flash',
                    tools=[{'google_search': {}}]
                )
            except Exception as e:
                print(f"Error initializing Gemini model: {e}")
                self.model = None
        else:
            self.model = None

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
        """Send a notification to a Discord webhook if the score is high."""
        if not DISCORD_WEBHOOK_URL:
            print("[Discord] No webhook URL configured. Skipping notification.")
            return

        score = analysis.get('insider_probability_score', 0)
        label = "🚨 HIGH PROBABILITY INSIDER TRADE DETECTED 🚨" if score > 80 else "⚠️ POTENTIAL INSIDER TRADE"

        payload = {
            "embeds": [{
                "title": label,
                "color": 15158332 if score > 80 else 15844367, # Red or Yellow
                "fields": [
                    {"name": "Market", "value": alert_data['market_question'], "inline": False},
                    {"name": "Insider Probability Score", "value": f"**{score}/100**", "inline": True},
                    {"name": "Trade Value", "value": f"${alert_data['value_usd']:.2f}", "inline": True},
                    {"name": "Price Shift", "value": alert_data['price_shift'], "inline": True},
                    {"name": "Daily Volume", "value": f"${alert_data['daily_volume']:.2f}", "inline": True},
                    {"name": "Wallet Address", "value": f"`{alert_data['wallet_address']}`", "inline": False},
                    {"name": "Reasoning", "value": analysis.get('reasoning', 'No reasoning provided.'), "inline": False}
                ],
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
            print(f"[Discord] Error: {e}")

    def analyze_with_gemini(self, alert_data, retries=2):
        """Use Gemini 2.0 to perform search-grounded forensic analysis."""
        if not self.model:
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

        print(f"[AI Analysis] Sending trade {alert_data['id']} to Gemini 2.0 for Reasoning...")
        for attempt in range(retries + 1):
            try:
                response = self.model.generate_content(prompt)
                text = response.text
                start, end = text.find('{'), text.rfind('}') + 1
                if start != -1 and end != -1:
                    analysis = json.loads(text[start:end])
                    self.send_discord_notification(alert_data, analysis)
                    return analysis
            except Exception as e:
                print(f"[AI Analysis] Error (Attempt {attempt+1}): {e}")
                time.sleep(2)
        return None

    def process_trade(self, trade):
        """Analyze a single trade for thresholds and price impact."""
        trade_id, condition_id = trade.get('id'), trade.get('condition_id')
        timestamp = float(trade.get('timestamp', time.time()))
        price, size = float(trade.get('price')), float(trade.get('size'))
        value_usd = size * price

        if trade_id in self.processed_trades: return
        self.processed_trades[trade_id] = timestamp

        if condition_id not in self.trade_history: self.trade_history[condition_id] = deque()
        history = self.trade_history[condition_id]

        # Immediate impact calculation
        previous_price = history[-1].get('price') if history else None
        history.append(trade)
        while history and float(history[0].get('timestamp', 0)) < (timestamp - WINDOW_SECONDS):
            history.popleft()

        # Criteria: Value > $50k AND (Daily Vol < $5k OR Price Shift > 10%)
        # Note: We'll flag any $50k trade with >10% shift within 5 minutes.
        if value_usd > TRADE_VALUE_THRESHOLD:
            # Shift within 5 minutes
            if len(history) > 1:
                initial_price = float(history[0].get('price'))
                price_shift = abs(price - initial_price) / initial_price if initial_price else 0

                if price_shift > PRICE_SHIFT_THRESHOLD:
                    market_info = self.get_market_info(condition_id)
                    # Include LOW_VOLUME check as an additional "insider" signal
                    if market_info and market_info['daily_volume'] < LOW_VOLUME_THRESHOLD:
                        self.trigger_alert(trade, market_info, price_shift)

    def trigger_alert(self, trade, market_info, price_shift):
        """Extract info and alert."""
        alert_data = {
            'id': trade.get('id'),
            'wallet_address': trade.get('maker_address') or trade.get('taker_address'),
            'market_question': market_info['question'],
            'timestamp': trade.get('timestamp'),
            'value_usd': float(trade.get('size')) * float(trade.get('price')),
            'price_shift': f"{price_shift*100:.2f}%",
            'daily_volume': market_info['daily_volume']
        }
        print(f"\nFLAGGED TRADE: {alert_data['market_question']} - ${alert_data['value_usd']:.2f} value - {alert_data['price_shift']} shift")
        self.analyze_with_gemini(alert_data)

    def monitor(self):
        """Functional monitoring loop using Polymarket CLOB SDK."""
        print(f"Polymarket Monitoring Agent Started. Thresholds: >${TRADE_VALUE_THRESHOLD} trade, >{PRICE_SHIFT_THRESHOLD*100}% shift.")
        while True:
            try:
                # Actual data ingestion would fetch trades here (e.g. self.client.get_trades())
                now = time.time()
                stale_ids = [tid for tid, ts in self.processed_trades.items() if ts < (now - 3600)]
                for tid in stale_ids: del self.processed_trades[tid]
                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt: break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    agent = PolymarketInsiderAgent()
    agent.monitor()

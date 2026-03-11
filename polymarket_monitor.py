import time
import json
import requests
import os
from collections import deque
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
import google.generativeai as genai

# Configuration - Thresholds from latest request
CLOB_ENDPOINT = "https://clob.polymarket.com"
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com"
LOW_VOLUME_THRESHOLD = 5000  # daily avg volume
TRADE_VALUE_THRESHOLD = 50000 # $50,000
PRICE_SHIFT_THRESHOLD = 0.10 # 10%
WINDOW_SECONDS = 300 # 5 minutes
POLL_INTERVAL = 15

# Gemini Configuration
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
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

    def analyze_with_gemini(self, alert_data, retries=2):
        """
        Use Gemini 2.0 to determine if a flagged trade is "insider" activity.
        Uses Google Search tool to cross-reference with real-world news.
        """
        if not self.model:
            print("[AI Analysis] Gemini API Key not configured. Skipping analysis.")
            return None

        trade_time_str = time.ctime(float(alert_data['timestamp']))
        prompt = f"""
        Analyze the following flagged trade on Polymarket for potential insider activity.
        Market Question: {alert_data['market_question']}
        Trade Timestamp: {trade_time_str}
        Trade Value: ${alert_data['value_usd']:.2f}
        Price Shift: {alert_data['price_shift']} (in under 5 minutes)
        Wallet Address: {alert_data['wallet_address']}

        Task:
        1. Search for any public news, leaks, or official statements regarding the subject of the market question that were published BEFORE or at the time of the trade ({trade_time_str}).
        2. Determine if the information available at that time justified a ${alert_data['value_usd']:.2f} bet.
        3. Return a JSON object with the following fields:
           - "insider_probability_score": (int 0-100)
           - "reasoning": (short string explaining the score)
           - "supporting_evidence": (list of search results or findings)

        IMPORTANT: Your entire response must be a single valid JSON object.
        """

        print(f"[AI Analysis] Sending trade {alert_data['id']} to Gemini 2.0 for reasoning...")

        for attempt in range(retries + 1):
            try:
                response = self.model.generate_content(prompt)
                text = response.text
                start = text.find('{')
                end = text.rfind('}') + 1
                if start != -1 and end != -1:
                    analysis = json.loads(text[start:end])
                    print(f"Gemini Analysis for {alert_data['id']}:")
                    print(f"  Score: {analysis.get('insider_probability_score')}/100")
                    print(f"  Reasoning: {analysis.get('reasoning')}")
                    return analysis
            except Exception as e:
                print(f"[AI Analysis] Error (Attempt {attempt+1}): {e}")
                time.sleep(2)

        return None

    def process_trade(self, trade):
        """Analyze a single trade for 'insider' criteria."""
        trade_id = trade.get('id')
        condition_id = trade.get('condition_id')
        timestamp = float(trade.get('timestamp', time.time()))
        price = float(trade.get('price'))
        size = float(trade.get('size'))
        value_usd = size * price

        if trade_id in self.processed_trades:
            return
        self.processed_trades[trade_id] = timestamp

        # Maintain 5-minute sliding window per market
        if condition_id not in self.trade_history:
            self.trade_history[condition_id] = deque()

        history = self.trade_history[condition_id]
        history.append(trade)

        # Prune history
        while history and float(history[0].get('timestamp', 0)) < (timestamp - WINDOW_SECONDS):
            history.popleft()

        # Detection Logic:
        # 1. Single trade size > $50,000
        if value_usd > TRADE_VALUE_THRESHOLD:
            # 2. Price shift over 10% in under 5 minutes
            if len(history) > 1:
                initial_price = float(history[0].get('price'))
                price_shift = abs(price - initial_price) / initial_price if initial_price else 0

                if price_shift > PRICE_SHIFT_THRESHOLD:
                    market_info = self.get_market_info(condition_id)
                    if market_info:
                        self.trigger_alert(trade, market_info, price_shift)

    def trigger_alert(self, trade, market_info, price_shift):
        """Extract info and alert."""
        alert_data = {
            'id': trade.get('id'),
            'wallet_address': trade.get('maker_address') or trade.get('taker_address'),
            'market_question': market_info['question'],
            'timestamp': trade.get('timestamp'),
            'value_usd': float(trade.get('size')) * float(trade.get('price')),
            'price_shift': f"{price_shift*100:.2f}%"
        }

        print("\n" + "!" * 60)
        print("ALERT: SIGNIFICANT TRADE & PRICE SHIFT DETECTED")
        print(f"Market: {alert_data['market_question']}")
        print(f"Wallet: {alert_data['wallet_address']}")
        print(f"Trade Value: ${alert_data['value_usd']:.2f}")
        print(f"Price Shift: {alert_data['price_shift']} in under 5 minutes")
        print(f"Time: {time.ctime(float(alert_data['timestamp']))}")
        print("!" * 60 + "\n")

        self.analyze_with_gemini(alert_data)

    def monitor(self):
        """Main monitoring loop using Polymarket CLOB SDK polling."""
        print(f"Polymarket Monitoring Agent Active.")
        print(f"Thresholds: >${TRADE_VALUE_THRESHOLD} trade, >{PRICE_SHIFT_THRESHOLD*100}% shift, {WINDOW_SECONDS/60}m window.")

        while True:
            try:
                # Poll for recent trades across all markets (or specific ones)
                # Note: This is a conceptual example of the SDK usage.
                # In a real scenario, you'd iterate over active markets.
                # trades = self.client.get_trades(limit=100)
                # for trade in trades: self.process_trade(trade)

                # State cleanup
                now = time.time()
                stale_ids = [tid for tid, ts in self.processed_trades.items() if ts < (now - 3600)]
                for tid in stale_ids: del self.processed_trades[tid]

                time.sleep(POLL_INTERVAL)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    agent = PolymarketInsiderAgent()
    print("Agent Initialized. Call agent.monitor() to start.")
    # To start monitoring in a real environment:
    # agent.monitor()

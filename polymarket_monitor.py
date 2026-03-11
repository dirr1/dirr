import time
import json
import requests
from collections import deque
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON

# Configuration - Thresholds from latest request
CLOB_ENDPOINT = "https://clob.polymarket.com"
GAMMA_API_ENDPOINT = "https://gamma-api.polymarket.com"
LOW_VOLUME_THRESHOLD = 5000  # daily avg volume
INSIDER_TRADE_SIZE_THRESHOLD = 10000 # $10,000
IMMEDIATE_PRICE_SHIFT_THRESHOLD = 0.05 # 5%
WINDOW_SECONDS = 300 # 5 minutes for general monitoring
POLL_INTERVAL = 10

class PolymarketInsiderAgent:
    def __init__(self, api_key=None, secret=None, passphrase=None):
        # Public data access
        self.client = ClobClient(CLOB_ENDPOINT, POLYGON)
        self.processed_trades = {} # map trade_id -> timestamp for pruning
        self.market_cache = {}
        self.price_history = {} # condition_id -> last_price for "immediate" shift detection

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

    def analyze_with_gemini(self, alert_data):
        """
        Placeholder function to send data to Gemini API
        for sentiment and news cross-referencing.
        """
        print(f"[AI Analysis] Sending trade {alert_data['id']} to Gemini for sentiment and news cross-referencing...")
        # Implementation: response = gemini.generate_content(f"Analyze: {alert_data}")
        return "Gemini analysis result pending..."

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

        # Detection Logic:
        # 1. Single trade size > $10,000
        if value_usd > INSIDER_TRADE_SIZE_THRESHOLD:
            market_info = self.get_market_info(condition_id)

            if market_info:
                # 2. Low volume market (less than $5,000 daily avg)
                if market_info['daily_volume'] < LOW_VOLUME_THRESHOLD:

                    # 3. Immediate price shift of > 5%
                    last_price = self.price_history.get(condition_id)
                    price_shift = abs(price - last_price) / last_price if last_price else 0

                    if price_shift > IMMEDIATE_PRICE_SHIFT_THRESHOLD:
                        self.trigger_alert(trade, market_info, price_shift)

        # Always update last price for "immediate" shift detection
        self.price_history[condition_id] = price

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

        print("\n" + "!" * 60)
        print("INSIDER CRITERIA MET - TRADE FLAGGED")
        print(f"Market: {alert_data['market_question']}")
        print(f"Daily Volume: ${alert_data['daily_volume']:.2f}")
        print(f"Wallet: {alert_data['wallet_address']}")
        print(f"Trade Value: ${alert_data['value_usd']:.2f}")
        print(f"Immediate Price Shift: {alert_data['price_shift']}")
        print(f"Time: {time.ctime(float(alert_data['timestamp']))}")
        print("!" * 60 + "\n")

        self.analyze_with_gemini(alert_data)

    def monitor(self):
        """Main monitoring loop using Polymarket CLOB SDK."""
        print(f"Polymarket Insider Monitoring Agent Active.")
        print(f"Thresholds: >${INSIDER_TRADE_SIZE_THRESHOLD} size, <${LOW_VOLUME_THRESHOLD} vol, >{IMMEDIATE_PRICE_SHIFT_THRESHOLD*100}% shift.")

        while True:
            try:
                # In actual use: trades = self.client.get_trades(limit=100)
                # for trade in trades: self.process_trade(trade)

                # Prune old processed IDs
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
    print("Polymarket Insider Agent Initialized.")
    # agent.monitor()

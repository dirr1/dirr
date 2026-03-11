import json
import time
from collections import deque
from urllib.request import urlopen

# Configuration
TRADES_URL = "http://localhost:8080/trades"
POLL_INTERVAL = 1
VALUE_THRESHOLD = 50000
PRICE_SHIFT_THRESHOLD = 0.10
WINDOW_SECONDS = 300 # 5 minutes

# State
processed_trade_ids = {} # map trade_id -> timestamp for pruning
trade_history = deque() # list of trade objects

def fetch_trades():
    try:
        with urlopen(TRADES_URL) as response:
            data = response.read().decode()
            trades = json.loads(data)
            # Sort trades chronologically to ensure they're processed correctly
            # regardless of API response order.
            return sorted(trades, key=lambda x: x.get('timestamp', 0))
    except Exception as e:
        print(f"Error fetching trades: {e}", flush=True)
    return []

def monitor():
    print(f"Monitoring {TRADES_URL} for trades > ${VALUE_THRESHOLD} with > {PRICE_SHIFT_THRESHOLD*100}% price shift in {WINDOW_SECONDS/60} minutes...", flush=True)

    while True:
        trades = fetch_trades()
        current_time = time.time()

        # Add new trades to history and check for alerts
        for trade in trades:
            # Generate a more robust trade_id if it's missing
            # Using price, amount, and timestamp as a composite key.
            trade_id = trade.get('id', f"{trade.get('timestamp')}-{trade.get('price')}-{trade.get('amount')}")

            if trade_id not in processed_trade_ids:
                # This is a new trade
                timestamp = trade.get('timestamp', current_time)
                processed_trade_ids[trade_id] = timestamp
                trade_history.append(trade)

                # Condition 1: Single trade over $50k
                if trade.get('value', 0) > VALUE_THRESHOLD:
                    # Condition 2: Check for > 10% price shift within the last 5 minutes
                    # Calculate shift relative to the OLDEST trade currently in our 5-minute history
                    if len(trade_history) > 1:
                        # Find the oldest trade that is still within 5 mins of THIS trade's timestamp
                        # (since trade_history is sorted, it's likely the first element)
                        while trade_history and trade_history[0]['timestamp'] < (timestamp - WINDOW_SECONDS):
                            trade_history.popleft()

                        if trade_history:
                            initial_trade = trade_history[0]
                            initial_price = initial_trade.get('price')
                            current_price = trade.get('price')

                            if initial_price and current_price:
                                price_shift = abs(current_price - initial_price) / initial_price

                                if price_shift > PRICE_SHIFT_THRESHOLD:
                                    print(f"ALERT: Significant trade and price shift detected!", flush=True)
                                    print(f"Trade: Value=${trade['value']:.2f}, Price={current_price:.2f}", flush=True)
                                    print(f"Price Shift: {price_shift*100:.2f}% (from {initial_price:.2f} at {time.ctime(initial_trade['timestamp'])})", flush=True)
                                    print("-" * 40, flush=True)

        # Pruning: Remove old trade IDs and history entries that have aged out
        # This prevents the memory leak.
        limit_time = current_time - WINDOW_SECONDS

        # Prune trade_history
        while trade_history and trade_history[0]['timestamp'] < limit_time:
            trade_history.popleft()

        # Prune processed_trade_ids (converting to list to avoid "dictionary changed size during iteration")
        expired_ids = [tid for tid, ts in processed_trade_ids.items() if ts < limit_time]
        for tid in expired_ids:
            del processed_trade_ids[tid]

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    monitor()

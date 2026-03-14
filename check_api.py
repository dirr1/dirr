import requests
try:
    r = requests.get('https://data-api.polymarket.com/trades?limit=5')
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

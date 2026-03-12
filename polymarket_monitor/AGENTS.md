# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades in near-real-time and use Gemini 2.0 to detect potential insider activity.

## Monitoring Strategy: Cache-Bypassing High-Frequency Polling
Due to regional WebSocket ghosting and heavy Data API caching, this agent uses a robust high-frequency polling strategy:
1.  **Cache Bypassing**: Uses a random `nonce` parameter in every request to force the CDN to fetch fresh data from the origin server.
2.  **High-Density Ingestion**: Polls the Polymarket Data API `/trades` endpoint every **1 second** with a `limit=500`.
3.  **Maximum Coverage**: By fetching the most recent 500 trades every second, the agent can ingest up to **1.8 million trades per hour**, covering 100% of platform activity.
4.  **Reliable Enrichment**: The Data API includes the **wallet address** (`proxyWallet`) and **trade size** for every record, ensuring forensic accuracy for every flagged trade.

## Allowed Libraries
- `google-genai`: The modern standard SDK for reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For high-speed data ingestion and Discord notifications.

## APIs Used
- **Polymarket Data API**: High-frequency trade history ingestion (`https://data-api.polymarket.com/trades`).
- **Polymarket Gamma API**: Market metadata and volume retrieval.
- **Google AI Studio (Gemini 2.0)**: Search-grounded forensic reasoning.
- **Discord Webhooks**: Automated high-risk alerting.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within 5 minutes in low-volume markets (< $5k).
2. **Forensic Analysis**: Gemini 2.0 Flash searches for public news published *before* the trade.
3. **Notification**: Scores > 80 are labeled "High Probability Insider" and sent to Discord.

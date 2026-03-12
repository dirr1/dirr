# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades in real-time and use Gemini 2.0 to detect potential insider activity.

## Hybrid Monitoring Strategy
To maximize performance while fulfilling data requirements, this agent uses a hybrid approach:
1.  **Real-Time Detection**: Connects to the Polymarket CLOB WebSocket (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) to ingest every trade event as it happens. This allows it to detect >10% price shifts within 5 minutes instantly.
2.  **Data Enrichment**: When a suspicious trade is detected, the agent queries the Polymarket Data API (`https://data-api.polymarket.com/trades`) for the specific market to extract the trader's **wallet address** (`proxyWallet`).

## Allowed Libraries
- `websockets`: For high-speed real-time transaction monitoring.
- `google-genai`: The modern standard SDK for reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For fetching market metadata and wallet enrichment from Polymarket APIs.

## APIs Used
- **Polymarket CLOB WebSocket**: Live transaction stream.
- **Polymarket Data API**: Targeted wallet lookup and historical data.
- **Polymarket Gamma API**: Market discovery and volume metadata.
- **Google AI Studio (Gemini 2.0)**: Search-grounded forensic reasoning.
- **Discord Webhooks**: Automated high-risk alerting.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within 5 minutes in low-volume markets (< $5k).
2. **Wallet Extraction**: Match the real-time event to the Data API to identify the actor.
3. **Forensic Analysis**: Gemini 2.0 Flash searches for public news published *before* the trade.
4. **Notification**: Scores > 80 are labeled "High Probability Insider" and sent to Discord.

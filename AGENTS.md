# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades in real-time using a hybrid WebSocket/REST strategy and forensic AI reasoning.

## Hybrid Monitoring Strategy
To ensure 100% platform coverage and granular data accuracy, this agent uses a hybrid approach:
1.  **WebSocket Stream**: Connects to the Polymarket CLOB WebSocket (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) to detect price shifts and high-impact trades instantly.
2.  **On-Demand Enrichment**: When a suspicious trade is detected via the stream, the agent performs a targeted lookup on the Data API (`/trades`) for the specific market to extract the **trade size** and **wallet address** (`proxyWallet`).
3.  **Real-Time Feedback**: A background reporter task provides constant confirmation of the agent's health and ingestion rate in the console.

## Allowed Libraries
- `websockets`: For high-speed real-time transaction monitoring.
- `google-genai`: The modern standard SDK for reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For fetching market metadata and targeted data enrichment.

## APIs Used
- **Polymarket CLOB WebSocket**: Live event ingestion.
- **Polymarket Data API**: Targeted wallet and size extraction.
- **Polymarket Gamma API**: Active market discovery and volume metadata.
- **Google AI Studio (Gemini 2.0)**: Search-grounded forensic reasoning.
- **Discord Webhooks**: Automated high-risk alerting.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within 5 minutes in low-volume markets (< $5k).
2. **Forensic Analysis**: Gemini 2.0 Flash searches for public news published *before* the trade.
3. **Notification**: Scores > 80 are labeled "High Probability Insider" and sent to Discord.

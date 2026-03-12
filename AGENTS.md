# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades in near-real-time and use Gemini 2.0 to detect potential insider activity.

## Monitoring Strategy: Optimized High-Frequency Polling
Due to non-responsive platform WebSocket behavior in certain regions, this agent uses a high-frequency polling strategy to capture 100% of platform trades:
1.  **High-Density Fetching**: Polls the Polymarket Data API `/trades` endpoint every **1 second** with a `limit=500`.
2.  **Max Throughput**: By fetching the most recent 500 trades every second, the agent can ingest up to **1.8 million trades per hour**, covering peak platform activity without data loss.
3.  **Real-Time Feedback**: The agent provides a live console ticker and minute-by-minute throughput reports to confirm ongoing activity.

## Allowed Libraries
- `google-genai`: The modern standard SDK for reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For high-speed data ingestion and Discord notifications.

## APIs Used
- **Polymarket Data API**: High-frequency trade history ingestion.
- **Polymarket Gamma API**: Active market discovery and volume metadata.
- **Google AI Studio (Gemini 2.0)**: Search-grounded forensic reasoning.
- **Discord Webhook**: Automated high-risk alerting.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within 5 minutes in low-volume markets (< $5k).
2. **Forensic Analysis**: Gemini 2.0 Flash searches for public news published *before* the trade.
3. **Notification**: Scores > 80 are labeled "High Probability Insider" and sent to Discord.

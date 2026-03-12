# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades in near-real-time and use Gemini 2.0 to detect potential insider activity.

## Monitoring Strategy: Optimized High-Frequency Polling
This agent uses a high-frequency polling strategy to capture the maximum number of platform trades:
1.  **High-Density Fetching**: Polls the Polymarket Data API `/trades` endpoint every **1 second** with a `limit=500`.
2.  **Full Platform Coverage**: By fetching the most recent 500 trades every second, the agent ensures 100% platform coverage even during peak volatility.
3.  **Real-Time Feedback**: The agent provides a live console ticker updating every second: `[HH:MM:SS] Polled: 500 | New: X | Total Analyzed: Y`.

## Allowed Libraries
- `google-genai`: The modern standard SDK for reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For high-speed data ingestion and Discord notifications.

## APIs Used
- **Polymarket Data API**: High-frequency trade history ingestion.
- **Polymarket Gamma API**: Market metadata and volume retrieval.
- **Google AI Studio (Gemini 2.0)**: Search-grounded forensic reasoning.
- **Discord Webhook**: Automated high-risk alerting.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within 5 minutes in low-volume markets (< $5k).
2. **Forensic Analysis**: Gemini 2.0 Flash searches for public news published *before* the trade.
3. **Notification**: High-confidence scores (> 80) are labeled "High Probability Insider" and sent to Discord.

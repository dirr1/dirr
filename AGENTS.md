# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades and use Gemini 2.0 to detect potential insider activity.

## Allowed Libraries
- `py-clob-client`: For interacting with Polymarket's Central Limit Order Book (CLOB).
- `google-genai`: The modern standard SDK for reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For fetching market metadata from the Polymarket Gamma API and sending Discord notifications.

## APIs Used
- **Polymarket CLOB API**: For fetching real-time transaction data.
- **Polymarket Data API**: For retrieving global trade history (`https://data-api.polymarket.com/trades`).
- **Polymarket Gamma API**: For retrieving market metadata and volume data (`https://gamma-api.polymarket.com`).
- **Google AI Studio (Gemini 2.0)**: For search-grounded reasoning and "insider" probability scoring.
- **Discord Webhooks**: For automated alerting of flagged trades.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within a 5-minute window in low-volume markets (< $5k).
2. **AI Reasoning**: Flagged trades are sent to Gemini 2.0 Flash using the `google-genai` SDK.
3. **Search Grounding**: Gemini uses its built-in Google Search tool to find public news justifying the trade at its specific timestamp.
4. **Scoring**: Gemini returns an "Insider Probability Score" (0-100).
5. **Notification**: Trades are sent to a Discord webhook, with scores > 80 labeled as "High Probability Insider".

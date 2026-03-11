# Polymarket Insider Monitoring Agent

This agent is designed to monitor Polymarket trades and use Gemini 2.0 to detect potential insider activity.

## Allowed Libraries
- `py-clob-client`: For interacting with Polymarket's Central Limit Order Book (CLOB).
- `google-generativeai`: For reasoning using Gemini 2.0 and its Google Search tool.
- `python-dotenv`: For managing API keys and webhook URLs.
- `requests`: For fetching market metadata from the Polymarket Gamma API and sending Discord notifications.

## APIs Used
- **Polymarket CLOB API**: For fetching real-time transaction data (`https://clob.polymarket.com`).
- **Polymarket Gamma API**: For retrieving market metadata and volume data (`https://gamma-api.polymarket.com`).
- **Google AI Studio (Gemini 2.0)**: For search-grounded reasoning and "insider" probability scoring.
- **Discord Webhooks**: For automated alerting of flagged trades.

## Logic Overview
1. **Trade Detection**: Flag trades > $50,000 with a > 10% price shift within a 5-minute window.
2. **AI Reasoning**: Flagged trades are sent to Gemini 2.0 Flash.
3. **Search Grounding**: Gemini uses its built-in Google Search tool to find public news justifying the trade at its specific timestamp.
4. **Scoring**: Gemini returns an "Insider Probability Score" (0-100).
5. **Notification**: Scores > 80 are labeled as "High Probability Insider" and sent to a configured Discord webhook.

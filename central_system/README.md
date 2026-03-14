# Polymarket Central Intelligence Dashboard

A unified intelligence platform for monitoring Polymarket activity. This system integrates real-time trade monitoring, statistical anomaly detection (binomial p-values), wallet clustering, and AI-driven forensic analysis.

## Features

*   **Real-time Whale Tracker**: Monitor trades over $10,000 as they happen.
*   **Statistical Insider Detection**: Identify wallets with anomalous win rates using p-value analysis.
*   **Wallet Clustering**: Discover linked wallets using timing correlation and market overlap patterns.
*   **AI Forensic Reports**: Automated investigation of price-shifting trades (>$50k, >10% shift) using Gemini 2.0 Flash with Google Search grounding.
*   **Multi-Channel Alerting**: Concurrent notifications to Slack and Discord.

## Installation

1.  **Clone the repository** (if you haven't already).
2.  **Navigate to the central system directory**:
    ```bash
    cd central_system
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure environment variables**:
    Create a `.env` file in the `central_system/` root (or use the one in `polymarket_monitors/`):
    ```env
    GEMINI_API_KEY=your_gemini_key
    SLACK_WEBHOOK_URL=your_slack_webhook
    DISCORD_WEBHOOK_URL=your_discord_webhook
    ```

## Running the System

You need to run both the backend API and the frontend dashboard.

### 1. Start the Backend API (FastAPI)
The backend handles trade ingestion, analysis, and alerting.
```bash
# From the root of the repository
export PYTHONPATH=$PYTHONPATH:.
uvicorn central_system.backend.api:app --host 0.0.0.0 --port 8000
```

### 2. Start the Frontend Dashboard (Streamlit)
The frontend provides the interactive UI.
```bash
# From the root of the repository
streamlit run central_system/frontend/dashboard.py
```

## Project Structure

*   `/backend`: Core logic for monitoring, statistical analysis, and alerting.
*   `/frontend`: Streamlit user interface.
*   `/tests`: Integration and unit tests for the intelligence engines.

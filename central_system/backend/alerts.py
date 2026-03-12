import os
import json
import requests
import time
from typing import Dict, Any, List
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

class AlertManager:
    """
    Unified alerting system with AI forensics.
    Combines:
    1. Gemini 2.0 Flash forensic analysis (from polymarket_monitor.py)
    2. Slack notifications (from bot/src/slack_notifier.py)
    3. Discord notifications (from polymarket_monitor.py)
    """

    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

        if self.gemini_api_key:
            try:
                self.client_ai = genai.Client(api_key=self.gemini_api_key)
                self.model_id = 'gemini-2.0-flash'
            except Exception as e:
                print(f"Error initializing Gemini: {e}")
                self.client_ai = None
        else:
            self.client_ai = None

    async def run_ai_forensics(self, trade_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform AI forensic analysis on a suspicious trade."""
        if not self.client_ai:
            return {"insider_probability_score": 0, "reasoning": "AI Analysis Disabled"}

        timestamp = trade_data.get('timestamp', time.time())
        market_question = trade_data.get('market_question', 'Unknown Market')

        prompt = f"""
        You are an elite forensic market analyst.
        Analyze this Polymarket trade:
        - Market: {market_question}
        - Trade Value: ${trade_data.get('value_usd', 0):,.2f}
        - Wallet: {trade_data.get('wallet_address')}
        - Time: {time.ctime(float(timestamp))}

        Use the Google Search tool to find if any public news justified this odds movement AT THIS EXACT TIME.
        1. Search specifically for news published BEFORE the trade.
        2. If no news exists, assign a high "insider_probability_score".
        3. Return JSON: {{"insider_probability_score": int, "reasoning": str, "supporting_evidence": list}}
        """

        try:
            response = self.client_ai.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[{'google_search': {}}])
            )

            text = response.text
            start, end = text.find('{'), text.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"AI Forensics Error: {e}")

        return {"insider_probability_score": 0, "reasoning": "Analysis Failed"}

    def send_slack_alert(self, alert_data: Dict[str, Any]):
        """Send alert to Slack."""
        if not self.slack_webhook_url: return

        payload = {
            "text": f"🚨 *Suspicious Trade Detected*\n"
                    f"*Market:* {alert_data.get('market_question')}\n"
                    f"*Value:* ${alert_data.get('value_usd', 0):,.2f}\n"
                    f"*AI Score:* {alert_data.get('ai_analysis', {}).get('insider_probability_score', 'N/A')}/100\n"
                    f"*Wallet:* `{alert_data.get('wallet_address')}`"
        }
        try:
            requests.post(self.slack_webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Slack Error: {e}")

    def send_discord_alert(self, alert_data: Dict[str, Any]):
        """Send alert to Discord."""
        if not self.discord_webhook_url: return

        analysis = alert_data.get('ai_analysis', {})
        score = analysis.get('insider_probability_score', 0)

        payload = {
            "embeds": [{
                "title": "🚨 POTENTIAL INSIDER TRADE",
                "color": 15158332 if score > 70 else 15844367,
                "fields": [
                    {"name": "Market", "value": alert_data.get('market_question', 'N/A')},
                    {"name": "Value", "value": f"${alert_data.get('value_usd', 0):,.2f}", "inline": True},
                    {"name": "AI Score", "value": f"{score}/100", "inline": True},
                    {"name": "Wallet", "value": f"`{alert_data.get('wallet_address')}`"},
                    {"name": "Reasoning", "value": analysis.get('reasoning', 'N/A')}
                ]
            }]
        }
        try:
            requests.post(self.discord_webhook_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Discord Error: {e}")

    async def broadcast_alert(self, alert_data: Dict[str, Any]):
        """Run forensics and broadcast to all channels."""
        print(f"[Alert] Processing Suspicious Activity for {alert_data.get('wallet_address')}")

        # Run AI Forensics
        ai_result = await self.run_ai_forensics(alert_data)
        alert_data['ai_analysis'] = ai_result

        # Send to channels
        self.send_slack_alert(alert_data)
        self.send_discord_alert(alert_data)
        print(f"[Alert] Broadcast Complete. AI Score: {ai_result.get('insider_probability_score')}")

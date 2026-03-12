"""Slack webhook notifications"""

import aiohttp

from src.config import SLACK_ENABLED, SLACK_WEBHOOK_URL
from src.logger import logger


class SlackNotifier:
    def __init__(self):
        self.webhook_url = SLACK_WEBHOOK_URL
        self.enabled = SLACK_ENABLED and bool(self.webhook_url)

        if not self.enabled:
            logger.info("Slack notifications disabled")

    async def send_alert(self, alert: dict):
        """Send alert to Slack channel"""
        if not self.enabled:
            return

        try:
            # Build Slack message
            score = alert["suspicion_score"]

            # Emoji based on severity
            if score >= 9:
                emoji = "🚨"
                color = "#ff0000"
            elif score >= 7:
                emoji = "⚠️"
                color = "#ffa500"
            else:
                emoji = "ℹ️"
                color = "#0099ff"

            # Format wallet address
            wallet = alert["wallet"]
            wallet_short = f"{wallet[:8]}...{wallet[-6:]}"

            # Build message blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{emoji} Suspicious Activity Detected",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Score:*\n{score:.1f}/10"},
                        {"type": "mrkdwn", "text": f"*Wallet:*\n`{wallet_short}`"},
                    ],
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Market:*\n{alert['market_title']}"},
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Trade:*\n{alert['trade']['side']} ${alert['trade']['value_usd']:.2f}",
                        },
                        {"type": "mrkdwn", "text": f"*Price:*\n${alert['trade']['price']}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Red Flags:*\n"
                        + "\n".join([f"• {r}" for r in alert["reasons"][:3]]),
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "View on Polymarket"},
                            "url": f"https://polymarket.com/event/{alert['market_slug']}",
                        }
                    ],
                },
            ]

            payload = {"attachments": [{"color": color, "blocks": blocks}]}

            # Send to Slack
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 200:
                        logger.debug("Alert sent to Slack")
                    else:
                        logger.error(f"Failed to send Slack alert: {response.status}")

        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")

"""Alert system with SQLite and Slack integration"""

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.database import Database
from src.logger import logger
from src.slack_notifier import SlackNotifier

console = Console()


class AlertSystem:
    def __init__(self, db: Database):
        self.db = db
        self.slack = SlackNotifier()

    async def create_alert(
        self,
        wallet: str,
        market: dict,
        trade: dict,
        score: float,
        reasons: list[str],
        wallet_stats: dict,
    ) -> dict:
        """Create a new alert"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "wallet": wallet,
            "market_title": market.get("question", "Unknown"),
            "market_slug": market.get("slug", ""),
            "condition_id": market.get("condition_id", ""),
            "trade": {
                "size": trade.get("size"),
                "price": trade.get("price"),
                "side": trade.get("side"),
                "value_usd": float(trade.get("size", 0)) * float(trade.get("price", 0)),
            },
            "suspicion_score": score,
            "reasons": reasons,
            "wallet_stats": {
                "age_days": wallet_stats.get("age_days"),
                "total_trades": wallet_stats.get("total_trades"),
                "unique_markets": wallet_stats.get("unique_markets"),
                "avg_bet_size": wallet_stats.get("avg_bet_size"),
            },
            "current_price": market.get("price", "Unknown"),
        }

        await self.db.save_alert(alert)
        await self.slack.send_alert(alert)
        logger.info(f"Alert created: {wallet[:10]}... score {score:.1f}/10")
        return alert

    def print_alert(self, alert: dict):
        """Print alert to console with rich formatting"""
        score = alert["suspicion_score"]

        if score >= 9:
            color = "red"
            emoji = "🚨"
        elif score >= 7:
            color = "yellow"
            emoji = "⚠️"
        else:
            color = "blue"
            emoji = "ℹ️"

        title = Text()
        title.append(f"{emoji} SUSPICIOUS ACTIVITY ", style=f"bold {color}")
        title.append(f"(Score: {score:.1f}/10)", style="bold white")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="cyan", width=20)
        table.add_column(style="white")

        table.add_row("Market", alert["market_title"][:60])
        table.add_row("Wallet", f"{alert['wallet'][:12]}...{alert['wallet'][-10:]}")
        table.add_row(
            "Trade",
            f"{alert['trade']['side']} {alert['trade']['size']} @ ${alert['trade']['price']} = [green]${alert['trade']['value_usd']:.2f}[/green]",
        )
        table.add_row("Current Price", str(alert["current_price"]))

        table.add_row("", "")
        table.add_row("[bold]Wallet Stats[/bold]", "")
        table.add_row("  Age", f"{alert['wallet_stats']['age_days']:.1f} days")
        table.add_row("  Total Trades", str(alert["wallet_stats"]["total_trades"]))
        table.add_row("  Unique Markets", str(alert["wallet_stats"]["unique_markets"]))
        table.add_row("  Avg Bet Size", f"${alert['wallet_stats']['avg_bet_size']:.2f}")

        table.add_row("", "")
        table.add_row("[bold]Red Flags[/bold]", "")
        for i, reason in enumerate(alert["reasons"], 1):
            table.add_row(f"  {i}.", reason)

        table.add_row("", "")
        table.add_row("Link", f"https://polymarket.com/event/{alert['market_slug']}")

        panel = Panel(table, title=title, border_style=color, expand=False)
        console.print(panel)
        console.print()

    async def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        """Get alerts from last N hours"""
        return await self.db.get_recent_alerts(hours)

    async def get_alert_stats(self) -> dict:
        """Get statistics about alerts"""
        return await self.db.get_alert_stats()

    async def print_stats_table(self):
        """Print beautiful stats table"""
        stats = await self.get_alert_stats()

        table = Table(title="📊 Alert Statistics", show_header=True)
        table.add_column("Metric", style="cyan", width=30)
        table.add_column("Value", style="white", justify="right")

        table.add_row("Total Alerts", str(stats.get("total_alerts", 0)))
        table.add_row("Alerts (24h)", f"[yellow]{stats.get('recent_24h', 0)}[/yellow]")
        table.add_row("Avg Score", f"{stats.get('avg_score', 0):.2f}/10")
        table.add_row("Unique Wallets Flagged", str(stats.get("unique_wallets", 0)))

        if stats.get("most_flagged_wallet"):
            wallet = stats["most_flagged_wallet"]
            table.add_row("Most Flagged Wallet", f"{wallet[:12]}...{wallet[-10:]}")

        console.print(table)

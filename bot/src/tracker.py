"""Main tracking logic - Optimized async version"""

import asyncio

from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from src.alert_system import AlertSystem
from src.anomaly_detector import AnomalyDetector
from src.config import (
    CONCURRENT_BATCH_SIZE,
    DATABASE_PATH,
    POLL_INTERVAL,
    SUSPICIOUS_SCORE_THRESHOLD,
    TRACKED_TAG_IDS,
)
from src.database import Database
from src.logger import console, logger
from src.polymarket_api import PolymarketAPI
from src.wallet_tracker import WalletTracker


class InsiderTracker:
    def __init__(self):
        self.db = Database(DATABASE_PATH)
        self.wallet_tracker = WalletTracker(self.db)
        self.anomaly_detector = AnomalyDetector()
        self.alert_system = AlertSystem(self.db)
        self.processed_trades = set()
        self.scan_stats = {
            "markets_scanned": 0,
            "trades_analyzed": 0,
            "alerts_triggered": 0,
            "errors": 0,
        }

    async def initialize(self):
        """Initialize database"""
        await self.db.init_db()

    async def get_all_markets(self, api: PolymarketAPI) -> list[dict]:
        """Fetch all markets we're tracking concurrently"""

        async def fetch_tag(tag_id):
            try:
                events = await api.fetch_active_events(tag_id)
                markets = []
                for event in events:
                    for market in event.get("markets", []):
                        market["event_title"] = event.get("title", "")
                        market["event_slug"] = event.get("slug", "")
                        markets.append(market)
                logger.debug(f"Fetched {len(markets)} markets for tag {tag_id}")
                return markets
            except Exception as e:
                logger.error(f"Error fetching events for tag {tag_id}: {e}")
                self.scan_stats["errors"] += 1
                return []

        results = await asyncio.gather(*[fetch_tag(tag_id) for tag_id in TRACKED_TAG_IDS])
        all_markets = [market for markets in results for market in markets]
        logger.info(
            f"Found {len(all_markets)} total markets across {len(TRACKED_TAG_IDS)} categories"
        )
        return all_markets

    async def analyze_market(self, api: PolymarketAPI, market: dict) -> dict:
        """Analyze a single market for suspicious activity"""
        condition_id = market.get("condition_id")
        if not condition_id:
            return {"alerts": 0, "trades": 0}

        alerts_count = 0
        trades_count = 0

        try:
            trades = await api.fetch_trades(condition_id, limit=100)

            if not trades:
                return {"alerts": 0, "trades": 0}

            trades_count = len(trades)
            market_stats = self.anomaly_detector.calculate_market_stats(trades)

            for trade in trades:
                trade_id = trade.get("id")
                if trade_id in self.processed_trades:
                    continue

                self.processed_trades.add(trade_id)

                wallet = trade.get("maker")
                if not wallet:
                    continue

                await self.wallet_tracker.register_trade(
                    wallet,
                    {
                        **trade,
                        "market": condition_id,
                        "market_title": market.get("question", ""),
                    },
                )

                wallet_stats = await self.wallet_tracker.get_wallet_stats(wallet)
                score, reasons = self.anomaly_detector.score_wallet_suspiciousness(
                    wallet_stats, trade, market_stats
                )

                if score >= SUSPICIOUS_SCORE_THRESHOLD:
                    alert = await self.alert_system.create_alert(
                        wallet, market, trade, score, reasons, wallet_stats
                    )
                    self.alert_system.print_alert(alert)
                    alerts_count += 1

            coordinated = self.anomaly_detector.detect_coordinated_activity(trades)
            if coordinated:
                for group in coordinated:
                    logger.warning(
                        f"Coordinated activity in {market.get('question', 'market')[:40]}: "
                        f"{group['count']} similar trades"
                    )

        except Exception as e:
            logger.error(f"Error analyzing market {market.get('question', 'unknown')[:40]}: {e}")
            self.scan_stats["errors"] += 1

        return {"alerts": alerts_count, "trades": trades_count}

    async def run_scan(self):
        """Run a single scan of all markets concurrently"""
        logger.info("Starting market scan...")

        self.scan_stats = {
            "markets_scanned": 0,
            "trades_analyzed": 0,
            "alerts_triggered": 0,
            "errors": 0,
        }

        async with PolymarketAPI() as api:
            markets = await self.get_all_markets(api)

            if not markets:
                logger.warning("No markets found to scan")
                return

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"[cyan]Scanning {len(markets)} markets...", total=len(markets)
                )

                for i in range(0, len(markets), CONCURRENT_BATCH_SIZE):
                    batch = markets[i : i + CONCURRENT_BATCH_SIZE]

                    results = await asyncio.gather(
                        *[self.analyze_market(api, market) for market in batch],
                        return_exceptions=True,
                    )

                    for result in results:
                        if isinstance(result, dict):
                            self.scan_stats["markets_scanned"] += 1
                            self.scan_stats["trades_analyzed"] += result.get("trades", 0)
                            self.scan_stats["alerts_triggered"] += result.get("alerts", 0)

                    progress.update(task, advance=len(batch))

                    if i + CONCURRENT_BATCH_SIZE < len(markets):
                        await asyncio.sleep(0.3)

        logger.info("Scan complete")

        console.print("\n")
        summary_table = Table(title="✅ Scan Complete", show_header=True, header_style="bold green")
        summary_table.add_column("Metric", style="cyan", width=25)
        summary_table.add_column("Value", justify="right", style="white")

        summary_table.add_row(
            "Markets Scanned", f"[green]{self.scan_stats['markets_scanned']}[/green]"
        )
        summary_table.add_row(
            "Trades Analyzed", f"[blue]{self.scan_stats['trades_analyzed']}[/blue]"
        )
        summary_table.add_row(
            "New Alerts", f"[yellow]{self.scan_stats['alerts_triggered']}[/yellow]"
        )
        summary_table.add_row("Errors Encountered", f"[red]{self.scan_stats['errors']}[/red]")

        stats = await self.alert_system.get_alert_stats()
        summary_table.add_row("", "")
        summary_table.add_row("Total Alerts (All Time)", str(stats.get("total_alerts", 0)))
        summary_table.add_row("Alerts (Last 24h)", str(stats.get("recent_24h", 0)))
        summary_table.add_row("Unique Flagged Wallets", str(stats.get("unique_wallets", 0)))

        console.print(summary_table)
        console.print()

    async def run_continuous(self):
        """Run continuous monitoring"""
        console.print(
            Panel.fit(
                "[bold cyan]🤖 Polymarket Insider Activity Tracker[/bold cyan]\n\n"
                f"[white]Polling Interval:[/white] [yellow]{POLL_INTERVAL}s[/yellow]\n"
                f"[white]Tracking Categories:[/white] [yellow]{len(TRACKED_TAG_IDS)}[/yellow]\n"
                f"[white]Alert Threshold:[/white] [yellow]{SUSPICIOUS_SCORE_THRESHOLD}/10[/yellow]\n"
                f"[white]Concurrent Batch Size:[/white] [yellow]{CONCURRENT_BATCH_SIZE}[/yellow]\n"
                f"[white]Mode:[/white] [green]ASYNC + OPTIMIZED + SQLite[/green]\n\n"
                "[dim]Press Ctrl+C to stop[/dim]",
                border_style="cyan",
            )
        )
        console.print()

        try:
            scan_count = 0
            while True:
                scan_count += 1
                logger.info(f"Starting scan #{scan_count}")

                await self.run_scan()

                logger.info(f"Waiting {POLL_INTERVAL}s until next scan...")
                for remaining in range(POLL_INTERVAL, 0, -1):
                    if remaining % 10 == 0 or remaining <= 5:
                        logger.debug(f"Next scan in {remaining}s...")
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            console.print("\n")
            console.print(
                Panel("[yellow]👋 Shutting down gracefully...[/yellow]", border_style="yellow")
            )
            logger.info("Shutdown complete")
            console.print("[green]✅ Goodbye![/green]\n")

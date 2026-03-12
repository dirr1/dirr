#!/usr/bin/env python3
"""
Polymarket Insider Activity Tracker
Monitors suspicious trading patterns to detect potential insider activity
"""

import argparse
import asyncio
import logging

from rich.console import Console
from rich.panel import Panel

from src.logger import logger
from src.tracker import InsiderTracker

console = Console()


async def main_async(args):
    """Async main function"""
    tracker = InsiderTracker()
    await tracker.initialize()

    if args.mode == "continuous":
        await tracker.run_continuous()
    elif args.mode == "scan":
        await tracker.run_scan()
    elif args.mode == "stats":
        console.print()
        await tracker.alert_system.print_stats_table()
        console.print()

        console.print(
            Panel.fit("[bold cyan]Recent Alerts (Last 24h)[/bold cyan]", border_style="cyan")
        )
        console.print()

        recent = await tracker.alert_system.get_recent_alerts(24)
        if not recent:
            console.print("[dim]No alerts in the last 24 hours[/dim]\n")
        else:
            for alert in recent[-10:]:
                console.print(f"[dim]{alert['timestamp']}[/dim]")
                console.print(f"  [cyan]Market:[/cyan] {alert['market_title'][:60]}")
                console.print(
                    f"  [cyan]Wallet:[/cyan] {alert['wallet'][:12]}...{alert['wallet'][-10:]}"
                )
                console.print(
                    f"  [cyan]Score:[/cyan] [yellow]{alert['suspicion_score']:.1f}/10[/yellow]"
                )
                console.print(
                    f"  [cyan]Trade:[/cyan] [green]${alert['trade']['value_usd']:.2f}[/green]"
                )
                console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Insider Activity Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Start continuous monitoring
  python main.py --mode scan        # Run a single scan
  python main.py --mode stats       # View statistics
  python main.py --debug            # Enable debug logging
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["continuous", "scan", "stats"],
        default="continuous",
        help="Run mode (default: continuous)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.info("Debug logging enabled")

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        console.print("\n[yellow]Stopped by user[/yellow]\n")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        console.print(f"\n[red]Error: {e}[/red]\n")
        raise


if __name__ == "__main__":
    main()

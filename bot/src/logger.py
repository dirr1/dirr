"""Logging setup with rich formatting"""

import logging

from rich.console import Console
from rich.logging import RichHandler

from src.config import LOG_FILE, LOG_LEVEL

console = Console()


def setup_logger(name: str = "polymarket_tracker") -> logging.Logger:
    """Setup logger with rich formatting"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))
    logger.handlers.clear()

    # Rich console handler
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    console_handler.setLevel(getattr(logging, LOG_LEVEL))

    # File handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger()

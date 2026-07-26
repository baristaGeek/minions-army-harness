"""Logging configuration."""

import logging
import sys
from pathlib import Path

from minions_army.core.config.loader import config as settings

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


class FlyVisibleConsoleFormatter(logging.Formatter):
    """Keep Fly stdout compact so app markers stay visually prominent."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%H:%M:%S")
        return f"{timestamp} {record.getMessage()}"


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Set up root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO if settings.app.environment == "production" else logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(FlyVisibleConsoleFormatter())
root_logger.addHandler(console_handler)

# File handler
file_handler = logging.FileHandler(LOGS_DIR / f"{settings.app.name}.log")
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
root_logger.addHandler(file_handler)

# Get logger for modules
logger = logging.getLogger(settings.app.name)

"""Execution logger for Idea Seed.

Provides a simple file + console dual-output logger for tracking
orchestrator execution progress.
"""

from datetime import datetime
from pathlib import Path


class Logger:
    """Simple file logger for tracking execution.

    Writes timestamped log entries to both a file and stdout.
    """

    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: str = "INFO") -> None:
        """Write log entry with timestamp.

        Args:
            message: Log message
            level: Log level (INFO, WARN, ERROR)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}\n"
        with open(self.log_path, "a") as f:
            f.write(entry)
        print(entry.rstrip())

    def log_section(self, title: str) -> None:
        """Log a section header with separator lines."""
        separator = "=" * 60
        self.log(separator)
        self.log(title)
        self.log(separator)

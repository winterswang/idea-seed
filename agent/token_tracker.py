"""Token usage tracking and reporting."""

import fcntl
import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# Token pricing per 1M tokens (input, output)
TOKEN_PRICING = {
    "minimax2.7": (0.10, 0.30),
    "qwen3.6-plus": (0.08, 0.24),
    "glm-5.1": (0.12, 0.36),
}

# Single call anomaly threshold
SINGLE_CALL_THRESHOLD = 50000


@dataclass
class TokenRecord:
    """Single API call token record."""

    timestamp: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_estimate: float
    is_estimated: bool
    phase: str = ""
    round: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TokenStats:
    """Token usage statistics."""

    total_tokens: int = 0
    total_cost: float = 0.0
    call_count: int = 0
    avg_tokens_per_call: float = 0.0
    max_tokens_single_call: int = 0
    anomaly_count: int = 0


class TokenTracker:
    """Track and report token consumption."""

    def __init__(self, state_dir: Path) -> None:
        """
        Initialize token tracker.

        Args:
            state_dir: Directory for storing token records
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.records_file = self.state_dir / "token_records.json"
        self.stats_file = self.state_dir / "token_stats.json"
        self._lock_file = self.state_dir / "token_records.lock"

        self._logger = logging.getLogger("idea-seed")

    @contextmanager
    def _file_lock(self, timeout: float = 10.0):
        """File lock context manager for thread-safe record access."""
        lock_fd = None
        try:
            lock_fd = open(self._lock_file, "w")
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() - start_time >= timeout:
                        raise TimeoutError(
                            f"Failed to acquire token tracker lock after {timeout}s"
                        )
                    time.sleep(0.1)
            yield
        finally:
            if lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()

    def record(
        self,
        model: str,
        usage: dict,
        phase: str = "",
        round_num: int = 0,
    ) -> TokenRecord:
        """
        Record a single API call's token usage.

        Args:
            model: Model identifier
            usage: Dict with input_tokens and output_tokens
            phase: Current phase (requirements/tech_design)
            round_num: Current round number

        Returns:
            TokenRecord created
        """
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = input_tokens + output_tokens

        # Calculate cost
        cost = self._calculate_cost(model, input_tokens, output_tokens)

        # Create record
        record = TokenRecord(
            timestamp=datetime.now().isoformat(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_estimate=cost,
            is_estimated=False,
            phase=phase,
            round=round_num,
        )

        # Save record with lock
        with self._file_lock():
            records = self._load_records_unsafe()
            records.append(record.to_dict())
            self._save_records_unsafe(records)

        # Check for anomaly
        self._check_anomaly(record)

        # Update stats cache
        self._update_stats()

        return record

    def get_stats(self, period: str = "all") -> TokenStats:
        """
        Get token statistics.

        Args:
            period: Time period - "daily", "weekly", "monthly", or "all"

        Returns:
            TokenStats object
        """
        records = self._load_records()

        if period != "all":
            cutoff = self._get_period_cutoff(period)
            records = [r for r in records if r["timestamp"] >= cutoff]

        return self._compute_stats(records)

    def detect_anomalies(
        self, records: Optional[list[dict]] = None
    ) -> list[TokenRecord]:
        """
        Detect anomalous token usage records.

        Args:
            records: Optional pre-loaded records (avoids re-reading file)

        Returns:
            List of records exceeding SINGLE_CALL_THRESHOLD
        """
        if records is None:
            records = self._load_records()

        anomalies: list[TokenRecord] = []

        for r in records:
            if r["total_tokens"] > SINGLE_CALL_THRESHOLD:
                anomalies.append(TokenRecord(**r))

        return anomalies

    def generate_report(self) -> str:
        """
        Generate token consumption report.

        Returns:
            Markdown formatted report string
        """
        stats = self.get_stats("all")
        anomalies = self.detect_anomalies()

        report = f"""# Token 消耗报告

## 总体统计

| 指标 | 值 |
|------|-----|
| 总 Token 数 | {stats.total_tokens:,} |
| 总费用 | ${stats.total_cost:.4f} |
| 调用次数 | {stats.call_count} |
| 平均每次调用 | {stats.avg_tokens_per_call:,.0f} tokens |
| 单次最大 | {stats.max_tokens_single_call:,} tokens |
| 异常次数 | {stats.anomaly_count} |

## 异常记录

"""
        if anomalies:
            for a in anomalies:
                report += f"- **{a.timestamp}**: {a.total_tokens:,} tokens (model: {a.model})\n"
        else:
            report += "无异常记录。\n"

        return report

    # === Private methods ===

    def _load_records(self) -> list[dict]:
        """Load records from file (with lock)."""
        with self._file_lock():
            return self._load_records_unsafe()

    def _load_records_unsafe(self) -> list[dict]:
        """Load records from file (without lock)."""
        if self.records_file.exists():
            with open(self.records_file) as f:
                return json.load(f)
        return []

    def _save_records_unsafe(self, records: list[dict]) -> None:
        """Save records to file (without lock - caller must hold lock)."""
        with open(self.records_file, "w") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def _update_stats(self) -> None:
        """Update stats cache file."""
        stats = self.get_stats("all")
        with open(self.stats_file, "w") as f:
            json.dump(asdict(stats), f, indent=2)

    def _calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate cost based on model pricing."""
        pricing = TOKEN_PRICING.get(model)
        if pricing is None:
            # Default to minimax pricing if model not found
            pricing = TOKEN_PRICING["minimax2.7"]

        input_price, output_price = pricing
        cost = (input_tokens / 1_000_000) * input_price + (
            output_tokens / 1_000_000
        ) * output_price
        return cost

    def _check_anomaly(self, record: TokenRecord) -> None:
        """Check for anomaly and log warning."""
        if record.total_tokens > SINGLE_CALL_THRESHOLD:
            self._logger.warning(
                f"Token anomaly detected: single call {record.total_tokens:,} tokens "
                f"(threshold: {SINGLE_CALL_THRESHOLD:,})"
            )

    def _get_period_cutoff(self, period: str) -> str:
        """Get period cutoff timestamp."""
        now = datetime.now()
        if period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        elif period == "weekly":
            days_ago = now.weekday()
            return (
                (now - timedelta(days=days_ago))
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .isoformat()
            )
        elif period == "monthly":
            return now.replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            ).isoformat()
        return ""

    def _compute_stats(self, records: list[dict]) -> TokenStats:
        """Compute statistics from records."""
        if not records:
            return TokenStats()

        total_tokens = sum(r["total_tokens"] for r in records)
        total_cost = sum(r["cost_estimate"] for r in records)
        call_count = len(records)

        return TokenStats(
            total_tokens=total_tokens,
            total_cost=total_cost,
            call_count=call_count,
            avg_tokens_per_call=total_tokens / call_count if call_count > 0 else 0,
            max_tokens_single_call=max(r["total_tokens"] for r in records),
            anomaly_count=len(self.detect_anomalies(records)),
        )

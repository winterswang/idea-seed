"""Tests for TokenTracker."""

from pathlib import Path
import shutil

from agent.token_tracker import TokenTracker


class TestTokenTracker:
    """Test TokenTracker class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = Path("/tmp/test_token_tracker")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.tracker = TokenTracker(self.test_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_record_basic(self):
        """Test basic token recording."""
        record = self.tracker.record(
            model="minimax2.7",
            usage={"input_tokens": 1000, "output_tokens": 500},
            phase="requirements",
            round_num=1,
        )

        assert record.total_tokens == 1500
        assert record.input_tokens == 1000
        assert record.output_tokens == 500
        assert record.model == "minimax2.7"
        assert record.phase == "requirements"
        assert record.round == 1

    def test_record_cost_calculation(self):
        """Test cost calculation for different models."""
        # minimax2.7: input $0.10/1M, output $0.30/1M
        record = self.tracker.record(
            model="minimax2.7",
            usage={"input_tokens": 1000000, "output_tokens": 500000},
        )
        # Cost = 1 * 0.10 + 0.5 * 0.30 = 0.25
        assert abs(record.cost_estimate - 0.25) < 0.001

    def test_record_cost_unknown_model(self):
        """Test cost calculation defaults for unknown model."""
        record = self.tracker.record(
            model="unknown-model",
            usage={"input_tokens": 1000, "output_tokens": 500},
        )
        # Should use default minimax pricing
        assert record.cost_estimate > 0

    def test_get_stats_all(self):
        """Test getting stats for all records."""
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 2000, "output_tokens": 1000}
        )

        stats = self.tracker.get_stats("all")
        assert stats.total_tokens == 4500
        assert stats.call_count == 2
        assert stats.avg_tokens_per_call == 2250

    def test_get_stats_empty(self):
        """Test getting stats with no records."""
        stats = self.tracker.get_stats("all")
        assert stats.total_tokens == 0
        assert stats.call_count == 0

    def test_detect_anomalies(self):
        """Test anomaly detection."""
        # Normal call
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )
        # Anomalous call (> 50000 tokens)
        self.tracker.record(
            model="minimax2.7",
            usage={"input_tokens": 40000, "output_tokens": 20000},
        )

        anomalies = self.tracker.detect_anomalies()
        assert len(anomalies) == 1
        assert anomalies[0].total_tokens == 60000

    def test_detect_anomalies_none(self):
        """Test anomaly detection with no anomalies."""
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        anomalies = self.tracker.detect_anomalies()
        assert len(anomalies) == 0

    def test_generate_report(self):
        """Test report generation."""
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        report = self.tracker.generate_report()
        assert "# Token 消耗报告" in report
        assert "总 Token 数" in report
        assert "调用次数" in report

    def test_records_persistence(self):
        """Test that records persist across tracker instances."""
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        # Create new tracker instance pointing to same directory
        tracker2 = TokenTracker(self.test_dir)
        stats = tracker2.get_stats("all")

        assert stats.call_count == 1
        assert stats.total_tokens == 1500

    def test_load_records(self):
        """Test loading records from file."""
        self.tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        records = self.tracker._load_records()
        assert len(records) == 1
        assert records[0]["total_tokens"] == 1500

    def test_load_records_empty(self):
        """Test loading from non-existent file."""
        records = self.tracker._load_records()
        assert records == []

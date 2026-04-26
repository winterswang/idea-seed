"""Tests for TokenTracker."""

from agent.token_tracker import TokenTracker


class TestTokenTracker:
    """Test TokenTracker class."""

    def test_record_basic(self, tmp_path):
        """Test basic token recording."""
        tracker = TokenTracker(tmp_path)
        record = tracker.record(
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

    def test_record_cost_calculation(self, tmp_path):
        """Test cost calculation for different models."""
        tracker = TokenTracker(tmp_path)
        # minimax2.7: input $0.10/1M, output $0.30/1M
        record = tracker.record(
            model="minimax2.7",
            usage={"input_tokens": 1000000, "output_tokens": 500000},
        )
        # Cost = 1 * 0.10 + 0.5 * 0.30 = 0.25
        assert abs(record.cost_estimate - 0.25) < 0.001

    def test_record_cost_unknown_model(self, tmp_path):
        """Test cost calculation defaults for unknown model."""
        tracker = TokenTracker(tmp_path)
        record = tracker.record(
            model="unknown-model",
            usage={"input_tokens": 1000, "output_tokens": 500},
        )
        # Should use default minimax pricing
        assert record.cost_estimate > 0

    def test_get_stats_all(self, tmp_path):
        """Test getting stats for all records."""
        tracker = TokenTracker(tmp_path)
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 2000, "output_tokens": 1000}
        )

        stats = tracker.get_stats("all")
        assert stats.total_tokens == 4500
        assert stats.call_count == 2
        assert stats.avg_tokens_per_call == 2250

    def test_get_stats_empty(self, tmp_path):
        """Test getting stats with no records."""
        tracker = TokenTracker(tmp_path)
        stats = tracker.get_stats("all")
        assert stats.total_tokens == 0
        assert stats.call_count == 0

    def test_detect_anomalies(self, tmp_path):
        """Test anomaly detection."""
        tracker = TokenTracker(tmp_path)
        # Normal call
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )
        # Anomalous call (> 50000 tokens)
        tracker.record(
            model="minimax2.7",
            usage={"input_tokens": 40000, "output_tokens": 20000},
        )

        anomalies = tracker.detect_anomalies()
        assert len(anomalies) == 1
        assert anomalies[0].total_tokens == 60000

    def test_detect_anomalies_none(self, tmp_path):
        """Test anomaly detection with no anomalies."""
        tracker = TokenTracker(tmp_path)
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        anomalies = tracker.detect_anomalies()
        assert len(anomalies) == 0

    def test_generate_report(self, tmp_path):
        """Test report generation."""
        tracker = TokenTracker(tmp_path)
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        report = tracker.generate_report()
        assert "# Token 消耗报告" in report
        assert "总 Token 数" in report
        assert "调用次数" in report

    def test_records_persistence(self, tmp_path):
        """Test that records persist across tracker instances."""
        tracker = TokenTracker(tmp_path)
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        # Create new tracker instance pointing to same directory
        tracker2 = TokenTracker(tmp_path)
        stats = tracker2.get_stats("all")

        assert stats.call_count == 1
        assert stats.total_tokens == 1500

    def test_load_records(self, tmp_path):
        """Test loading records from file."""
        tracker = TokenTracker(tmp_path)
        tracker.record(
            model="minimax2.7", usage={"input_tokens": 1000, "output_tokens": 500}
        )

        records = tracker._load_records()
        assert len(records) == 1
        assert records[0]["total_tokens"] == 1500

    def test_load_records_empty(self, tmp_path):
        """Test loading from non-existent file."""
        tracker = TokenTracker(tmp_path)
        records = tracker._load_records()
        assert records == []

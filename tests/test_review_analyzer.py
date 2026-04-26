"""Tests for ReviewAnalyzer."""

from agent.review import ReviewAnalyzer, ReviewResult


class TestReviewAnalyzer:
    """Test ReviewAnalyzer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.analyzer = ReviewAnalyzer()

    def test_extract_scores_simple(self):
        """Test simple score extraction."""
        output = "意图对齐: 5, 完整性: 4, 可执行性: 3, 格式合规: 5"
        scores = self.analyzer.extract_scores(output)
        assert scores["意图对齐"] == 5
        assert scores["完整性"] == 4
        assert scores["可执行性"] == 3
        assert scores["格式合规"] == 5

    def test_extract_scores_with_alias(self):
        """Test score extraction with dimension aliases."""
        output = "意图一致性: 5, 完整度: 4, 可执行: 3, 格式: 5"
        scores = self.analyzer.extract_scores(output)
        assert "意图对齐" in scores
        assert "完整性" in scores
        assert "可执行性" in scores
        assert "格式合规" in scores

    def test_extract_scores_invalid_range(self):
        """Test that scores outside 1-5 range are ignored."""
        output = "意图对齐: 6, 完整性: 0, 可执行性: 3"
        scores = self.analyzer.extract_scores(output)
        assert "意图对齐" not in scores
        assert "完整性" not in scores
        assert scores.get("可执行性") == 3

    def test_check_approval_negative_patterns(self):
        """Test negation patterns result in rejection."""
        assert self.analyzer.check_approval("not approved") is False
        assert self.analyzer.check_approval("需修改") is False
        assert self.analyzer.check_approval("需要修改") is False
        assert self.analyzer.check_approval("不通过") is False
        assert self.analyzer.check_approval("rejected") is False
        assert self.analyzer.check_approval("驳回") is False
        assert self.analyzer.check_approval("未通过") is False

    def test_check_approval_positive_patterns(self):
        """Test approval patterns result in acceptance."""
        assert self.analyzer.check_approval("评审结果：通过") is True
        assert self.analyzer.check_approval("评审：通过") is True
        assert self.analyzer.check_approval("approved") is True
        assert self.analyzer.check_approval("审核通过") is True
        assert self.analyzer.check_approval("审查通过") is True
        assert self.analyzer.check_approval("pass") is True
        assert self.analyzer.check_approval("OK") is True
        assert self.analyzer.check_approval("✓") is True

    def test_check_approval_negation_overrides(self):
        """Test that negation overrides approval."""
        # "not approved" should reject even if contains "approved"
        assert self.analyzer.check_approval("not approved") is False
        assert self.analyzer.check_approval("not fully approved") is False

    def test_check_approval_default(self):
        """Test default behavior is rejection."""
        assert self.analyzer.check_approval("random text") is False
        assert self.analyzer.check_approval("") is False

    def test_check_approval_ok_word_boundary(self):
        """Test 'ok' only matches as a whole word, not inside other words."""
        assert self.analyzer.check_approval("looks good") is False
        assert self.analyzer.check_approval("book") is False
        assert self.analyzer.check_approval("token") is False
        assert self.analyzer.check_approval("ok") is True
        assert self.analyzer.check_approval("OK") is True

    def test_check_approval_conditional_approval(self):
        """Test conditional approval (修改后通过) is rejected."""
        assert self.analyzer.check_approval("修改后通过") is False
        assert self.analyzer.check_approval("需修改后通过") is False

    def test_generate_summary_with_issues(self):
        """Test summary generation with issues."""
        issues = ["问题1", "问题2", "问题3"]
        summary = self.analyzer.generate_summary(issues)
        assert "主要问题" in summary
        assert "问题1" in summary
        assert "问题2" in summary

    def test_generate_summary_empty_issues(self):
        """Test summary generation with no issues."""
        summary = self.analyzer.generate_summary([])
        assert "整体良好" in summary

    def test_generate_summary_truncation(self):
        """Test summary truncation at max length."""
        issues = ["问题" + str(i) for i in range(20)]
        summary = self.analyzer.generate_summary(issues, max_length=100)
        assert len(summary) <= 103  # 100 + "..."

    def test_analyze_complete(self):
        """Test full analysis returns all fields."""
        output = "意图对齐: 5, 完整性: 4, 可执行性: 3, 格式合规: 5\n\n摘要: 整体较好\n\n评审结果: 通过"
        result = self.analyzer.analyze(output)

        assert isinstance(result, ReviewResult)
        assert result.approved is True
        assert result.scores["意图对齐"] == 5
        assert result.scores["完整性"] == 4
        assert result.scores["可执行性"] == 3
        assert result.scores["格式合规"] == 5
        assert result.raw_feedback == output
        assert result.summary is not None

    def test_analyze_rejection(self):
        """Test analysis of rejected review."""
        output = "意图对齐: 3, 完整性: 2, 可执行性: 3, 格式合规: 4\n\n评审结果: 需修改"
        result = self.analyzer.analyze(output)

        assert result.approved is False
        assert result.scores["完整性"] == 2

    def test_extract_existing_summary(self):
        """Test extraction of existing summary."""
        output = "意图对齐: 5\n\n摘要: 这是一个很好的文档"
        summary = self.analyzer._extract_existing_summary(output)
        assert summary == "这是一个很好的文档"

    def test_extract_issues_from_low_scores(self):
        """Test issue extraction from low scores."""
        scores = {"意图对齐": 5, "完整性": 2, "可执行性": 3, "格式合规": 5}
        issues = self.analyzer._extract_issues("", scores)
        assert any("完整性" in issue and "2" in issue for issue in issues)

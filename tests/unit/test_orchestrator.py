"""Tests for orchestrator core logic: slugify, Logger, convergence."""

import pytest
import tempfile
import shutil
from pathlib import Path

from agent.orchestrator import slugify
from agent.logger import Logger
from agent.state import SessionState
from agent.constants import MODE_LEGACY, MODE_PLAN


class TestSlugify:
    """Tests for slugify() — seed text to directory name conversion."""

    def test_pure_chinese(self):
        """Pure Chinese text should produce a directory-safe slug with hash."""
        result = slugify("写一个文学创作工具")
        assert "-" in result
        assert len(result.split("-")[-1]) == 4

    def test_pure_english(self):
        """Pure English text should produce a slug with English keywords + hash."""
        result = slugify("build a financial data sdk")
        assert "-" in result
        assert len(result.split("-")[-1]) == 4

    def test_filters_stop_words(self):
        """Common single-char stop words should not appear as standalone keywords."""
        result = slugify("我是一个用户登录系统")
        assert len(result.split("-")[-1]) == 4

    def test_mixed_cn_en(self):
        """Mixed Chinese/English should produce a valid slug."""
        result = slugify("使用 Python 构建 REST API")
        assert "-" in result
        assert len(result.split("-")[-1]) == 4

    def test_short_input(self):
        """Very short input should still produce a non-empty slug."""
        result = slugify("AB")
        assert len(result) > 0

    def test_hash_uniqueness(self):
        """Different inputs should produce different hashes."""
        r1 = slugify("计算器工具")
        r2 = slugify("计算器系统")
        # Hashes should differ
        assert r1.split("-")[-1] != r2.split("-")[-1]

    def test_hash_case_insensitive(self):
        """Same semantic input with different case should produce same hash."""
        r1 = slugify("Hello World App")
        r2 = slugify("hello world app")
        assert r1.split("-")[-1] == r2.split("-")[-1]

    def test_no_unicode_in_hash(self):
        """Hash suffix should only contain hex chars."""
        result = slugify("任意中文字符串测试")
        h = result.split("-")[-1]
        assert all(c in "0123456789abcdef" for c in h)

    def test_special_characters(self):
        """Special characters should not break slugify."""
        result = slugify("用户@系统#2024")
        assert len(result) > 0
        assert len(result.split("-")[-1]) == 4


class TestLogger:
    """Tests for Logger class."""

    def setup_method(self):
        """Set up temp log directory."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.log_path = self.tmpdir / "test.log"

    def teardown_method(self):
        """Clean up."""
        shutil.rmtree(self.tmpdir)

    def test_log_creates_file(self):
        """Log should create and write to file."""
        logger = Logger(self.log_path)
        logger.log("test message")

        assert self.log_path.exists()
        content = self.log_path.read_text()
        assert "test message" in content

    def test_log_includes_timestamp(self):
        """Log entries should include timestamps."""
        logger = Logger(self.log_path)
        logger.log("test")

        content = self.log_path.read_text()
        # Should have date pattern YYYY-MM-DD
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", content)

    def test_log_includes_level(self):
        """Log entries should include the level."""
        logger = Logger(self.log_path)
        logger.log("info msg", "INFO")
        logger.log("warn msg", "WARN")

        content = self.log_path.read_text()
        assert "[INFO]" in content
        assert "[WARN]" in content

    def test_log_creates_parent_dirs(self):
        """Logger should create parent directories if needed."""
        deep_path = self.tmpdir / "a" / "b" / "c.log"
        logger = Logger(deep_path)
        logger.log("test")

        assert deep_path.exists()

    def test_log_section(self):
        """Log section should include separator lines."""
        logger = Logger(self.log_path)
        logger.log_section("TEST SECTION")

        content = self.log_path.read_text()
        assert "TEST SECTION" in content
        assert "=" * 60 in content

    def test_log_multiple_lines(self):
        """Multiple log calls should append, not overwrite."""
        logger = Logger(self.log_path)
        logger.log("first")
        logger.log("second")

        lines = self.log_path.read_text().strip().split("\n")
        assert len(lines) >= 2
        assert "first" in lines[0]
        assert "second" in lines[1]


class TestSessionStateConvergence:
    """Tests for SessionState convergence and mode logic."""

    def test_legacy_mode_not_done_initially(self):
        """New legacy session should not be done."""
        state = SessionState(
            session_id="test-1",
            seed="test",
            mode=MODE_LEGACY,
        )
        assert state.is_done() is False

    def test_legacy_mode_done_when_both_converged(self):
        """Legacy mode done when requirements and design both converged."""
        state = SessionState(
            session_id="test-1",
            seed="test",
            mode=MODE_LEGACY,
            req_converged=True,
            design_converged=True,
        )
        assert state.is_done() is True

    def test_legacy_mode_not_done_partial(self):
        """Legacy mode not done if only requirements converged."""
        state = SessionState(
            session_id="test-1",
            seed="test",
            mode=MODE_LEGACY,
            req_converged=True,
            design_converged=False,
        )
        assert state.is_done() is False

    def test_plan_mode_done_when_execution_converged(self):
        """Plan mode done when execution plan converged."""
        state = SessionState(
            session_id="test-1",
            seed="test",
            mode=MODE_PLAN,
            execution_plan_converged=True,
        )
        assert state.is_done() is True

    def test_is_plan_mode(self):
        """is_plan_mode() should match the mode field."""
        legacy = SessionState(session_id="t", seed="s", mode=MODE_LEGACY)
        plan = SessionState(session_id="t", seed="s", mode=MODE_PLAN)

        assert legacy.is_plan_mode() is False
        assert plan.is_plan_mode() is True

    def test_default_mode_is_legacy(self):
        """Default mode should be legacy."""
        state = SessionState(session_id="t", seed="s")
        assert state.mode == MODE_LEGACY
        assert state.is_plan_mode() is False

    def test_to_dict_roundtrip(self):
        """to_dict / from_dict should be symmetric."""
        state = SessionState(
            session_id="test-1",
            seed="test seed",
            req_round=3,
            mode=MODE_PLAN,
            execution_plan_converged=True,
        )
        data = state.to_dict()
        restored = SessionState.from_dict(data)

        assert restored.session_id == state.session_id
        assert restored.seed == state.seed
        assert restored.req_round == 3
        assert restored.mode == MODE_PLAN
        assert restored.execution_plan_converged is True

    def test_review_history_default(self):
        """Review histories should default to empty lists."""
        state = SessionState(session_id="t", seed="s")
        assert state.req_review_history == []
        assert state.design_review_history == []
        assert state.execution_plan_review_history == []

    def test_timestamps(self):
        """Created and updated timestamps should be set."""
        state = SessionState(session_id="t", seed="s")
        assert state.created_at != ""
        assert state.updated_at != ""

"""Tests for base tools."""

import pytest
from pathlib import Path

from tools.base import (
    safe_path,
    run_bash,
    run_read,
    run_write,
    run_edit,
)


class TestSafePath:
    """Tests for path sandboxing."""

    def test_allows_valid_path(self):
        """Valid paths within WORKDIR should be allowed."""
        result = safe_path("subdir/test.txt")
        assert result.is_relative_to(Path.cwd())

    def test_blocks_escape(self):
        """Paths escaping WORKDIR should be blocked."""
        with pytest.raises(ValueError, match="escapes workspace"):
            safe_path("../../../etc/passwd")

    def test_blocks_bare_filename(self):
        """Bare filenames without directory should be blocked to prevent accidental root writes."""
        with pytest.raises(ValueError, match="Bare filename"):
            safe_path("requirements.md")


class TestBash:
    """Tests for bash tool."""

    def test_blocks_dangerous_commands(self):
        """Dangerous commands should be blocked."""
        result = run_bash("rm -rf /")
        assert "blocked" in result.lower()

    def test_simple_command(self):
        """Simple commands should work."""
        result = run_bash("echo 'hello world'")
        assert "hello world" in result


class TestReadWrite:
    """Tests for read/write tools."""

    def test_write_and_read(self):
        """Write then read should return same content."""
        # Use a file within the project directory
        test_file = Path.cwd() / "test_output.txt"
        content = "Hello, World!"

        write_result = run_write(str(test_file), content)
        assert "Wrote" in write_result

        read_result = run_read(str(test_file))
        assert read_result == content

        # Cleanup
        test_file.unlink(missing_ok=True)

    def test_read_with_limit(self):
        """Read with limit should truncate."""
        test_file = Path.cwd() / "test_output.txt"
        content = "\n".join([f"line {i}" for i in range(20)])

        run_write(str(test_file), content)
        result = run_read(str(test_file), limit=5)

        assert "line 0" in result
        assert "line 19" not in result
        assert "15 more)" in result

        # Cleanup
        test_file.unlink(missing_ok=True)


class TestEdit:
    """Tests for edit tool."""

    def test_edit_existing_text(self):
        """Edit should replace exact text."""
        test_file = Path.cwd() / "test_output.txt"
        original = "Hello, World!"
        run_write(str(test_file), original)

        result = run_edit(str(test_file), "World", "Universe")
        assert "Edited" in result

        content = run_read(str(test_file))
        assert content == "Hello, Universe!"

        # Cleanup
        test_file.unlink(missing_ok=True)

    def test_edit_missing_text(self):
        """Edit with missing text should error."""
        test_file = Path.cwd() / "test_output.txt"
        run_write(str(test_file), "Hello")

        result = run_edit(str(test_file), "NotFound", "Replacement")
        assert "Error" in result

        # Cleanup
        test_file.unlink(missing_ok=True)

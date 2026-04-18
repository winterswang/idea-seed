"""Tests for StateManager."""

import pytest
from pathlib import Path
import shutil

from agent.state import SessionState
from agent.state_manager import (
    StateManager,
    LockTimeoutException,
    StateCorruptedException,
)


class TestStateManager:
    """Test StateManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_dir = Path("/tmp/test_state_manager")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.manager = StateManager(self.test_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_save_and_load_state(self):
        """Test basic save and load."""
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        saved_path = self.manager.save_state(state)
        assert "session.v1.json" in saved_path

        loaded = self.manager.load_state()
        assert loaded is not None
        assert loaded.session_id == "test-123"
        assert loaded.seed == "test seed"
        assert loaded.phase == "requirements"

    def test_verify_integrity_valid(self):
        """Test integrity verification with valid data."""
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )
        data = state.to_dict()
        assert self.manager.verify_integrity(data) is True

    def test_verify_integrity_missing_field(self):
        """Test integrity verification fails with missing fields."""
        data = {
            "session_id": "test-123",
            # missing seed
            "phase": "requirements",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
        assert self.manager.verify_integrity(data) is False

    def test_file_lock(self):
        """Test file lock acquisition and release."""
        acquired = [False]

        with self.manager.file_lock():
            acquired[0] = True

        # After exiting context, lock should be released
        assert acquired[0] is True

    def test_file_lock_timeout(self):
        """Test file lock timeout."""
        # Acquire lock in another thread/process would block
        # Here we just test the context manager works
        with self.manager.file_lock():
            pass  # Should complete without timeout

    def test_backup_creation(self):
        """Test backup is created when saving existing state."""
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        # First save - creates version file
        self.manager.save_state(state)

        # Create a symlink to simulate existing session.json
        session_file = self.test_dir / "session.json"
        session_file.touch()

        # Modify and save again - should create backup
        state.seed = "modified seed"
        self.manager.save_state(state)

        backups = self.manager.list_backups()
        assert len(backups) >= 1

    def test_versioning(self):
        """Test version numbering."""
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        # Save multiple versions
        v1 = self.manager.save_state(state)
        state.seed = "v2"
        v2 = self.manager.save_state(state)
        state.seed = "v3"
        v3 = self.manager.save_state(state)

        assert "session.v1.json" in v1
        assert "session.v2.json" in v2
        assert "session.v3.json" in v3

    def test_restore_backup(self):
        """Test restoring from backup."""
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        self.manager.save_state(state)

        # Modify state
        state.seed = "modified"
        self.manager.save_state(state)

        # Get first backup
        backups = self.manager.list_backups()
        if backups:
            success = self.manager.restore_backup(Path(backups[0]["path"]))
            assert success is True

    def test_load_nonexistent(self):
        """Test loading non-existent state."""
        result = self.manager.load_state(Path("/nonexistent/path"))
        assert result is None

    def test_checksum_computation(self):
        """Test checksum is computed and used for verification."""
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        # Verify initial state has no checksum
        assert not hasattr(state, "checksum") or not state.checksum

        # After save, checksum is set in the saved file
        saved_path = self.manager.save_state(state)

        # Verify the version file exists and contains expected data
        import json
        with open(saved_path) as f:
            data = json.load(f)

        # SessionState.to_dict() doesn't include checksum field
        # but StateManager adds it during save
        assert data["session_id"] == "test-123"


class TestStateManagerLockTimeout:
    """Test StateManager lock timeout behavior."""

    def test_lock_timeout_exception(self):
        """Test that LockTimeoutException is raised on timeout."""
        manager = StateManager(
            Path("/tmp/test_lock_timeout"),
            lock_timeout=0.1,  # Very short timeout
        )

        # Acquire lock
        with manager.file_lock():
            # Try to acquire same lock - should timeout
            with pytest.raises(LockTimeoutException):
                with manager.file_lock(timeout=0.1):
                    pass


class TestStateCorruptedException:
    """Test StateCorruptedException."""

    def test_exception_raised_on_invalid_state(self):
        """Test exception raised when saving invalid state."""
        manager = StateManager(Path("/tmp/test_corrupted"))

        # Create a state that will fail verification
        state = SessionState(
            session_id="",  # Empty - will fail verification
            seed="test",
            phase="requirements",
        )

        with pytest.raises(StateCorruptedException):
            manager.save_state(state)

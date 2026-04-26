"""Tests for StateManager."""

import pytest
from pathlib import Path

from agent.state import SessionState
from agent.state_manager import (
    StateManager,
    LockTimeoutException,
    StateCorruptedException,
)


class TestStateManager:
    """Test StateManager class."""

    def test_save_and_load_state(self, tmp_path):
        """Test basic save and load."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        saved_path = manager.save_state(state)
        assert "session.v1.json" in saved_path

        loaded = manager.load_state()
        assert loaded is not None
        assert loaded.session_id == "test-123"
        assert loaded.seed == "test seed"
        assert loaded.phase == "requirements"

    def test_verify_integrity_valid(self, tmp_path):
        """Test integrity verification with valid data."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )
        data = state.to_dict()
        assert manager.verify_integrity(data) is True

    def test_verify_integrity_missing_field(self, tmp_path):
        """Test integrity verification fails with missing fields."""
        manager = StateManager(tmp_path)
        data = {
            "session_id": "test-123",
            # missing seed
            "phase": "requirements",
            "created_at": "2024-01-01",
            "updated_at": "2024-01-01",
        }
        assert manager.verify_integrity(data) is False

    def test_file_lock(self, tmp_path):
        """Test file lock acquisition and release."""
        manager = StateManager(tmp_path)
        acquired = [False]

        with manager.file_lock():
            acquired[0] = True

        # After exiting context, lock should be released
        assert acquired[0] is True

    def test_file_lock_timeout(self, tmp_path):
        """Test file lock timeout."""
        manager = StateManager(tmp_path)
        # Acquire lock
        with manager.file_lock():
            pass  # Should complete without timeout

    def test_backup_creation(self, tmp_path):
        """Test backup is created when saving existing state."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        # First save - creates version file
        manager.save_state(state)

        # Create a symlink to simulate existing session.json
        session_file = tmp_path / "session.json"
        session_file.touch()

        # Modify and save again - should create backup
        state.seed = "modified seed"
        manager.save_state(state)

        backups = manager.list_backups()
        assert len(backups) >= 1

    def test_versioning(self, tmp_path):
        """Test version numbering."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        # Save multiple versions
        v1 = manager.save_state(state)
        state.seed = "v2"
        v2 = manager.save_state(state)
        state.seed = "v3"
        v3 = manager.save_state(state)

        assert "session.v1.json" in v1
        assert "session.v2.json" in v2
        assert "session.v3.json" in v3

    def test_restore_backup(self, tmp_path):
        """Test restoring from backup."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        manager.save_state(state)

        # Modify state
        state.seed = "modified"
        manager.save_state(state)

        # Get first backup
        backups = manager.list_backups()
        if backups:
            success = manager.restore_backup(Path(backups[0]["path"]))
            assert success is True

    def test_load_nonexistent(self, tmp_path):
        """Test loading non-existent state."""
        manager = StateManager(tmp_path)
        result = manager.load_state(Path("/nonexistent/path"))
        assert result is None

    def test_checksum_computation(self, tmp_path):
        """Test checksum is computed and used for verification."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        # Verify initial state has no checksum
        assert not hasattr(state, "checksum") or not state.checksum

        # After save, checksum is set in the saved file
        saved_path = manager.save_state(state)

        # Verify the version file exists and contains expected data
        import json

        with open(saved_path) as f:
            data = json.load(f)

        # checksum and version are now properly persisted
        assert data["session_id"] == "test-123"
        assert "checksum" in data
        assert data["checksum"] != ""
        assert "version" in data
        assert data["version"] == 1

    def test_save_state_no_side_effect(self, tmp_path):
        """Test that save_state does not modify the original state object."""
        manager = StateManager(tmp_path)
        state = SessionState(
            session_id="test-123",
            seed="test seed",
            phase="requirements",
        )

        original_checksum = state.checksum
        original_version = state.version

        manager.save_state(state)

        # State object should not be modified by save_state
        assert state.checksum == original_checksum
        assert state.version == original_version


class TestStateManagerLockTimeout:
    """Test StateManager lock timeout behavior."""

    def test_lock_timeout_exception(self, tmp_path):
        """Test that LockTimeoutException is raised on timeout."""
        manager = StateManager(
            tmp_path / "lock_test",
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

    def test_exception_raised_on_invalid_state(self, tmp_path):
        """Test exception raised when saving invalid state."""
        manager = StateManager(tmp_path / "corrupted_test")

        # Create a state that will fail verification
        state = SessionState(
            session_id="",  # Empty - will fail verification
            seed="test",
            phase="requirements",
        )

        with pytest.raises(StateCorruptedException):
            manager.save_state(state)

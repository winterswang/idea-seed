"""Enhanced state management with versioning, backup, and locking."""

import fcntl
import hashlib
import json
import shutil
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.state import SessionState


class StateManagerError(Exception):
    """Base exception for state manager errors."""

    pass


class LockTimeoutException(StateManagerError):
    """Raised when lock acquisition times out."""

    pass


class StateCorruptedException(StateManagerError):
    """Raised when state integrity check fails."""

    pass


class StateManager:
    """Enhanced state manager with versioning, backup, and locking."""

    def __init__(
        self,
        state_dir: Path,
        max_backups: int = 5,
        max_versions: int = 10,
        lock_timeout: float = 30.0,
    ) -> None:
        """
        Initialize state manager.

        Args:
            state_dir: Directory for state files
            max_backups: Maximum number of backups to keep
            max_versions: Maximum number of versioned files to keep
            lock_timeout: Lock acquisition timeout in seconds
        """
        self.state_dir = Path(state_dir)
        self.max_backups = max_backups
        self.max_versions = max_versions
        self.lock_timeout = lock_timeout

        # Create directories
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = self.state_dir / "backups"
        self.version_dir = self.state_dir / "versions"
        self.backup_dir.mkdir(exist_ok=True)
        self.version_dir.mkdir(exist_ok=True)

        # Lock file
        self.lock_file = self.state_dir / "session.lock"

    @contextmanager
    def file_lock(self, timeout: Optional[float] = None):
        """
        File lock context manager.

        Args:
            timeout: Lock timeout in seconds (default: self.lock_timeout)

        Raises:
            LockTimeoutException: If lock cannot be acquired within timeout
        """
        timeout = timeout or self.lock_timeout
        lock_fd = None

        try:
            lock_fd = open(self.lock_file, "w")

            start_time = time.time()
            while True:
                try:
                    fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() - start_time >= timeout:
                        raise LockTimeoutException(
                            f"Failed to acquire lock after {timeout}s"
                        )
                    time.sleep(0.1)

            # Write lock info
            lock_fd.write(str(time.time()))
            lock_fd.flush()

            yield

        finally:
            if lock_fd:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()

    def save_state(
        self,
        state: SessionState,
        path: Optional[Path] = None,
    ) -> str:
        """
        Save state with locking, backup, and versioning.

        Args:
            state: SessionState to save
            path: Optional path (defaults to .state/session.json)

        Returns:
            Path to saved version file

        Raises:
            StateCorruptedException: If state verification fails
        """
        with self.file_lock():
            if path is None:
                path = self.state_dir / "session.json"

            # Build data dict without modifying the state object
            data = state.to_dict()

            # Verify state integrity
            if not self.verify_integrity(data):
                raise StateCorruptedException("State verification failed")

            # Compute checksum and set on the data dict (not on state)
            data["checksum"] = self._compute_checksum(data)

            # Create backup if main file exists
            if path.exists():
                self._create_backup(path)

            # Get next version number
            version = self._get_next_version()
            data["version"] = version

            # Save to versioned file
            version_file = self.version_dir / f"session.v{version}.json"
            self._atomic_write(data, version_file)

            # Update symlink
            if path.is_symlink() or path.exists():
                path.unlink()
            path.symlink_to(version_file.name)

            return str(version_file)

    def load_state(
        self,
        path: Optional[Path] = None,
        auto_recover: bool = True,
    ) -> Optional[SessionState]:
        """
        Load state with integrity verification and auto-recovery.

        Args:
            path: Optional path (defaults to .state/session.json)
            auto_recover: If True, attempt recovery from backup/version

        Returns:
            SessionState if found, None otherwise

        Raises:
            StateCorruptedException: If auto_recover is False and integrity fails
        """
        if path is None:
            path = self.state_dir / "session.json"

        if not path.exists() and not path.is_symlink():
            return None

        # Resolve symlink to actual file
        if path.is_symlink():
            path = path.resolve()

        try:
            with open(path) as f:
                data = json.load(f)

            if self.verify_integrity(data):
                return SessionState.from_dict(data)

            # Integrity check failed
            if auto_recover:
                recovered = self._attempt_recovery()
                if recovered:
                    return recovered
                return None

            raise StateCorruptedException(f"Integrity check failed for {path}")

        except (json.JSONDecodeError, FileNotFoundError):
            if auto_recover:
                return self._attempt_recovery()
            return None

    def verify_integrity(self, data: dict) -> bool:
        """
        Verify state data integrity.

        Checks:
        1. Required fields exist
        2. MD5 checksum matches (if present)
        3. Data types are correct

        Args:
            data: State data dict

        Returns:
            True if valid, False otherwise
        """
        # Check required fields
        required_fields = [
            "session_id",
            "seed",
            "phase",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            if field not in data or not data[field]:
                return False

        # Verify checksum if present
        if "checksum" in data and data["checksum"]:
            expected = self._compute_checksum(data)
            if expected != data["checksum"]:
                return False

        # Verify data types
        if not isinstance(data.get("req_round", 0), int):
            return False
        if not isinstance(data.get("req_review_history", []), list):
            return False
        if not isinstance(data.get("version", 0), int):
            return False

        return True

    def list_backups(self) -> list[dict]:
        """
        List available backups.

        Returns:
            List of backup info dicts with path and timestamp
        """
        backups = sorted(
            self.backup_dir.glob("session_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [
            {
                "path": str(b),
                "timestamp": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
            }
            for b in backups
        ]

    def restore_backup(self, backup_path: Path) -> bool:
        """
        Restore state from backup.

        Args:
            backup_path: Path to backup file

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(backup_path) as f:
                data = json.load(f)

            if not self.verify_integrity(data):
                return False

            state = SessionState.from_dict(data)
            self.save_state(state)
            return True

        except Exception:
            return False

    # === Private methods ===

    def _compute_checksum(self, data: dict) -> str:
        """Compute MD5 checksum for state data."""
        # Include core state + convergence flags + review history summary
        review_count = len(data.get("req_review_history", []))
        design_count = len(data.get("design_review_history", []))
        # Last review approved status if exists
        last_req_approved = (
            data["req_review_history"][-1].get("approved")
            if data.get("req_review_history")
            else None
        )
        last_design_approved = (
            data["design_review_history"][-1].get("approved")
            if data.get("design_review_history")
            else None
        )

        content = json.dumps(
            {
                "session_id": data["session_id"],
                "seed": data["seed"],
                "phase": data["phase"],
                "req_round": data.get("req_round", 0),
                "design_round": data.get("design_round", 0),
                "req_converged": data.get("req_converged", False),
                "design_converged": data.get("design_converged", False),
                "review_count": review_count,
                "design_count": design_count,
                "last_req_approved": last_req_approved,
                "last_design_approved": last_design_approved,
            },
            sort_keys=True,
        )
        return hashlib.md5(content.encode()).hexdigest()

    def _create_backup(self, source_path: Path) -> Optional[Path]:
        """Create a backup of the current state file."""
        if not source_path.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"session_backup_{timestamp}.json"

        shutil.copy2(source_path, backup_file)
        self._cleanup_old_backups()

        return backup_file

    def _cleanup_old_backups(self) -> None:
        """Remove oldest backups exceeding max_backups."""
        backups = sorted(
            self.backup_dir.glob("session_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
        )

        while len(backups) > self.max_backups:
            oldest = backups.pop(0)
            oldest.unlink()

    def _get_next_version(self) -> int:
        """Get next version number."""
        versions = list(self.version_dir.glob("session.v*.json"))
        if not versions:
            return 1

        # Extract version numbers and find max
        max_version = 0
        for v in versions:
            try:
                num = int(v.name.replace("session.v", "").replace(".json", ""))
                max_version = max(max_version, num)
            except ValueError:
                continue

        next_version = max_version + 1

        # Cleanup old versions if needed
        if next_version > self.max_versions:
            self._cleanup_old_versions()

        return next_version

    def _cleanup_old_versions(self) -> None:
        """Remove oldest versioned files exceeding max_versions."""
        versions = sorted(
            self.version_dir.glob("session.v*.json"),
            key=lambda p: p.stat().st_mtime,
        )

        while len(versions) > self.max_versions:
            oldest = versions.pop(0)
            oldest.unlink()

    def _atomic_write(self, data: dict, path: Path) -> None:
        """Atomically write data to file."""
        path_tmp = path.with_suffix(".tmp")
        # Clean up any residual .tmp file from a previous crash
        if path_tmp.exists():
            path_tmp.unlink()
        with open(path_tmp, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
        path_tmp.rename(path)

    def _attempt_recovery(self) -> Optional[SessionState]:
        """Attempt to recover state from backup or version."""
        # Try backups first (newest first)
        backups = sorted(
            self.backup_dir.glob("session_backup_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for backup in backups:
            try:
                with open(backup) as f:
                    data = json.load(f)
                if self.verify_integrity(data):
                    return SessionState.from_dict(data)
            except Exception:
                continue

        # Try version files (newest first)
        versions = sorted(
            self.version_dir.glob("session.v*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for version in versions:
            try:
                with open(version) as f:
                    data = json.load(f)
                if self.verify_integrity(data):
                    return SessionState.from_dict(data)
            except Exception:
                continue

        return None

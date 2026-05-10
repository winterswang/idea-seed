"""Session state persistence."""

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime

from agent.config import STATE_DIR
from agent.constants import (
    PHASE_REQUIREMENTS,
    SESSION_STATE_FILE,
    MODE_LEGACY,
    MODE_PLAN,
)

# Current state schema version (increment when adding/removing fields)
STATE_CURRENT_VERSION = 2


@dataclass
class SessionState:
    """Session state for iterative document building."""

    session_id: str
    seed: str
    phase: str = PHASE_REQUIREMENTS
    req_round: int = 0
    design_round: int = 0
    requirements_md5: str = ""
    tech_design_md5: str = ""
    req_review_history: list = None
    design_review_history: list = None
    req_converged: bool = False
    design_converged: bool = False
    checksum: str = ""
    version: int = 0
    created_at: str = ""
    updated_at: str = ""

    # V2 fields (for execution plan mode)
    mode: str = MODE_LEGACY
    execution_plan_md5: str = ""
    execution_plan_round: int = 0
    execution_plan_review_history: list = None
    execution_plan_converged: bool = False
    tasks: list = None
    checkpoints: list = None
    current_task_index: int = 0
    execution_summary: dict = None

    def __post_init__(self) -> None:
        if self.req_review_history is None:
            self.req_review_history = []
        if self.design_review_history is None:
            self.design_review_history = []
        if self.execution_plan_review_history is None:
            self.execution_plan_review_history = []
        if self.tasks is None:
            self.tasks = []
        if self.checkpoints is None:
            self.checkpoints = []
        if self.execution_summary is None:
            self.execution_summary = {}
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def is_done(self) -> bool:
        """Check if entire process is done."""
        if self.mode == MODE_LEGACY:
            return self.req_converged and self.design_converged
        else:
            return self.execution_plan_converged

    def is_plan_mode(self) -> bool:
        """Check if running in plan mode."""
        return self.mode == MODE_PLAN

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d["version"] = STATE_CURRENT_VERSION
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """Create from dict loaded from JSON."""
        data = _migrate_state(data)
        return cls(**data)


def _migrate_state(data: dict) -> dict:
    """Migrate state data from older versions to current version.

    Handles v0/v1 → v2: adds missing fields with defaults.
    """
    version = data.get("version", 0)
    if version >= STATE_CURRENT_VERSION:
        return data
    defaults = {
        "execution_plan_md5": "",
        "execution_plan_round": 0,
        "execution_plan_review_history": [],
        "execution_plan_converged": False,
        "tasks": [],
        "checkpoints": [],
        "current_task_index": 0,
        "execution_summary": {},
        "mode": "legacy",
    }
    for key, val in defaults.items():
        data.setdefault(key, val)
    data["version"] = STATE_CURRENT_VERSION
    return data


def save_state(state: SessionState, path: Path | None = None) -> str:
    """Save session state to JSON file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if path is None:
        path = STATE_DIR / SESSION_STATE_FILE
    state.updated_at = datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(state.to_dict(), f, indent=2)
    return f"State saved to {path}"


def load_state(path: Path | None = None) -> SessionState | None:
    """Load session state from JSON file."""
    if path is None:
        path = STATE_DIR / SESSION_STATE_FILE
    if not path.exists():
        return None
    with open(path, "r") as f:
        data = json.load(f)
    return SessionState.from_dict(data)


def state_exists(path: Path | None = None) -> bool:
    """Check if state file exists."""
    if path is None:
        path = STATE_DIR / SESSION_STATE_FILE
    return path.exists()

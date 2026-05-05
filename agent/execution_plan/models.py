"""Data models for execution plan."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class TaskStatus(Enum):
    """Task execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFICATION_FAILED = "verification_failed"
    BLOCKED = "blocked"


class VerificationType(Enum):
    """Type of verification for task/checkpoint."""

    COMMAND_EXECUTION = "command_execution"
    FILE_EXISTENCE = "file_existence"
    COVERAGE_CHECK = "coverage_check"
    MANUAL = "manual"
    PHASE_COMPLETION = "phase_completion"


class CheckpointStatus(Enum):
    """Checkpoint verification status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Execution task within a phase."""

    id: str
    name: str
    description: str
    phase: str
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0
    depends_on: list[str] = field(default_factory=list)
    verification_type: VerificationType = VerificationType.MANUAL
    verification_config: dict = field(default_factory=dict)
    executor: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    verification_result: dict = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "phase": self.phase,
            "status": self.status.value,
            "priority": self.priority,
            "depends_on": self.depends_on,
            "verification_type": self.verification_type.value,
            "verification_config": self.verification_config,
            "executor": self.executor,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "verification_result": self.verification_result,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Create from dict."""
        data = data.copy()
        data["status"] = TaskStatus(data.get("status", "pending"))
        data["verification_type"] = VerificationType(
            data.get("verification_type", "manual")
        )
        return cls(**data)


@dataclass
class Checkpoint:
    """Verification checkpoint for a phase."""

    id: str
    name: str
    description: str
    task_ids: list[str] = field(default_factory=list)
    status: CheckpointStatus = CheckpointStatus.PENDING
    verification_type: VerificationType = VerificationType.COVERAGE_CHECK
    verification_config: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    created_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_ids": self.task_ids,
            "status": self.status.value,
            "verification_type": self.verification_type.value,
            "verification_config": self.verification_config,
            "output": self.output,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        """Create from dict."""
        data = data.copy()
        data["status"] = CheckpointStatus(data.get("status", "pending"))
        data["verification_type"] = VerificationType(
            data.get("verification_type", "coverage_check")
        )
        return cls(**data)


@dataclass
class VerificationResult:
    """Result of a verification operation."""

    passed: bool
    verification_type: VerificationType
    details: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    coverage_percentage: float = 0.0
    consistency_check: dict = field(default_factory=dict)
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "passed": self.passed,
            "verification_type": self.verification_type.value,
            "details": self.details,
            "errors": self.errors,
            "warnings": self.warnings,
            "coverage_percentage": self.coverage_percentage,
            "consistency_check": self.consistency_check,
            "timestamp": self.timestamp,
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan for a project."""

    metadata: dict = field(default_factory=dict)
    phases: list = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    total_tasks: int = 0
    estimated_duration: str = ""
    executability_score: float = 0.0
    verification_coverage: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "metadata": self.metadata,
            "phases": self.phases,
            "tasks": [t.to_dict() if isinstance(t, Task) else t for t in self.tasks],
            "checkpoints": [
                c.to_dict() if isinstance(c, Checkpoint) else c
                for c in self.checkpoints
            ],
            "total_tasks": self.total_tasks,
            "estimated_duration": self.estimated_duration,
            "executability_score": self.executability_score,
            "verification_coverage": self.verification_coverage,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionPlan":
        """Create from dict."""
        tasks = [
            Task.from_dict(t) if isinstance(t, dict) else t
            for t in data.get("tasks", [])
        ]
        checkpoints = [
            Checkpoint.from_dict(c) if isinstance(c, dict) else c
            for c in data.get("checkpoints", [])
        ]
        data["tasks"] = tasks
        data["checkpoints"] = checkpoints
        return cls(**data)


@dataclass
class Phase:
    """Execution phase containing tasks."""

    id: str
    name: str
    description: str
    order: int = 0
    task_ids: list[str] = field(default_factory=list)
    checkpoint_id: Optional[str] = None
    status: str = "pending"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "order": self.order,
            "task_ids": self.task_ids,
            "checkpoint_id": self.checkpoint_id,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Phase":
        """Create from dict."""
        return cls(**data)

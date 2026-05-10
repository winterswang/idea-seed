"""Plan data structures for v2 iterative project management."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class PlanStage(Enum):
    """Stage of a plan within its lifecycle."""
    DEV = "dev"
    TEST = "test"
    RELEASE = "release"
    BLOCKED = "blocked"


class PlanStatus(Enum):
    """Status of a plan's execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Priority(Enum):
    """Plan priority."""
    P0 = "P0"  # Critical, must do first
    P1 = "P1"  # High priority
    P2 = "P2"  # Medium priority
    P3 = "P3"  # Low priority


@dataclass
class PlanHistoryEntry:
    """Single entry in plan history."""
    timestamp: str
    action: str  # e.g., "created", "stage_changed", "status_changed", "updated"
    details: Optional[str] = None


@dataclass
class Plan:
    """Represents a single plan within a project.

    A plan is the core unit of work in v2. Each plan is independently
    iterated and tracked through its lifecycle.

    Attributes:
        plan_id: Unique identifier (e.g., "plan-001")
        feature: Brief feature description
        priority: Plan priority (P0-P3)
        stage: Current stage (dev/test/release/blocked)
        status: Current status (pending/in_progress/done/blocked)
        depends_on: List of plan_ids this plan depends on
        blocks: List of plan_ids this plan blocks
        history: List of history entries
        summary: Brief summary for context compression
        tech_spec_path: Path to this plan's tech spec document
    """
    plan_id: str
    feature: str
    priority: Priority = Priority.P1
    stage: PlanStage = PlanStage.DEV
    status: PlanStatus = PlanStatus.PENDING
    depends_on: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)
    history: list[PlanHistoryEntry] = field(default_factory=list)
    summary: str = ""
    tech_spec_path: Optional[str] = None

    def __post_init__(self):
        """Validate plan data after initialization."""
        if not self.plan_id:
            raise ValueError("plan_id cannot be empty")
        if not self.feature:
            raise ValueError("feature cannot be empty")

    @classmethod
    def create(cls, feature: str, priority: Priority = Priority.P1,
               plan_id: Optional[str] = None) -> "Plan":
        """Create a new plan with auto-generated ID.

        Args:
            feature: Brief feature description
            priority: Plan priority
            plan_id: Optional explicit plan_id, auto-generated if not provided

        Returns:
            New Plan instance with history entry
        """
        import datetime

        if plan_id is None:
            plan_id = f"plan-{uuid.uuid4().hex[:8]}"

        plan = cls(
            plan_id=plan_id,
            feature=feature,
            priority=priority,
            history=[
                PlanHistoryEntry(
                    timestamp=datetime.datetime.now().isoformat(),
                    action="created",
                    details=f"Plan created with priority {priority.value}"
                )
            ]
        )
        return plan

    def to_dict(self) -> dict:
        """Serialize plan to dictionary.

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "plan_id": self.plan_id,
            "feature": self.feature,
            "priority": self.priority.value,
            "stage": self.stage.value,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "history": [
                {
                    "timestamp": h.timestamp,
                    "action": h.action,
                    "details": h.details
                }
                for h in self.history
            ],
            "summary": self.summary,
            "tech_spec_path": self.tech_spec_path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Plan":
        """Deserialize plan from dictionary.

        Args:
            data: Dictionary representation of plan

        Returns:
            Plan instance
        """
        history = [
            PlanHistoryEntry(
                timestamp=h["timestamp"],
                action=h["action"],
                details=h.get("details")
            )
            for h in data.get("history", [])
        ]

        return cls(
            plan_id=data["plan_id"],
            feature=data["feature"],
            priority=Priority(data.get("priority", "P1")),
            stage=PlanStage(data.get("stage", "dev")),
            status=PlanStatus(data.get("status", "pending")),
            depends_on=data.get("depends_on", []),
            blocks=data.get("blocks", []),
            history=history,
            summary=data.get("summary", ""),
            tech_spec_path=data.get("tech_spec_path"),
        )

    def add_history_entry(self, action: str, details: Optional[str] = None) -> None:
        """Add an entry to plan history.

        Args:
            action: Action performed (e.g., "stage_changed")
            details: Optional details about the action
        """
        import datetime
        self.history.append(PlanHistoryEntry(
            timestamp=datetime.datetime.now().isoformat(),
            action=action,
            details=details
        ))

    def update_stage(self, new_stage: PlanStage) -> None:
        """Update plan stage.

        Args:
            new_stage: New stage value
        """
        old_stage = self.stage.value
        self.stage = new_stage
        self.add_history_entry(
            "stage_changed",
            f"Changed from {old_stage} to {new_stage.value}"
        )

    def update_status(self, new_status: PlanStatus) -> None:
        """Update plan status.

        Args:
            new_status: New status value
        """
        old_status = self.status.value
        self.status = new_status
        self.add_history_entry(
            "status_changed",
            f"Changed from {old_status} to {new_status.value}"
        )

    def is_blocked_by(self, plan_id: str) -> bool:
        """Check if this plan is blocked by another plan.

        Args:
            plan_id: ID of potential blocker plan

        Returns:
            True if blocked by the specified plan
        """
        return plan_id in self.depends_on

    def __repr__(self) -> str:
        return (
            f"Plan(id={self.plan_id}, feature={self.feature!r}, "
            f"stage={self.stage.value}, status={self.status.value})"
        )
"""Incremental updater for execution plans."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, NamedTuple

if TYPE_CHECKING:
    from agent.orchestrator import Orchestrator

from agent.execution_plan.models import ExecutionPlan, TaskStatus


class ChangeImpact(NamedTuple):
    """Describes the impact of a change on the execution plan."""

    tasks_affected: list[str]
    phases_affected: list[str]
    checkpoints_affected: list[str]
    needs_full_regeneration: bool
    change_summary: str


class IncrementalUpdater:
    """Handles incremental updates to execution plans."""

    def __init__(self, orchestrator: "Orchestrator") -> None:
        """Initialize with orchestrator reference."""
        self.orchestrator = orchestrator

    def update_if_needed(
        self,
        new_requirements_md5: str,
        current_plan: ExecutionPlan,
    ) -> tuple[bool, Optional[ExecutionPlan]]:
        """
        Check if plan needs update and perform incremental update.

        Args:
            new_requirements_md5: MD5 of new requirements
            current_plan: Current execution plan

        Returns:
            Tuple of (needs_update, updated_plan or None)
        """
        old_md5 = self.orchestrator.state.requirements_md5

        if new_requirements_md5 == old_md5:
            return False, None

        # Detect changes and assess impact
        impact = self._assess_impact(current_plan)

        if impact.needs_full_regeneration:
            # Full regeneration needed - return True to trigger regeneration
            return True, None

        # Apply incremental changes
        updated_plan = self._apply_incremental_changes(current_plan, impact)

        return True, updated_plan

    def _assess_impact(self, current_plan: ExecutionPlan) -> ChangeImpact:
        """Assess the impact of requirements changes on current plan."""
        # In a full implementation, this would compare old vs new requirements
        # For now, return a conservative estimate

        # Check if any tasks are in progress
        in_progress_tasks = [
            t.id
            for t in current_plan.tasks
            if t.status.value in ("in_progress", "pending")
        ]

        if not in_progress_tasks:
            # No active work, full regeneration is safe
            return ChangeImpact(
                tasks_affected=[],
                phases_affected=[],
                checkpoints_affected=[],
                needs_full_regeneration=True,
                change_summary="No active tasks, safe to regenerate",
            )

        # Some tasks are in progress - assess impact
        return ChangeImpact(
            tasks_affected=in_progress_tasks[:5],  # First 5 affected tasks
            phases_affected=[],
            checkpoints_affected=[],
            needs_full_regeneration=False,
            change_summary=f"{len(in_progress_tasks)} tasks in progress, incremental update recommended",
        )

    def _apply_incremental_changes(
        self,
        current_plan: ExecutionPlan,
        impact: ChangeImpact,
    ) -> ExecutionPlan:
        """Apply incremental changes to the plan."""
        # Create a deep copy with modifications
        import copy

        updated_plan = copy.deepcopy(current_plan)

        # Update metadata to track changes
        updated_plan.metadata["last_incremental_update"] = self._get_timestamp()
        updated_plan.metadata["tasks_affected"] = impact.tasks_affected

        # Mark affected tasks for review
        for task in updated_plan.tasks:
            if task.id in impact.tasks_affected:
                # Reset status if task needs review due to changes
                if task.status == TaskStatus.COMPLETED:
                    task.status = TaskStatus.PENDING
                    task.verification_result = {}

        return updated_plan

    def _get_timestamp(self) -> str:
        """Get current timestamp."""
        from datetime import datetime

        return datetime.now().isoformat()

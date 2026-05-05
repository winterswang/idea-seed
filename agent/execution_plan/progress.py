"""Progress manager for tracking execution plan progress."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, NamedTuple

if TYPE_CHECKING:
    from agent.orchestrator import Orchestrator

from agent.execution_plan.models import ExecutionPlan, TaskStatus


class ProgressSummary(NamedTuple):
    """Summary of execution plan progress."""

    total_tasks: int
    completed_tasks: int
    in_progress_tasks: int
    pending_tasks: int
    blocked_tasks: int
    failed_tasks: int
    progress_percentage: float
    verification_coverage: float
    current_phase: Optional[str]


class ProgressManager:
    """Tracks and reports execution plan progress."""

    def __init__(self, orchestrator: "Orchestrator") -> None:
        """Initialize with orchestrator reference."""
        self.orchestrator = orchestrator

    def get_execution_summary(self, plan: ExecutionPlan) -> ProgressSummary:
        """
        Get a summary of execution progress.

        Args:
            plan: ExecutionPlan to track

        Returns:
            ProgressSummary with current state
        """
        total = len(plan.tasks)

        if total == 0:
            return ProgressSummary(
                total_tasks=0,
                completed_tasks=0,
                in_progress_tasks=0,
                pending_tasks=0,
                blocked_tasks=0,
                failed_tasks=0,
                progress_percentage=0.0,
                verification_coverage=0.0,
                current_phase=None,
            )

        status_counts = {
            "completed": 0,
            "in_progress": 0,
            "pending": 0,
            "blocked": 0,
            "verification_failed": 0,
        }

        for task in plan.tasks:
            status = task.status.value if hasattr(task.status, "value") else task.status
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts["pending"] += 1

        # Calculate progress
        completed = status_counts["completed"]
        progress_pct = (completed / total) * 100 if total > 0 else 0.0

        # Find current phase
        current_phase = None
        for phase in plan.phases:
            # Check if any task in this phase is in progress
            phase_tasks = [t for t in plan.tasks if t.phase == phase.id]
            if any(t.status == TaskStatus.IN_PROGRESS for t in phase_tasks):
                current_phase = phase.id
                break

        return ProgressSummary(
            total_tasks=total,
            completed_tasks=completed,
            in_progress_tasks=status_counts["in_progress"],
            pending_tasks=status_counts["pending"],
            blocked_tasks=status_counts["blocked"],
            failed_tasks=status_counts["verification_failed"],
            progress_percentage=progress_pct,
            verification_coverage=plan.verification_coverage,
            current_phase=current_phase,
        )

    def update_task_progress(
        self,
        plan: ExecutionPlan,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
    ) -> ExecutionPlan:
        """
        Update progress for a specific task.

        Args:
            plan: Current execution plan
            task_id: ID of task to update
            status: New status
            result: Optional verification result

        Returns:
            Updated execution plan
        """
        import copy

        updated_plan = copy.deepcopy(plan)

        for task in updated_plan.tasks:
            if task.id == task_id:
                task.status = status
                if result:
                    task.verification_result = result

                # Update timestamps
                from datetime import datetime

                if status == TaskStatus.IN_PROGRESS and not task.started_at:
                    task.started_at = datetime.now().isoformat()
                elif status == TaskStatus.COMPLETED:
                    task.completed_at = datetime.now().isoformat()

                break

        return updated_plan

    def generate_progress_report(self, plan: ExecutionPlan) -> str:
        """Generate a human-readable progress report."""
        summary = self.get_execution_summary(plan)

        lines = [
            "# 执行进度报告",
            "",
            f"## 总体进度: {summary.progress_percentage:.1%}",
            "",
            "| 状态 | 数量 |",
            "|------|------|",
            f"| ✅ 已完成 | {summary.completed_tasks} |",
            f"| 🔄 进行中 | {summary.in_progress_tasks} |",
            f"| ⏳ 等待中 | {summary.pending_tasks} |",
            f"| 🚫 阻塞 | {summary.blocked_tasks} |",
            f"| ❌ 验证失败 | {summary.failed_tasks} |",
            "",
            f"**验证覆盖率**: {summary.verification_coverage:.1%}",
            f"**当前阶段**: {summary.current_phase or 'N/A'}",
            "",
        ]

        # Phase breakdown
        if plan.phases:
            lines.append("## 各阶段进度")
            lines.append("")

            for phase in plan.phases:
                phase_tasks = [t for t in plan.tasks if t.phase == phase.id]
                if phase_tasks:
                    completed = sum(
                        1 for t in phase_tasks if t.status == TaskStatus.COMPLETED
                    )
                    total = len(phase_tasks)
                    pct = (completed / total) * 100 if total > 0 else 0

                    lines.append(f"### {phase.name}")
                    lines.append(f"进度: {completed}/{total} ({pct:.0f}%)")

                    if pct < 100:
                        incomplete = [
                            t for t in phase_tasks if t.status != TaskStatus.COMPLETED
                        ]
                        if incomplete:
                            lines.append(
                                f"未完成: {', '.join(t.id for t in incomplete[:5])}"
                            )
                            if len(incomplete) > 5:
                                lines.append(f"... 还有 {len(incomplete) - 5} 个任务")
                    lines.append("")

        return "\n".join(lines)

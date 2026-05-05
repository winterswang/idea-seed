"""Consistency checker for execution plans."""

from typing import NamedTuple

from agent.execution_plan.models import ExecutionPlan, Task


class ConsistencyIssue(NamedTuple):
    """Represents a consistency issue found in the plan."""

    type: str
    severity: str  # "error", "warning", "info"
    message: str
    task_ids: list[str] = []


class ConsistencyResult(NamedTuple):
    """Result of consistency check."""

    passed: bool
    issues: list[ConsistencyIssue]
    pass_rate: float
    executability_score: float


class ConsistencyChecker:
    """Checks execution plan consistency and quality."""

    def __init__(self) -> None:
        """Initialize consistency checker."""
        pass

    def check(self, plan: ExecutionPlan) -> ConsistencyResult:
        """
        Perform consistency check on execution plan.

        Args:
            plan: ExecutionPlan to check

        Returns:
            ConsistencyResult with issues and scores
        """
        issues = []

        # 1. Check for circular dependencies
        circular_issues = self._find_circular_dependencies(plan.tasks)
        issues.extend(circular_issues)

        # 2. Check for orphaned tasks (tasks not in any phase)
        orphan_issues = self._find_orphaned_tasks(plan)
        issues.extend(orphan_issues)

        # 3. Check task dependency validity
        dependency_issues = self._check_task_dependencies(plan.tasks)
        issues.extend(dependency_issues)

        # 4. Check checkpoint-task alignment
        checkpoint_issues = self._check_checkpoint_alignment(plan)
        issues.extend(checkpoint_issues)

        # 5. Check verification configuration completeness
        verification_issues = self._check_verification_completeness(plan.tasks)
        issues.extend(verification_issues)

        # Calculate pass rate
        error_count = sum(1 for i in issues if i.severity == "error")

        # Pass if no errors
        passed = error_count == 0

        # Pass rate calculation (0-1)
        total_checks = 5  # Number of check types
        failed_checks = error_count
        pass_rate = max(0, (total_checks - failed_checks) / total_checks)

        # Executability score from plan
        executability_score = plan.executability_score

        return ConsistencyResult(
            passed=passed,
            issues=issues,
            pass_rate=pass_rate,
            executability_score=executability_score,
        )

    def _find_circular_dependencies(self, tasks: list[Task]) -> list[ConsistencyIssue]:
        """Find circular dependencies in task graph."""
        issues = []
        task_map = {t.id: t for t in tasks}

        for task in tasks:
            visited = set()
            path = []

            def dfs(t: Task) -> bool:
                if t.id in path:
                    # Found cycle
                    cycle_start = path.index(t.id)
                    cycle_list = path[cycle_start:] + [t.id]
                    issues.append(
                        ConsistencyIssue(
                            type="circular_dependency",
                            severity="error",
                            message=f"Circular dependency detected: {' -> '.join(cycle_list)}",
                            task_ids=list(set(path)),
                        )
                    )
                    return True

                if t.id in visited:
                    return False

                visited.add(t.id)
                path.append(t.id)

                for dep_id in t.depends_on:
                    if dep_id in task_map:
                        if dfs(task_map[dep_id]):
                            return True

                path.pop()
                return False

            if dfs(task):
                issues.append(
                    ConsistencyIssue(
                        type="circular_dependency",
                        severity="error",
                        message=f"Circular dependency detected involving task {task.id}",
                        task_ids=list(set(path)),
                    )
                )

        return issues

    def _find_orphaned_tasks(self, plan: ExecutionPlan) -> list[ConsistencyIssue]:
        """Find tasks that are not referenced by any phase or checkpoint."""
        issues = []

        # Get all task IDs referenced by phases and checkpoints
        referenced_ids = set()

        for phase in plan.phases:
            referenced_ids.update(phase.task_ids)

        for checkpoint in plan.checkpoints:
            referenced_ids.update(checkpoint.task_ids)

        # Find orphaned tasks
        orphaned = []
        for task in plan.tasks:
            if task.id not in referenced_ids:
                orphaned.append(task.id)

        if orphaned:
            issues.append(
                ConsistencyIssue(
                    type="orphaned_task",
                    severity="warning",
                    message=f"Tasks not referenced by any phase or checkpoint: {orphaned}",
                    task_ids=orphaned,
                )
            )

        return issues

    def _check_task_dependencies(self, tasks: list[Task]) -> list[ConsistencyIssue]:
        """Check that task dependencies reference valid tasks."""
        issues = []
        task_ids = {t.id for t in tasks}

        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id not in task_ids:
                    issues.append(
                        ConsistencyIssue(
                            type="invalid_dependency",
                            severity="error",
                            message=f"Task {task.id} depends on non-existent task {dep_id}",
                            task_ids=[task.id],
                        )
                    )

        return issues

    def _check_checkpoint_alignment(
        self, plan: ExecutionPlan
    ) -> list[ConsistencyIssue]:
        """Check that checkpoints reference valid tasks."""
        issues = []
        task_ids = {t.id for t in plan.tasks}

        for checkpoint in plan.checkpoints:
            for task_id in checkpoint.task_ids:
                if task_id not in task_ids:
                    issues.append(
                        ConsistencyIssue(
                            type="invalid_checkpoint_reference",
                            severity="error",
                            message=f"Checkpoint {checkpoint.id} references non-existent task {task_id}",
                            task_ids=[task_id],
                        )
                    )

        # Check that each phase has a checkpoint
        for phase in plan.phases:
            if not phase.checkpoint_id:
                issues.append(
                    ConsistencyIssue(
                        type="missing_phase_checkpoint",
                        severity="warning",
                        message=f"Phase {phase.id} has no checkpoint assigned",
                        task_ids=phase.task_ids,
                    )
                )

        return issues

    def _check_verification_completeness(
        self, tasks: list[Task]
    ) -> list[ConsistencyIssue]:
        """Check that all tasks have proper verification configuration."""
        issues = []

        for task in tasks:
            if task.verification_type.value == "manual":
                # Manual verification is acceptable but warn
                continue

            if not task.verification_config:
                issues.append(
                    ConsistencyIssue(
                        type="missing_verification_config",
                        severity="error",
                        message=f"Task {task.id} has no verification configuration",
                        task_ids=[task.id],
                    )
                )

        return issues

    def generate_report(self, result: ConsistencyResult) -> str:
        """Generate a human-readable consistency report."""
        lines = [
            "# 一致性检查报告",
            "",
            f"**通过状态**: {'✅ 通过' if result.passed else '❌ 未通过'}",
            f"**通过率**: {result.pass_rate:.1%}",
            f"**可执行性评分**: {result.executability_score:.1%}",
            "",
        ]

        if not result.issues:
            lines.append("未发现问题。")
            return "\n".join(lines)

        # Group by severity
        errors = [i for i in result.issues if i.severity == "error"]
        warnings = [i for i in result.issues if i.severity == "warning"]

        if errors:
            lines.append("## ❌ 错误")
            for issue in errors:
                lines.append(f"- **{issue.type}**: {issue.message}")
                if issue.task_ids:
                    lines.append(f"  - 相关任务: {', '.join(issue.task_ids)}")
            lines.append("")

        if warnings:
            lines.append("## ⚠️ 警告")
            for issue in warnings:
                lines.append(f"- **{issue.type}**: {issue.message}")
                if issue.task_ids:
                    lines.append(f"  - 相关任务: {', '.join(issue.task_ids)}")

        return "\n".join(lines)

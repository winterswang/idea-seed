"""Tests for consistency checker."""

from agent.execution_plan.models import (
    Task,
    Checkpoint,
    ExecutionPlan,
    Phase,
    VerificationType,
)
from agent.execution_plan.consistency import ConsistencyChecker, ConsistencyIssue


class TestConsistencyChecker:
    """Tests for ConsistencyChecker."""

    def setup_method(self):
        """Set up test fixtures."""
        self.checker = ConsistencyChecker()

    def test_check_empty_plan(self):
        """Test checking an empty plan."""
        plan = ExecutionPlan()
        result = self.checker.check(plan)
        # Empty plan should pass with low scores
        assert result.pass_rate == 1.0  # No errors
        assert result.executability_score == 0.0

    def test_check_valid_plan(self):
        """Test checking a valid plan with no issues."""
        tasks = [
            Task(
                id="task-1",
                name="First Task",
                description="Do first thing",
                phase="phase-1",
                verification_type=VerificationType.COMMAND_EXECUTION,
                verification_config={"command": "echo test"},
            ),
            Task(
                id="task-2",
                name="Second Task",
                description="Do second thing",
                phase="phase-1",
                depends_on=["task-1"],
                verification_type=VerificationType.FILE_EXISTENCE,
                verification_config={"files": ["output.txt"]},
            ),
        ]
        phases = [
            Phase(
                id="phase-1",
                name="Phase 1",
                description="First phase",
                order=0,
                task_ids=["task-1", "task-2"],
                checkpoint_id="cp-1",
            )
        ]
        checkpoints = [
            Checkpoint(
                id="cp-1",
                name="Phase 1 Check",
                description="Verify phase 1",
                task_ids=["task-1", "task-2"],
            )
        ]
        plan = ExecutionPlan(
            tasks=tasks,
            phases=phases,
            checkpoints=checkpoints,
            total_tasks=2,
            executability_score=1.0,
            verification_coverage=1.0,
        )

        result = self.checker.check(plan)
        assert result.passed is True
        assert len(result.issues) == 0

    def test_detect_circular_dependency(self):
        """Test detection of circular dependencies."""
        tasks = [
            Task(
                id="task-a",
                name="Task A",
                description="A depends on B",
                phase="phase-1",
                depends_on=["task-b"],
            ),
            Task(
                id="task-b",
                name="Task B",
                description="B depends on C",
                phase="phase-1",
                depends_on=["task-c"],
            ),
            Task(
                id="task-c",
                name="Task C",
                description="C depends on A - CIRCULAR",
                phase="phase-1",
                depends_on=["task-a"],
            ),
        ]
        plan = ExecutionPlan(tasks=tasks, total_tasks=3)

        result = self.checker.check(plan)
        # Should detect circular dependency
        circular_issues = [i for i in result.issues if i.type == "circular_dependency"]
        assert len(circular_issues) > 0

    def test_detect_invalid_dependency(self):
        """Test detection of invalid task dependencies."""
        tasks = [
            Task(
                id="task-1",
                name="Task 1",
                description="Depends on non-existent task",
                phase="phase-1",
                depends_on=["non-existent-task"],
            ),
        ]
        plan = ExecutionPlan(tasks=tasks, total_tasks=1)

        result = self.checker.check(plan)
        invalid_dep_issues = [
            i for i in result.issues if i.type == "invalid_dependency"
        ]
        assert len(invalid_dep_issues) > 0

    def test_detect_missing_verification_config(self):
        """Test detection of missing verification configuration."""
        tasks = [
            Task(
                id="task-1",
                name="Task without verification",
                description="This task has no verification config",
                phase="phase-1",
                verification_type=VerificationType.COMMAND_EXECUTION,
                # Missing verification_config
            ),
        ]
        plan = ExecutionPlan(tasks=tasks, total_tasks=1)

        result = self.checker.check(plan)
        missing_config_issues = [
            i for i in result.issues if i.type == "missing_verification_config"
        ]
        assert len(missing_config_issues) > 0

    def test_manual_verification_acceptable(self):
        """Test that manual verification doesn't trigger missing config warning."""
        tasks = [
            Task(
                id="task-1",
                name="Manual task",
                description="This is a manual task",
                phase="phase-1",
                verification_type=VerificationType.MANUAL,
                # No verification_config needed for manual
            ),
        ]
        plan = ExecutionPlan(tasks=tasks, total_tasks=1)

        result = self.checker.check(plan)
        missing_config_issues = [
            i for i in result.issues if i.type == "missing_verification_config"
        ]
        assert len(missing_config_issues) == 0

    def test_orphaned_task_detection(self):
        """Test detection of tasks not referenced by any phase."""
        tasks = [
            Task(id="task-1", name="T1", description="D", phase="phase-1"),
            Task(id="task-2", name="T2", description="D", phase="phase-1"),
            Task(id="task-3", name="T3", description="D", phase="phase-X"),  # Orphaned
        ]
        phases = [
            Phase(
                id="phase-1",
                name="P1",
                description="D",
                order=0,
                task_ids=["task-1", "task-2"],
            )
        ]
        plan = ExecutionPlan(tasks=tasks, phases=phases, total_tasks=3)

        result = self.checker.check(plan)
        orphan_issues = [i for i in result.issues if i.type == "orphaned_task"]
        assert len(orphan_issues) > 0

    def test_checkpoint_invalid_reference(self):
        """Test detection of checkpoint referencing non-existent task."""
        tasks = [
            Task(id="task-1", name="T1", description="D", phase="phase-1"),
        ]
        checkpoints = [
            Checkpoint(
                id="cp-1",
                name="Checkpoint",
                description="D",
                task_ids=["task-1", "non-existent-task"],
            )
        ]
        plan = ExecutionPlan(tasks=tasks, checkpoints=checkpoints, total_tasks=1)

        result = self.checker.check(plan)
        invalid_ref_issues = [
            i for i in result.issues if i.type == "invalid_checkpoint_reference"
        ]
        assert len(invalid_ref_issues) > 0

    def test_generate_report(self):
        """Test report generation."""
        tasks = [
            Task(
                id="task-1",
                name="T1",
                description="D",
                phase="phase-1",
                depends_on=["non-existent"],
            ),
        ]
        plan = ExecutionPlan(tasks=tasks, total_tasks=1)
        result = self.checker.check(plan)

        report = self.checker.generate_report(result)
        assert "一致性检查报告" in report
        assert "未通过" in report  # Has issues


class TestConsistencyIssue:
    """Tests for ConsistencyIssue."""

    def test_issue_creation(self):
        """Test ConsistencyIssue creation."""
        issue = ConsistencyIssue(
            type="test_issue",
            severity="error",
            message="Test error message",
            task_ids=["task-1", "task-2"],
        )
        assert issue.type == "test_issue"
        assert issue.severity == "error"
        assert len(issue.task_ids) == 2

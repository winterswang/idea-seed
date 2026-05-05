"""Tests for execution plan models."""

from agent.execution_plan.models import (
    Task,
    Checkpoint,
    TaskStatus,
    VerificationType,
    CheckpointStatus,
    VerificationResult,
    ExecutionPlan,
    Phase,
)


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.IN_PROGRESS.value == "in_progress"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.VERIFICATION_FAILED.value == "verification_failed"
        assert TaskStatus.BLOCKED.value == "blocked"


class TestVerificationType:
    """Tests for VerificationType enum."""

    def test_verification_type_values(self):
        """Test VerificationType enum values."""
        assert VerificationType.COMMAND_EXECUTION.value == "command_execution"
        assert VerificationType.FILE_EXISTENCE.value == "file_existence"
        assert VerificationType.COVERAGE_CHECK.value == "coverage_check"
        assert VerificationType.MANUAL.value == "manual"
        assert VerificationType.PHASE_COMPLETION.value == "phase_completion"


class TestTask:
    """Tests for Task model."""

    def test_task_creation(self):
        """Test basic Task creation."""
        task = Task(
            id="task-1-1",
            name="Test Task",
            description="A test task",
            phase="phase-1",
        )
        assert task.id == "task-1-1"
        assert task.name == "Test Task"
        assert task.status == TaskStatus.PENDING
        assert task.priority == 0

    def test_task_to_dict(self):
        """Test Task serialization to dict."""
        task = Task(
            id="task-1",
            name="Test",
            description="Test description",
            phase="phase-1",
            status=TaskStatus.IN_PROGRESS,
            priority=1,
            depends_on=["task-0"],
        )
        d = task.to_dict()
        assert d["id"] == "task-1"
        assert d["status"] == "in_progress"
        assert d["depends_on"] == ["task-0"]

    def test_task_from_dict(self):
        """Test Task deserialization from dict."""
        data = {
            "id": "task-2",
            "name": "From Dict",
            "description": "Created from dict",
            "phase": "phase-2",
            "status": "completed",
            "priority": 2,
        }
        task = Task.from_dict(data)
        assert task.id == "task-2"
        assert task.status == TaskStatus.COMPLETED


class TestCheckpoint:
    """Tests for Checkpoint model."""

    def test_checkpoint_creation(self):
        """Test basic Checkpoint creation."""
        cp = Checkpoint(
            id="cp-1",
            name="Phase 1 Checkpoint",
            description="Verify phase 1 completion",
            task_ids=["task-1-1", "task-1-2"],
        )
        assert cp.id == "cp-1"
        assert len(cp.task_ids) == 2
        assert cp.status == CheckpointStatus.PENDING

    def test_checkpoint_to_dict(self):
        """Test Checkpoint serialization."""
        cp = Checkpoint(
            id="cp-1",
            name="Test",
            description="Test checkpoint",
            task_ids=["task-1"],
            status=CheckpointStatus.COMPLETED,
        )
        d = cp.to_dict()
        assert d["id"] == "cp-1"
        assert d["status"] == "completed"


class TestPhase:
    """Tests for Phase model."""

    def test_phase_creation(self):
        """Test basic Phase creation."""
        phase = Phase(
            id="phase-1",
            name="Foundation",
            description="Setup foundation",
            order=0,
            task_ids=["task-1-1", "task-1-2"],
        )
        assert phase.order == 0
        assert len(phase.task_ids) == 2

    def test_phase_to_dict(self):
        """Test Phase serialization."""
        phase = Phase(
            id="phase-1",
            name="Test Phase",
            description="Test",
            order=1,
        )
        d = phase.to_dict()
        assert d["id"] == "phase-1"
        assert d["order"] == 1


class TestExecutionPlan:
    """Tests for ExecutionPlan model."""

    def test_execution_plan_creation(self):
        """Test basic ExecutionPlan creation."""
        plan = ExecutionPlan()
        assert plan.total_tasks == 0
        assert len(plan.tasks) == 0

    def test_execution_plan_with_tasks(self):
        """Test ExecutionPlan with tasks."""
        tasks = [
            Task(id="task-1", name="Task 1", description="Desc", phase="phase-1"),
            Task(id="task-2", name="Task 2", description="Desc", phase="phase-1"),
        ]
        plan = ExecutionPlan(
            tasks=tasks,
            total_tasks=2,
            executability_score=0.95,
            verification_coverage=1.0,
        )
        assert plan.total_tasks == 2
        assert len(plan.tasks) == 2

    def test_execution_plan_to_dict(self):
        """Test ExecutionPlan serialization."""
        tasks = [Task(id="task-1", name="T", description="D", phase="p")]
        plan = ExecutionPlan(
            tasks=tasks,
            total_tasks=1,
            executability_score=0.9,
        )
        d = plan.to_dict()
        assert d["total_tasks"] == 1
        assert len(d["tasks"]) == 1

    def test_execution_plan_from_dict(self):
        """Test ExecutionPlan deserialization."""
        data = {
            "tasks": [
                {
                    "id": "task-1",
                    "name": "T1",
                    "description": "D",
                    "phase": "p1",
                    "status": "pending",
                }
            ],
            "total_tasks": 1,
            "phases": [],
            "checkpoints": [],
            "metadata": {},
            "estimated_duration": "1d",
            "executability_score": 0.95,
            "verification_coverage": 1.0,
        }
        plan = ExecutionPlan.from_dict(data)
        assert plan.total_tasks == 1
        assert len(plan.tasks) == 1


class TestVerificationResult:
    """Tests for VerificationResult model."""

    def test_verification_result_pass(self):
        """Test VerificationResult for passing verification."""
        result = VerificationResult(
            passed=True,
            verification_type=VerificationType.COMMAND_EXECUTION,
            details={"exit_code": 0},
        )
        assert result.passed is True
        assert result.verification_type == VerificationType.COMMAND_EXECUTION

    def test_verification_result_fail(self):
        """Test VerificationResult for failing verification."""
        result = VerificationResult(
            passed=False,
            verification_type=VerificationType.COVERAGE_CHECK,
            errors=["Coverage 75% below threshold 80%"],
            coverage_percentage=75.0,
        )
        assert result.passed is False
        assert len(result.errors) == 1

    def test_verification_result_to_dict(self):
        """Test VerificationResult serialization."""
        result = VerificationResult(
            passed=True,
            verification_type=VerificationType.FILE_EXISTENCE,
            details={"files": ["a.txt", "b.txt"]},
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert d["verification_type"] == "file_existence"

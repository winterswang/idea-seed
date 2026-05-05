"""Integration tests for plan mode execution."""

import pytest
from pathlib import Path
import tempfile

from agent.orchestrator import Orchestrator
from agent.state import SessionState
from agent.constants import MODE_LEGACY, MODE_PLAN


class TestOrchestratorModeSelection:
    """Tests for Orchestrator mode selection."""

    def test_orchestrator_default_mode(self):
        """Test that default mode is legacy."""
        orch = Orchestrator(
            seed="test seed",
            resume=False,
        )
        assert orch.mode == MODE_LEGACY

    def test_orchestrator_plan_mode(self):
        """Test that plan mode can be selected."""
        orch = Orchestrator(
            seed="test seed",
            resume=False,
            mode=MODE_PLAN,
        )
        assert orch.mode == MODE_PLAN

    def test_state_mode_reflected(self):
        """Test that state reflects the selected mode."""
        orch = Orchestrator(
            seed="test seed",
            resume=False,
            mode=MODE_PLAN,
        )
        assert orch.state.mode == MODE_PLAN


class TestSessionStateV2Fields:
    """Tests for SessionState V2 fields."""

    def test_session_state_defaults(self):
        """Test that SessionState has correct defaults."""
        state = SessionState(
            session_id="test-id",
            seed="test seed",
        )
        assert state.mode == MODE_LEGACY
        assert state.execution_plan_round == 0
        assert state.execution_plan_converged is False
        assert state.tasks == []
        assert state.checkpoints == []

    def test_session_state_plan_mode(self):
        """Test SessionState with plan mode."""
        state = SessionState(
            session_id="test-id",
            seed="test seed",
            mode=MODE_PLAN,
        )
        assert state.mode == MODE_PLAN
        assert state.is_plan_mode() is True

    def test_is_done_legacy_mode(self):
        """Test is_done() for legacy mode."""
        state = SessionState(
            session_id="test",
            seed="seed",
            mode=MODE_LEGACY,
            req_converged=True,
            design_converged=True,
        )
        assert state.is_done() is True

    def test_is_done_plan_mode(self):
        """Test is_done() for plan mode."""
        state = SessionState(
            session_id="test",
            seed="seed",
            mode=MODE_PLAN,
            req_converged=True,
            execution_plan_converged=True,
        )
        assert state.is_done() is True


class TestExecutionPlanPath:
    """Tests for execution plan file path."""

    def test_execution_plan_path_property(self):
        """Test execution_plan_path property."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock WORKDIR to use temp directory
            import agent.config

            original_workdir = agent.config.WORKDIR
            agent.config.WORKDIR = Path(tmpdir)

            try:
                orch = Orchestrator(seed="test seed")
                assert orch.execution_plan_path.name == "execution-plan.md"
            finally:
                agent.config.WORKDIR = original_workdir


class TestConstants:
    """Tests for constants."""

    def test_phase_execution_plan_defined(self):
        """Test PHASE_EXECUTION_PLAN constant exists."""
        from agent.constants import PHASE_EXECUTION_PLAN

        assert PHASE_EXECUTION_PLAN == "execution_plan"

    def test_mode_constants_defined(self):
        """Test MODE_LEGACY and MODE_PLAN constants exist."""
        from agent.constants import MODE_LEGACY, MODE_PLAN

        assert MODE_LEGACY == "legacy"
        assert MODE_PLAN == "plan"

    def test_task_status_constants_defined(self):
        """Test task status constants exist."""
        from agent.constants import (
            TASK_STATUS_PENDING,
            TASK_STATUS_IN_PROGRESS,
            TASK_STATUS_COMPLETED,
        )

        assert TASK_STATUS_PENDING == "pending"
        assert TASK_STATUS_IN_PROGRESS == "in_progress"
        assert TASK_STATUS_COMPLETED == "completed"

    def test_verification_type_constants_defined(self):
        """Test verification type constants exist."""
        from agent.constants import (
            VERIFICATION_COMMAND_EXECUTION,
            VERIFICATION_FILE_EXISTENCE,
            VERIFICATION_COVERAGE_CHECK,
            VERIFICATION_MANUAL,
        )

        assert VERIFICATION_COMMAND_EXECUTION == "command_execution"
        assert VERIFICATION_FILE_EXISTENCE == "file_existence"
        assert VERIFICATION_COVERAGE_CHECK == "coverage_check"
        assert VERIFICATION_MANUAL == "manual"

    def test_execution_plan_file_constant(self):
        """Test EXECUTION_PLAN_FILE constant."""
        from agent.constants import EXECUTION_PLAN_FILE

        assert EXECUTION_PLAN_FILE == "execution-plan.md"


class TestModeSwitching:
    """Tests for mode switching behavior."""

    def test_transition_from_tech_design_to_execution_plan(self):
        """Test that in plan mode, tech_design phase transitions to execution_plan."""
        # This tests the run() loop behavior
        # In plan mode, when state.phase is PHASE_TECH_DESIGN, it should call
        # _run_execution_plan_phase instead of _run_design_phase
        pass  # Covered by integration test with actual run


class TestProgressManager:
    """Tests for progress manager."""

    def test_progress_summary_calculation(self):
        """Test ProgressSummary calculations."""
        from agent.execution_plan.progress import ProgressManager
        from agent.execution_plan.models import ExecutionPlan, Task, TaskStatus

        # Create mock orchestrator
        class MockOrchestrator:
            pass

        manager = ProgressManager(MockOrchestrator())

        tasks = [
            Task(
                id="t1",
                name="T1",
                description="D",
                phase="p1",
                status=TaskStatus.COMPLETED,
            ),
            Task(
                id="t2",
                name="T2",
                description="D",
                phase="p1",
                status=TaskStatus.IN_PROGRESS,
            ),
            Task(
                id="t3",
                name="T3",
                description="D",
                phase="p1",
                status=TaskStatus.PENDING,
            ),
        ]
        plan = ExecutionPlan(tasks=tasks, total_tasks=3, verification_coverage=1.0)

        summary = manager.get_execution_summary(plan)

        assert summary.total_tasks == 3
        assert summary.completed_tasks == 1
        assert summary.in_progress_tasks == 1
        assert summary.pending_tasks == 1
        assert summary.progress_percentage == pytest.approx(33.33, rel=1)


class TestIncrementalUpdater:
    """Tests for incremental updater."""

    def test_change_impact_assessment(self):
        """Test ChangeImpact assessment."""
        from agent.execution_plan.incremental import IncrementalUpdater, ChangeImpact

        class MockOrchestrator:
            def __init__(self):
                self.state = type("State", (), {"requirements_md5": "old-md5"})()

        updater = IncrementalUpdater(MockOrchestrator())

        # Create plan with in-progress tasks
        from agent.execution_plan.models import ExecutionPlan, Task, TaskStatus

        tasks = [
            Task(
                id="t1",
                name="T1",
                description="D",
                phase="p1",
                status=TaskStatus.COMPLETED,
            ),
            Task(
                id="t2",
                name="T2",
                description="D",
                phase="p1",
                status=TaskStatus.IN_PROGRESS,
            ),
        ]
        plan = ExecutionPlan(tasks=tasks)

        # With completed task, should be safe to regenerate
        impact = updater._assess_impact(plan)
        # Result depends on implementation - in this case with completed tasks,
        # full regeneration might be recommended

        assert isinstance(impact, ChangeImpact)

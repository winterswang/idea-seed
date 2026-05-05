"""Verification engine for task and checkpoint verification."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agent.orchestrator import Orchestrator

from agent.execution_plan.models import (
    Task,
    Checkpoint,
    VerificationResult,
    VerificationType,
    TaskStatus,
)


class VerificationEngine:
    """Verifies task and checkpoint completion."""

    def __init__(self, orchestrator: "Orchestrator") -> None:
        """Initialize with orchestrator reference."""
        self.orchestrator = orchestrator

    def verify_task(self, task: Task) -> VerificationResult:
        """
        Verify a single task completion.

        Args:
            task: Task to verify

        Returns:
            VerificationResult with pass/fail and details
        """
        if task.verification_type == VerificationType.COMMAND_EXECUTION:
            return self._verify_command(task)
        elif task.verification_type == VerificationType.FILE_EXISTENCE:
            return self._verify_file_existence(task)
        elif task.verification_type == VerificationType.COVERAGE_CHECK:
            return self._verify_coverage(task)
        elif task.verification_type == VerificationType.PHASE_COMPLETION:
            return self._verify_phase_completion(task)
        else:
            return self._verify_manual(task)

    def verify_checkpoint(
        self, checkpoint: Checkpoint, tasks: list[Task]
    ) -> VerificationResult:
        """
        Verify a checkpoint by checking all associated tasks.

        Args:
            checkpoint: Checkpoint to verify
            tasks: All tasks in the plan

        Returns:
            VerificationResult with pass/fail and details
        """
        task_map = {t.id: t for t in tasks}
        checkpoint_tasks = [
            task_map[tid] for tid in checkpoint.task_ids if tid in task_map
        ]

        # First check all tasks are completed
        incomplete_tasks = [
            t for t in checkpoint_tasks if t.status != TaskStatus.COMPLETED
        ]

        if incomplete_tasks:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.PHASE_COMPLETION,
                details={
                    "incomplete_tasks": [t.id for t in incomplete_tasks],
                    "message": f"{len(incomplete_tasks)} tasks not completed",
                },
                errors=[f"Task {t.id} is not completed" for t in incomplete_tasks],
            )

        # Then verify based on checkpoint type
        if checkpoint.verification_type == VerificationType.COVERAGE_CHECK:
            return self._verify_checkpoint_coverage(checkpoint, checkpoint_tasks)
        else:
            return VerificationResult(
                passed=True,
                verification_type=checkpoint.verification_type,
                details={"message": f"All {len(checkpoint_tasks)} tasks completed"},
            )

    def _verify_command(self, task: Task) -> VerificationResult:
        """Verify task via command execution."""
        config = task.verification_config
        command = config.get("command", "")

        if not command:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COMMAND_EXECUTION,
                errors=["No command specified in verification config"],
            )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=config.get("timeout", 60),
            )

            # Check exit code
            expected_codes = config.get("expected_exit_codes", [0])
            passed = result.returncode in expected_codes

            return VerificationResult(
                passed=passed,
                verification_type=VerificationType.COMMAND_EXECUTION,
                details={
                    "command": command,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:500] if result.stdout else "",
                    "stderr": result.stderr[:500] if result.stderr else "",
                },
                errors=[]
                if passed
                else [f"Command failed with exit code {result.returncode}"],
            )

        except subprocess.TimeoutExpired:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COMMAND_EXECUTION,
                details={"command": command},
                errors=["Command execution timed out"],
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COMMAND_EXECUTION,
                details={"command": command},
                errors=[f"Command execution error: {str(e)}"],
            )

    def _verify_file_existence(self, task: Task) -> VerificationResult:
        """Verify task via file existence check."""
        config = task.verification_config
        file_paths = config.get("files", [])

        if not file_paths:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.FILE_EXISTENCE,
                errors=["No files specified in verification config"],
            )

        missing_files = []
        existing_files = []

        for fp in file_paths:
            path = Path(fp)
            if path.exists():
                existing_files.append(str(path))
            else:
                missing_files.append(str(path))

        passed = len(missing_files) == 0

        return VerificationResult(
            passed=passed,
            verification_type=VerificationType.FILE_EXISTENCE,
            details={
                "existing_files": existing_files,
                "missing_files": missing_files,
            },
            errors=[f"Missing file: {f}" for f in missing_files]
            if missing_files
            else [],
        )

    def _verify_coverage(self, task: Task) -> VerificationResult:
        """Verify task via code coverage check."""
        config = task.verification_config
        command = config.get("command", "")
        threshold = config.get("threshold", 80.0)

        if not command:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COVERAGE_CHECK,
                errors=["No coverage command specified"],
            )

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=config.get("timeout", 120),
            )

            # Parse coverage output - expect percentage
            coverage_pct = self._parse_coverage_output(result.stdout, result.stderr)

            passed = coverage_pct >= threshold if coverage_pct is not None else False

            return VerificationResult(
                passed=passed,
                verification_type=VerificationType.COVERAGE_CHECK,
                details={
                    "command": command,
                    "coverage_percentage": coverage_pct,
                    "threshold": threshold,
                },
                coverage_percentage=coverage_pct or 0.0,
                errors=[]
                if passed
                else [f"Coverage {coverage_pct}% below threshold {threshold}%"]
                if coverage_pct is not None
                else ["Failed to parse coverage output"],
            )

        except Exception as e:
            return VerificationResult(
                passed=False,
                verification_type=VerificationType.COVERAGE_CHECK,
                errors=[f"Coverage check error: {str(e)}"],
            )

    def _verify_phase_completion(self, task: Task) -> VerificationResult:
        """Verify task as phase completion."""
        # Phase completion is verified by checkpoint, not individual task
        return VerificationResult(
            passed=True,
            verification_type=VerificationType.PHASE_COMPLETION,
            details={"message": "Phase completion verified via checkpoint"},
        )

    def _verify_manual(self, task: Task) -> VerificationResult:
        """Manual verification - requires human confirmation."""
        return VerificationResult(
            passed=False,
            verification_type=VerificationType.MANUAL,
            details={
                "message": "Manual verification required",
                "task_id": task.id,
                "task_name": task.name,
            },
            warnings=["Task requires manual verification before completion"],
        )

    def _verify_checkpoint_coverage(
        self,
        checkpoint: Checkpoint,
        tasks: list[Task],
    ) -> VerificationResult:
        """Verify checkpoint coverage across tasks."""
        coverage_pcts = []

        for task in tasks:
            if task.verification_type == VerificationType.COVERAGE_CHECK:
                # Extract coverage percentage from task
                if task.verification_result:
                    cp = task.verification_result.get("coverage_percentage", 0)
                    coverage_pcts.append(cp)

        avg_coverage = sum(coverage_pcts) / len(coverage_pcts) if coverage_pcts else 0.0
        threshold = checkpoint.verification_config.get("threshold", 80.0)

        passed = avg_coverage >= threshold

        return VerificationResult(
            passed=passed,
            verification_type=VerificationType.COVERAGE_CHECK,
            details={
                "average_coverage": avg_coverage,
                "threshold": threshold,
                "task_coverages": coverage_pcts,
            },
            coverage_percentage=avg_coverage,
            errors=[]
            if passed
            else [f"Average coverage {avg_coverage:.1f}% below threshold {threshold}%"],
        )

    def _parse_coverage_output(self, stdout: str, stderr: str) -> Optional[float]:
        """Parse coverage command output to extract percentage."""
        import re

        combined = stdout + stderr

        # Look for percentage patterns like "95.5%" or "95%"
        patterns = [
            r"(\d+\.?\d*)%\s*coverage",
            r"COVERAGE\s*:\s*(\d+\.?\d*)%",
            r"TOTAL\s*.*?\s*(\d+\.?\d*)%",
        ]

        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue

        # Try to find last number with percent sign
        match = re.search(r"(\d+\.?\d*)\s*%", combined)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                pass

        return None

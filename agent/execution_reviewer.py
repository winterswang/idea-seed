"""Execution Reviewer for v2 Plan-based project management.

Verifies that a Plan's implementation matches its Tech-Spec by:
1. Checking expected files exist
2. Running test commands
3. Generating a pass/fail report
4. Updating Plan status via PlanManager
5. Propagating dependency statuses

Usage:
    reviewer = ExecutionReviewer(project_dir)
    result = reviewer.verify_plan("plan-001")
    # result.passed → True/False
    # result.report → markdown report
"""

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from agent.plan import Plan, PlanStatus, PlanStage
from agent.plan_manager import PlanManager


@dataclass
class FileCheck:
    """Result of checking a single file."""
    path: str
    exists: bool
    size: int = 0
    note: str = ""


@dataclass
class TestResult:
    """Result of running a test command."""
    command: str
    passed: bool
    output: str = ""
    duration: float = 0.0


@dataclass
class VerificationReport:
    """Complete verification report for a Plan."""
    plan_id: str
    feature: str
    passed: bool
    file_checks: list[FileCheck] = field(default_factory=list)
    test_results: list[TestResult] = field(default_factory=list)
    summary: str = ""
    timestamp: str = ""
    tech_spec_path: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_markdown(self) -> str:
        """Format as markdown report."""
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"# Execution Review: {self.plan_id}",
            "",
            f"**Plan**: {self.feature}",
            f"**Result**: {status}",
            f"**Time**: {self.timestamp}",
            f"**Tech-Spec**: {self.tech_spec_path}",
            "",
            "## File Checks",
            "",
        ]

        for fc in self.file_checks:
            icon = "✅" if fc.exists else "❌"
            lines.append(f"- {icon} `{fc.path}` ({fc.size}B){' — ' + fc.note if fc.note else ''}")

        if self.test_results:
            lines.extend(["", "## Test Results", ""])
            for tr in self.test_results:
                icon = "✅" if tr.passed else "❌"
                lines.append(f"- {icon} `{tr.command}` ({tr.duration:.1f}s)")

        lines.extend(["", "## Summary", "", self.summary])
        return "\n".join(lines)


class ExecutionReviewer:
    """Verifies Plan implementation against its Tech-Spec.

    Reads a Plan's Tech-Spec document, checks that expected files
    exist in the project directory, runs test commands, and generates
    a pass/fail report.

    Usage:
        er = ExecutionReviewer(project_dir)
        result = er.verify_plan("plan-001")
        if result.passed:
            er.mark_done("plan-001")
    """

    def __init__(self, project_dir: Path) -> None:
        """Initialize with project directory.

        Args:
            project_dir: Root directory of the project (e.g., projects/my-project/)
        """
        self.project_dir = Path(project_dir)
        self.state_dir = self.project_dir / ".state"
        self.pm = PlanManager(self.state_dir)

    def verify_plan(self, plan_id: str) -> VerificationReport:
        """Verify a Plan's implementation against its Tech-Spec.

        Args:
            plan_id: Plan identifier (e.g., "plan-001")

        Returns:
            VerificationReport with pass/fail status and details
        """
        plans = self.pm.load_plans()
        plan = self.pm.get_plan(plan_id, plans)

        if not plan:
            raise ValueError(f"Plan {plan_id} not found in {self.project_dir}")

        tech_spec_path = Path(plan.tech_spec_path) if plan.tech_spec_path else None
        if not tech_spec_path or not tech_spec_path.exists():
            raise FileNotFoundError(f"Tech-Spec not found for {plan_id}: {plan.tech_spec_path}")

        tech_spec = tech_spec_path.read_text()

        # Parse expected files and test commands from Tech-Spec
        expected_files = self._parse_expected_files(tech_spec)
        test_commands = self._parse_test_commands(tech_spec)

        # Run checks
        file_checks = self._check_files(expected_files)
        test_results = self._run_tests(test_commands)

        all_passed = all(fc.exists for fc in file_checks) and all(tr.passed for tr in test_results)

        summary = self._generate_summary(file_checks, test_results, all_passed)

        return VerificationReport(
            plan_id=plan_id,
            feature=plan.feature,
            passed=all_passed,
            file_checks=file_checks,
            test_results=test_results,
            summary=summary,
            tech_spec_path=str(tech_spec_path),
        )

    def mark_done(self, plan_id: str) -> None:
        """Mark a plan as done and propagate dependency statuses."""
        self.pm.update_plan_stage(plan_id, PlanStage.RELEASE)
        self.pm.update_plan_status(plan_id, PlanStatus.DONE)

        # Propagate: unblock downstream plans whose dependencies are all done
        plans = self.pm.load_plans()
        done_plan = self.pm.get_plan(plan_id, plans)

        if done_plan and done_plan.blocks:
            for blocked_id in done_plan.blocks:
                blocked = self.pm.get_plan(blocked_id, plans)
                if blocked and blocked.status == PlanStatus.BLOCKED:
                    # Check if ALL dependencies are now done
                    all_deps_done = True
                    for dep_id in blocked.depends_on:
                        dep = self.pm.get_plan(dep_id, plans)
                        if dep and dep.status != PlanStatus.DONE:
                            all_deps_done = False
                            break
                    if all_deps_done:
                        self.pm.update_plan_status(blocked_id, PlanStatus.PENDING)

    def mark_failed(self, plan_id: str, reason: str = "") -> None:
        """Mark a plan as verification failed."""
        self.pm.update_plan_status(plan_id, PlanStatus.BLOCKED)

    # === Private parsing methods ===

    def _parse_expected_files(self, tech_spec: str) -> list[str]:
        """Extract expected file paths from Tech-Spec.

        Looks for:
        - Directory tree blocks (├──, └──, │)
        - File paths in code blocks under "目录结构" or "File structure"
        - Lines containing .py / .ts / .js / .rs / .go file extensions
        """
        files: list[str] = []

        # Pattern 1: Tree diagram (├── path/to/file.py)
        tree_pattern = re.compile(r"[├└│]\s*─+\s*(.+\.\w+)")
        for match in tree_pattern.finditer(tech_spec):
            path = match.group(1).strip()
            if self._is_source_file(path):
                files.append(path)

        # Pattern 2: Paths in code blocks or bullet lists
        path_pattern = re.compile(r"[-*`]\s*([\w/.-]+\.(?:py|ts|js|rs|go|java|rb|php|sql|yaml|yml|toml|json|md))")
        for match in path_pattern.finditer(tech_spec):
            path = match.group(1).strip()
            if self._is_source_file(path) and path not in files:
                files.append(path)

        # Pattern 3: Explicit "目录结构" section
        in_structure = False
        for line in tech_spec.split("\n"):
            if "目录结构" in line or "File structure" in line or "file structure" in line:
                in_structure = True
                continue
            if in_structure:
                if line.startswith("##") or line.startswith("# "):
                    in_structure = False
                    continue
                m = re.search(r"([\w/.-]+\.(?:py|ts|js|rs|go|java|rb|sql|yaml|json|md))", line)
                if m and self._is_source_file(m.group(1)):
                    path = m.group(1).strip()
                    if path not in files:
                        files.append(path)

        return files

    def _parse_test_commands(self, tech_spec: str) -> list[str]:
        """Extract test commands from Tech-Spec.

        Looks for:
        - Shell commands in code blocks after "测试" / "test" / "验证" keywords
        - pytest / npm test / cargo test patterns
        """
        commands: list[str] = []
        in_test_section = False
        in_code_block = False
        code_lines: list[str] = []

        for line in tech_spec.split("\n"):
            stripped = line.strip()

            # Detect test sections
            if re.search(r"(测试|验收|验证|test|verify)", stripped, re.IGNORECASE):
                if stripped.startswith("##") or stripped.startswith("###"):
                    in_test_section = True
                    continue

            if in_test_section and stripped.startswith("##") and not re.search(r"(测试|验收|验证|test)", stripped, re.IGNORECASE):
                in_test_section = False
                continue

            # Track code blocks
            if stripped.startswith("```"):
                if in_code_block:
                    # End of code block — extract commands
                    for cl in code_lines:
                        if re.search(r"(pytest|npm test|cargo test|go test|unittest|python -m)", cl):
                            commands.append(cl.strip())
                        elif cl.strip().startswith("$ "):
                            cmd = cl.strip()[2:].strip()
                            if "test" in cmd.lower():
                                commands.append(cmd)
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block and in_test_section:
                code_lines.append(line)

        # Fallback: plain-text test commands (not in code blocks)
        if not commands:
            for line in tech_spec.split("\n"):
                m = re.search(r"(pytest|npm test|cargo test|go test|python -m pytest)\b.*", line)
                if m:
                    commands.append(m.group(0).strip())
        return commands

    # === Private check methods ===

    def _check_files(self, expected_files: list[str]) -> list[FileCheck]:
        """Check if expected files exist in the project directory."""
        checks: list[FileCheck] = []
        for fpath in expected_files:
            full_path = self.project_dir / fpath
            if full_path.exists():
                size = full_path.stat().st_size
                checks.append(FileCheck(path=fpath, exists=True, size=size))
            else:
                checks.append(FileCheck(path=fpath, exists=False, note="not found"))
        return checks

    def _run_tests(self, commands: list[str]) -> list[TestResult]:
        """Run test commands and return results."""
        results: list[TestResult] = []
        for cmd in commands:
            try:
                start = datetime.now()
                r = subprocess.run(
                    cmd, shell=True, cwd=self.project_dir,
                    capture_output=True, text=True, timeout=120,
                )
                duration = (datetime.now() - start).total_seconds()
                passed = r.returncode == 0
                output = (r.stdout + r.stderr)[:2000]
                results.append(TestResult(
                    command=cmd, passed=passed,
                    output=output, duration=duration,
                ))
            except subprocess.TimeoutExpired:
                results.append(TestResult(
                    command=cmd, passed=False,
                    output="Timed out after 120s", duration=120.0,
                ))
            except Exception as e:
                results.append(TestResult(
                    command=cmd, passed=False,
                    output=str(e), duration=0,
                ))
        return results

    # === Helpers ===

    @staticmethod
    def _is_source_file(path: str) -> bool:
        """Check if a path looks like a source file (not a directory or config)."""
        # Must have a known extension
        valid_extensions = {".py", ".ts", ".js", ".rs", ".go", ".java", ".rb", ".sql", ".yaml", ".json", ".md"}
        _, ext = Path(path).suffix, ""
        for ve in valid_extensions:
            if path.endswith(ve):
                return True
        return False

    @staticmethod
    def _generate_summary(
        file_checks: list[FileCheck],
        test_results: list[TestResult],
        all_passed: bool,
    ) -> str:
        """Generate a human-readable summary."""
        total_files = len(file_checks)
        files_ok = sum(1 for fc in file_checks if fc.exists)
        total_tests = len(test_results)
        tests_ok = sum(1 for tr in test_results if tr.passed)

        lines = []
        if all_passed:
            lines.append("All checks passed.")
        else:
            missing = [fc.path for fc in file_checks if not fc.exists]
            failed = [tr.command for tr in test_results if not tr.passed]
            if missing:
                lines.append(f"Missing files: {', '.join(missing)}")
            if failed:
                lines.append(f"Failed tests: {', '.join(failed)}")

        lines.append(f"Files: {files_ok}/{total_files} ok, Tests: {tests_ok}/{total_tests} ok")
        return "\n".join(lines)

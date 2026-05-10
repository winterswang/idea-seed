"""Execution plan generator."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from agent.orchestrator import Orchestrator

from agent.execution_plan.models import (
    ExecutionPlan,
    Task,
    Checkpoint,
    Phase,
    VerificationType,
)
from agent.execution_plan.prompts import (
    BUILDER_EXECUTION_PLAN_SYSTEM,
    BUILDER_EXECUTION_PLAN_PROMPT,
    EXECUTION_PLAN_BUILDER_PROMPT,
)


class ExecutionPlanGenerator:
    """Generates execution plans from requirements."""

    def __init__(self, orchestrator: "Orchestrator") -> None:
        """Initialize the generator with orchestrator reference."""
        self.orchestrator = orchestrator

    def generate(
        self,
        requirements: str,
        output_path: Path,
        previous_feedback: Optional[str] = None,
        previous_plan: Optional[str] = None,
    ) -> tuple[ExecutionPlan, str]:
        """
        Generate an execution plan from requirements.

        Args:
            requirements: Requirements document content
            output_path: Path to write the execution-plan.md
            previous_feedback: Optional feedback from previous review
            previous_plan: Optional previous plan content to revise

        Returns:
            Tuple of (ExecutionPlan object, markdown content)
        """
        if previous_plan and previous_feedback:
            # Revision mode
            plan_md = self._generate_revision(
                requirements, output_path, previous_feedback, previous_plan
            )
        else:
            # New generation
            plan_md = self._generate_new(requirements, output_path)

        # Parse the generated markdown into structured ExecutionPlan
        execution_plan = self._parse_markdown(plan_md)

        # Validate the plan
        self._validate_plan(execution_plan)

        return execution_plan, plan_md

    def _generate_new(
        self,
        requirements: str,
        output_path: Path,
    ) -> str:
        """Generate a new execution plan."""
        prompt = BUILDER_EXECUTION_PLAN_PROMPT.format(
            requirements=requirements[:5000],  # Limit length
            output_path=str(output_path),
            feedback="Initial generation - no previous feedback",
        )

        system = BUILDER_EXECUTION_PLAN_SYSTEM

        response = self._call_llm(prompt, system, output_path)

        # If file was properly written by subagent, trust it
        # Otherwise write the response
        if not output_path.exists() or len(output_path.read_text()) < 500:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(response)

        return output_path.read_text() if output_path.exists() else response

    def _generate_revision(
        self,
        requirements: str,
        output_path: Path,
        feedback: str,
        previous_plan: str,
    ) -> str:
        """Generate revision based on feedback."""
        prompt = EXECUTION_PLAN_BUILDER_PROMPT.format(
            previous_summary=self._summarize_plan(previous_plan),
            feedback=feedback,
            output_path=str(output_path),
        )

        system = BUILDER_EXECUTION_PLAN_SYSTEM

        response = self._call_llm(prompt, system, output_path)

        # If file was properly written by subagent, trust it
        # Otherwise write the response
        if not output_path.exists() or len(output_path.read_text()) < 500:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(response)

        return output_path.read_text() if output_path.exists() else response

    def _call_llm(self, prompt: str, system: str, output_path: Path) -> str:
        """Call LLM to generate content."""
        from agent.subagent import run_subagent

        summary, _ = run_subagent(
            prompt=prompt,
            system=system,
            phase="execution_plan",
            round_num=0,
            compact_enabled=False,
        )

        # Read the actual file content that was written
        # The subagent writes the execution plan directly to output_path
        if output_path.exists():
            content = output_path.read_text()
            if len(content) > 500:
                return content

        # Fallback to summary if file is empty or too short
        return summary

    def _parse_markdown(self, markdown_content: str) -> ExecutionPlan:
        """Parse markdown content into ExecutionPlan object."""
        # Simple parsing - in production would use more robust parsing
        plan = ExecutionPlan()

        # Extract phases
        phases = self._extract_phases(markdown_content)
        plan.phases = phases

        # Extract tasks
        tasks = self._extract_tasks(markdown_content)
        plan.tasks = tasks
        plan.total_tasks = len(tasks)

        # If no tasks extracted from structured format, try to parse from summary
        if len(tasks) == 0 and len(markdown_content) > 200:
            tasks = self._extract_tasks_from_summary(markdown_content)
            plan.tasks = tasks
            plan.total_tasks = len(tasks)

        # Extract checkpoints
        checkpoints = self._extract_checkpoints(markdown_content)
        plan.checkpoints = checkpoints

        # Calculate metrics
        plan.executability_score = self._calculate_executability_score(tasks)
        plan.verification_coverage = self._calculate_verification_coverage(tasks)

        return plan

    def _extract_phases(self, markdown: str) -> list[Phase]:
        """Extract phases from markdown."""
        phases = []
        lines = markdown.split("\n")
        current_phase = None

        for i, line in enumerate(lines):
            if line.startswith("### Phase ") or "Phase" in line and ":" in line:
                # New phase detected
                phase_name = (
                    line.split(":", 1)[-1].strip()
                    if ":" in line
                    else line.split("-", 1)[-1].strip()
                )
                current_phase = Phase(
                    id=f"phase-{len(phases) + 1}",
                    name=phase_name,
                    description="",
                    order=len(phases),
                )
                phases.append(current_phase)
            elif current_phase and not line.strip():
                # Empty line after phase name - accumulate description
                pass

        # Fallback: extract phases from table format
        if len(phases) == 0:
            phases = self._extract_phases_from_table(markdown)

        return phases

    def _extract_phases_from_table(self, markdown: str) -> list[Phase]:
        """Extract phases from table format when structured format fails."""
        phases = []
        lines = markdown.split("\n")

        for line in lines:
            # Match table rows like "| Phase 1 | 基础架构搭建 | 4 | 目录结构、数据库设计 |"
            if line.startswith("|") and "Phase" in line:
                # Skip header row
                if "名称" in line or "任务数" in line:
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    # phase_num = parts[1].strip()
                    phase_name = parts[2].strip() if len(parts) > 2 else ""
                    if phase_name:
                        phase = Phase(
                            id=f"phase-{len(phases) + 1}",
                            name=phase_name,
                            description=f"Phase from table: {phase_name}",
                            order=len(phases),
                        )
                        phases.append(phase)

        return phases

    def _extract_tasks(self, markdown: str) -> list[Task]:
        """Extract tasks from markdown."""
        tasks = []
        lines = markdown.split("\n")
        current_task = None

        for line in lines:
            if "### Task" in line or line.startswith("### Task"):
                # New task
                task_id = self._extract_task_id(line)
                if task_id:
                    current_task = Task(
                        id=task_id,
                        name="",
                        description="",
                        phase="",
                    )
                    tasks.append(current_task)
            elif current_task:
                if line.startswith("- **"):
                    # Parse key-value pairs
                    if "**描述**:" in line or "**Description**:" in line:
                        current_task.description = self._extract_value(line)
                    elif "**优先级**:" in line or "**Priority**:" in line:
                        priority_str = self._extract_value(line)
                        current_task.priority = self._priority_to_int(priority_str)
                    elif "**验证类型**:" in line or "**Verification**:" in line:
                        vtype = self._extract_value(line)
                        current_task.verification_type = self._parse_verification_type(
                            vtype
                        )
                    elif "**依赖**:" in line or "**Dependencies**:" in line:
                        deps = self._extract_value(line)
                        current_task.depends_on = self._parse_dependencies(deps)

        return tasks

    def _extract_tasks_from_summary(self, markdown: str) -> list[Task]:
        """Extract tasks from summary format when structured format fails."""
        tasks = []
        lines = markdown.split("\n")

        # Parse table format: | Phase | 名称 | 任务数 | 关键内容 |
        phases_data = []
        for line in lines:
            # Match table rows like "| Phase 1 | 基础架构搭建 | 4 | 目录结构、数据库设计 |"
            if line.startswith("|") and "Phase" in line and "任务数" in line:
                continue  # Skip header row
            if line.startswith("|") and "Phase" in line and "｜" in line or "|" in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 4:
                    phase_name = parts[1].replace("Phase", "").replace("Phase", "").strip()
                    if phase_name and phase_name[0].isdigit():
                        phases_data.append({
                            "name": parts[2].strip() if len(parts) > 2 else phase_name,
                            "task_count": int(parts[3].strip()) if len(parts) > 3 and parts[3].strip().isdigit() else 0
                        })

        # If we found phases from table, create tasks
        if phases_data:
            task_num = 0
            for phase in phases_data:
                for i in range(phase["task_count"]):
                    task_num += 1
                    task = Task(
                        id=f"task-{task_num}",
                        name=f"Task in {phase['name']}",
                        description=f"任务 in phase: {phase['name']}",
                        phase=phase["name"],
                        priority=0,
                        verification_type=VerificationType.COMMAND_EXECUTION,
                        depends_on=[],
                    )
                    tasks.append(task)

        # Fallback: also look for P0/P1/P2 task counts in bullet points
        if len(tasks) == 0:
            current_phase = ""
            task_num = 0
            for line in lines:
                if "Phase" in line and ("｜" in line or "|" in line):
                    parts = line.split("|")
                    if len(parts) >= 3:
                        current_phase = parts[2].strip()

                if "P0" in line and "任务" in line:
                    match = re.search(r'P0.*?(\d+)', line)
                    if match:
                        count = int(match.group(1))
                        for i in range(count):
                            task_num += 1
                            task = Task(
                                id=f"task-{task_num}",
                                name=f"Phase task",
                                description=f"P0 priority task from {current_phase}",
                                phase=current_phase,
                                priority=0,
                                verification_type=VerificationType.COMMAND_EXECUTION,
                                depends_on=[],
                            )
                            tasks.append(task)

        return tasks

    def _extract_checkpoints(self, markdown: str) -> list[Checkpoint]:
        """Extract checkpoints from markdown."""
        checkpoints = []

        # Simple checkpoint extraction
        lines = markdown.split("\n")
        for line in lines:
            if "Checkpoint" in line and ":" in line:
                cp_id = f"cp-{len(checkpoints) + 1}"
                cp_name = line.split(":", 1)[-1].strip()
                checkpoint = Checkpoint(
                    id=cp_id,
                    name=cp_name,
                    description=f"Checkpoint for {cp_name}",
                )
                checkpoints.append(checkpoint)

        return checkpoints

    def _extract_task_id(self, line: str) -> str:
        """Extract task ID from task header line."""
        import re

        match = re.search(r"Task\s+([\w-]+)", line, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_value(self, line: str) -> str:
        """Extract value from bullet point line."""
        if ":" in line:
            return line.split(":", 1)[-1].strip()
        return ""

    def _priority_to_int(self, priority: str) -> int:
        """Convert priority string to integer."""
        priority = priority.upper()
        if "P0" in priority or "高" in priority or "high" in priority:
            return 0
        elif "P1" in priority or "中" in priority or "medium" in priority:
            return 1
        else:
            return 2

    def _parse_verification_type(self, vtype: str) -> VerificationType:
        """Parse verification type string to enum."""
        vtype = vtype.lower()
        if "command" in vtype:
            return VerificationType.COMMAND_EXECUTION
        elif "file" in vtype or "existence" in vtype:
            return VerificationType.FILE_EXISTENCE
        elif "coverage" in vtype:
            return VerificationType.COVERAGE_CHECK
        elif "phase" in vtype:
            return VerificationType.PHASE_COMPLETION
        else:
            return VerificationType.MANUAL

    def _parse_dependencies(self, deps: str) -> list[str]:
        """Parse dependencies string to list."""
        if not deps or deps in ["无", "none", "-"]:
            return []
        # Split by comma or similar
        deps = deps.replace("，", ",").replace("、", ",")
        return [d.strip() for d in deps.split(",") if d.strip()]

    def _summarize_plan(self, plan: str) -> str:
        """Summarize previous plan for revision prompt."""
        lines = plan.split("\n")
        summary = []
        for line in lines[:50]:  # First 50 lines
            if line.startswith("### Phase") or "Task" in line:
                summary.append(line)
        return "\n".join(summary[:20])

    def _calculate_executability_score(self, tasks: list[Task]) -> float:
        """Calculate executability score based on task completeness."""
        if not tasks:
            return 0.0

        complete_count = 0
        for task in tasks:
            # Check if task has sufficient description
            if (
                len(task.description) > 50
                and task.verification_type != VerificationType.MANUAL
            ):
                complete_count += 1
            elif len(task.description) > 50:
                # MANUAL verification is acceptable but scores lower
                complete_count += 0.8

        return min(1.0, complete_count / len(tasks))

    def _calculate_verification_coverage(self, tasks: list[Task]) -> float:
        """Calculate verification coverage percentage."""
        if not tasks:
            return 0.0

        verified_count = sum(
            1 for t in tasks if t.verification_type != VerificationType.MANUAL
        )
        return verified_count / len(tasks)

    def _validate_plan(self, plan: ExecutionPlan) -> None:
        """Validate plan meets quality criteria."""
        # Check for circular dependencies
        self._check_circular_dependencies(plan.tasks)

        # Check verification coverage
        if plan.verification_coverage < 1.0:
            # Log warning but don't fail
            print(
                f"[WARNING] Verification coverage is {plan.verification_coverage:.1%}, below 100%"
            )

    def _check_circular_dependencies(self, tasks: list[Task]) -> None:
        """Check for circular dependencies in tasks."""
        task_map = {t.id: t for t in tasks}

        for task in tasks:
            visited = set()
            current = task
            while current and current.id in task_map:
                if current.id in visited:
                    raise ValueError(
                        f"Circular dependency detected at task {current.id}"
                    )
                visited.add(current.id)
                # Follow first dependency
                if current.depends_on and current.depends_on[0] in task_map:
                    current = task_map[current.depends_on[0]]
                else:
                    break

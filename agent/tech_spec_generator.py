"""Tech-Spec generator for v2 Plan-level iteration.

Each Plan gets its own iterative tech spec generation with Builder + Reviewer
dual-agent loop and independent convergence判断.
"""

from pathlib import Path
from typing import Optional

from agent.plan import Plan
from agent.review import ReviewAnalyzer
from agent.subagent import run_subagent


# Prompt templates for Plan-level tech spec
TECH_SPEC_BUILDER_SYSTEM = """You are a technical spec writer for a specific Plan within a larger project.

Your role:
1. Generate detailed technical specifications for ONE specific Plan/feature
2. Write implementation-ready specs that can be executed by Claude Code
3. Focus ONLY on the feature assigned to your Plan, not the entire project

Output format: Write the tech spec to the specified file path.
"""

TECH_SPEC_BUILDER_PROMPT = """
## Plan Information
- Plan ID: {plan_id}
- Feature: {feature}
- Priority: {priority}

## Project Context
{project_context}

## Requirements for this Plan
{plan_requirements}

## Previous Feedback (if any)
{previous_feedback}

## Task
Generate the COMPLETE tech spec for this specific Plan.

The tech spec should include:
1. Implementation approach (detailed, actionable)
2. File structure for this Plan's implementation
3. API design (if applicable)
4. Data models (if applicable)
5. Key implementation details and code snippets
6. Dependencies on other Plans (if any)
7. Acceptance criteria for this Plan

## CRITICAL INSTRUCTIONS
1. Write the COMPLETE tech spec, not an outline
2. Use concrete examples and code snippets
3. Make it actionable - Claude Code should be able to implement directly
4. Do NOT reference other Plans' internals, only their public interfaces

## Output
Write to file: {tech_spec_path}

Use write_file tool to write the complete content.
"""

TECH_SPEC_REVIEWER_SYSTEM = """You review Plan-level technical specifications.

Your role:
1. Verify the spec is implementation-ready
2. Check for completeness and correctness
3. Ensure it meets the Plan's acceptance criteria

Provide clear, actionable feedback.
"""

TECH_SPEC_REVIEWER_PROMPT = """
## Plan Information
- Plan ID: {plan_id}
- Feature: {feature}
- Acceptance Criteria:
{acceptance_criteria}

## Current Tech Spec
{tech_spec}

## Review Checklist

### Completeness
- [ ] All acceptance criteria addressed?
- [ ] Implementation approach is clear?
- [ ] No ambiguities that could block implementation?

### Correctness
- [ ] Technical approach is sound?
- [ ] Dependencies are correctly identified?
- [ ] API/data models are consistent?

### Executability
- [ ] Code snippets are correct and compilable?
- [ ] File structure is implementable?
- [ ] No circular dependencies?

## Output Format
```
评审结果：通过 / 需修改

### 完整性
- [x/ ] 描述
- 需补充：...

### 正确性
- [x/ ] 描述
- 问题：...

### 可执行性
- [x/ ] 描述
- 问题：...

### 改进建议
1. 具体可操作的建议
2. ...
```
"""


class TechSpecGenerator:
    """Generates and iterates on Plan-level tech specs.

    Each Plan goes through its own Builder → Reviewer iteration loop
    with independent convergence (2 consecutive approvals).

    Usage:
        generator = TechSpecGenerator()
        converged, spec = generator.generate_for_plan(
            plan=plan,
            project_context="...",
            requirements="..."
        )
    """

    def __init__(self) -> None:
        """Initialize the generator."""
        self.review_analyzer = ReviewAnalyzer()

    def generate_for_plan(
        self,
        plan: Plan,
        project_dir: Path,
        project_context: str,
        requirements: str,
        previous_feedback: Optional[str] = None,
        max_rounds: int = 5,
        token_tracker=None,
    ) -> tuple[bool, str, int]:
        """Generate tech spec for a specific Plan.

        Args:
            plan: Plan object to generate spec for
            project_dir: Project root directory
            project_context: Project-level context for reference
            requirements: Requirements document content
            previous_feedback: Optional previous review feedback
            max_rounds: Maximum iteration rounds
            token_tracker: Optional token tracker for usage recording

        Returns:
            Tuple of (converged, tech_spec_content, final_round)
        """
        plan_dir = project_dir / "plans" / plan.plan_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        tech_spec_path = plan_dir / f"{plan.plan_id}-tech-spec.md"

        # Extract requirements relevant to this plan (simple keyword match)
        plan_requirements = self._extract_plan_requirements(plan, requirements)

        round_num = 0
        consecutive_approvals = 0
        last_content = ""

        for round_num in range(1, max_rounds + 1):
            # Build prompt
            prompt = TECH_SPEC_BUILDER_PROMPT.format(
                plan_id=plan.plan_id,
                feature=plan.feature,
                priority=plan.priority.value,
                project_context=project_context,
                plan_requirements=plan_requirements,
                previous_feedback=previous_feedback or "Initial generation",
                tech_spec_path=str(tech_spec_path),
            )

            # Run builder via subagent
            result_text, usage = run_subagent(
                prompt=prompt,
                system=TECH_SPEC_BUILDER_SYSTEM,
                token_tracker=token_tracker,
                phase=f"tech-spec-{plan.plan_id}",
                round_num=round_num,
            )

            # Read generated spec
            if tech_spec_path.exists():
                tech_spec_content = tech_spec_path.read_text()
            else:
                tech_spec_content = result_text

            # Verify file was written
            if not tech_spec_path.exists() or len(tech_spec_content) < 200:
                raise RuntimeError(
                    f"Builder failed to write tech spec for {plan.plan_id} to {tech_spec_path}"
                )

            # Run reviewer
            acceptance_criteria_str = "\n".join(
                f"- {c}" for c in plan_requirements.split("\n") if c.strip()
            )

            review_prompt = TECH_SPEC_REVIEWER_PROMPT.format(
                plan_id=plan.plan_id,
                feature=plan.feature,
                acceptance_criteria=acceptance_criteria_str,
                tech_spec=tech_spec_content[:3000],  # Limit for review
            )

            review_result_text, _ = run_subagent(
                prompt=review_prompt,
                system=TECH_SPEC_REVIEWER_SYSTEM,
                token_tracker=token_tracker,
                phase=f"tech-spec-{plan.plan_id}",
                round_num=round_num,
            )

            # Analyze review result
            review_obj = self.review_analyzer.analyze(review_result_text)

            if review_obj.approved:
                consecutive_approvals += 1
                if consecutive_approvals >= 2:
                    # Converged!
                    return True, tech_spec_content, round_num
            else:
                consecutive_approvals = 0
                previous_feedback = review_obj.raw_feedback

        # Did not converge within max_rounds
        return False, tech_spec_content, round_num

    def _extract_plan_requirements(self, plan: Plan, requirements: str) -> str:
        """Extract requirements relevant to a specific plan.

        Uses simple keyword matching to find relevant sections.

        Args:
            plan: Plan object
            requirements: Full requirements document

        Returns:
            Filtered requirements text relevant to this plan
        """
        # Find features that match the plan's feature name
        plan_words = set(plan.feature.lower().split())

        relevant_lines = []
        current_section = []

        for line in requirements.split("\n"):
            # Check if line mentions the plan's feature keywords
            line_lower = line.lower()
            matches = sum(1 for w in plan_words if w in line_lower and len(w) > 2)

            if matches >= 1 and len(plan_words) > 0:
                # This line is relevant
                relevant_lines.extend(current_section)
                relevant_lines.append(line)
                current_section = []
            else:
                # Accumulate potential context
                if line.strip() and not line.startswith("#"):
                    current_section.append(line)
                elif current_section:
                    relevant_lines.extend(current_section[-3:])  # Keep last 3 context lines
                    current_section = []

        if relevant_lines:
            return "\n".join(relevant_lines[:100])  # Limit length

        # Fallback: return first 500 chars of requirements
        return requirements[:500]
"""V2 workflow extensions for Orchestrator.

Adds support for:
- Requirements → Plans → Tech-Spec flow
- Plan-level iteration and tracking
- v2 document structure

Usage:
    from agent.v2_orchestrator import V2Workflow

    v2 = V2Workflow(orchestrator)
    v2.run_plans_phase()
"""

from pathlib import Path
from typing import Optional

from agent.plan import Plan, PlanStage, PlanStatus, Priority
from agent.plan_manager import PlanManager
from agent.plan_splitter import PlanSplitter, SplittedPlan
from agent.plan_compact import PlanContextCompressor
from agent.tech_spec_generator import TechSpecGenerator
from agent.readme_generator import ReadmeGenerator
from agent.review import ReviewAnalyzer
from agent.plan_reviewer_prompts import PLAN_REVIEWER_SYSTEM, PLAN_REVIEWER_PROMPT


class V2WorkflowError(Exception):
    """Error in v2 workflow."""
    pass


class V2Workflow:
    """V2 specific workflow extensions for the Orchestrator.

    This class encapsulates v2-specific operations while delegating
    to the main Orchestrator for core functionality.
    """

    def __init__(self, orchestrator) -> None:
        """Initialize with parent orchestrator reference.

        Args:
            orchestrator: Parent Orchestrator instance
        """
        self.orch = orchestrator
        self.logger = orchestrator.logger
        self.state = orchestrator.state
        self.project_dir = orchestrator.project_dir

        # Initialize v2 components
        self.plan_manager = PlanManager(orchestrator.state_dir)
        self.plan_splitter = PlanSplitter()
        self.plan_compressor = PlanContextCompressor(orchestrator.project_dir)
        self.tech_spec_generator = TechSpecGenerator()
        self.readme_generator = ReadmeGenerator()
        self.review_analyzer = ReviewAnalyzer()

    def run_plans_phase(self) -> None:
        """Run the full v2 Plans phase.

        Flow: Requirements → Plans → Tech-Spec for each Plan → README

        This is the main entry point for v2 plan-based workflow.
        """
        self.logger.log("=" * 60)
        self.logger.log("  V2 PLANS PHASE")
        self.logger.log("=" * 60)

        # Step 1: Load requirements
        req_path = self.project_dir / "requirements.md"
        if not req_path.exists():
            raise V2WorkflowError("requirements.md not found")

        requirements = req_path.read_text()
        self.logger.log(f"Loaded requirements: {len(requirements)} chars")

        # Step 2: Split requirements into Plans
        self.logger.log("\n[1/5] Splitting requirements into Plans...")
        existing_plans = self.plan_manager.load_plans()
        splitted = self.plan_splitter.split(requirements, existing_plans)

        # Step 3: Plan Review — verify split quality
        self.logger.log(f"\n[2/5] Reviewing Plan split ({len(splitted)} plans)...")
        splitted = self._review_plan_split(requirements, splitted, existing_plans)

        # Step 4: Convert splitted plans to Plan objects and save
        self.logger.log(f"\n[3/5] Creating {len(splitted)} Plans...")
        plans = self._create_plans_from_splitted(splitted, existing_plans)

        # Step 5: Generate Tech-Spec for each Plan
        self.logger.log(f"\n[4/5] Generating Tech-Spec for each Plan...")
        self._generate_tech_specs_for_plans(plans, requirements)

        # Step 6: Update README
        self.logger.log("\n[5/5] Updating README...")
        self.readme_generator.update_readme(self.project_dir, plans)

        self.logger.log("\n✅ Plans phase complete!")
        self.logger.log(f"   Created {len(plans)} Plans")
        self.logger.log(f"   README updated at: {self.project_dir / 'README.md'}")

    def _review_plan_split(
        self,
        requirements: str,
        splitted: list[SplittedPlan],
        existing_plans: list[Plan],
        max_rounds: int = 3,
    ) -> list[SplittedPlan]:
        """Review and iterate on Plan splitting quality.

        Runs the Plan Reviewer against the split results. If reviewer
        identifies gaps or overlaps, attempts re-split with LLM feedback.
        Iterates until convergence or max_rounds.

        Returns:
            Validated list of SplittedPlan objects
        """
        from agent.subagent import run_subagent

        consecutive_approvals = 0
        previous_feedback = None
        re_split_attempts = 0

        for round_num in range(1, max_rounds + 1):
            # Build plans summary for reviewer
            plans_text = self._format_plans_for_review(splitted)

            # Run plan reviewer
            prompt = PLAN_REVIEWER_PROMPT.format(
                seed=self.orch.state.seed,
                requirements=requirements[:3000],  # Limit for review
                plans_list=plans_text,
            )

            self.logger.log(f"    Plan Review Round {round_num}/{max_rounds}...")
            result_text, _ = run_subagent(
                prompt=prompt,
                system=PLAN_REVIEWER_SYSTEM,
                max_tokens=4000,
                phase="plan-review",
                round_num=round_num,
            )

            # Analyze result
            review = self.review_analyzer.analyze(result_text)

            if review.approved:
                consecutive_approvals += 1
                self.logger.log(f"      ✅ Plan review APPROVED ({consecutive_approvals}/2)")
                if consecutive_approvals >= 2:
                    break
            else:
                consecutive_approvals = 0
                self.logger.log(f"      ❌ Plan review: NEEDS WORK")
                previous_feedback = review.raw_feedback

                # LLM re-split (max 2 attempts total)
                if re_split_attempts < 2:
                    try:
                        re_split_prompt = self.plan_splitter.generate_split_prompt(
                            requirements, existing_plans
                        )
                        re_split_prompt += f"\n\n## Previous Review Feedback\n{previous_feedback}\n\nPlease re-split addressing the feedback above."

                        new_summary, _ = run_subagent(
                            prompt=re_split_prompt,
                            system="You are a Plan Split expert. Output a JSON array of plans.",
                            max_tokens=4000,
                            phase="plan-re-split",
                            round_num=round_num,
                        )
                        # Parse new plans from LLM output
                        new_splitted = self._parse_llm_plans(new_summary, existing_plans)
                        re_split_attempts += 1
                        if new_splitted:
                            splitted = new_splitted
                            self.logger.log(f"      → Re-split into {len(splitted)} plans")
                    except Exception as e:
                            self.logger.log(f"      ⚠️ Re-split failed: {e}, keeping original split")

        # Final validation warning
        if consecutive_approvals < 2:
            self.logger.log(f"    ⚠️ Plan review did not converge, proceeding with {len(splitted)} plans")

        return splitted

    def _format_plans_for_review(self, splitted: list) -> str:
        """Format splitted plans as text for reviewer."""
        lines = []
        for i, sp in enumerate(splitted, 1):
            lines.append(f"Plan {i}: {sp.feature} [{sp.priority.value}]")
            if sp.description:
                lines.append(f"  描述: {sp.description[:150]}")
            if sp.acceptance_criteria:
                lines.append(f"  验收: {len(sp.acceptance_criteria)} criteria")
            if sp.depends_on:
                lines.append(f"  依赖: {', '.join(sp.depends_on)}")
        return "\n".join(lines)

    def _parse_llm_plans(self, text: str, existing: list) -> list:
        """Parse LLM-generated plan list from JSON in text."""
        import json, re
        # Try to find JSON array in the response
        m = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(0))
                return [
                    SplittedPlan(
                        feature=p.get("feature", p.get("name", "Unknown")),
                        description=p.get("description", ""),
                        priority=Priority(p.get("priority", "P1")),
                        depends_on=p.get("depends_on", []),
                        acceptance_criteria=p.get("acceptance_criteria", []),
                        tasks=p.get("tasks", []),
                    )
                    for p in data
                ]
            except (json.JSONDecodeError, ValueError):
                pass
        return []  # Fallback: keep original split


    def _create_plans_from_splitted(
        self,
        splitted_plans: list[SplittedPlan],
        existing_plans: list[Plan],
    ) -> list[Plan]:
        """Convert SplittedPlan objects to Plan objects and save.

        Args:
            splitted_plans: List of SplittedPlan from splitter
            existing_plans: Existing plans for context

        Returns:
            List of created Plan objects
        """
        plans = list(existing_plans)
        plan_id_counter = len(existing_plans)

        for sp in splitted_plans:
            plan_id_counter += 1
            plan_id = f"plan-{plan_id_counter:03d}"

            # Check if similar plan already exists
            existing_ids = [p.plan_id for p in plans]
            if any(sp.feature.lower() in p.feature.lower() for p in plans):
                self.logger.log(f"  Skipping duplicate: {sp.feature}")
                continue

            # Create new plan
            plan = Plan(
                plan_id=plan_id,
                feature=sp.feature,
                priority=sp.priority,
                depends_on=sp.depends_on,
                summary=f"P0={sp.priority.value}, {len(sp.acceptance_criteria)} criteria",
            )
            plan.tech_spec_path = str(
                self.project_dir / "plans" / plan_id / f"{plan_id}-tech-spec.md"
            )

            plans.append(plan)
            self.logger.log(f"  Created: {plan_id} - {sp.feature}")

        # Save all plans
        self.plan_manager.save_plans(plans)

        return plans

    def _generate_tech_specs_for_plans(
        self,
        plans: list[Plan],
        requirements: str,
    ) -> None:
        """Generate tech spec for each plan.

        Args:
            plans: List of Plan objects
            requirements: Full requirements document
        """
        project_context = self._generate_project_context(plans)

        for plan in plans:
            self.logger.log(f"\n  Processing: {plan.plan_id} - {plan.feature}")

            # Check if tech spec already exists and is valid
            tech_spec_path = Path(plan.tech_spec_path or "")
            if tech_spec_path.exists() and tech_spec_path.stat().st_size > 500:
                self.logger.log(f"    Tech spec already exists, skipping")
                continue

            try:
                converged, spec, rounds = self.tech_spec_generator.generate_for_plan(
                    plan=plan,
                    project_dir=self.project_dir,
                    project_context=project_context,
                    requirements=requirements,
                    token_tracker=getattr(self.orch, 'token_tracker', None),
                    max_rounds=3,  # Quick rounds for tech spec
                )

                plan.summary = f"Tech spec: {rounds} rounds, converged={converged}"
                self.logger.log(
                    f"    Tech spec: {rounds} rounds, converged={converged}"
                )

            except Exception as e:
                self.logger.log(f"    ⚠️ Tech spec generation failed: {e}")
                plan.summary = f"Tech spec failed: {e}"

        # Save plans with updated summaries
        self.plan_manager.save_plans(plans)

    def _generate_project_context(self, plans: list[Plan]) -> str:
        """Generate project context string for tech spec prompts.

        Args:
            plans: List of Plan objects

        Returns:
            Project context string
        """
        lines = [
            f"Project: {self.project_dir.name}",
            f"Total Plans: {len(plans)}",
            "",
            "Existing Plans:",
        ]

        for plan in plans:
            deps = f" (depends on: {', '.join(plan.depends_on)})" if plan.depends_on else ""
            lines.append(
                f"  - {plan.plan_id}: {plan.feature} [{plan.priority.value}]{deps}"
            )

        return "\n".join(lines)

    def add_plan_from_idea(self, idea: str, priority: Priority = Priority.P1) -> Plan:
        """Add a new plan from an idea string.

        Args:
            idea: Feature description
            priority: Plan priority

        Returns:
            Created Plan object
        """
        plans = self.plan_manager.load_plans()

        # Analyze append strategy
        strategy, affected = self.plan_manager.resolve_append(idea, plans)

        # Create new plan
        plan = Plan.create(idea, priority)

        if strategy == "depends_on" and affected:
            plan.depends_on.extend(affected)

        self.plan_manager.add_plan(plan, plans)

        # Update README
        plans = self.plan_manager.load_plans()
        self.readme_generator.update_readme(self.project_dir, plans)

        return plan

    def update_plan_status(
        self,
        plan_id: str,
        stage: Optional[PlanStage] = None,
        status: Optional[PlanStatus] = None,
    ) -> None:
        """Update a plan's stage and/or status.

        Args:
            plan_id: Plan to update
            stage: New stage (optional)
            status: New status (optional)
        """
        if stage:
            self.plan_manager.update_plan_stage(plan_id, stage)

        if status:
            self.plan_manager.update_plan_status(plan_id, status)

        # Update README after status change
        plans = self.plan_manager.load_plans()
        self.readme_generator.update_readme(self.project_dir, plans)

    def get_plan_summary(self, plan_id: str) -> dict:
        """Get a summary of plan progress.

        Args:
            plan_id: Plan identifier

        Returns:
            Dict with plan info and progress
        """
        plans = self.plan_manager.load_plans()
        plan = self.plan_manager.get_plan(plan_id, plans)

        if not plan:
            return {"error": f"Plan {plan_id} not found"}

        return {
            "plan_id": plan.plan_id,
            "feature": plan.feature,
            "priority": plan.priority.value,
            "stage": plan.stage.value,
            "status": plan.status.value,
            "depends_on": plan.depends_on,
            "tech_spec_exists": Path(plan.tech_spec_path).exists()
            if plan.tech_spec_path
            else False,
            "summary": plan.summary,
        }
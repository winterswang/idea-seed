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
        self.logger.log("\n[1/4] Splitting requirements into Plans...")
        existing_plans = self.plan_manager.load_plans()
        splitted = self.plan_splitter.split(requirements, existing_plans)

        # Step 3: Convert splitted plans to Plan objects and save
        self.logger.log(f"\n[2/4] Creating {len(splitted)} Plans...")
        plans = self._create_plans_from_splitted(splitted, existing_plans)

        # Step 4: Generate Tech-Spec for each Plan
        self.logger.log(f"\n[3/4] Generating Tech-Spec for each Plan...")
        self._generate_tech_specs_for_plans(plans, requirements)

        # Step 5: Update README
        self.logger.log("\n[4/4] Updating README...")
        self.readme_generator.update_readme(self.project_dir, plans)

        self.logger.log("\n✅ Plans phase complete!")
        self.logger.log(f"   Created {len(plans)} Plans")
        self.logger.log(f"   README updated at: {self.project_dir / 'README.md'}")

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
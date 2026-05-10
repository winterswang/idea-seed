"""PlanManager - CRUD operations for plans.json with cycle detection and incremental logic."""

import json
from pathlib import Path
from typing import Optional

from agent.plan import Plan, PlanStage, PlanStatus


class PlanManagerError(Exception):
    """Base exception for PlanManager errors."""
    pass


class CycleDetectedError(PlanManagerError):
    """Raised when a dependency cycle is detected."""
    pass


class PlanNotFoundError(PlanManagerError):
    """Raised when a referenced plan does not exist."""
    pass


class PlanManager:
    """Manages plans.json for v2 iterative project management.

    Provides CRUD operations for plans, state updates, and dependency
    management with cycle detection.

    Usage:
        pm = PlanManager(project_dir / ".state")
        plans = pm.loadPlans()
        pm.add_plan(Plan.create("New feature"))
        pm.savePlans(plans)
    """

    PLANS_FILE = "plans.json"

    def __init__(self, state_dir: Path) -> None:
        """Initialize PlanManager.

        Args:
            state_dir: Path to .state directory (contains plans.json)
        """
        self.state_dir = Path(state_dir)
        self.plans_file = self.state_dir / self.PLANS_FILE

    def load_plans(self) -> list[Plan]:
        """Load plans from plans.json.

        Returns:
            List of Plan objects, empty list if file doesn't exist
        """
        if not self.plans_file.exists():
            return []

        try:
            with open(self.plans_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Plan.from_dict(p) for p in data.get("plans", [])]
        except (json.JSONDecodeError, KeyError) as e:
            raise PlanManagerError(f"Failed to parse plans.json: {e}") from e

    def save_plans(self, plans: list[Plan]) -> None:
        """Save plans to plans.json.

        Args:
            plans: List of Plan objects to save

        Raises:
            CycleDetectedError: If dependency cycle detected
            PlanNotFoundError: If referenced plan doesn't exist
        """
        self._validate_plans(plans)

        data = {"plans": [p.to_dict() for p in plans]}
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Write atomically: temp file then rename
        temp_file = self.plans_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_file.rename(self.plans_file)

    def _validate_plans(self, plans: list[Plan]) -> None:
        """Validate plan list for cycles and referential integrity.

        Args:
            plans: List of plans to validate

        Raises:
            CycleDetectedError: If cycle detected
            PlanNotFoundError: If referenced plan doesn't exist
        """
        plan_ids = {p.plan_id for p in plans}
        plan_map = {p.plan_id: p for p in plans}

        for plan in plans:
            # Check depends_on references
            for dep_id in plan.depends_on:
                if dep_id not in plan_ids:
                    raise PlanNotFoundError(
                        f"Plan {plan.plan_id} depends on non-existent plan {dep_id}"
                    )

            # Check blocks references
            for blocked_id in plan.blocks:
                if blocked_id not in plan_ids:
                    raise PlanNotFoundError(
                        f"Plan {plan.plan_id} blocks non-existent plan {blocked_id}"
                    )

        # Detect cycles using DFS
        self._detect_cycles(plans)

    def _detect_cycles(self, plans: list[Plan]) -> None:
        """Detect dependency cycles in plan graph.

        Args:
            plans: List of plans to check

        Raises:
            CycleDetectedError: If cycle detected
        """
        plan_map = {p.plan_id: p for p in plans}

        def dfs(plan_id: str, visiting: set[str], path: list[str]) -> None:
            if plan_id in visiting:
                cycle_start = path.index(plan_id)
                cycle = path[cycle_start:] + [plan_id]
                raise CycleDetectedError(
                    f"Dependency cycle detected: {' -> '.join(cycle)}"
                )

            visiting.add(plan_id)
            path.append(plan_id)

            plan = plan_map.get(plan_id)
            if plan:
                for dep_id in plan.depends_on:
                    dfs(dep_id, visiting, path.copy())

        for plan in plans:
            dfs(plan.plan_id, set(), [])

    def add_plan(self, plan: Plan, plans: Optional[list[Plan]] = None) -> list[Plan]:
        """Add a new plan to the list.

        Args:
            plan: Plan to add
            plans: Existing plans list (loads from file if None)

        Returns:
            Updated plans list

        Raises:
            CycleDetectedError: If adding would create cycle
            PlanNotFoundError: If depends_on reference doesn't exist
        """
        if plans is None:
            plans = self.load_plans()

        plans.append(plan)
        self._validate_plans(plans)
        self.save_plans(plans)
        return plans

    def get_plan(self, plan_id: str, plans: Optional[list[Plan]] = None) -> Optional[Plan]:
        """Get a plan by ID.

        Args:
            plan_id: Plan ID to find
            plans: Plans list to search (loads from file if None)

        Returns:
            Plan if found, None otherwise
        """
        if plans is None:
            plans = self.load_plans()
        for plan in plans:
            if plan.plan_id == plan_id:
                return plan
        return None

    def update_plan(self, plan_id: str, updater: callable, plans: Optional[list[Plan]] = None) -> list[Plan]:
        """Update a plan using an updater function.

        Args:
            plan_id: ID of plan to update
            updater: Function that takes Plan and returns modified Plan
            plans: Existing plans list (loads from file if None)

        Returns:
            Updated plans list

        Raises:
            PlanNotFoundError: If plan_id not found
        """
        if plans is None:
            plans = self.load_plans()

        for i, plan in enumerate(plans):
            if plan.plan_id == plan_id:
                plans[i] = updater(plan)
                self._validate_plans(plans)
                self.save_plans(plans)
                return plans

        raise PlanNotFoundError(f"Plan {plan_id} not found")

    def update_plan_stage(self, plan_id: str, stage: PlanStage) -> None:
        """Update a plan's stage.

        Args:
            plan_id: Plan ID
            stage: New stage
        """
        plans = self.load_plans()
        self.update_plan(
            plan_id,
            lambda p: (p.update_stage(stage), p)[1],
            plans
        )

    def update_plan_status(self, plan_id: str, status: PlanStatus) -> None:
        """Update a plan's status.

        Args:
            plan_id: Plan ID
            status: New status
        """
        plans = self.load_plans()
        self.update_plan(
            plan_id,
            lambda p: (p.update_status(status), p)[1],
            plans
        )

    def remove_plan(self, plan_id: str) -> list[Plan]:
        """Remove a plan from the list.

        Args:
            plan_id: Plan ID to remove

        Returns:
            Updated plans list

        Raises:
            PlanNotFoundError: If plan_id not found
        """
        plans = self.load_plans()
        original_len = len(plans)
        plans = [p for p in plans if p.plan_id != plan_id]

        if len(plans) == original_len:
            raise PlanNotFoundError(f"Plan {plan_id} not found")

        # Remove from other plans' depends_on and blocks lists
        for plan in plans:
            if plan_id in plan.depends_on:
                plan.depends_on.remove(plan_id)
            if plan_id in plan.blocks:
                plan.blocks.remove(plan_id)

        self._validate_plans(plans)
        self.save_plans(plans)
        return plans

    def get_ready_plans(self, plans: Optional[list[Plan]] = None) -> list[Plan]:
        """Get plans that are ready to execute (not blocked by pending plans).

        Args:
            plans: Plans list to check (loads from file if None)

        Returns:
            List of plans ready for execution
        """
        if plans is None:
            plans = self.load_plans()

        ready = []
        for plan in plans:
            if plan.status != PlanStatus.PENDING:
                continue

            # Check if all dependencies are done
            blocked = False
            for dep_id in plan.depends_on:
                dep = self.get_plan(dep_id, plans)
                if dep and dep.status != PlanStatus.DONE:
                    blocked = True
                    break

            if not blocked:
                ready.append(plan)

        return ready

    def get_blocked_plans(self, plans: Optional[list[Plan]] = None) -> list[tuple[Plan, list[str]]]:
        """Get plans that are blocked by pending dependencies.

        Args:
            plans: Plans list to check (loads from file if None)

        Returns:
            List of (plan, list of blocker plan_ids) tuples
        """
        if plans is None:
            plans = self.load_plans()

        blocked = []
        for plan in plans:
            if plan.status not in (PlanStatus.PENDING, PlanStatus.IN_PROGRESS):
                continue

            blockers = []
            for dep_id in plan.depends_on:
                dep = self.get_plan(dep_id, plans)
                if dep and dep.status != PlanStatus.DONE:
                    blockers.append(dep_id)

            if blockers:
                blocked.append((plan, blockers))

        return blocked

    def resolve_append(
        self,
        new_feature: str,
        existing_plans: Optional[list[Plan]] = None
    ) -> tuple[str, list[str]]:
        """Determine how to append a new feature.

        Analyzes the new feature against existing plans to determine:
        - Whether it's completely independent (new plan)
        - Whether it depends on existing plans
        - Whether it modifies existing plans (mark as superseded)

        Args:
            new_feature: Description of new feature
            existing_plans: Existing plans (loads from file if None)

        Returns:
            Tuple of (strategy, affected_plan_ids)
            strategy: "new" | "depends_on" | "supersedes" | "conflict"
            affected_plan_ids: List of plan IDs affected

        Note:
            This is a simplified heuristic. Real decision may need AI.
        """
        if existing_plans is None:
            existing_plans = self.load_plans()

        # Check for direct keyword matches (simple heuristic)
        new_lower = new_feature.lower()
        for plan in existing_plans:
            # If feature keywords overlap significantly, might be related
            existing_words = set(plan.feature.lower().split())
            new_words = set(new_lower.split())
            overlap = existing_words & new_words

            if len(overlap) >= 2 and len(overlap) / len(new_words) > 0.5:
                # Likely related - suggest depends_on
                return ("depends_on", [plan.plan_id])

        # Check for conflict (same feature name)
        for plan in existing_plans:
            if plan.feature.lower() == new_lower:
                return ("supersedes", [plan.plan_id])

        return ("new", [])
"""Requirements → Plans splitter for v2 iterative project management.

Analyzes requirements document and splits into independent Plans based on
functional modules with dependency analysis.
"""

import re
from dataclasses import dataclass
from typing import Optional

from agent.plan import Plan, Priority


@dataclass
class SplittedPlan:
    """Result of splitting requirements into a plan."""
    feature: str  # Brief feature name
    description: str  # What this plan covers
    priority: Priority
    depends_on: list[str]  # Plan IDs this depends on
    acceptance_criteria: list[str]  # Extracted from requirements
    tasks: list[str]  # Task list for this plan


class PlanSplitterError(Exception):
    """Error during plan splitting."""
    pass


class PlanSplitter:
    """Splits requirements document into Plans based on functional modules.

    Usage:
        splitter = PlanSplitter()
        plans = splitter.split(requirements_text, existing_plans=None)
    """

    def __init__(self) -> None:
        """Initialize plan splitter."""
        pass

    def split(self, requirements: str, existing_plans: Optional[list[Plan]] = None) -> list[SplittedPlan]:
        """Split requirements into Plans.

        Args:
            requirements: Requirements document text
            existing_plans: Optional existing plans for incremental mode

        Returns:
            List of SplittedPlan objects ready for Plan creation

        Raises:
            PlanSplitterError: If requirements cannot be parsed
        """
        if existing_plans is None:
            existing_plans = []

        # Extract features from requirements
        features = self._extract_features(requirements)

        if not features:
            raise PlanSplitterError("No features found in requirements document")

        # Group related requirements into plans
        plans = self._create_plans(features, existing_plans)

        return plans

    def _extract_features(self, requirements: str) -> list[dict]:
        """Extract features from requirements document.

        Args:
            requirements: Raw requirements text

        Returns:
            List of feature dicts with name, description, priority, criteria
        """
        features = []

        # Skip these sections (not features)
        skip_sections = {
            "项目概述", "数据需求", "非功能需求",
            "Out of Scope", "任务清单", "目录",
            "项目简介", "背景", "目标", "成功标准", "目标用户",
            "功能描述", "功能详细说明",
            "详细说明", "接口设计", "数据模型", "需求文档"
        }
        # Skip headers containing these
        skip_containing = {"功能需求", "数据需求", "非功能需求", "成功标准"}

        # Feature patterns (in priority order):
        # 1. ### Feature: Name or #### Feature: Name (explicit)
        # 2. #### 2.1.1 Name (numbered subsection = feature under 功能需求)
        feature_pattern = re.compile(
            r"^(#{3,4})\s*"                           # 3 or 4 #s
            r"(?:(?:Feature|feature|功能点)[:：]?\s*)?" # optional keyword
            r"[\d\.：:、]+\s*"                        # number like 2.1.1 or 1
            r"(.+)$"                                  # feature name
        )

        current_feature = None
        current_criteria = []
        current_tasks = []
        in_task_section = False
        in_feature_section = False  # True when inside 功能需求 section

        for line in requirements.split("\n"):
            line = line.rstrip()

            # Check if this is a header line
            stripped = line.strip()
            is_header = stripped.startswith("#")

            # Track which section we're in
            if is_header and "功能需求" in stripped:
                in_feature_section = True
            elif is_header and (stripped.startswith("# 1") or stripped.startswith("# 2") or "概述" in stripped):
                in_feature_section = False

            # Check for task section
            if is_header:
                for skip in skip_containing:
                    if skip in stripped:
                        in_task_section = "任务清单" in stripped or "Task" in stripped
                        break

                for skip in skip_sections:
                    if stripped == f"# {skip}" or stripped == f"## {skip}" or stripped == f"### {skip}":
                        in_task_section = "任务清单" in stripped or "Task" in stripped
                        break

            # Match feature header
            match = feature_pattern.match(stripped)
            if match and in_feature_section:
                level = match.group(1)  # ### or ####
                feature_name = match.group(2).strip()

                # Skip if name is in skip_sections
                if feature_name in skip_sections:
                    continue

                # Remove any trailing :：from name
                feature_name = re.sub(r'[\s:：:、]+$', '', feature_name)

                if feature_name:
                    # Save previous feature
                    if current_feature:
                        current_feature["acceptance_criteria"] = current_criteria
                        current_feature["tasks"] = current_tasks
                        features.append(current_feature)

                    # Start new feature
                    current_feature = {
                        "name": feature_name,
                        "description": "",
                        "priority": Priority.P1,
                        "acceptance_criteria": [],
                        "tasks": [],
                    }
                    current_criteria = []
                    current_tasks = []
                    in_task_section = False
                continue

            # Look for priority indicators
            if current_feature:
                # Priority: P0 or 优先级：P0
                if re.search(r"优先级\s*[:：]\s*P0", line, re.IGNORECASE):
                    current_feature["priority"] = Priority.P0
                elif re.search(r"优先级\s*[:：]\s*P1", line, re.IGNORECASE):
                    current_feature["priority"] = Priority.P1
                elif re.search(r"优先级\s*[:：]\s*P2", line, re.IGNORECASE):
                    current_feature["priority"] = Priority.P2

                # Look for acceptance criteria checkboxes
                if re.search(r"^\s*[-*]\s*\[\s*[x ]?\]", line, re.IGNORECASE):
                    match = re.search(r"\[\s*[x ]?\]\s*(.+)", line, re.IGNORECASE)
                    if match:
                        current_criteria.append(match.group(1).strip())

                # Look for task items (in task list section)
                if in_task_section:
                    task_match = re.match(r"^\s*(?:\d+\.|[-*])\s*(.+)", line)
                    if task_match and line.strip():
                        current_tasks.append(task_match.group(1).strip())

                # Accumulate description (non-header, non-criteria lines)
                if line and not line.startswith("#") and "[" not in line:
                    current_feature["description"] += " " + line

        # Save last feature
        if current_feature:
            current_feature["acceptance_criteria"] = current_criteria
            current_feature["tasks"] = current_tasks
            features.append(current_feature)

        return features

    def _create_plans(self, features: list[dict], existing_plans: list[Plan]) -> list[SplittedPlan]:
        """Create Plans from extracted features with dependency analysis.

        Args:
            features: Extracted features
            existing_plans: Existing plans for dependency check

        Returns:
            List of SplittedPlan objects
        """
        plans = []
        feature_to_plan_id = {}

        for i, feat in enumerate(features):
            plan_id = f"plan-{i+1:03d}"

            # Analyze dependencies on previous plans
            depends_on = self._analyze_dependencies(feat, plans, existing_plans)

            # Create splitted plan
            sp = SplittedPlan(
                feature=feat["name"],
                description=feat["description"].strip(),
                priority=feat["priority"],
                depends_on=depends_on,
                acceptance_criteria=feat["acceptance_criteria"],
                tasks=feat["tasks"],
            )
            plans.append(sp)
            feature_to_plan_id[feat["name"]] = plan_id

        return plans

    def _analyze_dependencies(
        self,
        feature: dict,
        previous_plans: list[SplittedPlan],
        existing_plans: list[Plan]
    ) -> list[str]:
        """Analyze which plans this feature depends on.

        Args:
            feature: Current feature dict
            previous_plans: Plans created so far
            existing_plans: Existing plans from file

        Returns:
            List of plan IDs this feature depends on
        """
        deps = []

        # Check against previous plans in this batch
        feature_lower = feature["name"].lower()
        for prev_plan in previous_plans:
            prev_lower = prev_plan.feature.lower()
            # Simple keyword matching
            shared = set(feature_lower.split()) & set(prev_lower.split())
            if len(shared) >= 2:
                # Likely related - mark as dependency
                plan_id = f"plan-{previous_plans.index(prev_plan)+1:03d}"
                deps.append(plan_id)

        # Check against existing plans
        for existing in existing_plans:
            existing_lower = existing.feature.lower()
            shared = set(feature_lower.split()) & set(existing_lower.split())
            if len(shared) >= 2 and len(shared) / len(set(feature_lower.split())) > 0.4:
                deps.append(existing.plan_id)

        return list(set(deps))  # Deduplicate

    def generate_split_prompt(self, requirements: str, existing_plans: Optional[list[Plan]] = None) -> str:
        """Generate the prompt for AI-based splitting.

        This is used when simple regex extraction is insufficient and
        we need AI to properly analyze and split requirements.

        Args:
            requirements: Requirements document text
            existing_plans: Optional existing plans

        Returns:
            Formatted prompt string for AI splitting
        """
        existing_info = ""
        if existing_plans:
            existing_info = "## Existing Plans (do not duplicate)\n"
            for p in existing_plans:
                existing_info += f"- {p.plan_id}: {p.feature} (status: {p.status.value})\n"

        return f"""## Task: Split Requirements into Plans

Analyze the following requirements document and split it into independent Plans.
Each Plan should be a self-contained feature that can be developed and verified independently.

{existing_info}

## Requirements Document
```
{requirements}
```

## Output Format
Return a JSON array of plans:
```json
[
  {{
    "feature": "Brief feature name",
    "description": "What this plan covers",
    "priority": "P0|P1|P2|P3",
    "depends_on": ["plan-id or empty array"],
    "acceptance_criteria": ["criterion 1", "criterion 2"],
    "tasks": ["task 1", "task 2"]
  }}
]
```

## Rules
1. Each feature = one Plan
2. Plans should be independent (minimize depends_on)
3. P0 = must have, P1 = should have, P2 = nice to have, P3 = future
4. If a plan needs output from another plan, add it to depends_on
5. Extract concrete acceptance criteria from the requirements
"""
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
    feature: str
    description: str
    priority: Priority
    depends_on: list[str]
    acceptance_criteria: list[str]
    tasks: list[str]


class PlanSplitterError(Exception):
    """Error during plan splitting."""
    pass


class PlanSplitter:
    """Splits requirements document into Plans based on functional modules.

    Extracts individual features (#### F1: Name) under 功能需求 section.
    Falls back to ### numbered headings if no F-pattern features exist.
    """

    def __init__(self) -> None:
        pass

    def split(self, requirements: str, existing_plans: Optional[list[Plan]] = None) -> list[SplittedPlan]:
        if existing_plans is None:
            existing_plans = []
        features = self._extract_features(requirements)
        if not features:
            raise PlanSplitterError("No features found in requirements document")
        return self._create_plans(features, existing_plans)

    def _extract_features(self, requirements: str) -> list[dict]:
        """Extract F-pattern features (#### F1: Name) under 功能需求.

        Falls back to ### numbered headings if no F-pattern found.
        """
        features: list[dict] = []

        # Primary pattern: #### F1: Feature Name inside 功能需求
        f_pattern = re.compile(
            r"^####\s+"
            r"F\d+\s*[:：]\s*"
            r"(.+)$"
        )

        # Fallback pattern: ### N.XX Name inside 功能需求
        fallback_pattern = re.compile(
            r"^###\s+"
            r"[\d\.]+\s+"
            r"(.+)$"
        )

        skip_sections = {
            "项目概述", "数据需求", "非功能需求", "Out of Scope",
            "任务清单", "目录", "附录", "核心功能", "用户界面功能",
        }

        current_feature = None
        current_criteria: list[str] = []
        current_tasks: list[str] = []
        in_task_section = False
        in_feature_section = False
        pattern = f_pattern  # default
        has_f_features = self._has_f_pattern(requirements)

        if has_f_features:
            pattern = f_pattern
        else:
            pattern = fallback_pattern

        for line in requirements.split("\n"):
            stripped = line.strip()
            is_header = stripped.startswith("#")

            # Section tracking: enter 功能需求, exit on next ## or # heading
            if is_header and "功能需求" in stripped and "非功能需求" not in stripped and "##" in stripped[:3]:
                in_feature_section = True
            elif is_header and (stripped.startswith("## ") or stripped.startswith("# ")):
                if "功能需求" not in stripped:
                    in_feature_section = False

            # Detect task section
            if is_header and ("任务清单" in stripped or "Task" in stripped):
                in_task_section = True
            elif is_header and stripped.startswith("## "):
                in_task_section = False

            # Match feature header
            match = pattern.match(stripped)
            if match and in_feature_section:
                feature_name = match.group(1).strip()
                feature_name = re.sub(r'[\s:：、]+$', '', feature_name)

                if feature_name and feature_name not in skip_sections:
                    # Save previous feature
                    if current_feature:
                        current_feature["acceptance_criteria"] = current_criteria
                        current_feature["tasks"] = current_tasks
                        features.append(current_feature)

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

            if current_feature:
                # Priority detection
                if re.search(r"优先级\s*[:：]\s*P0", line, re.IGNORECASE):
                    current_feature["priority"] = Priority.P0
                elif re.search(r"优先级\s*[:：]\s*P2", line, re.IGNORECASE):
                    current_feature["priority"] = Priority.P2

                # Acceptance criteria checkboxes
                if re.search(r"^\s*[-*]\s*\[\s*[x ]?\]", line, re.IGNORECASE):
                    m = re.search(r"\[\s*[x ]?\]\s*(.+)", line, re.IGNORECASE)
                    if m:
                        current_criteria.append(m.group(1).strip())

                # Task items
                if in_task_section:
                    task_match = re.match(r"^\s*(?:\d+\.|[-*])\s*(.+)", line)
                    if task_match and line.strip():
                        current_tasks.append(task_match.group(1).strip())

                # Accumulate description
                if line and not line.startswith("#") and "[" not in line:
                    current_feature["description"] += " " + line

        if current_feature:
            current_feature["acceptance_criteria"] = current_criteria
            current_feature["tasks"] = current_tasks
            features.append(current_feature)

        return features

    def _has_f_pattern(self, requirements: str) -> bool:
        """Check if requirements doc uses F1:, F2: feature naming."""
        return bool(re.search(r"^####\s+F\d+\s*[:：]", requirements, re.MULTILINE))

    def _create_plans(self, features: list[dict], existing_plans: list[Plan]) -> list[SplittedPlan]:
        plans: list[SplittedPlan] = []
        for feat in features:
            depends_on = self._analyze_dependencies(feat, plans, existing_plans)
            plans.append(SplittedPlan(
                feature=feat["name"],
                description=feat["description"].strip(),
                priority=feat["priority"],
                depends_on=depends_on,
                acceptance_criteria=feat["acceptance_criteria"],
                tasks=feat["tasks"],
            ))
        return plans

    def _analyze_dependencies(
        self, feature: dict, previous_plans: list[SplittedPlan],
        existing_plans: list[Plan]
    ) -> list[str]:
        deps: list[str] = []
        feature_lower = feature["name"].lower()
        for i, pp in enumerate(previous_plans):
            shared = set(feature_lower.split()) & set(pp.feature.lower().split())
            if len(shared) >= 2:
                deps.append(f"plan-{i+1:03d}")
        for ep in existing_plans:
            shared = set(feature_lower.split()) & set(ep.feature.lower().split())
            if len(shared) >= 2 and len(shared) / len(set(feature_lower.split())) > 0.4:
                deps.append(ep.plan_id)
        return list(set(deps))

    def generate_split_prompt(self, requirements: str, existing_plans: Optional[list[Plan]] = None) -> str:
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

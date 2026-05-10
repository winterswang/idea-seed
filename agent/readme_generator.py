"""README auto-generator for v2 projects.

Automatically generates and updates project README.md with:
- Plan list table
- Quick command reference
- Status overview

Usage:
    generator = ReadmeGenerator()
    generator.generate(project_dir, plans)
"""

from pathlib import Path
from datetime import datetime

from agent.plan import Plan


class ReadmeGenerator:
    """Generates and updates project README for v2 plan-based structure.

    The README provides:
    - Project overview
    - Plan list with status
    - Quick commands
    - Recent activity
    """

    def __init__(self) -> None:
        """Initialize the generator."""
        pass

    def generate(self, project_dir: Path, plans: list[Plan]) -> str:
        """Generate README.md content for a project.

        Args:
            project_dir: Project root directory
            plans: List of Plan objects

        Returns:
            Generated README content as string
        """
        # Get project name from directory
        project_name = project_dir.name

        # Count plans by status
        total = len(plans)
        done = sum(1 for p in plans if p.status.value == "done")
        in_progress = sum(1 for p in plans if p.status.value == "in_progress")
        blocked = sum(1 for p in plans if p.status.value == "blocked")

        # Generate plan table rows
        plan_rows = []
        for plan in sorted(plans, key=lambda p: p.plan_id):
            stage_badge = self._stage_badge(plan.stage.value)
            status_badge = self._status_badge(plan.status.value)
            deps = ", ".join(plan.depends_on) if plan.depends_on else "-"

            row = f"| {plan.plan_id} | {plan.feature} | {plan.priority.value} | {stage_badge} | {status_badge} | {deps} |"
            plan_rows.append(row)

        plan_table = "\n".join(plan_rows) if plan_rows else "| - | No plans yet | - | - | - | - |"

        # Build README content
        readme = f"""# {project_name}

**Iterative Project Management** - 基于 AI 多智能体协作的迭代式项目管理系统

> 本项目由 Idea Seed v2 生成

---

## 项目概述

- **总 Plans**: {total}
- **已完成**: {done}
- **进行中**: {in_progress}
- **阻塞**: {blocked}

---

## Plans 清单

| Plan ID | Feature | Priority | Stage | Status | Depends On |
|---------|---------|----------|-------|--------|------------|
{plan_table}

---

## 快速命令

```bash
# 查看所有 Plans
python -m agent.main plans {project_name}

# 查看特定 Plan 详情
python -m agent.main review <plan-id> --project {project_name}

# 更新 Plan 阶段
python -m agent.main review <plan-id> --stage test --project {project_name}

# 更新 Plan 状态
python -m agent.main review <plan-id> --status done --project {project_name}

# 追加新功能
python -m agent.main append "新功能描述" --project {project_name}
```

---

## 最近活动

{self._generate_recent_activity(plans)}

---

## 目录结构

```
{project_name}/
├── README.md                    # 本文件
├── requirements.md              # 需求文档
├── plans/
│   ├── plan-001.md             # Plan 元信息
│   ├── plan-001-tech-spec.md   # Plan 技术方案
│   └── ...
└── .state/
    ├── session.json            # 会话状态
    └── plans.json              # Plan 状态追踪
```

---

*最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        return readme

    def update_readme(self, project_dir: Path, plans: list[Plan]) -> None:
        """Update README.md for a project.

        Args:
            project_dir: Project root directory
            plans: List of Plan objects
        """
        readme_content = self.generate(project_dir, plans)
        readme_path = project_dir / "README.md"

        readme_path.write_text(readme_content, encoding="utf-8")

    def _stage_badge(self, stage: str) -> str:
        """Generate stage badge."""
        badges = {
            "dev": "🔧 dev",
            "test": "🧪 test",
            "release": "🚀 release",
            "blocked": "⛔ blocked",
        }
        return badges.get(stage, stage)

    def _status_badge(self, status: str) -> str:
        """Generate status badge."""
        badges = {
            "pending": "⏳ pending",
            "in_progress": "🔄 in_progress",
            "done": "✅ done",
            "blocked": "🚫 blocked",
        }
        return badges.get(status, status)

    def _generate_recent_activity(self, plans: list[Plan]) -> str:
        """Generate recent activity section from plan history.

        Args:
            plans: List of Plan objects

        Returns:
            Markdown string with recent activity
        """
        # Collect all history entries and sort by timestamp
        all_entries = []
        for plan in plans:
            for entry in plan.history:
                all_entries.append((entry.timestamp, plan.plan_id, plan.feature, entry.action, entry.details))

        if not all_entries:
            return "*暂无活动记录*"

        # Sort by timestamp descending and take recent 5
        all_entries.sort(key=lambda x: x[0], reverse=True)
        recent = all_entries[:5]

        lines = []
        for timestamp, plan_id, feature, action, details in recent:
            date = timestamp.split("T")[0]
            detail_str = f" - {details}" if details else ""
            lines.append(f"- **{date}** [{plan_id}] {action}: {feature}{detail_str}")

        return "\n".join(lines) if lines else "*暂无活动记录*"
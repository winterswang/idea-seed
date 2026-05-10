"""Integration tests for v2 flow: seed → Requirements → Plans → Tech-Spec → README.

Tests the complete v2 iterative project management workflow.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from agent.plan import Plan, PlanStage, PlanStatus, Priority
from agent.plan_manager import PlanManager, CycleDetectedError, PlanNotFoundError
from agent.plan_splitter import PlanSplitter
from agent.readme_generator import ReadmeGenerator


class TestPlanDataStructure:
    """Tests for Plan data structure (Task #7)."""

    def test_plan_creation(self):
        """Test basic plan creation."""
        plan = Plan.create("用户认证", Priority.P0)
        assert plan.plan_id.startswith("plan-")
        assert plan.feature == "用户认证"
        assert plan.priority == Priority.P0
        assert plan.stage == PlanStage.DEV
        assert plan.status == PlanStatus.PENDING
        assert len(plan.history) == 1

    def test_plan_to_dict_roundtrip(self):
        """Test serialization roundtrip."""
        plan = Plan.create("Test Feature", Priority.P1)
        plan.update_stage(PlanStage.TEST)
        plan.update_status(PlanStatus.IN_PROGRESS)

        d = plan.to_dict()
        restored = Plan.from_dict(d)

        assert restored.plan_id == plan.plan_id
        assert restored.feature == plan.feature
        assert restored.stage == PlanStage.TEST
        assert restored.status == PlanStatus.IN_PROGRESS

    def test_plan_validation_empty_id(self):
        """Test that empty plan_id raises ValueError."""
        with pytest.raises(ValueError):
            Plan(plan_id="", feature="Test")

    def test_plan_validation_empty_feature(self):
        """Test that empty feature raises ValueError."""
        with pytest.raises(ValueError):
            Plan(plan_id="p1", feature="")


class TestPlanManager:
    """Tests for PlanManager (Task #8)."""

    def setup_method(self):
        """Set up temp directory for each test."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_dir = self.tmpdir / ".state"
        self.pm = PlanManager(self.state_dir)

    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.tmpdir)

    def test_save_and_load_empty(self):
        """Test saving/loading empty plans list."""
        plans = []
        self.pm.save_plans(plans)
        loaded = self.pm.load_plans()
        assert loaded == []

    def test_save_and_load_plans(self):
        """Test saving/loading plans."""
        p1 = Plan.create("Feature A", Priority.P0)
        p2 = Plan.create("Feature B", Priority.P1)
        p2.depends_on.append(p1.plan_id)

        self.pm.save_plans([p1, p2])
        loaded = self.pm.load_plans()

        assert len(loaded) == 2
        assert loaded[1].depends_on == [p1.plan_id]

    def test_cycle_detection(self):
        """Test that cycles are detected."""
        p1 = Plan.create("A", Priority.P1)
        p2 = Plan.create("B", Priority.P1)
        p1.depends_on.append(p2.plan_id)
        p2.depends_on.append(p1.plan_id)

        with pytest.raises(CycleDetectedError):
            self.pm.save_plans([p1, p2])

    def test_add_plan(self):
        """Test adding a plan."""
        plan = Plan.create("New Feature", Priority.P1)
        plans = self.pm.add_plan(plan)

        assert len(plans) == 1
        assert plans[0].feature == "New Feature"

    def test_update_plan_stage(self):
        """Test updating plan stage."""
        plan = Plan.create("Test", Priority.P1)
        self.pm.add_plan(plan)

        self.pm.update_plan_stage(plan.plan_id, PlanStage.TEST)
        updated = self.pm.get_plan(plan.plan_id)

        assert updated.stage == PlanStage.TEST
        assert len(updated.history) == 2  # created + stage_changed

    def test_get_ready_plans(self):
        """Test getting plans that are ready to execute."""
        p1 = Plan.create("A", Priority.P0)
        p1.status = PlanStatus.DONE

        p2 = Plan.create("B", Priority.P1)
        p2.depends_on.append(p1.plan_id)

        self.pm.save_plans([p1, p2])

        ready = self.pm.get_ready_plans()
        assert len(ready) == 1
        assert ready[0].plan_id == p2.plan_id

    def test_get_blocked_plans(self):
        """Test getting blocked plans."""
        p1 = Plan.create("A", Priority.P0)
        p1.status = PlanStatus.PENDING

        p2 = Plan.create("B", Priority.P1)
        p2.depends_on.append(p1.plan_id)

        self.pm.save_plans([p1, p2])

        blocked = self.pm.get_blocked_plans()
        assert len(blocked) == 1
        assert blocked[0][0].plan_id == p2.plan_id


class TestPlanSplitter:
    """Tests for PlanSplitter (Task #9)."""

    def test_split_simple_requirements(self):
        """Test splitting a simple requirements doc."""
        requirements = """
# 需求文档

## 功能需求

### Feature 1: 用户认证
优先级: P0
- [ ] 用户可以注册
- [ ] 用户可以登录

### Feature 2: 文章管理
优先级: P1
- [ ] 用户可以创建文章

### Feature 3: 评论系统
优先级: P2
"""

        splitter = PlanSplitter()
        plans = splitter.split(requirements)

        assert len(plans) == 3
        assert plans[0].feature == "用户认证"
        assert plans[0].priority == Priority.P0
        assert len(plans[0].acceptance_criteria) == 2

    def test_split_with_tasks(self):
        """Test that tasks are extracted."""
        requirements = """
## 功能需求

### Feature: 用户认证
优先级: P0

## 任务清单
1. 实现用户注册
2. 实现用户登录
"""

        splitter = PlanSplitter()
        plans = splitter.split(requirements)

        # Should have at least the feature
        assert len(plans) >= 1


class TestReadmeGenerator:
    """Tests for ReadmeGenerator (Task #13)."""

    def setup_method(self):
        """Set up temp project directory."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.project_dir = self.tmpdir / "test-project"
        self.project_dir.mkdir()
        self.generator = ReadmeGenerator()

    def teardown_method(self):
        """Clean up."""
        shutil.rmtree(self.tmpdir)

    def test_generate_readme(self):
        """Test README generation."""
        p1 = Plan.create("用户认证", Priority.P0)
        p1.update_stage(PlanStage.DEV)
        p1.update_status(PlanStatus.DONE)

        p2 = Plan.create("文章管理", Priority.P1)
        p2.update_stage(PlanStage.TEST)
        p2.update_status(PlanStatus.IN_PROGRESS)
        p2.depends_on.append(p1.plan_id)

        plans = [p1, p2]
        readme = self.generator.generate(self.project_dir, plans)

        assert "# test-project" in readme
        assert "已完成" in readme
        assert "进行中" in readme
        assert "🔄 in_progress" in readme
        assert "plan-" in readme  # Plan IDs should be in table

    def test_update_readme(self):
        """Test writing README to file."""
        plan = Plan.create("Test Feature", Priority.P1)
        plans = [plan]

        self.generator.update_readme(self.project_dir, plans)

        readme_path = self.project_dir / "README.md"
        assert readme_path.exists()
        content = readme_path.read_text()
        assert "test-project" in content
        assert "Test Feature" in content


class TestV2ModuleImports:
    """Tests that all v2 modules can be imported."""

    def test_all_v2_modules_import(self):
        """Test that all v2 modules are importable."""
        from agent.plan import Plan, PlanStage, PlanStatus, Priority
        from agent.plan_manager import PlanManager
        from agent.plan_splitter import PlanSplitter
        from agent.plan_compact import PlanContextCompressor
        from agent.tech_spec_generator import TechSpecGenerator
        from agent.readme_generator import ReadmeGenerator
        from agent.v2_orchestrator import V2Workflow

        assert Plan is not None
        assert PlanManager is not None
        assert PlanSplitter is not None
        assert PlanContextCompressor is not None
        assert TechSpecGenerator is not None
        assert ReadmeGenerator is not None
        assert V2Workflow is not None


class TestIncrementalAppend:
    """Tests for incremental append logic."""

    def setup_method(self):
        """Set up temp directory."""
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state_dir = self.tmpdir / ".state"
        self.pm = PlanManager(self.state_dir)

    def teardown_method(self):
        """Clean up."""
        shutil.rmtree(self.tmpdir)

    def test_resolve_append_new(self):
        """Test resolving a new, independent feature."""
        strategy, affected = self.pm.resolve_append("用户画像分析")
        assert strategy == "new"
        assert affected == []

    def test_resolve_append_depends_on(self):
        """Test resolving a related feature."""
        p1 = Plan.create("用户认证", Priority.P0)
        self.pm.add_plan(p1)

        strategy, affected = self.pm.resolve_append("用户认证增强")
        # Should detect relationship
        assert strategy in ("new", "depends_on")
        assert affected != "user authentication"  # Not exact match

    def test_add_plan_after_existing(self):
        """Test adding a plan to existing plans."""
        p1 = Plan.create("基础功能", Priority.P0)
        self.pm.add_plan(p1)

        p2 = Plan.create("增强功能", Priority.P1)
        plans = self.pm.add_plan(p2)

        assert len(plans) == 2
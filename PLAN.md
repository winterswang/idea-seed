# Idea Seed v2: 迭代式项目管理 Feature Implementation Plan

## Issue Reference

Issue #6: [Feature] Idea Seed v2: 迭代式项目管理 + 执行跟踪 + 增量追加

## 目标

将 Idea Seed 从"一次性文档生成工具"升级为"迭代式项目管理工具"。

核心理念：**需求可执行、执行可跟踪、增量可持续**。

---

## v1 vs v2 对比

| 维度 | v1 | v2 |
|------|----|----|
| 文档结构 | Requirements + Tech-Design（大而全） | Requirements + Plans + Tech-Spec |
| 工作流 | 一次性完成 | 双阶段：准备 → 执行 |
| 执行跟踪 | 无 | Plan 状态跟踪 |
| 增量能力 | 不支持 | 支持追加到现有项目 |
| 循环单位 | 两个大文档整体迭代 | 每个 Plan 独立迭代 |

---

## 新增文档结构

```
projects/{slug}/
├── README.md                    # 项目总览 + Plan 清单（实时）
├── requirements.md              # 定稿后的精简需求文档
├── plans/
│   ├── plan-001.md              # Plan 元信息 + 状态
│   ├── plan-001-tech-spec.md    # 本 Plan 技术方案
│   ├── plan-002.md
│   └── ...
└── .state/
    ├── session.json             # 主会话状态
    └── plans.json               # Plan 状态追踪
```

---

## Task List

### Task #7: 创建 Plan 数据结构
- **文件**: `agent/plan.py`
- **内容**:
  - `Plan` 数据类（plan_id, feature, priority, stage, status, depends_on, blocks, history）
  - `PlanStage` 枚举 (dev/test/release/blocked)
  - `PlanStatus` 枚举 (pending/in_progress/done/blocked)
  - `to_dict()` / `from_dict()` 方法
- **验证**: 运行单元测试

### Task #8: 创建 PlanManager 类
- **文件**: `agent/plan_manager.py`
- **内容**:
  - `PlanManager` 类
  - 加载/保存 `plans.json`
  - Plan CRUD 操作
  - 状态更新
  - 增量追加逻辑
  - 依赖检查 (循环依赖检测)
- **验证**: 单元测试

### Task #9: 实现 Requirements → Plans 拆分器
- **文件**: `agent/plan_splitter.py`
- **内容**:
  - `PlanSplitter` 类
  - 基于功能模块拆分 Requirements
  - 依赖关系分析
  - Plan 列表生成
  - Prompt 模板设计
- **验证**: 用现有 requirements.md 测试拆分

### Task #10: 创建 Tech-Spec 生成器
- **文件**: `agent/tech_spec_generator.py`
- **内容**:
  - `TechSpecGenerator` 类
  - 单 Plan 的迭代循环（Builder + Reviewer）
  - 独立的收敛判断
  - `plan-{id}-tech-spec.md` 输出格式
- **验证**: 生成测试 Tech-Spec

### Task #11: 创建 Execution Reviewer
- **文件**: `agent/execution_reviewer.py`
- **内容**:
  - `ExecutionReviewer` 类
  - 验收标准检查清单
  - 结果报告生成
  - 自动检测开发完成度
- **验证**: 测试验证逻辑

### Task #12: 扩展 CLI 命令 (review/plans/append)
- **文件**: `agent/main.py`
- **内容**:
  - `review <plan-id>` 查看状态
  - `review <plan-id> --stage <stage>` 更新阶段
  - `plans <slug>` 查看项目 Plans
  - `append "<idea>" --project <slug>` 追加新功能
- **验证**: 命令行测试

### Task #13: 创建 README 自动生成器
- **文件**: `agent/readme_generator.py`
- **内容**:
  - `ReadmeGenerator` 类
  - Plan 清单表格生成
  - 快速命令说明
  - 状态变更时自动更新
- **验证**: 生成的 README 格式正确

### Task #14: 实现 Plan 级 Context 压缩
- **文件**: `agent/compact.py` (修改)
- **内容**:
  - 保存完整对话到 `plans/{plan_id}/transcript/`
  - 主 Context 只保留 plan_id, stage, status, summary
  - 压缩触发时机（每个 Plan 完成后）
- **验证**: token 用量统计

### Task #15: 更新 Orchestrator 支持 v2 工作流
- **文件**: `agent/orchestrator.py`
- **内容**:
  - 双阶段流程支持
  - Phase 1: Requirements → Plans → Tech-Spec
  - Phase 2: Plan 队列执行与状态跟踪
  - 状态转换逻辑
- **验证**: 完整流程测试

### Task #16: 集成测试
- **文件**: `tests/integration/test_v2_flow.py`
- **内容**:
  - 种子想法 → Requirements → Plans → Tech-Spec → README
  - 增量追加测试
  - 状态更新测试
- **验证**: 所有测试通过

---

## 依赖关系图

```
Task #7 (Plan 数据结构)
    ↓
Task #8 (PlanManager)
    ↓
Task #9 (PlanSplitter) ← Task #15 (Orchestrator)
    ↓
Task #10 (TechSpecGenerator) → Task #11 (ExecutionReviewer)
    ↓
Task #12 (CLI) ← Task #13 (ReadmeGenerator)
    ↓
Task #14 (Context Compression)
    ↓
Task #15 (Orchestrator 更新)
    ↓
Task #16 (集成测试)
```

---

## 实现优先级

### Phase 1: 核心循环 (Task #7-10)
1. Task #7: Plan 数据结构
2. Task #8: PlanManager
3. Task #9: PlanSplitter
4. Task #10: TechSpecGenerator

### Phase 2: 执行能力 (Task #11-13)
5. Task #11: ExecutionReviewer
6. Task #12: CLI 扩展
7. Task #13: ReadmeGenerator

### Phase 3: 增强 (Task #14-15)
8. Task #14: Context 压缩
9. Task #15: Orchestrator 更新

### Phase 4: 测试 (Task #16)
10. Task #16: 集成测试

---

## 关键设计决策

### 1. Plan 的独立性
每个 Plan 是独立迭代单位，有自己的：
- Tech-Spec (独立迭代收敛)
- 状态 (stage × status)
- 依赖关系 (depends_on / blocks)

### 2. 状态维度
```python
stage: dev | test | release | blocked
status: pending | in_progress | done | blocked
```

### 3. 收敛判断
- Requirements: 连续 2 轮评审通过
- 每个 Plan 的 Tech-Spec: 连续 2 轮评审通过
- 不是整个 document 收敛，是每个 Plan 独立收敛

### 4. 增量边界规则
| 场景 | 处理 |
|------|------|
| 完全独立 | 新增 Plan |
| 依赖现有 | 新 Plan depends_on 旧 Plan |
| 修改现有 | 标记旧为 superseded，新增 |
| 冲突 | 用户确认后归档旧 Plan |

---

## 讨论点 (待确认)

1. **Reviewer 评审轮次**：需要几轮评审才能收敛？
2. **Execution Reviewer 触发**：自动还是手动？
3. **Blocked 状态**：由谁判断 blocked？自动检测依赖未完成？
4. **多 Agent 并行**：哪些 Plans 可以并行？
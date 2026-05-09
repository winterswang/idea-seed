# Idea Seed v2 优化提案

## 背景

当前 idea-seed 的工作流是：

```
种子想法 → Requirements → Tech-Design → 完成（一次性）
```

存在的问题：
1. **Requirements 和 Tech-Design 大量重复**：背景、目标、用户等章节在两个文档中几乎相同
2. **缺乏执行跟踪**：生成 Tech-Design 后就结束了，不知道后续开发状态
3. **无法增量追加**：新需求只能新建项目，无法追加到现有项目
4. **颗粒度过粗**：一次性生成大文档，验证周期长

---

## 核心改动

### v1 vs v2 对比

| 维度 | v1 | v2 |
|------|----|----|
| 文档结构 | Requirements + Tech-Design（大而全） | Requirements + Plans + Tech-Spec（拆分） |
| 循环单位 | 两个大文档的整体迭代 | 每个独立功能点的迭代 |
| 执行跟踪 | 无 | Plan 状态跟踪 |
| 增量追加 | 不支持 | `idea-seed append` 支持 |
| 文档重复 | 大量重复章节 | 消除重复 |
| Context 管理 | 无压缩机制 | Plan 完成后及时压缩 |
| 多角色 Review | 只有 Requirements/Tech Reviewer | 新增 Execution Reviewer |
| 多 Agent | 未使用 team.py | 支持 Plans 并行开发 |

---

## v2 工作流

### 整体流程

```
种子想法
    ↓
生成 Requirements（含优先级）
    ↓
拆解为 Plans（独立功能点，LLM 自动判断）
    ↓
┌─────────────────────────────────────┐
│  Plan #1 (P0)          Plan #2 (P1) │
│  ┌─────────┐          ┌─────────┐   │
│  │Pending  │          │Pending  │   │
│  └─────────┘          └─────────┘   │
│       ↓                     ↓        │
│  Tech-Spec           Tech-Spec      │
│       ↓                     ↓        │
│  Execution Reviewer  Execution Reviewer│
│       ↓                     ↓        │
│  Done ✓             Blocked ⏸      │
└─────────────────────────────────────┘
    ↓
追加新需求：idea-seed append "新功能"
    ↓
融合到现有项目 + 新增 Plan
```

### 新增命令

| 命令 | 功能 |
|------|------|
| `idea-seed <seed>` | 启动新项目（现有逻辑） |
| `idea-seed append "<idea>" --project <slug>` | 追加功能到现有项目 |
| `idea-seed plans <slug>` | 查看项目下所有 Plans 及状态 |
| `idea-seed status <plan-id> <status>` | 更新 Plan 状态 |

---

## 文档结构变化

### v1 结构

```
projects/{slug}/
├── requirements.md      # 大而全的需求文档（~2000行）
├── tech-design.md       # 大而全的技术方案（~3000行）
├── rounds/
│   ├── requirements/    # 每轮迭代版本
│   ├── designs/
│   └── reviews/
└── .state/session.json
```

### v2 结构

```
projects/{slug}/
├── README.md            # 项目总览 + Plan 清单
├── requirements.md      # 精简的需求文档（~500行）
├── plans/
│   ├── plan-001.md      # Plan 元信息
│   ├── plan-001-requirements.md  # 本Plan需求
│   ├── plan-001-tech-spec.md    # 本Plan技术方案
│   ├── plan-002.md
│   ├── plan-002-requirements.md
│   ├── plan-002-tech-spec.md
│   └── ...
├── archive/             # 归档的废弃Plan
└── .state/
    ├── session.json     # 主会话状态
    └── plans.json       # Plan 状态追踪
```

---

## Plan 设计

### Plan 元信息结构

```yaml
# plans/plan-001.md
plan_id: plan-001
feature: 雪球登录态检查与Cookie刷新
priority: P0
status: done  # pending | in_progress | testing | done | blocked

description: |
  实现雪球登录态检查，当Cookie过期时自动刷新，
  保证爬虫能持续正常获取数据。

depends_on: []
blocks: []

created_at: 2026-05-09T16:00:00Z
updated_at: 2026-05-10T10:30:00Z

owner: Claude Code
estimate: 2h
actual: 1.5h

history:
  - 2026-05-09: created
  - 2026-05-10: in_progress
  - 2026-05-10: done
```

### Requirements 精简示例

```markdown
# 需求文档：价值投资日报工具

> **原始种子**：重构价值投资日报工具

## 项目概述
- 核心价值主张
- 目标用户
- 成功标准

## 功能清单（含Plan引用）

| 功能 | 描述 | Plan | 优先级 | 状态 |
|------|------|------|--------|------|
| 雪球登录态检查 | 检查并刷新Cookie | plan-001 | P0 | done |
| 文章爬取 | 爬取雪球文章列表 | plan-002 | P0 | in_progress |
| 内容分析 | AI分析文章核心观点 | plan-003 | P1 | pending |
| IMA同步 | 同步到IMA笔记 | plan-004 | P1 | pending |

## Out of Scope
...
```

---

## 增量追加流程

### 场景：现有项目追加新功能

```
idea-seed append "增加股票筛选功能，支持按PE、PB筛选" --project 价值投资日报-xxx
```

### 处理流程

1. **解析命令**：提取新想法内容 + 目标项目slug
2. **加载现有上下文**：
   - 读取现有 `requirements.md`
   - 读取 `plans/*.md` 了解落地情况
3. **融合分析**：
   - 新功能与现有功能的边界
   - 是否需要修改现有Plan
   - 生成新增Plan列表
4. **用户确认**：展示融合方案
5. **执行**：创建新的Plan文件

### 增量边界规则

| 场景 | 处理方式 |
|------|---------|
| 新功能完全独立 | 新增 Plan，无冲突 |
| 新功能依赖现有 Plan | 新 Plan depends_on 旧 Plan |
| 新功能修改现有功能 | 标记旧 Plan 为 superseded，新增 Plan |
| 新功能与现有冲突 | 用户确认后，旧 Plan 归档 |
| 新功能复用现有模块 | 在新 Plan 中引用，不重复开发 |

### 增量追加示例

```
现有：plan-001(P0/done) + plan-002(P0/in_progress)
追加：股票筛选功能

分析结果：
- 新增 plan-005: 股票筛选基础接口 (P1)
- 新增 plan-006: PE/PB筛选逻辑 (P1)  
- 修改 plan-002: 爬取时增加股票代码字段 (P0, depends_on plan-005)

用户确认后执行。
```

---

## Tech-Spec 设计

### 定位

每个Plan对应一个Tech-Spec，**只描述本功能点**，足够Claude Code直接执行。

### 结构

```markdown
# Tech-Spec: plan-001 雪球登录态检查

## 上下文
- 所属Plan: plan-001
- 依赖: 无
- 被依赖: plan-002

## 功能范围

### 必须实现
1. Cookie有效性检查接口
2. 自动登录并刷新Cookie
3. 异常情况处理（密码错误、网络超时）

### 不实现（Out of Scope）
- 多账号支持
- 验证码自动识别

## 接口设计

### `check_login_status() -> bool`
- 返回: True=有效, False=过期

### `refresh_cookie() -> str`
- 返回: 新Cookie字符串
- 异常: `LoginError`, `NetworkError`

## 目录结构

```
src/
├── plugins/
│   └── xueqiu/
│       ├── __init__.py
│       ├── auth.py          # 新增：认证模块
│       └── cookie_manager.py # 新增：Cookie管理
```

## 开发任务

- [ ] 实现 `cookie_manager.py`
- [ ] 实现 `check_login_status()`
- [ ] 实现 `refresh_cookie()`
- [ ] 单元测试覆盖率 > 80%

## 验收标准

- [ ] 正常登录情况下 check_login_status 返回 True
- [ ] Cookie过期时自动刷新并返回新Cookie
- [ ] 密码错误时抛出 LoginError
- [ ] 单元测试通过
```

---

## 执行状态机

```
                    ┌──────────────┐
                    │   pending    │
                    └──────┬───────┘
                           │ start
                           ▼
                    ┌──────────────┐
              ┌─────│ in_progress  │
              │     └──────┬───────┘
              │            │ complete
              │            ▼
              │     ┌──────────────┐
              │     │   testing   │
              │     └──────┬───────┘
              │            │ pass
              │     ┌──────┴───────┐
              │     │             │
        ┌─────┴─────┐           ▼
        │ blocked   │     ┌──────────┐
        └───────────┘     │ done ✓  │
                           └──────────┘
```

### 状态说明

| 状态 | 说明 |
|------|------|
| pending | 待开发 |
| in_progress | 开发中 |
| testing | 测试/需求验证中 |
| done | 完成 |
| blocked | 阻塞（依赖未完成或其他原因） |

---

## 三种 Reviewer 角色

| 角色 | 职责 | 评审内容 |
|------|------|---------|
| **Requirements Reviewer** | 评审需求完整性、Plan 拆分合理性 | Requirements 文档 |
| **Tech-Spec Reviewer** | 评审技术方案可执行性 | 每个 Plan 的 Tech-Spec |
| **Execution Reviewer** | 评审开发结果是否符合 Tech-Spec（新增） | Plan 执行结果 + 真实需求验证 |

### Execution Reviewer（新增）

v2 新增 Execution Reviewer，负责验证开发结果是否真正解决了用户问题：

```
## Execution Review 清单

### 功能验收
- [ ] 所有 Tech-Spec 中的「必须实现」已完成
- [ ] 所有验收标准（Acceptance Criteria）已通过
- [ ] 目录结构与 Tech-Spec 一致

### 需求验证
- [ ] 实现的功能解决了原始需求中的这个问题
- [ ] 没有引入新的问题
- [ ] 代码质量符合团队规范

### 测试覆盖
- [ ] 单元测试覆盖率 > 80%
- [ ] 边界条件已覆盖
- [ ] 异常情况已处理
```

---

## Context 压缩机制

v2 必须解决 Context 膨胀问题。每个 Plan 完成后，立即压缩历史：

### 压缩策略

1. **Plan 完成后**：
   - 将 Builder/Reviewer 的完整对话保存到 `plans/{plan_id}/transcript/`
   - 主 Context 只保留：`plan_id`, `status`, `tech_spec_path`, `summary`

2. **Requirements 完成后**：
   - 将 Requirements 迭代的完整对话保存到 `transcripts/requirements/`
   - 主 Context 只保留：最终版 Requirements + Plan 清单

3. **auto_compact 触发**：
   - 当 Context 超过 TOKEN_THRESHOLD 时自动压缩
   - 压缩后的 summary 保存到 `.transcripts/`

### 压缩后的 Context 结构

```
# 主 Context（轻量）
requirements: "完整的 requirements.md 内容"
plans:
  - id: plan-001
    feature: xxx
    status: done
    tech_spec: plans/plan-001/tech-spec.md
    summary: "实现了Cookie刷新，测试通过"
  - id: plan-002
    ...
```

---

## 多 Agent 并行开发

利用现有的 `team.py`（TeammateManager + MessageBus）实现 Plans 并行开发：

### 架构

```
┌──────────────────────────────────────────────────┐
│                  Orchestrator                     │
│  (管理 Plan 队列、状态、依赖关系)                   │
└─────────────────┬────────────────────────────────┘
                  │
        ┌─────────┼─────────┐
        │         │         │
        ▼         ▼         ▼
   ┌────────┐ ┌────────┐ ┌────────┐
   │Builder-A│ │Builder-B│ │Builder-C│
   │plan-001 │ │plan-002 │ │plan-003 │
   └────┬───┘ └────┬───┘ └────┬───┘
        │         │         │
        └─────────┼─────────┘
                  │
                  ▼
           ┌────────────┐
           │  MessageBus │
           └────────────┘
```

### 并行规则

- 无依赖关系的 Plan 可以并行开发
- 有依赖关系的 Plan 必须串行（依赖方等待被依赖方完成）
- 每个 Builder 是独立的 Agent，有自己的 Context
- Orchestrator 负责协调和状态汇总

---

## 实现优先级建议

### Phase 1: 核心循环
1. Plan/Plans 数据结构
2. Requirements → Plans 自动拆分
3. 单 Plan 的 Tech-Spec 生成循环
4. Plan 状态跟踪
5. 修复 v1 的 P0 bug（收敛逻辑、写入验证）

### Phase 2: 增量能力
6. `append` 命令实现
7. 增量融合逻辑（含边界判断规则）
8. Execution Reviewer 实现

### Phase 3: 增强功能
9. Context 压缩机制
10. 多 Agent 并行开发（利用 team.py）
11. 阻塞依赖可视化
12. 统计与报告

---

## 附录：与 Claude Code 的集成

### 建议的 Agent 模式

```python
# plan-executor agent
SYSTEM_PROMPT = """
你是一个 Plan 执行专家。
1. 阅读 Tech-Spec，理解本功能点的范围
2. 创建开发任务清单
3. 调用 Claude Code 执行开发
4. 更新 Plan 状态
5. 运行测试验证
"""

PROMPT_TEMPLATE = """
## 任务
执行 Plan {plan_id}: {feature}

## Tech-Spec
参考 {tech_spec_path}

## 当前状态
{status}

## 项目现状（已完成的Plans）
{completed_plans}

## 你的任务
1. 阅读 Tech-Spec
2. 评估是否可复用现有模块
3. 规划开发步骤
4. 执行开发
5. 运行 Execution Review
6. 更新 Plan 状态

开始执行。
"""
```

---

## 讨论点

1. **Plan颗粒度判断标准**：如何让LLM准确判断"独立功能点"？
2. **冲突处理**：追加需求与现有Plan冲突时如何处理？
3. **归档策略**：废弃的Plan是删除还是归档？
4. **多Agent并行**：多个Plan是否可以并行开发？
5. **Execution Reviewer 触发时机**：开发完成后自动触发还是手动触发？
6. **Context 压缩边界**：哪些信息必须保留，哪些可以压缩？

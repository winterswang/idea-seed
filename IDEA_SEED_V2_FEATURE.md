# Idea Seed v2 Feature Specification

## 概述

Idea Seed v2 将从"一次性文档生成工具"升级为"迭代式项目管理工具"。

核心理念：**需求可执行、执行可跟踪、增量可持续**。

---

## 核心改动

### v1 vs v2 对比

| 维度 | v1 | v2 |
|------|----|----|
| 文档结构 | Requirements + Tech-Design（大而全） | Requirements + Plans + Tech-Spec |
| 工作流 | 一次性完成 | 双阶段：准备 → 执行 |
| 执行跟踪 | 无 | Plan 状态跟踪 |
| 增量能力 | 不支持 | 支持追加到现有项目 |
| 循环单位 | 两个大文档整体迭代 | 每个 Plan 独立迭代 |

---

## 工作流：两个阶段

### PHASE 1：准备阶段

```
种子想法
    ↓
Requirements 多轮迭代（Reviewer 评审，收敛后定稿）
    ↓
Plans 拆解（基于定稿的 Requirements，自动拆成独立功能点）
    ↓
每个 Plan 生成 Tech-Spec（Builder + Reviewer 迭代完善）
    ↓
PHASE 1 完成 → 进入执行阶段
```

### PHASE 2：执行阶段

```
Plan 队列（pending）
    ↓
逐一执行 + 状态更新
    ↓
┌──────────────────────────────────────────────┐
│  idea-seed review <plan-id> --stage dev      │
│  idea-seed review <plan-id> --stage test    │
│  idea-seed review <plan-id> --stage release │
└──────────────────────────────────────────────┘
    ↓
增量追加
    ↓
┌──────────────────────────────────────────────┐
│  idea-seed append "新功能" --project <slug>  │
└──────────────────────────────────────────────┘
```

---

## 新增命令

### Phase 1 命令

| 命令 | 功能 |
|------|------|
| `idea-seed <seed>` | 启动新项目（种子想法 → Requirements → Plans） |

### Phase 2 命令

| 命令 | 功能 |
|------|------|
| `idea-seed review <plan-id>` | 查看 Plan 状态 |
| `idea-seed review <plan-id> --stage <stage>` | 更新 Plan 阶段 |
| `idea-seed plans <slug>` | 查看项目下所有 Plans |
| `idea-seed append "<idea>" --project <slug>` | 追加新功能到现有项目 |

### stage 状态值

| stage | 说明 |
|-------|------|
| `dev` | 开发中 |
| `test` | 测试中 |
| `release` | 已发布 |
| `blocked` | 阻塞 |

---

## 文档结构（v2）

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

### README.md 示例

```markdown
# 项目：价值投资日报工具

> 原始种子：重构价值投资日报工具

## Plan 清单

| Plan ID | 功能 | 优先级 | 阶段 | 状态 |
|---------|------|--------|------|------|
| plan-001 | 雪球登录态检查 | P0 | release | done |
| plan-002 | 文章爬取 | P0 | dev | in_progress |
| plan-003 | 内容分析 | P1 | pending | pending |
| plan-004 | IMA同步 | P1 | pending | pending |

## 快速命令

- 查看 Plans：`idea-seed plans <slug>`
- 更新状态：`idea-seed review plan-002 --stage test`
- 追加功能：`idea-seed append "新功能" --project <slug>`
```

---

## Plan 元信息

```yaml
# plans/plan-001.md
plan_id: plan-001
feature: 雪球登录态检查与Cookie刷新
priority: P0

stage: release  # dev | test | release | blocked
status: done    # pending | in_progress | done | blocked

depends_on: []
blocks: []

created_at: 2026-05-09
updated_at: 2026-05-10

history:
  - 2026-05-09: created
  - 2026-05-10: in_progress (Builder)
  - 2026-05-10: done (Execution Reviewer)
  - 2026-05-10: release
```

---

## Tech-Spec 结构

每个 Plan 对应一个 Tech-Spec，符合 Claude Code 开发规范：

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
3. 异常处理

### Out of Scope
- 多账号支持

## 接口设计

### check_login_status() -> bool

## 开发任务
- [ ] 实现 auth.py
- [ ] 实现 cookie_manager.py
- [ ] 单元测试 > 80%

## 验收标准
- [ ] 登录状态检查正常
- [ ] Cookie过期自动刷新
- [ ] 测试通过
```

---

## 增量追加流程

### 命令

```bash
idea-seed append "增加股票筛选功能，支持按PE、PB筛选" --project 价值投资日报-xxx
```

### 处理流程

1. **解析命令**：提取新想法 + 目标项目 slug
2. **加载现状**：读取 requirements.md + plans/*.md
3. **融合分析**：
   - 评估新功能与现有 Plans 的关系
   - 生成新增/修改 Plan 列表
4. **用户确认**：展示融合方案
5. **执行**：创建新的 Plan 文件，更新 README

### 增量边界规则

| 场景 | 处理 |
|------|------|
| 完全独立 | 新增 Plan |
| 依赖现有 | 新 Plan depends_on 旧 Plan |
| 修改现有 | 标记旧为 superseded，新增 |
| 冲突 | 用户确认后归档旧 Plan |

---

## 三种 Reviewer

| 角色 | 阶段 | 职责 |
|------|------|------|
| Requirements Reviewer | P1 | 评审需求完整性、Plan 拆分合理性 |
| Tech-Spec Reviewer | P1 | 评审技术方案可执行性 |
| Execution Reviewer | P2 | 验证开发结果是否符合 Tech-Spec |

---

## Context 压缩

每个 Plan 完成后：
1. 完整对话保存到 `plans/{plan_id}/transcript/`
2. 主 Context 只保留：plan_id, stage, status, summary

保持主 Context 轻量，避免 token 膨胀。

---

## 实现优先级

### Phase 1: 核心循环
1. Plan 数据结构 + plans.json
2. Requirements → Plans 拆分
3. 单 Plan 的 Tech-Spec 生成循环
4. Plan stage/status 更新机制
5. 修复 v1 的 P0 bug

### Phase 2: 执行能力
6. `review` 命令（查看/更新状态）
7. `plans` 命令（项目 Plan 清单）
8. `append` 命令（增量追加）
9. README 自动更新

### Phase 3: 增强
10. Execution Reviewer
11. Context 压缩
12. 多 Agent 并行（利用 team.py）

---

## 讨论点

1. **Reviewer 评审轮次**：需要几轮评审才能收敛？
2. **Execution Reviewer 触发**：自动还是手动？
3. **Blocked 状态**：由谁判断 blocked？自动检测依赖未完成？
4. **多 Agent 并行**：哪些 Plans 可以并行？
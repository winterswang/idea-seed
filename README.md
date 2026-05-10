# Idea Seed

**Iterative Document Builder** - 基于 AI 多智能体协作的迭代式文档生成系统

将一个简单的想法（种子）通过 Builder 和 Reviewer 两个角色的协作，迭代完善为完整的需求文档和可执行的行动计划。

---

## 核心能力

### 智能迭代生成
- **多角色协作**：Builder 生成内容，Reviewer 评审反馈
- **自动收敛**：连续 2 轮评审通过后自动进入下一阶段
- **版本管理**：每次保存自动生成版本历史，支持回溯

### 双模式执行
- **Legacy 模式**：生成传统技术方案文档（tech-design.md）
- **Plan 模式**：生成可执行的行动计划（execution-plan.md）

### 稳定性保障
- **写入验证**：Builder 写入后自动验证，防止空内容传播
- **状态持久化**：增强版 StateManager，支持版本、备份、校验、锁
- **断点恢复**：中断后可无缝继续

---

## 工作流程

```
种子想法
    ↓
┌─────────────────────────────────────────────────────────────┐
│                 REQUIREMENTS PHASE                          │
│  Round N:                                                    │
│    1. Builder → 生成需求文档（直接写入文件）                   │
│    2. Reviewer → 多维度评审，给出改进建议                     │
│    3. 收敛条件：连续 2 轮评审通过                             │
└─────────────────────────────────────────────────────────────┘
                            ↓ 收敛
┌─────────────────────────────────────────────────────────────┐
│              EXECUTION PLAN PHASE (Plan Mode)                │
│  Round N:                                                    │
│    1. Builder → 生成执行计划（Phase/Task/Checkpoint）       │
│    2. Reviewer → 评审可执行性和验证覆盖率                      │
│    3. 收敛条件：连续 2 轮评审通过                             │
└─────────────────────────────────────────────────────────────┘
                            ↓ 收敛
                          完成
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

创建 `.env` 文件：

```bash
# Provider 选择: minimax / aliyun / bytedance
PROVIDER=minimax

# MiniMax 配置
MINIMAX_API_KEY=your-api-key
MINIMAX_BASE_URL=https://api.minimax.chat
MINIMAX_MODEL=minimax2.7
```

### 3. 运行

```bash
# 基本用法
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法"

# Plan 模式（生成执行计划）
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法" --mode plan

# 恢复中断的会话
PYTHONPATH=$(pwd) python -m agent.main --resume "你的种子想法"

# 指定最大迭代轮数
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法" --max-rounds 20
```

### 4. 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `seed` | 种子想法 | 必填 |
| `--mode` | 执行模式：`legacy` 或 `plan` | legacy |
| `--resume` | 恢复中断的会话 | False |
| `--max-rounds` | 每阶段最大迭代轮数 | 10 |
| `--provider` | AI 服务商 | minimax |

---

## 执行模式详解

### Legacy 模式（默认）

生成技术方案文档，流程：
1. Requirements Phase（需求文档迭代）
2. Tech Design Phase（技术方案迭代）

### Plan 模式（V2）

生成可执行的行动计划，流程：
1. Requirements Phase（需求文档迭代）
2. Execution Plan Phase（执行计划迭代）

**执行计划特性**：
- **Phase（阶段）**：逻辑任务分组，每阶段有 Checkpoint 验证
- **Task（任务）**：可执行的最小单元，包含：
  - 描述（具体可执行）
  - 优先级（P0/P1/P2）
  - 验证类型（command_execution/file_existence/coverage_check/manual）
  - 验证配置（验证命令或文件路径）
  - 依赖关系
  - 预估时长
- **Checkpoint（检查点）**：验证阶段内所有任务完成情况

---

## 项目结构

```
idea-seed/
├── agent/                    # 核心智能体模块
│   ├── config.py            # 配置管理（.env 加载）
│   ├── constants.py         # 常量定义
│   ├── orchestrator.py      # 业务编排器（主循环）
│   ├── prompts.py           # Prompt 模板（Builder/Reviewer）
│   ├── state.py             # 会话状态定义
│   ├── state_manager.py      # 增强状态管理（版本/备份/校验/锁）
│   ├── review.py             # 多维度评审分析器（ReviewAnalyzer）
│   ├── token_tracker.py     # Token 用量追踪
│   ├── subagent.py          # 子智能体运行器
│   ├── compact.py           # 上下文压缩
│   ├── team.py              # 团队管理
│   └── main.py              # CLI 入口
├── tools/                   # 工具集
│   └── base.py              # 基础工具（bash/read/write/edit）
├── tests/                   # 测试
├── projects/                # 生成的项目目录
├── OUTPUT_SPEC.md           # 文档格式规范
├── DESIGN.md                # 设计文档
└── README.md
```

---

## 架构设计

### 1. 多智能体协作

```
Orchestrator
    ├── Builder（生成内容）
    │   └── 通过 write_file 直接写入完整内容到文件
    └── Reviewer（评审反馈）
        └── 通过 ReviewAnalyzer 进行多维度结构化分析
```

**Builder 直接写文件的好处**：
1. 不受 API 返回 token 限制
2. 完整内容不会因返回截断丢失
3. 文档直接落盘，更可靠

### 2. 多维度评审（ReviewAnalyzer）

Reviewer 输出通过 `ReviewAnalyzer` 进行结构化分析：

| 维度 | 说明 |
|------|------|
| 意图对齐 | 文档是否与种子想法一致 |
| 完整性 | 内容覆盖是否全面 |
| 可执行性 | 是否可直接用于开发 |
| 格式合规 | 文档结构是否规范 |

**评审判断优先级**：
1. 否定模式（需修改/不通过）> 通过模式（通过/approved）
2. 默认拒绝未明确通过的文档

### 3. 状态管理（StateManager）

增强的状态持久化机制：

| 特性 | 说明 |
|------|------|
| 版本控制 | 每次保存生成 `session.vN.json` |
| 自动备份 | 保存前自动备份旧状态到 `backups/` |
| 完整性校验 | MD5 checksum 验证状态未被篡改 |
| 文件锁 | `fcntl.flock` 保证并发安全 |
| 自动恢复 | 校验失败时自动从备份/版本中恢复 |
| 原子写入 | 先写临时文件再 rename，避免写入中断 |

### 4. 安全机制

- **路径验证**：所有文件操作经过路径验证，确保文件只能在项目目录内
- **禁止裸文件名**：必须使用子目录路径（如 `projects/my-project/requirements.md`）
- **路径穿越防护**：`../../../etc/passwd` 等非法路径被拦截

### 5. 多 Provider 支持

支持切换不同的 AI 服务商：

| Provider | 模型 | 默认模型 |
|----------|------|----------|
| MiniMax | minimax2.7 | ✅ |
| 阿里云 | qwen3.6-plus | - |
| 字节跳动 | glm-5.1 | - |

---

## 输出文档

### 目录结构

每个种子想法会生成独立的项目目录：

```
projects/
└── {project-slug}/
    ├── README.md              # 项目概览（自动生成）
    ├── requirements.md        # 需求文档（最新版本）
    ├── execution-plan.md     # 执行计划（Plan 模式）
    ├── tech-design.md         # 技术方案（Legacy 模式）
    ├── execution.log          # 执行日志
    ├── .state/                # 状态持久化目录
    │   ├── session.json       # 当前状态（symlink → session.vN.json）
    │   ├── versions/          # 版本历史
    │   │   └── session.v*.json
    │   ├── backups/           # 自动备份
    │   └── token_records.json # Token 用量记录
    └── rounds/                # 每轮迭代的版本记录
        ├── requirements/
        ├── designs/
        └── reviews/
```

### Plan 模式输出示例（execution-plan.md）

```markdown
# 执行计划

## 1. 概述
[高-level 总结]

## 2. 阶段划分
### Phase 1: [名称]
[描述]
Tasks: task-1-1, task-1-2
Checkpoint: cp-1

## 3. 任务详情
### Task task-1-1: [名称]
- **描述**: [详细描述]
- **优先级**: P0
- **验证类型**: command_execution
- **验证配置**: [验证命令]
- **依赖**: none
- **预估时长**: 4h

## 4. 检查点
### Checkpoint cp-1: [名称]
- **验证任务**: task-1-1, task-1-2
- **验证方式**: [如何验证]
```

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_TOKENS` | 80000 | 单次生成最大 token 数 |
| `MAX_ROUNDS` | 10 | 每阶段最大迭代轮数 |
| `TOKEN_THRESHOLD` | 150000 | 上下文压缩阈值 |
| `KEEP_RECENT` | 3 | 压缩时保留的最近消息数 |

---

## 执行日志示例

```
[2026-05-07 08:55:10] [INFO] ============================================================
[2026-05-07 08:55:10] [INFO]   IDEA SEED - Iterative Document Builder
[2026-05-07 08:55:10] [INFO]   🌱 Seed: 写一个文学创作工具
[2026-05-07 08:55:10] [INFO]   📍 Phase: REQUIREMENTS
[2026-05-07 08:55:10] [INFO]   🎯 Mode: PLAN
[2026-05-07 08:55:10] [INFO] ============================================================
[2026-05-07 08:55:10] [INFO]
[2026-05-07 08:55:10] [INFO]   [1/2] Running Requirements Builder...
[2026-05-07 09:00:58] [INFO]       → Generated 1456 lines, 28965 chars in 348.9s
[2026-05-07 09:00:58] [INFO]       → Written to: rounds/requirements/round-1.md
[2026-05-07 09:01:50] [INFO]   [2/2] Running Requirements Reviewer...
[2026-05-07 09:01:50] [INFO]       → Review: ❌ NEEDS WORK
[2026-05-07 09:01:50] [INFO]       → Feedback: [评审反馈内容]
```

---

## 常见问题

### Q: 如何中断正在运行的会话？

按 `Ctrl+C`。状态会自动保存，下次使用 `--resume` 恢复。

### Q: 生成的内容在哪里？

在 `projects/{项目slug}/` 目录下。

### Q: Plan 模式和 Legacy 模式有什么区别？

- **Legacy**：生成技术方案文档（tech-design.md），描述系统架构和技术选型
- **Plan**：生成执行计划文档（execution-plan.md），包含可执行的任务和验证方式

### Q: 最多能迭代多少轮？

默认 10 轮，可通过 `--max-rounds` 参数修改。

### Q: 如何查看 Token 用量？

```bash
cat projects/你的项目/.state/token_stats.json
```

---

## 相关文档

- [OUTPUT_SPEC.md](./OUTPUT_SPEC.md) - 文档格式规范
- [DESIGN.md](./DESIGN.md) - 设计文档

---

## 更新日志

### 2026-05-10
- 修复 Issue #2: Builder 写入文件后验证
- 修复 Issue #3: previous_feedback 重复出现
- 确认 Issue #1: 收敛判断逻辑已正确，无需修复

### 2026-05-07
- 实现 StateManager 增强版（版本/备份/校验/锁）
- 修复执行计划评审返回值被丢弃的问题

### 2026-05-05
- 添加 Plan 模式支持（Execution Plan）
- 实现 ReviewAnalyzer 多维度评审分析

---

## License

MIT
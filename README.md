# Idea Seed

**Iterative Document Builder** - 基于 AI 多智能体迭代的文档生成系统

将一个简单的想法（种子）通过 Builder 和 Reviewer 两个角色的协作，迭代完善为完整的需求文档和技术方案。

---

## 核心概念

### 什么是"种子"？

种子是一个简短的描述，表达你想要构建的项目的核心想法。例如：

> "我想设计一个财务服务工具，提供标准的财务数据接口，包括三表和核心财务指标"

### 两角色协作

| 角色 | 职责 |
|------|------|
| **Builder** | 根据反馈构建需求文档或技术方案 |
| **Reviewer** | 评估文档完整性，给出改进建议 |

### 迭代流程

```
┌─────────────────────────────────────────────────────────────┐
│                    REQUIREMENTS PHASE                       │
│  Round N:                                                    │
│    1. Builder → 生成需求文档                                 │
│    2. Reviewer → 评审，判断是否收敛                           │
│    3. 收敛条件：连续 2 轮评审通过                             │
└─────────────────────────────────────────────────────────────┘
                            ↓ 收敛
┌─────────────────────────────────────────────────────────────┐
│                    TECH DESIGN PHASE                         │
│  Round N:                                                    │
│    1. Builder → 生成技术方案                                 │
│    2. Reviewer → 评审，判断是否收敛                          │
│    3. 收敛条件：连续 2 轮评审通过                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

创建 `.env` 文件（从项目根目录）：

```bash
# Provider 选择: minimax / aliyun / bytedance
PROVIDER=minimax

# MiniMax 配置
MINIMAX_API_KEY=your-api-key
MINIMAX_BASE_URL=https://api.minimax.chat
MINIMAX_MODEL=minimax2.7

# 或使用阿里云
# ALIYUN_API_KEY=your-api-key
# ALIYUN_MODEL=qwen3.6-plus

# 或使用字节跳动
# BYTEDANCE_API_KEY=your-api-key
# BYTEDANCE_MODEL=glm-5.1
```

### 3. 运行

**方式一：直接运行（推荐用于测试）**

```bash
cd /path/to/idea-seed
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法"
```

**方式二：后台运行**

```bash
PYTHONPATH=$(pwd) nohup python -m agent.main "你的种子想法" > output.log 2>&1 &
```

**方式三：交互模式**

```bash
PYTHONPATH=$(pwd) python -m agent.main --interactive
```

**方式四：恢复中断的会话**

```bash
PYTHONPATH=$(pwd) python -m agent.main --resume "你的种子想法"
```

### 4. 命令行参数

| 参数 | 说明 |
|------|------|
| `seed` | 种子想法（必填，除非使用 --interactive） |
| `--resume` | 从中断的会话恢复 |
| `--interactive` | 交互模式，提示输入种子 |
| `--provider` | 指定 AI 服务商（minimax/aliyun/bytedance） |
| `--max-rounds` | 最大迭代轮数（默认 10） |
| `--mode` | 执行模式：`legacy`（默认）或 `plan` |

---

## 执行模式

Idea Seed V2 支持两种执行模式：

| 模式 | 流程 | 说明 |
|------|------|------|
| `legacy` | Requirements → Tech Design → Done | 传统技术方案模式 |
| `plan` | Requirements → Execution Plan → Done | V2 执行计划模式 |

### Legacy 模式（默认）

生成技术方案文档（tech-design.md），描述系统架构和技术选型。

### Plan 模式（V2）

生成执行计划文档（execution-plan.md），包含：
- **Phase（阶段）**：逻辑任务分组
- **Task（任务）**：可执行的最小单元，带验证配置
- **Checkpoint（检查点）**：验证任务完成情况

```bash
# 使用 Plan 模式
python -m agent.main "种子想法" --mode plan
```

### Plan 模式特性

- 每个任务有明确的验证方式（command、file、coverage、manual）
- 支持阶段性 Checkpoint 验证
- 支持增量更新（需求变更时局部更新计划）
- 支持一致性检查（依赖循环、孤立任务检测）

---

## 输出文档

### 目录结构

每个种子想法会生成独立的项目目录：

```
projects/
└── {project-slug}/           # 自动生成的目录名
    ├── requirements.md        # 需求文档（最新版本）
    ├── tech-design.md         # 技术方案（最新版本）
    ├── execution.log          # 执行日志
    ├── .state/                # 状态持久化目录
    │   ├── session.json       # 当前状态（symlink）
    │   ├── versions/          # 版本历史
    │   │   ├── session.v1.json
    │   │   └── session.v2.json
    │   ├── backups/           # 自动备份
    │   ├── token_records.json # Token 用量记录
    │   └── token_stats.json   # Token 统计缓存
    └── rounds/                # 每轮迭代的版本记录
        ├── requirements/
        │   ├── round-1.md
        │   └── round-2.md
        ├── designs/
        │   ├── round-1.md
        │   └── round-2.md
        └── reviews/
            ├── requirements-round-1.md
            └── design-round-1.md
```

### 需求文档 (requirements.md)

包含：
- 项目概述（核心价值、目标用户、成功标准）
- 功能需求（用户故事、验收标准、优先级）
- 数据需求（实体定义）
- 非功能需求（性能、安全、可用性）
- Out of Scope（明确排除的功能）
- 任务清单（可执行的开发任务）

### 技术方案 (tech-design.md)

包含：
- 技术栈选型及理由
- 系统架构图
- 接口设计（完整 API 规范）
- 数据模型（SQL schema）
- 目录结构
- 关键实现细节
- 开发任务分解

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_TOKENS` | 80000 | 单次生成最大 token 数 |
| `MAX_ROUNDS` | 10 | 每阶段最大迭代轮数 |
| `TOKEN_THRESHOLD` | 150000 | 上下文压缩阈值 |
| `KEEP_RECENT` | 3 | 压缩时保留的最近消息数 |

---

## 架构说明

### Builder 直接写文件

Builder subagent 通过 `write_file` 工具直接写入完整内容到文件，而不是通过返回值传递。这确保了：
1. 不受 API 返回 token 限制
2. 完整内容不会丢失
3. 文档直接落盘，更可靠

### 路径安全

所有文件操作都经过路径验证，确保文件只能在项目目录内：
- 禁止裸文件名（如 `requirements.md`）
- 必须使用子目录路径（如 `projects/my-project/requirements.md`）
- 禁止路径穿越（`../../../etc/passwd` 被拦截）

### 多 Provider 支持

支持切换不同的 AI 服务商：
- **MiniMax** - 默认
- **阿里云**（qwen3.6-plus）
- **字节跳动**（glm-5.1）

### 多维度评审 (ReviewAnalyzer)

Reviewer 的输出通过 `ReviewAnalyzer` 进行四维度结构化分析：

| 维度 | 说明 |
|------|------|
| 意图对齐 | 文档是否与种子想法一致 |
| 完整性 | 内容覆盖是否全面 |
| 可执行性 | 是否可直接用于开发 |
| 格式合规 | 文档结构是否规范 |

评审判断优先级：否定模式（需修改/不通过）> 通过模式（通过/approved）> 默认拒绝。

### 状态管理 (StateManager)

增强的状态持久化机制：
- **版本控制**：每次保存生成版本文件 (`session.v1.json`, `session.v2.json`, ...)
- **自动备份**：保存前自动备份旧状态
- **完整性校验**：MD5 checksum 验证状态未被篡改
- **文件锁**：`fcntl.flock` 保证并发安全
- **自动恢复**：校验失败时自动从备份/版本中恢复
- **原子写入**：先写临时文件再 rename，避免写入中断导致数据损坏

### Token 用量追踪 (TokenTracker)

自动记录和统计 API 调用消耗：
- 每次调用记录 input/output tokens
- 按模型定价计算费用估算
- 异常检测（单次调用超过 50000 tokens）
- 支持 daily/weekly/monthly/all 统计周期
- 生成 Markdown 格式的消耗报告

---

## 项目结构

```
idea-seed/
├── agent/                    # 核心智能体模块
│   ├── config.py            # 配置管理（.env 加载）
│   ├── constants.py         # 常量定义
│   ├── loop.py             # Agent Loop 核心
│   ├── orchestrator.py      # 业务编排器
│   ├── prompts.py           # Prompt 模板
│   ├── state.py             # 会话状态定义
│   ├── state_manager.py     # 增强状态管理（版本/备份/校验/锁）
│   ├── review.py            # 多维度评审分析器
│   ├── token_tracker.py     # Token 用量追踪与报告
│   ├── subagent.py          # 子智能体运行器
│   ├── main.py              # CLI 入口
│   ├── compact.py           # 上下文压缩
│   ├── team.py              # 团队管理
│   └── protocol.py          # 协议定义
├── tools/                   # 工具集
│   └── base.py              # 基础工具（bash/read/write/edit）
├── tests/                   # 测试
├── projects/                # 生成的项目目录（git 忽略）
├── .env                     # API 配置（git 忽略）
├── OUTPUT_SPEC.md          # 文档格式规范
├── DESIGN.md               # 设计文档
├── IMPLEMENTATION.md       # 实施计划
└── README.md
```

---

## 执行日志示例

```
[2026-04-11 21:59:45] [INFO] Started new session: xxx
[2026-04-11 21:59:45] [INFO] ============================================================
[2026-04-11 21:59:45] [INFO]   REQUIREMENTS PHASE - Round 1
[2026-04-11 21:59:45] [INFO]   Progress: [Round 1/10] [Recent approvals: 0/2]
[2026-04-11 21:59:45] [INFO] ============================================================
[2026-04-11 21:59:45] [INFO]
[2026-04-11 21:59:45] [INFO]   [1/2] Running Requirements Builder...
[2026-04-11 22:03:12] [INFO]       → Generated 765 lines, 19822 chars in 207.3s
[2026-04-11 22:03:12] [INFO]       → Written to: rounds/requirements/round-1.md
[2026-04-11 22:03:12] [INFO]       → Updated: requirements.md (latest)
[2026-04-11 22:04:05] [INFO]
[2026-04-11 22:04:05] [INFO]   [2/2] Running Requirements Reviewer...
[2026-04-11 22:04:05] [INFO]       → Review: ✅ APPROVED
[2026-04-11 22:04:05] [INFO]       → Review saved to: rounds/reviews/requirements-round-1.md
```

---

## 常见问题

### Q: 如何中断正在运行的会话？

按 `Ctrl+C`。状态会自动保存，下次使用 `--resume` 恢复。

### Q: 生成的内容在哪里？

在 `projects/{项目slug}/` 目录下。

### Q: 最多能迭代多少轮？

默认 10 轮，可通过 `--max-rounds` 参数修改。

### Q: 如何查看生成的文档？

```bash
# 查看需求文档
cat projects/财务工具-接口封装-7f2a/requirements.md

# 查看技术方案
cat projects/财务工具-接口封装-7f2a/tech-design.md
```

---

## 相关文档

- [OUTPUT_SPEC.md](./OUTPUT_SPEC.md) - 文档格式规范（必须遵循的结构）
- [IMPLEMENTATION.md](./IMPLEMENTATION.md) - 详细实施计划
- [DESIGN.md](./DESIGN.md) - 设计文档

---

## License

MIT

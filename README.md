# Idea Seed

**Iterative Project Builder** - 基于 AI 多智能体协作的迭代式文档生成与项目管理系统

将一个简单的想法（种子）通过 Builder 和 Reviewer 两个角色的协作，迭代完善为完整的需求文档和可执行的行动计划。支持独立的 Plan 管理、增量更新和上下文压缩。

---

## 核心能力

### 智能迭代生成
- **多角色协作**：Builder 生成内容，Reviewer 评审反馈
- **自动收敛**：连续 2 轮评审通过后自动进入下一阶段
- **版本管理**：每次保存自动生成版本历史，支持回溯

### 双模式执行
- **Legacy 模式**：生成传统技术方案文档（tech-design.md）
- **Plan 模式（V2）**：生成可执行的 Plan 列表和 Tech-Spec

### Plan 级迭代
- **独立迭代**：每个 Plan 有自己的 Tech-Spec 生成循环
- **依赖管理**：自动分析 Plan 间依赖关系，支持并行
- **状态跟踪**：stage × status 二维状态机

### 稳定性保障
- **写入验证**：Builder 写入后自动验证，防止空内容传播
- **状态持久化**：增强版 StateManager，支持版本、备份、校验、锁
- **断点恢复**：中断后可无缝继续
- **上下文压缩**：三层压缩机制防止上下文无限累积

---

## 工作流程

### Legacy 模式（传统技术方案）

```
种子想法
    ↓
Requirements Phase（需求文档迭代，2轮收敛）
    ↓
Tech Design Phase（技术方案迭代，2轮收敛）
    ↓
完成
```

### Plan 模式（V2 - 迭代式项目管理）

```
种子想法
    ↓
Requirements Phase（需求文档迭代，2轮收敛）
    ↓
Plans Phase（需求 → Plans 拆分）
    ↓
Tech-Spec Phase（每个 Plan 独立迭代生成 Tech-Spec）
    ↓
README 自动生成（Plan 清单 + 状态）
    ↓
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
# 基本用法（Legacy 模式）
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法"

# Plan 模式（生成可执行 Plans）
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法" --mode plan

# 恢复中断的会话
PYTHONPATH=$(pwd) python -m agent.main --resume "你的种子想法"

# 指定最大迭代轮数
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法" --max-rounds 20
```

### 4. 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `seed` | 种子想法 | 必填（新建） |
| `--mode` | 执行模式：`legacy` 或 `plan` | legacy |
| `--resume` | 恢复中断的会话 | False |
| `--max-rounds` | 每阶段最大迭代轮数 | 10 |
| `--provider` | AI 服务商 | minimax |

### 5. 子命令

```bash
# 查看项目所有 Plans
python -m agent.main plans my-project

# 查看/更新 Plan 状态
python -m agent.main review plan-001 --stage test --status in_progress

# 追加新功能到现有项目
python -m agent.main append "新功能描述" --project my-project
```

---

## 项目结构

```
idea-seed/
├── agent/                        # 核心智能体模块
│   ├── plan.py                   # Plan 数据结构
│   ├── plan_manager.py           # PlanManager (CRUD + 循环检测)
│   ├── plan_splitter.py          # Requirements → Plans 拆分
│   ├── plan_compact.py          # Plan 级上下文压缩
│   ├── tech_spec_generator.py   # Per-Plan Tech-Spec 生成
│   ├── readme_generator.py      # README 自动生成
│   ├── v2_orchestrator.py        # V2 工作流扩展
│   ├── orchestrator.py          # 主业务编排器
│   ├── subagent.py               # 子智能体运行器
│   ├── compact.py                # 三层上下文压缩
│   ├── state_manager.py          # 状态管理（版本/备份/校验/锁）
│   ├── review.py                 # 多维度评审分析器
│   ├── token_tracker.py         # Token 用量追踪
│   └── main.py                   # CLI 入口
├── tools/
│   └── base.py                   # 基础工具（bash/read/write/edit/compact）
├── execution_plan/               # Execution Plan 模块
│   ├── models.py                 # Task/Checkpoint/Phase 模型
│   ├── generator.py              # 执行计划生成器
│   ├── verifier.py               # 验证引擎
│   └── progress.py              # 进度管理器
├── tests/                        # 测试
├── projects/                     # 生成的项目目录
├── OUTPUT_SPEC.md               # 文档格式规范
└── README.md
```

---

## 架构设计

### 1. 多智能体协作

```
Orchestrator (主编排器)
    │
    ├── Builder（生成内容）
    │   └── 通过 write_file 直接写入完整内容到文件
    │
    └── Reviewer（评审反馈）
        └── 通过 ReviewAnalyzer 进行多维度结构化分析
```

**Builder 直接写文件的好处**：
1. 不受 API 返回 token 限制
2. 完整内容不会因返回截断丢失
3. 文档直接落盘，更可靠

### 2. V2 Plan 管理架构

```
Requirements Document
        ↓
   PlanSplitter
        ↓
┌───────────────────────────────────────┐
│           plans.json                  │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐     │
│  │ P1  │→│ P2  │→│ P3  │→│ P4  │     │
│  └──┬──┘ └──┬──┘ └─────┘ └─────┘     │
│     ↓       ↓                         │
│  Tech-Spec Tech-Spec                 │
│  (独立迭代) (独立迭代)                │
└───────────────────────────────────────┘
        ↓
   README.md (自动更新)
```

**Plan 状态机**：
```
stage: dev → test → release → (blocked)
status: pending → in_progress → done → (blocked)
```

### 3. 多维度评审（ReviewAnalyzer）

| 维度 | 说明 |
|------|------|
| 意图对齐 | 文档是否与种子想法一致 |
| 完整性 | 内容覆盖是否全面 |
| 可执行性 | 是否可直接用于开发 |
| 格式合规 | 文档结构是否规范 |

**评审判断优先级**：
1. 否定模式（需修改/不通过）> 通过模式（通过/approved）
2. 默认拒绝未明确通过的文档

### 4. 三层上下文压缩

| Layer | Function | Trigger | 效果 |
|-------|----------|---------|------|
| 1 | `micro_compact()` | 每轮后 | 旧 tool_result → 占位符 |
| 2 | `compact_if_needed()` | TOKEN_THRESHOLD 超限 | 保存 transcript，压缩上下文 |
| 3 | `compact_tool()` | LLM 显式调用 | 手动触发压缩 |

### 5. 状态管理（StateManager）

| 特性 | 说明 |
|------|------|
| 版本控制 | 每次保存生成 `session.vN.json` |
| 自动备份 | 保存前自动备份旧状态到 `backups/` |
| 完整性校验 | MD5 checksum 验证状态未被篡改 |
| 文件锁 | `fcntl.flock` 保证并发安全 |
| 自动恢复 | 校验失败时自动从备份/版本中恢复 |
| 原子写入 | 先写临时文件再 rename，避免写入中断 |

### 6. 安全机制

- **路径验证**：所有文件操作经过路径验证，确保文件只能在项目目录内
- **禁止裸文件名**：必须使用子目录路径（如 `projects/my-project/requirements.md`）
- **路径穿越防护**：`../../../etc/passwd` 等非法路径被拦截

### 7. 多 Provider 支持

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
    ├── README.md              # 项目概览（V2 自动生成，包含 Plan 清单）
    ├── requirements.md       # 需求文档（最新版本）
    ├── tech-design.md        # 技术方案（Legacy 模式）
    ├── execution-plan.md     # 执行计划（Legacy Plan 模式）
    ├── plans/                # V2 Plan 目录
    │   ├── plan-001/
    │   │   └── plan-001-tech-spec.md  # Plan Tech-Spec
    │   └── plan-002/
    │       └── plan-002-tech-spec.md
    ├── .state/               # 状态持久化目录
    │   ├── session.json     # 当前状态
    │   ├── plans.json       # Plan 状态追踪（V2）
    │   ├── versions/        # 版本历史
    │   ├── backups/         # 自动备份
    │   └── token_records.json
    └── rounds/              # 每轮迭代的版本记录
        ├── requirements/
        ├── designs/
        └── reviews/
```

### Plan 模式输出（V2）

```
projects/my-project/
├── README.md                    # Plan 清单表格 + 状态徽章
├── requirements.md             # 需求文档
└── plans/
    ├── plan-001/
    │   └── plan-001-tech-spec.md  # 详细实现方案
    └── plan-002/
        └── plan-002-tech-spec.md
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

## 常见问题

### Q: 如何中断正在运行的会话？

按 `Ctrl+C`。状态会自动保存，下次使用 `--resume` 恢复。

### Q: 生成的内容在哪里？

在 `projects/{项目slug}/` 目录下。

### Q: Plan 模式和 Legacy 模式有什么区别？

- **Legacy**：生成技术方案文档（tech-design.md），描述系统架构和技术选型
- **Plan（V2）**：生成独立可执行的 Plans，每个 Plan 有自己的 Tech-Spec，支持增量更新和状态跟踪

### Q: 最多能迭代多少轮？

默认 10 轮，可通过 `--max-rounds` 参数修改。

### Q: 如何查看 Token 用量？

```bash
cat projects/你的项目/.state/token_records.json
```

### Q: 如何查看项目有多少 Plans？

```bash
python -m agent.main plans your-project
```

### Q: 如何更新 Plan 状态？

```bash
python -m agent.main review plan-001 --stage test --status done
```

---

## 相关文档

- [OUTPUT_SPEC.md](./OUTPUT_SPEC.md) - 文档格式规范
- [DESIGN.md](./DESIGN.md) - 设计文档
- [PLAN.md](./PLAN.md) - V2 实现计划

---

## 更新日志

### 2026-05-10

**V2 功能完整实现：**
- ✅ Plan 数据结构（`agent/plan.py`）
- ✅ PlanManager CRUD + 循环检测（`agent/plan_manager.py`）
- ✅ PlanSplitter - Requirements → Plans（`agent/plan_splitter.py`）
- ✅ TechSpecGenerator - Per-Plan 迭代（`agent/tech_spec_generator.py`）
- ✅ ReadmeGenerator - 自动更新 README（`agent/readme_generator.py`）
- ✅ PlanContextCompressor - Plan 级压缩（`agent/plan_compact.py`）
- ✅ V2Workflow - Orchestrator 扩展（`agent/v2_orchestrator.py`）
- ✅ CLI 命令（review/plans/append）
- ✅ Context Compression 集成（compact tool）
- ✅ Issue #1, #2, #3, #4, #6, #8 已修复/完成

**代码质量：**
- 121 tests passed
- 36 files changed, +7502 insertions

### 2026-05-07
- 实现 StateManager 增强版（版本/备份/校验/锁）
- 修复执行计划评审返回值被丢弃的问题

### 2026-05-05
- 添加 Plan 模式支持（Execution Plan）
- 实现 ReviewAnalyzer 多维度评审分析

---

## License

MIT
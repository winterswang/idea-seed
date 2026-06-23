# Idea Seed

**Iterative Project Builder** — 基于 AI 多智能体协作的迭代式文档生成与项目管理系统

将一个简单的想法（种子）通过 Builder + Reviewer 双角色协作，经历 Requirements → Plans → Tech-Spec → Execution Review 全流程，输出可直接执行的项目方案。

---

## 核心能力

### V2 全流程（Plan 模式）
- **Requirements Phase**：Builder 生成需求文档，Reviewer 多维度评审（意图对齐/完整性/可执行性/格式合规/需求匹配度）
- **Plans Phase**：自动拆分 + Plan Reviewer 审查拆分质量 + LLM 迭代优化
- **Tech-Spec Phase**：每个 Plan 独立 Builder + Reviewer 循环，2 轮收敛
- **Execution Review**：`--verify` 命令验证 Plan 实现是否符合 Tech-Spec
- **依赖传播**：upstream done → downstream 自动解锁

### 智能迭代
- **多角色协作**：Builder 写文件，Reviewer 多维度打分
- **PASS RULE**：纯建议性反馈 → 自动通过，避免无限迭代
- **Scope 自适应**：简单种子 200-500 行，复杂领域 800-2000 行
- **5 维评审**：意图对齐/完整性/可执行性/格式合规/需求匹配度

### 稳定性
- **thinking block 检测**：自动处理 minimax 返回的 thinking 块，0-token 率 ≈ 0%
- **stop_reason=None 重试**：0 output tokens → 指数退避重试 + 非流式回退
- **优雅降级**：Builder/Reviewer 失败时不崩溃，复用已有文档推进
- **总超时保护**：子智能体 1h 总超时，防止模型卡死

### 状态管理
- **版本控制 + 自动备份 + MD5 校验 + fcntl 文件锁 + 原子写入**
- **版本兼容**：`STATE_CURRENT_VERSION=2` + `_migrate_state()` 自动迁移旧格式

---

## 工作流程

```
种子想法
    ↓
┌── REQUIREMENTS PHASE ───────────────────────────────────┐
│  Builder → write requirements.md                        │
│  Reviewer → 5-dim scoring (PASS RULE)                   │
│  收敛: 连续 2 轮 ✅ 或 max_rounds                       │
└─────────────────────────────────────────────────────────┘
    ↓
┌── PLANS PHASE (Plan 模式) ─────────────────────────────┐
│  PlanSplitter → 正则提取 F1:/F2: 功能点                 │
│  Plan Reviewer → LLM 审查覆盖度/边界/依赖/粒度          │
│  不通过 → LLM re-split (max 2 次)                      │
│  收敛: 连续 2 轮 ✅                                     │
└─────────────────────────────────────────────────────────┘
    ↓
┌── TECH-SPEC PHASE ─────────────────────────────────────┐
│  每个 Plan: Builder → Reviewer 循环 (max 3 rounds)      │
│  写入 plans/{plan-id}/plan-{id}-tech-spec.md            │
└─────────────────────────────────────────────────────────┘
    ↓
┌── README + EXECUTION REVIEW ───────────────────────────┐
│  ReadmeGenerator → Plan 清单表格 + 状态徽章             │
│  ExecutionReviewer → review plan-001 --verify           │
└─────────────────────────────────────────────────────────┘
    ↓
完成
```

---

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 配置 `.env`

```bash
PROVIDER=minimax
ARK_API_KEY=your-key
# 或：ARKCODE_API_KEY=your-key
ARK_CODING_BASE_URL=https://ark.cn-beijing.volces.com/api/coding
ARK_MODEL=minimax-m3
MAX_TOKENS=30000
MAX_ROUNDS=10
```

### 运行

```bash
# Plan 模式（推荐）
PYTHONPATH=$(pwd) python -m agent.main "你的种子想法" --mode plan

# 指定输出风格
PYTHONPATH=$(pwd) python -m agent.main "种子" --style methodology

# 恢复中断会话
PYTHONPATH=$(pwd) python -m agent.main --resume

# 子命令
python -m agent.main plans my-project          # 查看 Plans
python -m agent.main review plan-001 --verify  # 验证实现
python -m agent.main append "新功能" -p my-project  # 增量追加
```

### 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `seed` | 种子想法 | 新建必填 |
| `--mode plan` | Plan 模式 | legacy |
| `--style dev-doc\|methodology` | 输出风格 | dev-doc |
| `--max-rounds N` | 每阶段最大迭代轮数 | 10 |
| `--resume` | 恢复会话 | - |
| `--provider minimax\|aliyun\|bytedance` | AI 服务商 | minimax |

---

## 项目结构

```
idea-seed/
├── agent/                        # 核心模块
│   ├── main.py                  # CLI 入口 (review/plans/append/verify)
│   ├── orchestrator.py          # 主编排器 (Requirements + Plans Phase)
│   ├── v2_orchestrator.py       # V2 扩展 (Plan Review + Tech-Spec + Re-split)
│   ├── subagent.py              # 子智能体 (stream/non-stream, thinking 检测, 退避重试)
│   ├── prompts.py               # Builder/Reviewer/PlanReviewer Prompt 模板
│   ├── review.py                # ReviewAnalyzer (5 维评分)
│   ├── logger.py                # 执行日志
│   ├── config.py                # 多 Provider 配置
│   ├── constants.py             # 常量 (+ 运行时阈值)
│   ├── state.py                 # SessionState + 版本迁移
│   ├── state_manager.py         # 增强状态管理 (备份/锁/校验)
│   ├── compact.py               # 三层上下文压缩
│   ├── token_tracker.py         # Token 用量追踪
│   ├── plan.py                  # Plan 数据结构
│   ├── plan_manager.py          # PlanManager (CRUD + 循环检测 + ID 规范化)
│   ├── plan_splitter.py         # Requirements → Plans 拆分 (F-pattern)
│   ├── plan_compact.py          # Plan 级上下文压缩
│   ├── plan_reviewer_prompts.py # Plan Reviewer Prompt
│   ├── tech_spec_generator.py   # Per-Plan Tech-Spec 迭代生成
│   ├── execution_reviewer.py    # Execution Reviewer (verify 命令)
│   ├── readme_generator.py      # README 自动生成
│   ├── team.py                  # 团队管理 / MessageBus
│   └── protocol.py              # 团队通信协议
├── tools/
│   └── base.py                  # bash/read/write/edit (路径沙箱 + 命令拦截)
├── tests/                       # 测试 (110 passed)
├── projects/                    # 生成的项目目录
├── OUTPUT_SPEC.md              # 文档格式规范
└── README.md
```

---

## 架构设计

### 1. 多智能体协作

```
Orchestrator
    ├── Builder → write_file 直接写文件（不受 token 限制）
    ├── Reviewer → ReviewAnalyzer 5 维结构化评分
    ├── Plan Reviewer → LLM 审查 Plan 拆分质量
    └── Execution Reviewer → 验证实现 vs Tech-Spec
```

### 2. Plan 状态机

```
stage:  dev → test → release → (blocked)
status: pending → in_progress → done → (blocked)
```

### 3. 上下文压缩（三层）

| Layer | Trigger | Effect |
|-------|---------|--------|
| micro_compact | 每轮 API 响应后 | 旧 tool_result → 占位符 |
| compact_if_needed | API 调用前 + TOKEN_THRESHOLD 超限 | 保存 transcript，LLM 总结 |
| compact_tool | LLM 显式调用 | 手动触发 |

### 4. 安全

- 路径沙箱（`safe_path` 防目录穿越）
- 危险命令拦截（`rm -rf /`, `sudo`, `curl | bash`）
- API Key 通过 `.env` 加载，不硬编码

---

## 输出文档

```
projects/{slug}/
├── README.md                   # Plan 清单 + 状态徽章
├── requirements.md            # 需求文档
├── execution.log              # 执行日志
├── plans/
│   ├── plan-001/
│   │   └── plan-001-tech-spec.md
│   └── plan-002/
│       └── plan-002-tech-spec.md
├── .state/
│   ├── session.json           # 会话状态 (v2)
│   ├── plans.json             # Plan 状态
│   ├── token_records.json     # Token 记录
│   ├── versions/              # 版本历史
│   └── backups/               # 自动备份
└── rounds/                    # 每轮迭代记录
    ├── requirements/
    └── reviews/
```

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_TOKENS` | 80000 | Requirements 最大 token |
| `TECH_SPEC_MAX_TOKENS` | 32000 | Tech-Spec 最大 token |
| `MAX_ROUNDS` | 10 | 每阶段最大迭代轮数 |
| `TOKEN_THRESHOLD` | 150000 | 上下文压缩阈值 |
| `MODEL_MAX_CONTEXT` | 200000 | 模型上下文窗口 |
| `MIN_SUBAGENT_CONTENT_LENGTH` | 500 | 最小有效响应长度 |
| `API_TIMEOUT_SECONDS` | 600 | API 调用超时 |

---

## 更新日志

### 2026-05-11

- ✅ thinking block 检测 — minimax 返回 thinking 块时不再误判 0-token
- ✅ stop_reason=None 重试 + 非流式回退 + 总超时保护
- ✅ depends_on ID 格式化（plan-01 → plan-001）
- ✅ 优雅降级 — Builder/Reviewer 失败时不崩溃

### 2026-05-10

- ✅ Plan Review Phase — LLM 审查拆分质量 + 迭代 re-split
- ✅ Execution Reviewer — `review --verify` 命令
- ✅ `--style methodology|dev-doc` 参数
- ✅ 5 维评审（含需求匹配度）
- ✅ PASS RULE — 纯建议 → 通过
- ✅ Scope 自适应 — 简单/复杂领域分级
- ✅ SessionState 版本迁移 (v0/v1 → v2)
- ✅ Auto-compact 集成 + 0-token 监控
- ✅ PlanSplitter F-pattern + section boundary fix
- ✅ 全部 15 个 Issue 关闭
- ✅ 110 tests passed

### 2026-05-07

- StateManager 增强版（版本/备份/校验/锁）

### 2026-05-05

- Plan 模式 + ReviewAnalyzer 多维度评审

---

## License

MIT

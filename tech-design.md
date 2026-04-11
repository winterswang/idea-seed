# Idea Seed 技术方案

> 基于 MiniMax 2.7 的多智能体迭代式需求与方案构建系统

---

## 1. 概述

### 1.1 背景

需要一个系统，通过多轮迭代将原始想法（种子）完善为需求文档和技术方案文档。系统需要支持持续迭代、角色协作、上下文管理和长期运行。

### 1.2 目标

- 支持最多10轮迭代
- 角色分离：Builder（构建）、Reviewer（评审）、Aligner（对齐）
- 独立子智能体避免上下文污染
- 支持长期运行不溢出context window

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                     Orchestrator (主控)                          │
│  • 管理迭代状态（轮次、收敛判断、种子记忆）                         │
│  • 协调 Builder/Reviewer/Aligner 的工作流                         │
│  • 持久化会话状态（JSON）                                         │
│  • 判断迭代是否收敛                                               │
└─────────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┴─────────────────┐
          │                                   │
          ▼                                   ▼
┌─────────────────────┐           ┌─────────────────────┐
│   需求 Builder      │           │   Aligner           │
│   (subagent)        │           │   (subagent/内嵌)   │
│  • 种子发散扩展     │           │  • 检查偏离主线     │
│  • 需求文档迭代     │           │  • 提供校准反馈     │
└─────────┬───────────┘           └─────────────────────┘
          │
          ▼
┌─────────────────────┐
│  需求 Reviewer      │
│  (subagent)         │
│  • 需求完整性       │
│  • 意图对齐         │
└─────────────────────┘
          │ (需求通过后)
          ▼
┌─────────────────────┐
│   方案 Builder      │ ← 依赖需求文档
│   (subagent)        │
│  • 技术方案设计     │
│  • 技术选型         │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  方案 Reviewer      │
│  (subagent)         │
│  • 技术合理性       │
│  • 架构可行性       │
└─────────────────────┘
```

---

## 3. 核心组件

### 3.1 Orchestrator (主控智能体)

**职责**：
- 管理迭代轮次（最多10轮）
- 调度各子智能体工作
- 判断收敛条件
- 持久化会话状态

**工具能力**：
| 工具 | 功能 |
|------|------|
| `spawn_builder` | 启动需求/方案Builder子智能体 |
| `spawn_reviewer` | 启动评审子智能体 |
| `spawn_aligner` | 启动对齐子智能体 |
| `read_inbox` | 读取子智能体消息 |
| `send_message` | 向子智能体发消息 |
| `write_doc` | 写入需求/方案文档 |
| `read_doc` | 读取需求/方案文档 |
| `save_state` | 保存会话状态 |
| `load_state` | 加载会话状态 |

**收敛判断**：
- 连续两轮 Reviewer 反馈无实质性修改建议
- 或达到10轮迭代上限

### 3.2 需求 Builder (子智能体)

**职责**：
- 接收种子想法
- 进行发散性思维扩展
- 生成完整需求文档 (requirements.md)

**输入**：
- 种子想法（原始描述）
- 上一轮 Reviewer 反馈（如有）

**输出**：
- 需求文档草稿

**Prompt 模板**：
```
你是需求分析师，基于种子想法进行发散扩展。

## 种子想法
{seed}

## 上一轮评审反馈
{previous_feedback}

## 任务
1. 深入理解种子想法的核心价值
2. 发散思考：用户故事、功能需求、非功能需求
3. 补充遗漏的需求点
4. 输出一份完整的 requirements.md

请开始构建需求文档。
```

### 3.3 方案 Builder (子智能体)

> **重要**：方案 Builder 必须在需求 Builder 完成且需求文档通过评审后才能启动。

**职责**：
- 基于需求文档设计技术方案
- 进行技术选型
- 生成技术方案文档 (tech-design.md)

**输入**：
- 需求文档（**必需**，来自需求阶段）
- 上一轮 Reviewer 反馈（如有）

**输出**：
- 技术方案文档草稿

**Prompt 模板**：
```
你是技术架构师，基于需求文档设计技术方案。

## 需求文档
{requirements}

## 上一轮评审反馈
{previous_feedback}

## 任务
1. 分析需求的技术可行性
2. 设计系统架构
3. 选择技术栈
4. 定义接口和数据模型
5. 输出一份完整的技术方案文档

请开始设计技术方案。
```

### 3.4 需求 Reviewer (子智能体)

**职责**：
- 评审需求文档的完整性
- 检查是否符合种子想法的核心意图
- 提供改进建议

**输入**：
- 种子想法
- 当前需求文档

**输出**：
- 评审意见（是否通过 + 具体建议）

**Prompt 模板**：
```
你是需求评审专家，检查需求文档是否符合种子想法。

## 种子想法
{seed}

## 当前需求文档
{requirements}

## 评审标准
1. 是否覆盖了种子想法的核心需求？
2. 是否有遗漏的重要用户故事？
3. 需求是否清晰、可测试？
4. 是否有模糊或矛盾的地方？

## 输出格式
- 评审结果：通过 / 需修改
- 具体建议：（列出需要改进的地方）
```

### 3.5 方案 Reviewer (子智能体)

**职责**：
- 评审技术方案的合理性和可行性
- 检查是否满足需求
- 提供改进建议

**输入**：
- 需求文档
- 当前技术方案

**输出**：
- 评审意见（是否通过 + 具体建议）

**Prompt 模板**：
```
你是技术评审专家，检查技术方案是否合理可行。

## 需求文档
{requirements}

## 当前技术方案
{tech_design}

## 评审标准
1. 是否完整覆盖了所有需求？
2. 技术选型是否合理？
3. 架构设计是否清晰、可扩展？
4. 是否存在技术风险？

## 输出格式
- 评审结果：通过 / 需修改
- 具体建议：（列出需要改进的地方）
```

### 3.6 Aligner (对齐检查)

**职责**：
- 确保迭代过程不偏离种子想法
- 在关键节点进行检查

**触发时机**：
- 每轮迭代开始前（检查Builder工作是否偏离）
- 迭代结束时（检查整体方向）

---

## 4. 迭代流程

```
Round N:
┌─────────────────────────────────────────────────────────────┐
│ 1. Orchestrator 检查收敛条件                                  │
│    - 读取当前轮次、评审历史                                   │
│    - 判断是否继续迭代                                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Aligner 检查                                              │
│    - 对齐种子想法与当前进度                                  │
│    - 如偏离，提供校准反馈                                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 需求阶段 (串行，方案依赖需求)                             │
│    ┌──────────────┐                                        │
│    │ 需求 Builder  │                                        │
│    │ • 发散扩展    │                                        │
│    │ • 写文档      │                                        │
│    └──────┬───────┘                                        │
│           │                                                 │
│           ▼                                                 │
│    ┌──────────────┐                                        │
│    │需求 Reviewer │                                        │
│    │ • 评审完整性  │                                        │
│    │ • 意图对齐    │                                        │
│    └──────┬───────┘                                        │
│           │                                                 │
│           ▼                                                 │
│    ┌──────────────────────────────────────────────────────┐│
│    │ 需求通过？ → 否：反馈给需求Builder继续迭代              ││
│    │            → 是：进入方案阶段                          ││
│    └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ (需求通过后)
┌─────────────────────────────────────────────────────────────┐
│ 4. 方案阶段 (依赖需求文档)                                   │
│    ┌──────────────┐                                        │
│    │ 方案 Builder  │ ← 读取需求文档作为输入                   │
│    │ • 技术设计    │                                        │
│    │ • 写文档      │                                        │
│    └──────┬───────┘                                        │
│           │                                                 │
│           ▼                                                 │
│    ┌──────────────┐                                        │
│    │方案 Reviewer  │                                        │
│    │ • 评审合理性  │                                        │
│    │ • 可行性      │                                        │
│    └──────┬───────┘                                        │
│           │                                                 │
│           ▼                                                 │
│    ┌──────────────────────────────────────────────────────┐│
│    │ 方案通过？ → 否：反馈给方案Builder继续迭代              ││
│    │            → 是：输出最终文档                         ││
│    └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 5. 上下文管理策略

### 5.1 分层压缩机制

基于 s06 Context Compact 的三层压缩：

| 层级 | 触发条件 | 策略 |
|------|----------|------|
| **Layer 1: Micro Compact** | 每轮 | 旧 tool_result 替换为占位符 `[Previous: used {tool}]` |
| **Layer 2: Auto Compact** | token > 阈值 | 完整对话保存磁盘，LLM摘要替换 |
| **Layer 3: Manual Compact** | 手动触发 | 同 Layer 2 的摘要机制 |

### 5.2 Context 使用优化

- **子智能体独立上下文**：每个 Builder/Reviewer 维护自己的 messages[]，主智能体只接收摘要
- **文档外部化**：需求文档和方案文档保存为磁盘文件，不全部放在 context
- **摘要压缩**：子智能体返回时，主智能体只获得关键信息摘要

### 5.3 MiniMax 2.7 适配

> 待确认具体参数后调整

假设参数（请校准）：
- Context Window: ~200K tokens
- Max Output: ~16K tokens

**适配策略**：
- 单个 Builder 运行时的最大文档控制在 50K tokens 以内
- 超出则分块处理或触发压缩
- 建议 max_tokens=8000 留有余量

---

## 6. 状态持久化

### 6.1 会话状态文件

```json
{
  "session_id": "uuid",
  "seed": "原始种子想法",
  "phase": "requirements",  // 当前阶段: requirements | tech_design | done
  "req_round": 3,            // 需求阶段当前轮次
  "design_round": 0,         // 方案阶段当前轮次（需求通过后才累加）
  "requirements_md5": "xxx",
  "tech_design_md5": "xxx",
  "req_review_history": [
    {"round": 1, "approved": false, "feedback": "..."},
    {"round": 2, "approved": true, "feedback": "..."}
  ],
  "design_review_history": [],
  "req_converged": true,     // 需求是否已收敛
  "design_converged": false,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

**阶段流转**：
1. `requirements` → 需求收敛 → `tech_design`
2. `tech_design` → 方案收敛 → `done`
3. 各自最多10轮迭代

### 6.2 文档文件

```
projects/{seed-slug}/           # 每个种子想法独立的项目目录
├── session.json                # 会话状态
├── execution.log              # 执行日志
├── requirements.md            # 最新需求文档
├── tech-design.md             # 最新技术方案
├── iteration_summary.md       # 迭代总结
└── rounds/                    # 每轮独立的文档版本
    ├── requirements/
    │   ├── round-1.md         # Round 1 的需求文档
    │   └── round-2.md         # Round 2 的需求文档
    ├── designs/
    │   ├── round-1.md         # Round 1 的技术方案
    │   └── round-2.md         # Round 2 的技术方案
    └── reviews/
        ├── requirements-round-1.md   # Round 1 的需求评审报告
        ├── requirements-round-2.md   # Round 2 的需求评审报告
        ├── design-round-1.md         # Round 1 的方案评审报告
        └── design-round-2.md         # Round 2 的方案评审报告
```

### 6.3 评审报告格式

每轮评审生成独立的报告文件，包含：
```markdown
# {Phase} 评审报告 - Round N

## 元信息
- **种子想法**: xxx
- **评审轮次**: Round N
- **评审时间**: timestamp
- **评审结果**: ✅ APPROVED / ❌ NEEDS WORK

## 评审反馈
具体的改进建议...

## 评审文档内容
---（完整的需求/方案文档内容）---
```

**设计原则**：
- 每个种子想法完全隔离，互不影响
- 每轮迭代的产出独立保存，支持追溯
- 评审报告包含完整文档内容，方便离线审查

---

## 7. 工具能力

### 7.1 文档工具

| 工具 | 参数 | 功能 |
|------|------|------|
| `write_doc` | path, content | 写入文档 |
| `read_doc` | path, limit | 读取文档（可选行数限制） |
| `edit_doc` | path, old, new | 编辑文档特定部分 |

### 7.2 子智能体工具

| 工具 | 参数 | 功能 |
|------|------|------|
| `spawn_builder` | name, role, prompt | 启动子智能体 |
| `read_inbox` | - | 读取子智能体消息 |
| `send_message` | to, content, type | 发送消息 |

### 7.3 状态工具

| 工具 | 参数 | 功能 |
|------|------|------|
| `save_state` | path, state | 保存状态 |
| `load_state` | path | 加载状态 |
| `get_iteration_status` | - | 获取当前迭代状态 |

---

## 11. 收敛条件

**分阶段收敛**：

| 阶段 | 收敛条件 |
|------|----------|
| 需求阶段 | 需求Reviewer连续两轮通过，或达到10轮上限 |
| 方案阶段 | 方案Reviewer连续两轮通过，或达到10轮上限 |

**整体流程收敛**：
1. 需求阶段收敛 → 进入方案阶段
2. 方案阶段收敛 → 输出最终文档

**收敛后输出**：
- `rounds/requirements/round-N.md`（每轮版本）
- `rounds/designs/round-N.md`（每轮版本）
- `rounds/reviews/requirements-round-N.md`（每轮评审）
- `rounds/reviews/design-round-N.md`（每轮评审）
- `requirements.md`（最新版本）
- `tech-design.md`（最新版本）
- `iteration_summary.md`（迭代总结）
- `execution.log`（执行日志）

---

## 9. 执行日志系统

### 9.1 Logger 类

```python
class Logger:
    """Simple file logger for tracking execution."""

    def __init__(self, log_path: Path):
        self.log_path = log_path

    def log(self, message: str, level: str = "INFO"):
        """Write log entry with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}\n"
        with open(self.log_path, "a") as f:
            f.write(entry)
        print(entry.rstrip())

    def log_section(self, title: str):
        """Log a section header."""
        separator = "=" * 60
        self.log(separator)
        self.log(title)
        self.log(separator)
```

### 9.2 日志输出示例

**启动阶段**：
```
============================================================
  IDEA SEED - Iterative Document Builder
============================================================
  🌱 Seed: 用户登录系统
  📁 Project: projects/yi-hu-deng-lu-xi-tong
  📋 Session: abc-123-def
  📍 Phase: REQUIREMENTS
  🔄 Max Rounds: 10
  🎯 Convergence: 2 consecutive approvals needed
============================================================
```

**迭代阶段**：
```
============================================================
  REQUIREMENTS PHASE - Round 1
  Progress: [Round 1/10] [Recent approvals: 0/2]
============================================================

  [1/3] Running Aligner check...
      → 对齐状态：通过...

  [2/3] Running Requirements Builder...
      → Generated 120 lines, 4500 chars in 3.2s
      → Saved to: rounds/requirements/round-1.md
      → Updated: requirements.md (latest)

  [3/3] Running Requirements Reviewer...
      → Review: ❌ NEEDS WORK
      → Review saved to: rounds/reviews/requirements-round-1.md
      → Feedback: 缺少非功能性需求描述...

  → Not converged yet. (0/2 recent approvals needed)
```

**完成阶段**：
```
============================================================
  DOCUMENT BUILDING COMPLETE
============================================================
  Seed Idea: 用户登录系统
  Requirements Rounds: 3
  Design Rounds: 2

  Convergence Status:
    Requirements: ✅ Converged
    Tech Design:  ✅ Converged

  Requirements Review History:
    Round 1: ❌
    Round 2: ❌
    Round 3: ✅

  Tech Design Review History:
    Round 1: ❌
    Round 2: ✅

  Versioned Rounds:
    📁 projects/yi-hu-deng-lu-xi-tong/rounds/
       ├── requirements/ (3 rounds)
       ├── designs/ (2 rounds)
       └── reviews/ (all review reports)
============================================================
```

### 9.3 日志级别

| 级别 | 用途 |
|------|------|
| INFO | 正常进度信息 |
| WARN | 警告（达到最大轮次等） |
| ERROR | 错误（异常中断等） |

## 10. 技术选型

| 组件 | 技术 | 理由 |
|------|------|------|
| 主框架 | Python + Anthropic SDK | 参考 learn-claude-code |
| 子智能体 | 线程 + JSONL 邮箱 | 参考 s09 Agent Teams |
| 消息传递 | JSONL 文件 | 持久化、可追溯 |
| 状态存储 | JSON 文件 | 简单可靠 |
| 上下文压缩 | 三层压缩 | 参考 s06 |
| 日志 | 文件 + 控制台双输出 | 实时可观测性 |

---

## 12. 后续工作

- [x] 确认 MiniMax 2.7 具体参数（context / max_tokens）
- [x] 实现 Orchestrator 主循环
- [x] 实现 Builder/Reviewer 子智能体
- [x] 实现状态持久化
- [x] 实现 Logger 日志系统
- [x] 实现每轮独立文档版本
- [ ] 实现上下文压缩
- [ ] 端到端测试

---

## 附录：参考章节

| 章节 | 主题 | 应用 |
|------|------|------|
| s01 | Agent Loop | 主循环模式 |
| s02 | Tool Use | 工具分发架构 |
| s04 | Subagent | 上下文隔离 |
| s06 | Context Compact | 三层压缩 |
| s09 | Agent Teams | 持久化团队 |
| s10 | Team Protocols | 请求-响应协议 |

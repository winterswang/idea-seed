# Idea Seed

**Iterative Document Builder** - 基于多智能体迭代的文档生成系统

通过 Builder（构建者）、Reviewer（评审）两个角色的协作，将一个简单的想法（种子）迭代完善为完整的需求文档和技术方案。

---

## 核心概念

### 种子（Seed）

一个简短的描述，表达你想要构建的项目的核心想法。例如：

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

## 项目结构

```
idea-seed/
├── agent/                    # 核心智能体模块
│   ├── config.py            # 配置管理（.env 加载）
│   ├── constants.py          # 常量定义
│   ├── loop.py              # Agent Loop 核心
│   ├── orchestrator.py      # 业务编排器
│   ├── prompts.py           # Prompt 模板
│   ├── state.py             # 状态持久化
│   └── subagent.py          # 子智能体运行器
├── tools/                   # 工具集
│   ├── base.py              # 基础工具（bash/read/write/edit）
│   └── ...
├── projects/                # 生成的项目目录
│   └── {project-slug}/      # 每个种子想法的项目
│       ├── requirements.md   # 需求文档（最新）
│       ├── tech-design.md   # 技术方案（最新）
│       ├── rounds/          # 迭代版本记录
│       │   ├── requirements/round-N.md
│       │   ├── designs/round-N.md
│       │   └── reviews/
│       └── execution.log    # 执行日志
├── tests/                   # 测试
├── .env                     # API 配置
├── OUTPUT_SPEC.md          # 文档格式规范
└── README.md
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API

编辑 `.env` 文件：

```bash
# Provider: minimax / aliyun / bytedance
PROVIDER=minimax

# MiniMax API
MINIMAX_API_KEY=your-api-key
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic
MINIMAX_MODEL=minimax2.7

# 或使用阿里云
# ALIYUN_API_KEY=your-api-key
# ALIYUN_MODEL=qwen3.6-plus
```

### 3. 运行

```bash
PYTHONPATH=$(pwd) python -c "
from agent.orchestrator import Orchestrator

seed = '你的种子想法'
o = Orchestrator(seed)
o.run()
"
```

或使用 nohup 后台运行：

```bash
PYTHONPATH=$(pwd) nohup python -c "
from agent.orchestrator import Orchestrator
o = Orchestrator('你的种子想法')
o.run()
" > output.log 2>&1 &
```

---

## 输出文档

### 需求文档 (requirements.md)

包含：
- 项目概述（核心价值、目标用户、成功标准）
- 功能需求（用户故事、验收标准）
- 数据需求（实体定义）
- 非功能需求（性能、安全、可用性）
- 任务清单

### 技术方案 (tech-design.md)

包含：
- 技术栈选型
- 系统架构
- 接口设计（API 规范）
- 数据模型（SQL schema）
- 目录结构
- 开发任务分解

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MAX_TOKENS` | 32000 | 单次生成最大 token 数 |
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

### 文件路径验证

`_write_doc` 方法验证所有路径在项目目录内：

```python
path.resolve().relative_to(self.project_dir.resolve())
```

### 多 Provider 支持

支持切换不同的 AI 服务商：

- MiniMax
- 阿里云
- 字节跳动

---

## 执行日志

每次运行会在项目目录生成 `execution.log`，记录完整执行过程：

```
[2026-04-11 21:59:45] [INFO] Started new session: xxx
[2026-04-11 21:59:45] [INFO] REQUIREMENTS PHASE - Round 1
[2026-04-11 21:59:45] [INFO]   [1/2] Running Requirements Builder...
[2026-04-11 22:03:12] [INFO]       → Generated 765 lines, 19822 chars in 207.3s
[2026-04-11 22:03:12] [INFO]       → Written to: rounds/requirements/round-1.md
[2026-04-11 22:04:05] [INFO]       → Review: ✅ APPROVED
```

---

## 相关文档

- [OUTPUT_SPEC.md](./OUTPUT_SPEC.md) - 文档格式规范
- [IMPLEMENTATION.md](./IMPLEMENTATION.md) - 实施计划
- [DESIGN.md](./DESIGN.md) - 设计文档

---

## License

MIT

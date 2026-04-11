# Idea Seed 实现计划

> 分步骤实施指南

---

## 概述

实现一个基于 MiniMax 2.7 (200K context, 8K max_tokens) 的多智能体迭代式文档构建系统。

**核心目标**：生成对 Claude Code 友好的需求文档和技术方案

**关键规范**：
- 输出格式遵循 `OUTPUT_SPEC.md` 定义的结构
- 文档可直接指导 Claude Code 执行开发任务
- 任务清单、验收标准、接口设计全部结构化

**阶段划分**：
- Phase 1: 基础架构（Agent Loop + Tools）
- Phase 2: 子智能体系统
- Phase 3: 上下文管理
- Phase 4: 团队协作
- Phase 5: 业务编排
- Phase 6: 测试与集成

---

## Phase 1: 基础架构

### 1.1 项目结构

```
idea-seed/
├── agent/
│   ├── __init__.py
│   ├── main.py              # 入口
│   ├── config.py             # 配置
│   ├── constants.py          # 常量定义
│   ├── loop.py              # Agent Loop
│   ├── orchestrator.py      # 业务编排
│   ├── prompts.py           # Prompt 模板（引用 OUTPUT_SPEC）
│   ├── subagent.py          # 子智能体
│   ├── compact.py           # 上下文压缩
│   ├── state.py             # 状态持久化
│   ├── team.py              # 团队管理
│   └── protocol.py          # 协议
├── tools/
│   ├── __init__.py
│   ├── base.py               # 基础工具(bash/read/write/edit)
│   ├── doc.py                # 文档工具
│   └── dispatch.py           # 工具分发
├── tests/
│   └── ...
├── .env                      # API配置
├── requirements.txt
├── DESIGN.md                 # 设计文档
├── IMPLEMENTATION.md         # 实施计划
├── OUTPUT_SPEC.md            # 文档输出规范（关键！）
├── tech-design.md            # 技术方案（生成）
├── requirements.md           # 需求文档（生成）
└── README.md
```

**目标**：建立可运行的基础项目结构

**验收标准**：
- [ ] Python 模块可导入
- [ ] 配置可从环境变量读取
- [ ] 基础工具(bash/read/write/edit)可正常工作
- [ ] OUTPUT_SPEC.md 格式规范可引用

### 1.2 Agent Loop

**文件**：`agent/loop.py`

**实现内容**：
```python
def agent_loop(messages: list, system: str, tools: list):
    """核心循环：while stop_reason == 'tool_use'"""
    while True:
        response = client.messages.create(
            model=MODEL, system=system,
            messages=messages, tools=tools,
            max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return

        # 执行工具，返回结果
        results = []
        for block in response.content:
            if block.type == "tool_use":
                output = dispatch(block.name, block.input)
                results.append({"type": "tool_result", ...})
        messages.append({"role": "user", "content": results})
```

**验收标准**：
- [ ] 循环能正常执行
- [ ] 工具调用能被正确分发
- [ ] stop_reason 判断正确

### 1.3 基础工具

**文件**：`tools/base.py`

| 工具 | 参数 | 功能 |
|------|------|------|
| `bash` | command | 执行shell命令 |
| `read_file` | path, limit? | 读取文件 |
| `write_file` | path, content | 写入文件 |
| `edit_file` | path, old_text, new_text | 编辑文件 |

**安全措施**：
- 路径沙箱：`safe_path()` 防止目录遍历
- 危险命令拦截：`rm -rf /`, `sudo`, `shutdown`

**验收标准**：
- [ ] 路径沙箱有效
- [ ] 危险命令被拦截
- [ ] 文件读写正确

---

## Phase 2: 子智能体系统

### 2.1 Subagent 实现

**文件**：`agent/subagent.py`

**核心函数**：
```python
def run_subagent(prompt: str, system: str, tools: list) -> str:
    """启动独立子智能体，返回摘要"""
    sub_messages = [{"role": "user", "content": prompt}]

    for _ in range(30):  # 安全限制
        response = client.messages.create(
            model=MODEL, system=system,
            messages=sub_messages, tools=tools,
            max_tokens=8000,
        )
        sub_messages.append({"role": "assistant", ...})

        if response.stop_reason != "tool_use":
            break

        # 执行工具...
        results = execute_tools(response.content, tools)
        sub_messages.append({"role": "user", "content": results})

    # 只返回最终文本
    return extract_summary(response.content)
```

**关键设计**：
- `messages=[]` 全新上下文
- 禁止递归生成子智能体（子智能体tools不包含task）
- 只返回摘要，不返回完整上下文

**验收标准**：
- [ ] 子智能体独立运行
- [ ] 不污染父上下文
- [ ] 返回有效摘要

### 2.2 Task 工具

**文件**：`tools/dispatch.py`

**添加工具**：
```python
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task",
     "description": "Spawn a subagent with fresh context",
     "input_schema": {
         "type": "object",
         "properties": {
             "prompt": {"type": "string"},
             "description": {"type": "string"}
         },
         "required": ["prompt"]
     }}
]
```

**dispatch逻辑**：
```python
if block.name == "task":
    output = run_subagent(block.input["prompt"], SUBAGENT_SYSTEM, CHILD_TOOLS)
else:
    handler = TOOL_HANDLERS.get(block.name)
    output = handler(**block.input)
```

**验收标准**：
- [ ] task工具可用
- [ ] 子智能体正确执行
- [ ] 摘要正确返回

---

## Phase 3: 上下文管理

### 3.1 三层压缩

**文件**：`agent/compact.py`

| 层级 | 触发条件 | 策略 |
|------|----------|------|
| **Layer 1: micro_compact** | 每轮 | 旧tool_result→占位符 |
| **Layer 2: auto_compact** | token>150K | 保存transcript+LLM摘要 |
| **Layer 3: compact工具** | 手动触发 | 同Layer 2 |

**实现**：

```python
# Layer 1: 微压缩
def micro_compact(messages: list, keep_recent: int = 3):
    """替换旧的tool_result为占位符"""
    tool_results = find_tool_results(messages)
    if len(tool_results) <= keep_recent:
        return messages

    for result in tool_results[:-keep_recent]:
        tool_name = lookup_tool_name(result["tool_use_id"])
        result["content"] = f"[Previous: used {tool_name}]"
    return messages

# Layer 2: 自动压缩
def auto_compact(messages: list) -> list:
    """保存transcript，LLM摘要，替换messages"""
    # 1. 保存完整历史
    transcript_path = save_transcript(messages)

    # 2. LLM摘要
    summary = summarize_conversation(messages)

    # 3. 替换
    return [
        {"role": "user", "content": f"[Compressed]\n{summary}"},
        {"role": "assistant", "content": "Understood. Continuing."}
    ]

# Layer 3: 手动压缩
def compact_tool():
    """用户触发的压缩"""
    return auto_compact(messages)
```

**验收标准**：
- [ ] micro_compact 每轮执行
- [ ] auto_compact 在阈值触发
- [ ] 压缩后上下文正确

### 3.2 状态持久化

**文件**：`agent/state.py`

**状态结构**：
```python
@dataclass
class SessionState:
    session_id: str
    seed: str
    phase: str                    # requirements | tech_design | done
    req_round: int
    design_round: int
    requirements_md5: str
    tech_design_md5: str
    req_review_history: list
    design_review_history: list
    req_converged: bool
    design_converged: bool
    created_at: str
    updated_at: str
```

**操作**：
```python
def save_state(state: SessionState, path: Path):
    """保存状态到JSON"""
    with open(path, "w") as f:
        json.dump(asdict(state), f, indent=2)

def load_state(path: Path) -> SessionState:
    """从JSON加载状态"""
    with open(path, "r") as f:
        return SessionState(**json.load(f))
```

**文件结构**：
```
.state/
├── session.json         # 当前会话状态
└── requirements.md       # 需求文档（外部化）
└── tech-design.md       # 方案文档（外部化）
```

**验收标准**：
- [ ] 状态可保存/加载
- [ ] 文档外部化存储
- [ ] 支持断点恢复

---

## Phase 4: 团队协作

### 4.1 TeammateManager

**文件**：`agent/team.py`

**核心类**：
```python
class TeammateManager:
    """管理持久化子智能体"""

    def __init__(self, team_dir: Path):
        self.team_dir = team_dir
        self.config_path = team_dir / "config.json"
        self.threads = {}

    def spawn(self, name: str, role: str, prompt: str) -> str:
        """启动一个持久化子智能体"""
        # 1. 更新config.json
        # 2. 创建线程运行_teammate_loop
        # 3. 返回状态

    def _teammate_loop(self, name: str, role: str, prompt: str):
        """子智能体主循环"""
        messages = [{"role": "user", "content": prompt}]
        for _ in range(50):
            # 检查inbox
            # 执行agent loop
            # 检查shutdown信号
            ...

    def list_all(self) -> str:
        """列出所有队友状态"""

    def member_names(self) -> list:
        """获取所有队友名"""
```

**验收标准**：
- [ ] 可启动多个持久化子智能体
- [ ] 子智能体独立线程运行
- [ ] 状态持久化到config.json

### 4.2 MessageBus

**文件**：`agent/team.py`

**核心类**：
```python
class MessageBus:
    """JSONL邮箱系统"""

    def __init__(self, inbox_dir: Path):
        self.inbox_dir = inbox_dir
        self.inbox_dir.mkdir(parents=True, exist_ok=True)

    def send(self, sender: str, to: str, content: str,
             msg_type: str = "message", extra: dict = None) -> str:
        """发送消息（追加到收件箱）"""
        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
            **(extra or {})
        }
        inbox_path = self.inbox_dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")

    def read_inbox(self, name: str) -> list:
        """读取并清空收件箱"""
        inbox_path = self.inbox_dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []
        messages = [json.loads(l) for l in inbox_path.read_text().splitlines() if l]
        inbox_path.write_text("")  # 清空
        return messages
```

**消息类型**：
```python
VALID_MSG_TYPES = {
    "message",           # 普通消息
    "broadcast",         # 广播
    "shutdown_request",  # 关闭请求
    "shutdown_response", # 关闭响应
    "plan_approval",     # 计划审批
}
```

**验收标准**：
- [ ] 消息可发送/接收
- [ ] JSONL正确追加/读取
- [ ] 收件箱可清空

### 4.3 Team Protocols

**文件**：`agent/protocol.py`

**协议实现**：

```python
# Shutdown Protocol
shutdown_requests = {}  # {req_id: {target, status}}

def handle_shutdown_request(teammate: str) -> str:
    req_id = str(uuid.uuid4())[:8]
    shutdown_requests[req_id] = {"target": teammate, "status": "pending"}
    BUS.send("lead", teammate, "Please shut down", "shutdown_request", {"request_id": req_id})
    return f"Shutdown request {req_id} sent"

def handle_shutdown_response(req_id: str, approve: bool):
    shutdown_requests[req_id]["status"] = "approved" if approve else "rejected"

# Plan Approval Protocol
plan_requests = {}  # {req_id: {from, plan, status}}

def submit_plan(from: str, plan: str) -> str:
    req_id = str(uuid.uuid4())[:8]
    plan_requests[req_id] = {"from": from, "plan": plan, "status": "pending"}
    BUS.send(from, "lead", plan, "plan_approval", {"request_id": req_id, "plan": plan})
    return f"Plan submitted (req_id={req_id})"

def approve_plan(req_id: str, approve: bool, feedback: str = ""):
    req = plan_requests[req_id]
    req["status"] = "approved" if approve else "rejected"
    BUS.send("lead", req["from"], feedback, "plan_approval_response", ...)
```

**验收标准**：
- [ ] shutdown握手正确
- [ ] plan approval工作
- [ ] request_id关联正确

---

## Phase 5: 业务编排

### 5.1 Orchestrator

**文件**：`agent/orchestrator.py`

**状态机**：
```python
class Orchestrator:
    def __init__(self, seed: str):
        self.state = SessionState(
            session_id=str(uuid.uuid4()),
            seed=seed,
            phase="requirements",
            req_round=0,
            design_round=0,
            ...
        )

    def run(self):
        """主循环"""
        while not self.is_done():
            if self.state.phase == "requirements":
                self.run_requirements_phase()
            elif self.state.phase == "tech_design":
                self.run_design_phase()
            elif self.state.phase == "done":
                self.output_final_docs()

    def is_done(self) -> bool:
        return self.state.req_converged and self.state.design_converged
```

### 5.2 需求阶段

**文件**：`agent/orchestrator.py`

```python
def run_requirements_phase(self):
    """需求构建阶段"""
    self.state.req_round += 1
    if self.state.req_round > 10:
        self.state.req_converged = True
        return

    # 1. Builder 构建
    requirements = self.builder_req.build(
        seed=self.state.seed,
        previous_feedback=self.state.req_review_history[-1].feedback if self.state.req_review_history else None
    )
    self.write_doc("requirements.md", requirements)

    # 2. Reviewer 评审
    review_result = self.reviewer_req.review(
        seed=self.state.seed,
        requirements=requirements
    )
    self.state.req_review_history.append(review_result)

    # 3. 收敛判断
    if self.check_req_convergence():
        self.state.req_converged = True
        self.state.phase = "tech_design"
        self.save_state()

def check_req_convergence(self) -> bool:
    """连续两轮通过则收敛"""
    if len(self.state.req_review_history) < 2:
        return False
    last_two = self.state.req_review_history[-2:]
    return all(r["approved"] for r in last_two)
```

### 5.3 方案阶段

**文件**：`agent/orchestrator.py`

```python
def run_design_phase(self):
    """技术方案阶段"""
    self.state.design_round += 1
    if self.state.design_round > 10:
        self.state.design_converged = True
        return

    # 1. 读取需求文档
    requirements = self.read_doc("requirements.md")

    # 2. Builder 构建
    tech_design = self.builder_design.build(
        requirements=requirements,
        previous_feedback=self.state.design_review_history[-1].feedback if self.state.design_review_history else None
    )
    self.write_doc("tech-design.md", tech_design)

    # 3. Reviewer 评审
    review_result = self.reviewer_design.review(
        requirements=requirements,
        tech_design=tech_design
    )
    self.state.design_review_history.append(review_result)

    # 4. 收敛判断
    if self.check_design_convergence():
        self.state.design_converged = True
        self.state.phase = "done"
        self.save_state()
```

### 5.4 Prompt 模板

**文件**：`agent/prompts.py`

> **重要**：所有文档输出必须遵循 `OUTPUT_SPEC.md` 定义的格式规范

```python
# 参考 OUTPUT_SPEC.md 的结构化格式
BUILDER_REQ_SYSTEM = """你是需求分析师。
基于种子想法生成符合 Claude Code 开发需求的结构化需求文档。

## 输出规范
必须遵循 OUTPUT_SPEC.md 中 requirements.md 的格式：
- 项目概述：核心价值、目标用户、成功标准
- 功能需求：核心功能清单 + 用户故事 + 验收标准
- 数据需求：数据实体定义
- 非功能需求：性能、安全、可用性
- 任务清单：可执行的开发任务列表

## 关键原则
- 验收标准必须可测试（[ ] 格式）
- 每个功能点独立描述
- 任务清单可直接交给 Claude Code 执行"""

BUILDER_REQ_PROMPT = """
## 种子想法
{seed}

## 上一轮评审反馈
{previous_feedback}

## 输出要求
按照 OUTPUT_SPEC.md 的 requirements.md 格式输出完整需求文档。
"""

BUILDER_DESIGN_SYSTEM = """你是技术架构师。
基于需求文档设计符合 Claude Code 开发需求的结构化技术方案。

## 输出规范
必须遵循 OUTPUT_SPEC.md 中 tech-design.md 的格式：
- 技术栈：技术选型 + 选择理由
- 系统架构：架构图 + 目录结构
- 接口设计：REST API 规范（请求/响应格式）
- 数据模型：数据库表结构
- 关键实现：核心代码模板
- 开发任务：可执行的开发任务列表

## 关键原则
- 接口设计必须包含完整请求/响应格式
- 目录结构必须清晰、可执行
- 开发任务可直接交给 Claude Code 执行"""

BUILDER_DESIGN_PROMPT = """
## 需求文档
{requirements}

## 上一轮评审反馈
{previous_feedback}

## 输出要求
按照 OUTPUT_SPEC.md 的 tech-design.md 格式输出完整技术方案文档。
"""

REVIEWER_REQ_SYSTEM = """你是需求评审专家。
检查需求文档是否符合种子想法意图，并确保格式规范可执行。

## 评审标准
1. 意图对齐：是否覆盖种子想法核心诉求
2. 完整性：功能需求、数据需求、非功能需求是否完整
3. 可执行性：验收标准是否可测试
4. 格式规范：是否符合 OUTPUT_SPEC.md 的 requirements.md 格式"""

REVIEWER_REQ_PROMPT = """
## 种子想法
{seed}

## 当前需求文档
{requirements}

## 输出格式（评审报告）
评审结果：通过 / 需修改

### 意图对齐
- [x/ ] 覆盖种子想法核心诉求
- 需补充：{如有}

### 完整性
- [x/ ] 功能需求完整
- 需补充：{如有}

### 可执行性
- [x/ ] 验收标准可测试
- 问题：{如有}

### 改进建议
1. {具体可操作的建议}
2. ...
"""

REVIEWER_DESIGN_SYSTEM = """你是技术评审专家。
检查技术方案是否合理可行，并确保格式规范可执行。

## 评审标准
1. 完整性：是否完整覆盖所有需求
2. 技术合理性：技术选型是否合理
3. 可执行性：接口设计、代码模板是否清晰可实现
4. 格式规范：是否符合 OUTPUT_SPEC.md 的 tech-design.md 格式"""

REVIEWER_DESIGN_PROMPT = """
## 需求文档
{requirements}

## 当前技术方案
{tech_design}

## 输出格式（评审报告）
评审结果：通过 / 需修改

### 完整性
- [x/ ] 覆盖所有需求
- 遗漏需求：{如有}

### 技术合理性
- [x/ ] 技术选型合理
- 建议：{如有}

### 可执行性
- [x/ ] 接口设计清晰
- 问题：{如有}

### 改进建议
1. {具体可操作的建议}
2. ...
"""

---

## Phase 6: 测试与集成

### 6.1 单元测试

**文件**：`tests/test_tools.py`
```python
def test_safe_path_blocks_escape():
    with pytest.raises(ValueError):
        safe_path("../../../etc/passwd")

def test_bash_blocks_dangerous():
    assert "blocked" in bash("rm -rf /")

def test_read_write_roundtrip(tmp_path):
    write_file(str(tmp_path / "test.txt"), "hello")
    assert read_file(str(tmp_path / "test.txt")) == "hello"
```

**文件**：`tests/test_subagent.py`
```python
def test_subagent_returns_summary():
    result = run_subagent("Say 'hello world'", ...)
    assert "hello" in result.lower()

def test_subagent_fresh_context():
    # 子智能体不应继承父上下文
    ...
```

**文件**：`tests/test_compact.py`
```python
def test_micro_compact_replaces_old_results():
    messages = create_messages_with_tool_results(5)
    micro_compact(messages, keep_recent=2)
    # 验证旧结果被替换
    ...

def test_auto_compact_saves_transcript():
    messages = create_large_messages()
    compressed = auto_compact(messages)
    assert len(compressed) == 2  # 只剩摘要+确认
    assert Path(".transcripts").exists()
```

**文件**：`tests/test_team.py`
```python
def test_message_bus_send_receive():
    bus = MessageBus(tmp_path)
    bus.send("alice", "bob", "hello")
    messages = bus.read_inbox("bob")
    assert len(messages) == 1
    assert messages[0]["content"] == "hello"
    assert bus.read_inbox("bob") == []  # 已清空
```

### 6.2 集成测试

**文件**：`tests/test_integration.py`

```python
def test_end_to_end_requirements_flow():
    """端到端：种子 → 需求文档"""
    orchestrator = Orchestrator(seed="我想做一个博客系统")
    orchestrator.run()

    assert Path("requirements.md").exists()
    assert len(orchestrator.state.req_review_history) > 0
    assert orchestrator.state.phase in ["tech_design", "done"]

def test_end_to_end_full_flow():
    """端到端：种子 → 完整文档"""
    orchestrator = Orchestrator(seed="我想做一个博客系统")
    orchestrator.run()

    assert Path("requirements.md").exists()
    assert Path("tech-design.md").exists()
    assert orchestrator.state.phase == "done"
```

### 6.3 性能测试

```python
def test_context_compact_handles_large_input():
    """测试大输入下的压缩效果"""
    messages = create_large_conversation(200000)  # 模拟接近context限制
    micro_compact(messages)
    # 验证压缩有效

def test_many_rounds_no_leak():
    """测试多轮迭代后上下文不泄漏"""
    orchestrator = Orchestrator(seed="test")
    for _ in range(10):
        orchestrator.run_requirements_round()
    # 验证上下文大小可控
```

---

## 实施顺序

```
Week 1: Phase 1 - 基础架构
  ├── 1.1 项目结构
  ├── 1.2 Agent Loop
  └── 1.3 基础工具

Week 2: Phase 2 - 子智能体系统
  ├── 2.1 Subagent 实现
  └── 2.2 Task 工具

Week 3: Phase 3 - 上下文管理
  ├── 3.1 三层压缩
  └── 3.2 状态持久化

Week 4: Phase 4 - 团队协作
  ├── 4.1 TeammateManager
  ├── 4.2 MessageBus
  └── 4.3 Team Protocols

Week 5: Phase 5 - 业务编排
  ├── 5.1 Orchestrator
  ├── 5.2 需求阶段
  ├── 5.3 方案阶段
  └── 5.4 Prompt 模板

Week 6: Phase 6 - 测试与集成
  ├── 6.1 单元测试
  ├── 6.2 集成测试
  └── 6.3 性能测试
```

---

## 检查清单

### 交付物

- [ ] `agent/` 模块结构完整
- [ ] `tools/` 工具可正常调用
- [ ] 子智能体隔离有效
- [ ] 三层压缩工作正常
- [ ] 状态可保存/恢复
- [ ] 团队协作消息正确
- [ ] 协议握手正确
- [ ] Orchestrator 流程完整
- [ ] 单元测试覆盖
- [ ] 集成测试通过

### 质量标准

- [ ] 代码可读性
- [ ] 错误处理完善
- [ ] 文档完整
- [ ] 无安全漏洞

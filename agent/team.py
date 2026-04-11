"""Team management - persistent teammates with message bus."""

import json
import threading
import time
from pathlib import Path

from agent.loop import create_client
from agent.config import MODEL_ID, MAX_TOKENS, TEAM_DIR, INBOX_DIR, MAX_ITERATIONS
from agent.constants import VALID_MSG_TYPES


class MessageBus:
    """JSONL-based inbox per teammate."""

    def __init__(self, inbox_dir: Path | None = None) -> None:
        self.dir = inbox_dir or INBOX_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(
        self,
        sender: str,
        to: str,
        content: str,
        msg_type: str = "message",
        extra: dict | None = None,
    ) -> str:
        """Send message by appending to recipient's inbox."""
        if msg_type not in VALID_MSG_TYPES:
            return f"Error: Invalid type '{msg_type}'. Valid: {VALID_MSG_TYPES}"

        msg = {
            "type": msg_type,
            "from": sender,
            "content": content,
            "timestamp": time.time(),
        }
        if extra:
            msg.update(extra)

        inbox_path = self.dir / f"{to}.jsonl"
        with open(inbox_path, "a") as f:
            f.write(json.dumps(msg) + "\n")

        return f"Sent {msg_type} to {to}"

    def read_inbox(self, name: str) -> list:
        """Read and drain inbox."""
        inbox_path = self.dir / f"{name}.jsonl"
        if not inbox_path.exists():
            return []

        messages = []
        for line in inbox_path.read_text().strip().splitlines():
            if line:
                messages.append(json.loads(line))

        inbox_path.write_text("")  # drain
        return messages

    def broadcast(self, sender: str, content: str, teammates: list) -> str:
        """Broadcast to all teammates."""
        count = 0
        for name in teammates:
            if name != sender:
                self.send(sender, name, content, "broadcast")
                count += 1
        return f"Broadcast to {count} teammates"


class TeammateManager:
    """Manage persistent teammates with thread-based execution."""

    def __init__(self, team_dir: Path | None = None) -> None:
        self.dir = team_dir or TEAM_DIR
        self.dir.mkdir(exist_ok=True)
        self.config_path = self.dir / "config.json"
        self.threads = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load or initialize team config."""
        if self.config_path.exists():
            self.config = json.loads(self.config_path.read_text())
        else:
            self.config = {"team_name": "default", "members": []}

    def _save_config(self) -> None:
        """Save team config."""
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def _find_member(self, name: str) -> dict | None:
        """Find member by name."""
        for m in self.config["members"]:
            if m["name"] == name:
                return m
        return None

    def spawn(self, name: str, role: str, prompt: str) -> str:
        """Spawn a persistent teammate in a new thread."""
        member = self._find_member(name)
        if member:
            if member["status"] not in ("idle", "shutdown"):
                return f"Error: '{name}' is currently {member['status']}"
            member["status"] = "working"
            member["role"] = role
        else:
            member = {"name": name, "role": role, "status": "working"}
            self.config["members"].append(member)

        self._save_config()

        thread = threading.Thread(
            target=self._teammate_loop,
            args=(name, role, prompt),
            daemon=True,
        )
        self.threads[name] = thread
        thread.start()

        return f"Spawned '{name}' (role: {role})"

    def _teammate_loop(self, name: str, role: str, prompt: str) -> None:
        """Main loop for teammate agent."""
        sys_prompt = (
            f"You are '{name}', role: {role}. "
            f"Work on tasks assigned to you. Use send_message to communicate results."
        )


        messages = [{"role": "user", "content": prompt}]
        tools = self._teammate_tools()
        should_exit = False

        for _ in range(MAX_ITERATIONS):
            inbox = BUS.read_inbox(name)
            for msg in inbox:
                messages.append({"role": "user", "content": json.dumps(msg)})

            if should_exit:
                break

            try:
                client = create_client()
                response = client.messages.create(
                    model=MODEL_ID,
                    system=sys_prompt,
                    messages=messages,
                    tools=tools,
                    max_tokens=MAX_TOKENS,
                )
            except Exception as e:
                print(f"  [{name}] API error: {e}")
                break

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = self._exec(name, block.name, block.input)
                    print(f"  [{name}] {block.name}: {str(output)[:120]}")
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output),
                    })
                    if block.name == "shutdown_response" and block.input.get("approve"):
                        should_exit = True

            messages.append({"role": "user", "content": results})

        member = self._find_member(name)
        if member:
            member["status"] = "shutdown" if should_exit else "idle"
            self._save_config()

    def _exec(self, sender: str, tool_name: str, args: dict) -> str:
        """Execute tool call for teammate."""
        from tools.base import run_bash, run_read, run_write, run_edit

        if tool_name == "bash":
            return run_bash(args["command"])
        if tool_name == "read_file":
            return run_read(args["path"])
        if tool_name == "write_file":
            return run_write(args["path"], args["content"])
        if tool_name == "edit_file":
            return run_edit(args["path"], args["old_text"], args["new_text"])
        if tool_name == "send_message":
            return BUS.send(sender, args["to"], args["content"], args.get("msg_type", "message"))
        if tool_name == "read_inbox":
            return json.dumps(BUS.read_inbox(sender), indent=2)

        return f"Unknown tool: {tool_name}"

    def _teammate_tools(self) -> list:
        """Tools available to teammates."""
        from tools.base import TOOL_SCHEMAS

        return [
            *TOOL_SCHEMAS,
            {
                "name": "send_message",
                "description": "Send message to a teammate.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string"},
                        "content": {"type": "string"},
                        "msg_type": {
                            "type": "string",
                            "enum": list(VALID_MSG_TYPES),
                        },
                    },
                    "required": ["to", "content"],
                },
            },
            {
                "name": "read_inbox",
                "description": "Read and drain your inbox.",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]

    def list_all(self) -> str:
        """List all teammates with status."""
        if not self.config["members"]:
            return "No teammates."

        lines = [f"Team: {self.config['team_name']}"]
        for m in self.config["members"]:
            lines.append(f"  {m['name']} ({m['role']}): {m['status']}")
        return "\n".join(lines)

    def member_names(self) -> list:
        """Get list of all teammate names."""
        return [m["name"] for m in self.config["members"]]


# Global instances
BUS = MessageBus()
TEAM = TeammateManager()

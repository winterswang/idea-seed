"""Base tools: bash, read, write, edit with path sandboxing."""

import re
import subprocess
from pathlib import Path

from agent.config import WORKDIR


def safe_path(p: str) -> Path:
    """Resolve path and ensure it's within WORKDIR.

    Args:
        p: Path string (absolute or relative to WORKDIR)

    Returns:
        Resolved absolute path within WORKDIR

    Raises:
        ValueError: If path escapes WORKDIR or is a bare filename (no directory)
    """
    # Reject bare filenames - they would be written to WORKDIR root
    # This prevents subagents from accidentally writing to project root
    if "/" not in p and "\\" not in p and not p.startswith("."):
        raise ValueError(
            f"Path must be within a subdirectory. "
            f"Bare filename '{p}' not allowed. "
            f"Use format like 'projects/my-project/{p}' instead."
        )

    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path


def run_bash(command: str) -> str:
    """Execute shell command with safety checks."""
    # Block dangerous patterns for remote code execution and privilege escalation
    dangerous_patterns = [
        r"rm\s+-rf\s+/",  # rm -rf /
        r"sudo",  # sudo
        r"shutdown",  # shutdown
        r"reboot",  # reboot
        r">\s*/dev/",  # > /dev/
        r"curl.*\|",  # curl ... | (pipe to any command)
        r"curl.*&&\s*(bash|sh)",  # curl ... && bash/sh
        r"curl.*;\s*(bash|sh)",  # curl ... ; bash/sh
        r"wget.*\|",  # wget ... | (pipe to any command)
        r"wget.*&&\s*(bash|sh)",  # wget ... && bash/sh
        r"wget.*;\s*(bash|sh)",  # wget ... ; bash/sh
    ]
    if any(re.search(pattern, command) for pattern in dangerous_patterns):
        return "Error: Dangerous command blocked"

    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=WORKDIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"
    except Exception as e:
        return f"Error: {e}"


def run_read(path: str, limit: int | None = None) -> str:
    """Read file contents with optional line limit."""
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"


def run_write(path: str, content: str) -> str:
    """Write content to file."""
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"


def run_edit(path: str, old_text: str, new_text: str) -> str:
    """Replace exact text in file."""
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


# Tool handlers dispatch map
TOOL_HANDLERS = {
    "bash": lambda **kw: run_bash(kw["command"]),
    "read_file": lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file": lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
    "compact": lambda **kw: "Manual compact triggered - compression will happen if threshold exceeded",
}


# Tool schemas for LLM
TOOL_SCHEMAS = [
    {
        "name": "bash",
        "description": "Run a shell command.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read file contents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace exact text in file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "compact",
        "description": "Trigger context compression to free up context. Use when the conversation becomes too long or you're repeating yourself.",
        "input_schema": {
            "type": "object",
            "properties": {
                "focus": {
                    "type": "string",
                    "description": "What to focus on preserving in the compressed context",
                },
            },
        },
    },
]

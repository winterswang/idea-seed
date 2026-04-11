"""Subagent - spawn child agents with fresh context."""

import time
from typing import Any

from agent.loop import create_client
from agent.config import MODEL_ID, MAX_TOKENS
from tools.base import TOOL_HANDLERS, TOOL_SCHEMAS

# Minimum content length to consider valid (avoids "(no summary)" cases)
MIN_CONTENT_LENGTH = 500


def run_subagent(
    prompt: str,
    system: str,
    tools: list[dict] | None = None,
    max_tokens: int = MAX_TOKENS,
    max_iterations: int = 10,
    max_retries: int = 3,
) -> str:
    """
    Run a subagent with fresh context.

    Child agent works in its own context, shares filesystem,
    then returns only a summary to the parent.

    Args:
        prompt: Task prompt for the subagent
        system: System prompt for subagent
        tools: Tool schemas (uses base tools if None)
        max_tokens: Max tokens for response
        max_iterations: Safety limit for tool calls
        max_retries: Max retries for API errors or short content

    Returns:
        Summary text from the subagent
    """
    client = create_client()
    sub_messages = [{"role": "user", "content": prompt}]
    active_tools = tools if tools is not None else TOOL_SCHEMAS

    # Get handlers for active tools (exclude 'task' to prevent recursion)
    tool_handlers = {}
    for t in active_tools:
        name = t["name"]
        if name != "task" and name in TOOL_HANDLERS:
            tool_handlers[name] = TOOL_HANDLERS[name]

    for iteration in range(max_iterations):
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Use streaming for long-running operations
                with client.messages.stream(
                    model=MODEL_ID,
                    system=system,
                    messages=sub_messages,
                    tools=active_tools,
                    max_tokens=max_tokens,
                ) as stream:
                    response = stream.get_final_message()

                sub_messages.append({"role": "assistant", "content": response.content})

                if response.stop_reason != "tool_use":
                    break

                # Get tool use results from the streaming response
                # Reconstruct tool calls from the response
                results = []
                for block in response.content:
                    if block.type == "tool_use":
                        handler = tool_handlers.get(block.name)
                        if handler:
                            output = handler(**block.input)
                        else:
                            output = f"Unknown tool: {block.name}"

                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(output)[:50000],
                            }
                        )

                sub_messages.append({"role": "user", "content": results})

            except Exception as e:
                _ = e  # Suppress lint warning - error is re-raised below
                retry_count += 1
                if retry_count < max_retries:
                    # Exponential backoff
                    time.sleep(2**retry_count)
                    continue
                raise

        # After getting response, check content length
        content = _extract_summary(response.content)
        if len(content) < MIN_CONTENT_LENGTH and iteration < max_iterations - 1:
            # Content too short, retry with fresh context
            # Add a hint to the prompt about expected length
            hint = f"\n\n[Note: Previous response was too short ({len(content)} chars). Please generate a comprehensive document with substantial content (at least {MIN_CONTENT_LENGTH} chars).]"
            sub_messages = [{"role": "user", "content": prompt + hint}]
            continue

        # Return summary only - child context is discarded
        return content

    # Final fallback - return whatever we got
    return _extract_summary(response.content)


def _extract_summary(content: Any) -> str:
    """Extract summary text from final response."""
    if isinstance(content, list):
        texts = [b.text for b in content if hasattr(b, "text")]
        return "".join(texts) or "(no summary)"
    return str(content)


# Child agent tools - base tools only (no task to prevent recursion)
CHILD_TOOLS = [
    t for t in TOOL_SCHEMAS if t["name"] not in ("task", "spawn", "shutdown_request")
]


# Parent tools - base tools + task
PARENT_TOOLS = TOOL_SCHEMAS + [
    {
        "name": "task",
        "description": "Spawn a subagent with fresh context. Use for independent subtasks.",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "description": {
                    "type": "string",
                    "description": "Short description of the task",
                },
            },
            "required": ["prompt"],
        },
    },
]

"""Subagent - spawn child agents with fresh context."""

import time
from typing import Any, Optional

from agent.loop import create_client
from agent.config import MODEL_ID, MAX_TOKENS, TOKEN_THRESHOLD, KEEP_RECENT
from agent.compact import micro_compact, compact_if_needed
from tools.base import TOOL_HANDLERS, TOOL_SCHEMAS

# Minimum content length to consider valid (avoids "(no summary)" cases)
MIN_CONTENT_LENGTH = 500

# Type alias for token tracker
TokenTracker = "TokenTracker"  # Forward reference


def run_subagent(
    prompt: str,
    system: str,
    tools: list[dict] | None = None,
    max_tokens: int = MAX_TOKENS,
    max_iterations: int = 10,
    max_retries: int = 3,
    token_tracker: Optional[Any] = None,
    phase: str = "",
    round_num: int = 0,
    compact_enabled: bool = True,
) -> tuple[str, Optional[dict]]:
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
        token_tracker: Optional TokenTracker instance for recording usage
        phase: Current phase (requirements/tech_design)
        round_num: Current round number
        compact_enabled: Whether to enable context compression

    Returns:
        Tuple of (summary text, usage info dict or None)
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

    usage_info: Optional[dict] = None

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

                # Extract usage info from response
                if hasattr(response, "usage") and response.usage:
                    usage_info = {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    }
                    # Record usage if tracker is provided
                    if token_tracker:
                        token_tracker.record(
                            model=MODEL_ID,
                            usage=usage_info,
                            phase=phase,
                            round_num=round_num,
                        )

                sub_messages.append({"role": "assistant", "content": response.content})

                # Layer 1: Micro compression after each response
                if compact_enabled:
                    sub_messages = micro_compact(sub_messages, keep_recent=KEEP_RECENT)

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

        # Layer 2: Check if compression is needed before returning
        if compact_enabled:
            sub_messages = compact_if_needed(sub_messages, threshold=TOKEN_THRESHOLD)

        # Return summary and usage info - child context is discarded
        return content, usage_info

    # Final fallback - return whatever we got
    content = _extract_summary(response.content)
    return content, usage_info


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

"""Subagent - spawn child agents with fresh context."""

import logging
import threading
import time
from typing import Any, Optional

from agent.loop import create_client
from agent.config import MODEL_ID, MAX_TOKENS, TOKEN_THRESHOLD, KEEP_RECENT
from agent.compact import micro_compact, compact_if_needed
from agent.constants import MIN_SUBAGENT_CONTENT_LENGTH, API_TIMEOUT_SECONDS, HEARTBEAT_INTERVAL_SECONDS, SHELL_OUTPUT_TRUNCATION
from tools.base import TOOL_HANDLERS, TOOL_SCHEMAS

# Minimum content length to consider valid (avoids "(no summary)" cases)
MIN_CONTENT_LENGTH = MIN_SUBAGENT_CONTENT_LENGTH

# API timeout in seconds
API_TIMEOUT = API_TIMEOUT_SECONDS

# Heartbeat interval for long API calls
HEARTBEAT_INTERVAL = HEARTBEAT_INTERVAL_SECONDS


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
    _logger = logging.getLogger("idea-seed")
    _logger.info(f"[SUBAGENT] Starting subagent | phase={phase} round={round_num} max_tokens={max_tokens}")
    _logger.info(f"[SUBAGENT] Prompt length: {len(prompt)} chars, System length: {len(system)} chars")

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
    response = None
    last_error: Optional[Exception] = None

    for iteration in range(max_iterations):
        _logger.info(f"[SUBAGENT] Iteration {iteration + 1}/{max_iterations} | messages count: {len(sub_messages)}")
        retry_count = 0
        short_content_streak = 0

        while retry_count < max_retries:
            try:
                _logger.info(f"[SUBAGENT] Calling API | model={MODEL_ID} | messages={len(sub_messages)} | tools={len(active_tools)} | timeout={API_TIMEOUT}s")
                api_start = time.time()

                # Start heartbeat thread for long-running API calls
                stop_heartbeat = threading.Event()
                heartbeat_thread = threading.Thread(
                    target=_heartbeat_log,
                    args=(_logger, api_start, phase, iteration, stop_heartbeat),
                    daemon=True,
                )
                heartbeat_thread.start()

                # Use streaming for long-running operations with timeout
                try:
                    with client.messages.stream(
                        model=MODEL_ID,
                        system=system,
                        messages=sub_messages,
                        tools=active_tools,
                        max_tokens=max_tokens,
                        timeout=API_TIMEOUT,
                    ) as stream:
                        response = stream.get_final_message()
                finally:
                    stop_heartbeat.set()
                    heartbeat_thread.join(timeout=2)

                api_duration = time.time() - api_start
                _logger.info(f"[SUBAGENT] API response received | duration={api_duration:.1f}s | stop_reason={response.stop_reason}")

                # Extract usage info from response
                if hasattr(response, "usage") and response.usage:
                    usage_info = {
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    }
                    _logger.info(f"[SUBAGENT] Token usage | input={usage_info['input_tokens']} output={usage_info['output_tokens']} total={usage_info['input_tokens'] + usage_info['output_tokens']}")
                    # Record usage if tracker is provided
                    if token_tracker:
                        token_tracker.record(
                            model=MODEL_ID,
                            usage=usage_info,
                            phase=phase,
                            round_num=round_num,
                        )

                sub_messages.append({"role": "assistant", "content": response.content})
                _logger.info(f"[SUBAGENT] Response content length: {len(str(response.content))} chars | blocks: {len(response.content) if isinstance(response.content, list) else 'N/A'}")

                # Layer 1: Micro compression after each response
                if compact_enabled:
                    before_compact = len(sub_messages)
                    sub_messages = micro_compact(sub_messages, keep_recent=KEEP_RECENT)
                    after_compact = len(sub_messages)
                    if before_compact != after_compact:
                        _logger.info(f"[SUBAGENT] Micro compression | before={before_compact} after={after_compact}")

                if response.stop_reason != "tool_use":
                    _logger.info(f"[SUBAGENT] Stop reason: {response.stop_reason} (not tool_use)")
                    break

                # Get tool use results from the streaming response
                # Reconstruct tool calls from the response
                results = []
                tool_call_count = 0
                for block in response.content:
                    if block.type == "tool_use":
                        tool_call_count += 1
                        handler = tool_handlers.get(block.name)
                        if handler:
                            output = handler(**block.input)
                        else:
                            output = f"Unknown tool: {block.name}"

                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(output)[:SHELL_OUTPUT_TRUNCATION],
                            }
                        )
                _logger.info(f"[SUBAGENT] Tool calls: {tool_call_count} | results: {len(results)}")

                sub_messages.append({"role": "user", "content": results})

            except Exception as e:
                stop_heartbeat.set()
                last_error = e
                error_type = type(e).__name__

                # Check for timeout
                if "timeout" in error_type.lower() or "Timed out" in str(e):
                    _logger.warning(f"[SUBAGENT] API timeout after {API_TIMEOUT}s (attempt {retry_count + 1}/{max_retries})")
                else:
                    _logger.warning(f"[SUBAGENT] API error (attempt {retry_count + 1}/{max_retries}): {error_type}: {e}")

                retry_count += 1
                if retry_count < max_retries:
                    # Exponential backoff
                    sleep_time = 2**retry_count
                    _logger.info(f"[SUBAGENT] Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                raise RuntimeError(
                    f"Subagent failed after {max_retries} retries"
                ) from last_error

        # After getting response, check content length
        content = _extract_summary(response.content)
        _logger.info(f"[SUBAGENT] Content extracted | length={len(content)} chars | min_required={MIN_CONTENT_LENGTH}")

        short_content_streak += 1
        if len(content) < MIN_CONTENT_LENGTH and iteration < max_iterations - 1 and short_content_streak < 3:
            # Content too short, retry with fresh context
            # Add a hint to the prompt about expected length
            hint = f"\n\n[Note: Previous response was too short ({len(content)} chars). Please generate a comprehensive document with substantial content (at least {MIN_CONTENT_LENGTH} chars).]"
            sub_messages = [{"role": "user", "content": prompt + hint}]
            _logger.info(f"[SUBAGENT] Content too short, retrying with length hint")
            continue

        # Layer 2: Check if compression is needed before returning
        if compact_enabled:
            before_compact = len(sub_messages)
            sub_messages = compact_if_needed(sub_messages, threshold=TOKEN_THRESHOLD)
            after_compact = len(sub_messages)
            if before_compact != after_compact:
                _logger.info(f"[SUBAGENT] Context compression | before={before_compact} after={after_compact}")

        # Return summary and usage info - child context is discarded
        _logger.info(f"[SUBAGENT] Completed | content_length={len(content)} chars")
        return content, usage_info

    # Final fallback - return whatever we got
    _logger.warning(f"[SUBAGENT] Max iterations reached, returning fallback")
    if response is not None:
        content = _extract_summary(response.content)
        return content, usage_info
    _logger.warning(f"[SUBAGENT] No response, returning empty")
    return "(no response)", usage_info


def _heartbeat_log(logger: logging.Logger, start_time: float, phase: str, iteration: int, stop_event: threading.Event) -> None:
    """Log progress heartbeat while waiting for API response."""
    count = 0
    while not stop_event.is_set():
        count += 1
        elapsed = time.time() - start_time
        logger.info(f"[SUBAGENT] Waiting for API response... ({elapsed:.0f}s elapsed) [phase={phase} iteration={iteration + 1}]")
        stop_event.wait(HEARTBEAT_INTERVAL)


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

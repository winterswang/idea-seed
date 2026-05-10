"""Three-layer context compression for long sessions."""

import json
import logging
import time

from agent.loop import create_client
from agent.config import MODEL_ID, TOKEN_THRESHOLD, KEEP_RECENT, TRANSCRIPT_DIR

_logger = logging.getLogger("idea-seed")


def estimate_tokens(messages: list) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(str(messages)) // 4


def micro_compact(messages: list, keep_recent: int = KEEP_RECENT) -> list:
    """
    Layer 1: Replace old tool results with placeholders.

    Runs silently every turn to prevent context bloat.
    """
    tool_results = []
    for msg_idx, msg in enumerate(messages):
        if msg["role"] == "user" and isinstance(msg.get("content"), list):
            for part_idx, part in enumerate(msg["content"]):
                if isinstance(part, dict) and part.get("type") == "tool_result":
                    tool_results.append((msg_idx, part_idx, part))

    if len(tool_results) <= keep_recent:
        return messages

    # Build tool name map from assistant messages
    tool_name_map = {}
    for msg in messages:
        if msg["role"] == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_name_map[block.id] = block.name

    # Replace old results with placeholders
    replaced_count = 0
    for _, _, result in tool_results[:-keep_recent]:
        if isinstance(result.get("content"), str) and len(result["content"]) > 100:
            tool_id = result.get("tool_use_id", "")
            tool_name = tool_name_map.get(tool_id, "unknown")
            result["content"] = f"[Previous: used {tool_name}]"
            replaced_count += 1

    if replaced_count > 0:
        _logger.debug(f"[COMPACT] micro_compact replaced {replaced_count} tool results (keep_recent={keep_recent})")

    return messages


def auto_compact(messages: list) -> list:
    """
    Layer 2: Save transcript and summarize when token threshold exceeded.

    Saves full conversation to disk, asks LLM to summarize,
    replaces all messages with compressed summary.
    """
    before_count = len(messages)
    _logger.info(f"[COMPACT] auto_compact triggered | before={before_count} messages | threshold={TOKEN_THRESHOLD}")

    TRANSCRIPT_DIR.mkdir(exist_ok=True)
    transcript_path = TRANSCRIPT_DIR / f"transcript_{int(time.time())}.jsonl"

    # Save full transcript
    with open(transcript_path, "w") as f:
        for msg in messages:
            f.write(json.dumps(msg, default=str) + "\n")
    _logger.info(f"[COMPACT] Transcript saved to {transcript_path}")

    # Ask LLM to summarize
    client = create_client()
    conversation_text = json.dumps(messages, default=str)[:80000]

    _logger.info(f"[COMPACT] Calling summarization API | input_chars={len(conversation_text)}")
    start_time = time.time()

    response = client.messages.create(
        model=MODEL_ID,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this conversation for continuity. Include: "
                    "1) What was accomplished, 2) Current state, "
                    "3) Key decisions made. Be concise but preserve critical details.\n\n"
                    + conversation_text
                ),
            }
        ],
        max_tokens=2000,
    )

    duration = time.time() - start_time
    summary = response.content[0].text if response.content else "Summary unavailable"
    _logger.info(f"[COMPACT] Summarization completed | duration={duration:.1f}s | summary_len={len(summary)} chars")

    # Replace messages with compressed summary
    compressed = [
        {
            "role": "user",
            "content": f"[Compressed. Transcript saved: {transcript_path}]\n\n{summary}",
        },
        {
            "role": "assistant",
            "content": "Understood. I have the context from the summary. Continuing.",
        },
    ]
    _logger.info(f"[COMPACT] auto_compact done | after={len(compressed)} messages")

    return compressed


def compact_tool(messages: list) -> list:
    """
    Layer 3: Manual compression triggered by tool call.

    Same as auto_compact but triggered explicitly.
    """
    _logger.info("[COMPACT] manual compact triggered")
    return auto_compact(messages)


def compact_if_needed(messages: list, threshold: int = TOKEN_THRESHOLD) -> list:
    """
    Check threshold and compress if needed.

    Returns modified messages list if compressed, otherwise unchanged.
    """
    current_tokens = estimate_tokens(messages)
    if current_tokens > threshold:
        _logger.info(f"[COMPACT] threshold exceeded | current={current_tokens} > threshold={threshold}")
        print("[auto_compact triggered]")
        return auto_compact(messages)
    return messages


# Tool schema for manual compact
COMPACT_TOOL = {
    "name": "compact",
    "description": "Trigger manual conversation compression to free up context.",
    "input_schema": {
        "type": "object",
        "properties": {
            "focus": {
                "type": "string",
                "description": "What to preserve in the summary",
            },
        },
    },
}

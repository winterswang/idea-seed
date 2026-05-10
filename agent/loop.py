"""Agent Loop - core pattern for LLM interaction."""

import logging
import time
from anthropic import Anthropic

from agent.config import MODEL_ID, MAX_TOKENS, get_api_key, get_base_url
from tools.base import TOOL_HANDLERS, TOOL_SCHEMAS

_logger = logging.getLogger("idea-seed")


def create_client() -> Anthropic:
    """Create Anthropic client with active provider's configuration."""
    return Anthropic(
        base_url=get_base_url(),
        api_key=get_api_key(),
    )


def agent_loop(
    messages: list[dict],
    system: str,
    tools: list[dict] | None = None,
    max_tokens: int = MAX_TOKENS,
    max_iterations: int = 10,
) -> dict:
    """
    Core agent loop: while stop_reason == 'tool_use'.

    Args:
        messages: List of message dicts with 'role' and 'content'
        system: System prompt
        tools: List of tool schemas (uses base tools if None)
        max_tokens: Max tokens for response
        max_iterations: Safety limit for tool calls (default 10)

    Returns:
        Final response content

    Raises:
        RuntimeError: If max iterations reached
    """
    client = create_client()
    active_tools = tools if tools is not None else TOOL_SCHEMAS
    tool_handlers = {
        t["name"]: TOOL_HANDLERS[t["name"]]
        for t in active_tools
        if t["name"] in TOOL_HANDLERS
    }

    _logger.info(f"[LOOP] Starting agent_loop | tools={len(active_tools)} max_iterations={max_iterations}")

    for iteration in range(max_iterations):
        _logger.info(f"[LOOP] Iteration {iteration + 1}/{max_iterations} | messages={len(messages)}")

        # API call
        _logger.info(f"[LOOP] Calling API | model={MODEL_ID} | system_len={len(system)} | messages={len(messages)}")
        call_start = time.time()

        response = client.messages.create(
            model=MODEL_ID,
            system=system,
            messages=messages,
            tools=active_tools,
            max_tokens=max_tokens,
        )

        call_duration = time.time() - call_start
        _logger.info(f"[LOOP] API response | duration={call_duration:.1f}s | stop_reason={response.stop_reason}")

        # Log token usage
        if hasattr(response, "usage") and response.usage:
            _logger.info(f"[LOOP] Token usage | input={response.usage.input_tokens} output={response.usage.output_tokens}")

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            _logger.info(f"[LOOP] Final response | stop_reason={response.stop_reason}")
            return response.content

        # Execute tool calls
        _logger.info(f"[LOOP] Processing tool calls | blocks={len(response.content)}")
        results = []
        tool_count = 0
        for block in response.content:
            if block.type == "tool_use":
                tool_count += 1
                tool_name = block.name
                tool_input = block.input
                _logger.info(f"[LOOP] Tool call | name={tool_name} id={block.id}")

                handler = tool_handlers.get(tool_name)
                if handler:
                    exec_start = time.time()
                    output = handler(**tool_input)
                    exec_duration = time.time() - exec_start
                    _logger.info(f"[LOOP] Tool result | name={tool_name} duration={exec_duration:.1f}s output_len={len(str(output))}")
                else:
                    output = f"Unknown tool: {tool_name}"
                    _logger.warning(f"[LOOP] Unknown tool | name={tool_name}")

                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(output)[:10000],  # Truncate for logging
                    }
                )

        _logger.info(f"[LOOP] Tools executed | total={tool_count} results={len(results)}")
        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"Max iterations ({max_iterations}) reached")


def extract_text(content: object) -> str:
    """Extract text from response content."""
    if isinstance(content, list):
        return "".join(
            b.text if hasattr(b, "text") else b.thinking
            for b in content
            if hasattr(b, "text") or hasattr(b, "thinking")
        )
    return str(content)

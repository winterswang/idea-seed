"""Agent Loop - core pattern for LLM interaction."""

from anthropic import Anthropic

from agent.config import MODEL_ID, MAX_TOKENS, get_api_key, get_base_url
from tools.base import TOOL_HANDLERS, TOOL_SCHEMAS


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
    tool_handlers = {t["name"]: TOOL_HANDLERS[t["name"]] for t in active_tools if t["name"] in TOOL_HANDLERS}

    for _ in range(max_iterations):
        response = client.messages.create(
            model=MODEL_ID,
            system=system,
            messages=messages,
            tools=active_tools,
            max_tokens=max_tokens,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            return response.content

        # Execute tool calls
        results = []
        for block in response.content:
            if block.type == "tool_use":
                handler = tool_handlers.get(block.name)
                if handler:
                    output = handler(**block.input)
                else:
                    output = f"Unknown tool: {block.name}"

                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(output),
                })

        messages.append({"role": "user", "content": results})

    raise RuntimeError(f"Max iterations ({max_iterations}) reached")


def extract_text(content: object) -> str:
    """Extract text from response content."""
    if isinstance(content, list):
        return "".join(b.text for b in content if hasattr(b, "text"))
    return str(content)

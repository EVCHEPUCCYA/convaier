from __future__ import annotations

import logging
from pathlib import Path

import ollama as ollama_lib

from convaier.agent.tools import execute_tool
from convaier.config import OllamaConfig

log = logging.getLogger("convaier")


def create_client(config: OllamaConfig) -> ollama_lib.Client:
    return ollama_lib.Client(host=config.host, timeout=config.timeout)


def agent_loop(
    client: ollama_lib.Client,
    model: str,
    messages: list[dict],
    tools: list[dict] | None = None,
    project_root: Path | None = None,
    max_rounds: int = 5,
) -> str:
    for i in range(max_rounds):
        kwargs: dict = {"model": model, "messages": messages}
        if tools:
            kwargs["tools"] = tools

        response = client.chat(**kwargs)
        msg = response.message

        # Append assistant message
        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        # If no tool calls, we're done
        if not msg.tool_calls:
            return msg.content or ""

        # Execute tool calls
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = tc.function.arguments
            log.debug("  Tool call: %s(%s)", tool_name, tool_args)

            if project_root:
                result = execute_tool(tool_name, tool_args, project_root)
            else:
                result = f"Error: no project root for tool {tool_name}"

            messages.append({"role": "tool", "content": result})

    # Fallback after max rounds
    last_content = messages[-1].get("content", "")
    return last_content if isinstance(last_content, str) else ""

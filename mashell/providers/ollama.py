"""Ollama provider implementation."""

from typing import Any

import httpx

from mashell.providers.base import BaseProvider, Message, Response, ToolCall


class OllamaProvider(BaseProvider):
    """Provider for Ollama local API."""

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Response:
        """Send messages to Ollama and get response."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._format_message(m) for m in messages],
            "stream": False,
        }

        if tools:
            payload["tools"] = tools

        # 本地 Ollama 不走代理
        async with httpx.AsyncClient(
            proxy=None,
            transport=httpx.AsyncHTTPTransport(proxy=None),
        ) as client:
            response = await client.post(
                f"{self.url}/api/chat",
                json=payload,
                timeout=300.0,  # Longer timeout for local models
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _format_message(self, msg: Message) -> dict[str, Any]:
        """Format a message for the Ollama API."""
        d: dict[str, Any] = {"role": msg.role}

        if msg.content is not None:
            d["content"] = msg.content

        if msg.tool_calls:
            d["tool_calls"] = [self._format_tool_call(tc) for tc in msg.tool_calls]

        return d

    def _format_tool_call(self, tc: ToolCall) -> dict[str, Any]:
        """Format a tool call for Ollama."""
        return {
            "function": {
                "name": tc.name,
                "arguments": tc.arguments,
            }
        }

    def _parse_response(self, data: dict[str, Any]) -> Response:
        """Parse Ollama API response."""
        message = data.get("message", {})

        content = message.get("content")
        raw_tool_calls = message.get("tool_calls")

        tool_calls = None
        if raw_tool_calls:
            tool_calls = self._parse_ollama_tool_calls(raw_tool_calls)

        finish_reason = "tool_calls" if tool_calls else "stop"

        return Response(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    def _parse_ollama_tool_calls(self, raw_tool_calls: list[dict[str, Any]]) -> list[ToolCall]:
        """Parse Ollama-style tool calls."""
        tool_calls = []
        for i, tc in enumerate(raw_tool_calls):
            func = tc.get("function", {})
            tool_calls.append(
                ToolCall(
                    id=f"call_{i}",
                    name=func.get("name", ""),
                    arguments=func.get("arguments", {}),
                )
            )
        return tool_calls

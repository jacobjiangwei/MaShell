"""Anthropic provider implementation."""

from typing import Any

import httpx

from mashell.providers.base import BaseProvider, Message, Response, ToolCall


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude API."""

    API_VERSION = "2023-06-01"

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Response:
        """Send messages to Anthropic and get response."""
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.key or "",
            "anthropic-version": self.API_VERSION,
        }

        # Extract system message
        system_content = ""
        conversation_messages = []
        for msg in messages:
            if msg.role == "system":
                system_content = msg.content or ""
            else:
                conversation_messages.append(msg)

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [self._format_message(m) for m in conversation_messages],
        }

        if system_content:
            payload["system"] = system_content

        if tools:
            payload["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/v1/messages",
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

        return self._parse_response(data)

    def _format_message(self, msg: Message) -> dict[str, Any]:
        """Format a message for the Anthropic API."""
        if msg.role == "tool":
            # Tool result format for Anthropic
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content or "",
                    }
                ],
            }

        if msg.role == "assistant" and msg.tool_calls:
            # Assistant with tool calls
            content: list[dict[str, Any]] = []
            if msg.content:
                content.append({"type": "text", "text": msg.content})
            for tc in msg.tool_calls:
                content.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    }
                )
            return {"role": "assistant", "content": content}

        return {
            "role": msg.role,
            "content": msg.content or "",
        }

    def _convert_tools(self, openai_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI tool format to Anthropic format."""
        anthropic_tools = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                anthropic_tools.append(
                    {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "input_schema": func.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    }
                )
        return anthropic_tools

    def _parse_response(self, data: dict[str, Any]) -> Response:
        """Parse Anthropic API response."""
        content_blocks = data.get("content", [])

        text_content = ""
        tool_calls: list[ToolCall] = []

        for block in content_blocks:
            if block["type"] == "text":
                text_content += block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    )
                )

        stop_reason = data.get("stop_reason", "end_turn")
        finish_reason = "tool_calls" if stop_reason == "tool_use" else "stop"

        usage = data.get("usage", {})

        return Response(
            content=text_content if text_content else None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=finish_reason,
            usage={
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        )

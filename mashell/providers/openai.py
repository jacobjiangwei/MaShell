"""OpenAI provider implementation."""

from typing import Any
import httpx

from mashell.providers.base import BaseProvider, Message, Response


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI API."""
    
    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Response:
        """Send messages to OpenAI and get response."""
        headers = {
            "Content-Type": "application/json",
        }
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [self._format_message(m) for m in messages],
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse_response(data)
    
    def _format_message(self, msg: Message) -> dict[str, Any]:
        """Format a message for the OpenAI API."""
        d: dict[str, Any] = {"role": msg.role}
        
        if msg.content is not None:
            d["content"] = msg.content
        
        if msg.tool_calls:
            d["tool_calls"] = [tc.to_dict() for tc in msg.tool_calls]
        
        if msg.tool_call_id:
            d["tool_call_id"] = msg.tool_call_id
        
        return d
    
    def _parse_response(self, data: dict[str, Any]) -> Response:
        """Parse OpenAI API response."""
        choice = data["choices"][0]
        message = choice["message"]
        
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls")
        
        tool_calls = None
        if raw_tool_calls:
            tool_calls = self._parse_tool_calls(raw_tool_calls)
        
        finish_reason = choice.get("finish_reason", "stop")
        if finish_reason == "tool_calls":
            finish_reason = "tool_calls"
        
        usage = data.get("usage", {})
        
        return Response(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )

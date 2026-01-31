"""OpenAI provider implementation."""

import asyncio
from typing import Any

import httpx

from mashell.providers.base import BaseProvider, Message, Response


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI API."""

    # Rate limiting settings
    MAX_RETRIES = 5
    BASE_RETRY_DELAY = 2.0  # seconds
    MAX_RETRY_DELAY = 60.0  # seconds

    async def chat(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Response:
        """Send messages to OpenAI and get response with retry logic."""
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

        url = f"{self.url}/chat/completions"
        return await self._request_with_retry(url, headers, payload)

    async def _request_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> Response:
        """Make request with exponential backoff retry for rate limits."""
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=payload,
                        timeout=120.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return self._parse_response(data)

            except httpx.HTTPStatusError as e:
                last_error = e

                if e.response.status_code == 429:
                    # Rate limited - get retry-after header or use exponential backoff
                    retry_after = e.response.headers.get("retry-after")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = self.BASE_RETRY_DELAY * (2**attempt)
                    else:
                        delay = self.BASE_RETRY_DELAY * (2**attempt)

                    delay = min(delay, self.MAX_RETRY_DELAY)

                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(delay)
                        continue

                # Non-429 error or last retry - raise
                raise

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.BASE_RETRY_DELAY * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise RuntimeError("Request failed after max retries")

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

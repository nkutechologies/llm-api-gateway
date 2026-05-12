"""
Anthropic provider — Paid tier. Claude 3.5 Sonnet, Claude 3 Opus, etc.
Uses the Anthropic Messages API.
"""

from gateway.providers.base import BaseProvider


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    tier = "paid"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        response = await client.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        data = response.json()
        # Anthropic returns content as a list of blocks
        return data["content"][0]["text"]

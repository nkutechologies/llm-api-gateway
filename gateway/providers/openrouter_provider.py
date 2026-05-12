"""
OpenRouter provider — Free tier with many open-source models.
Uses OpenAI-compatible API format. Free models have `:free` suffix.
"""

from gateway.providers.base import BaseProvider


class OpenRouterProvider(BaseProvider):
    name = "openrouter"
    tier = "free"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://llm-gateway.app",
                "X-Title": "LLM Gateway",
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

"""
OpenAI provider — Paid tier. GPT-4o, GPT-4, GPT-3.5-turbo, etc.
"""

from gateway.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    name = "openai"
    tier = "paid"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        response = await client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
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

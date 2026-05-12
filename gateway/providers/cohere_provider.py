"""
Cohere provider — Paid tier. Command R+, Command R, etc.
Uses the Cohere Chat API v2.
"""

from gateway.providers.base import BaseProvider


class CohereProvider(BaseProvider):
    name = "cohere"
    tier = "paid"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        response = await client.post(
            f"{self.base_url}/chat",
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
        # Cohere v2 chat response
        return data["message"]["content"][0]["text"]

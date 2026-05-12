"""
Google Gemini provider — Paid tier with generous free quota.
Uses the Gemini REST API.
"""

from gateway.providers.base import BaseProvider


class GoogleProvider(BaseProvider):
    name = "google"
    tier = "paid"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        url = (
            f"{self.base_url}/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        response = await client.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

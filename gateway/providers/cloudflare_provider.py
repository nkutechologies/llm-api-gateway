"""
Cloudflare Workers AI provider — Free tier with 10K neurons/day.
Uses Cloudflare's REST API format.
"""

from gateway.providers.base import BaseProvider


class CloudflareProvider(BaseProvider):
    name = "cloudflare"
    tier = "free"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        # api_key format: "account_id:api_token"
        parts = self.api_key.split(":", 1)
        if len(parts) == 2:
            account_id, api_token = parts
        else:
            account_id = ""
            api_token = self.api_key

        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{self.model}"
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["result"]["response"]

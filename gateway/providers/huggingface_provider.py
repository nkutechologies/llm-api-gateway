"""
Hugging Face Inference API provider — Free tier for open-source models.
"""

from gateway.providers.base import BaseProvider, ProviderError


class HuggingFaceProvider(BaseProvider):
    name = "huggingface"
    tier = "free"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        url = f"{self.base_url}/{self.model}"

        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "inputs": prompt,
                "parameters": {
                    "max_new_tokens": max_tokens,
                    "temperature": temperature,
                    "return_full_text": False,
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        # HF returns a list of generated outputs
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("generated_text", "")
        elif isinstance(data, dict) and "generated_text" in data:
            return data["generated_text"]
        else:
            raise ProviderError(f"Unexpected response format: {str(data)[:200]}")

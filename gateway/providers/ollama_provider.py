"""
Ollama provider — Free local inference. Requires Ollama running on the machine.
Uses the Ollama REST API.
"""

from gateway.providers.base import BaseProvider, ProviderError


class OllamaProvider(BaseProvider):
    name = "ollama"
    tier = "free"

    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        client = await self.get_client()
        try:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                raise ProviderError(
                    "Ollama is not running. Start it with: ollama serve",
                    status="error",
                    retryable=False,
                )
            raise

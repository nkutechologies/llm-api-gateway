"""
Base class for all LLM provider implementations.
Defines the interface and common error handling.
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from gateway.logger import APIAttemptLog


class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, message: str, status: str = "error", retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class RateLimitError(ProviderError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, status="rate_limited", retryable=True)


class AuthenticationError(ProviderError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status="auth_error", retryable=False)


class TokenLimitError(ProviderError):
    def __init__(self, message: str = "Token limit exceeded"):
        super().__init__(message, status="token_limit", retryable=False)


class BaseProvider(ABC):
    """Abstract base class for LLM providers."""

    name: str = "base"
    tier: str = "free"

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int = 60):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.7) -> tuple[str, APIAttemptLog]:
        """
        Generate a response from the provider.
        Returns (response_text, attempt_log).
        Raises ProviderError on failure.
        """
        start = time.time()
        prompt_preview = prompt[:80] + "..." if len(prompt) > 80 else prompt

        try:
            response = await self._call_api(prompt, max_tokens, temperature)
            latency = (time.time() - start) * 1000

            log = APIAttemptLog(
                timestamp=time.time(),
                provider=self.name,
                model=self.model,
                status="success",
                latency_ms=latency,
                prompt_preview=prompt_preview,
            )
            return response, log

        except ProviderError:
            raise
        except httpx.TimeoutException:
            latency = (time.time() - start) * 1000
            raise ProviderError(
                f"Timeout after {latency:.0f}ms",
                status="timeout",
                retryable=True,
            )
        except httpx.HTTPStatusError as e:
            latency = (time.time() - start) * 1000
            self._handle_http_error(e, latency)
        except Exception as e:
            latency = (time.time() - start) * 1000
            raise ProviderError(f"Unexpected error: {str(e)}", retryable=False)

    def _handle_http_error(self, error: httpx.HTTPStatusError, latency_ms: float):
        """Classify HTTP errors into specific provider exceptions."""
        status = error.response.status_code
        body = ""
        try:
            body = error.response.text
        except Exception:
            pass

        if status == 401 or status == 403:
            raise AuthenticationError(f"HTTP {status}: {body[:200]}")
        elif status == 429:
            raise RateLimitError(f"HTTP 429: {body[:200]}")
        elif status == 413 or "token" in body.lower():
            raise TokenLimitError(f"HTTP {status}: {body[:200]}")
        elif status >= 500:
            raise ProviderError(f"Server error {status}: {body[:200]}", retryable=True)
        else:
            raise ProviderError(f"HTTP {status}: {body[:200]}", retryable=False)

    @abstractmethod
    async def _call_api(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Provider-specific API call implementation. Must return the generated text."""
        ...

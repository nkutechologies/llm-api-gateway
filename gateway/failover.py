"""
Failover orchestrator — Routes requests through providers in priority order.
Handles retries, caching, and logging of the entire failover chain.
"""

import time
import uuid

from gateway.config import GatewayConfig, ProviderConfig
from gateway.cache import ResponseCache
from gateway.logger import APIAttemptLog, FailoverLog, gateway_logger
from gateway.providers.base import (
    BaseProvider,
    ProviderError,
    AuthenticationError,
    RateLimitError,
)
from gateway.providers.groq_provider import GroqProvider
from gateway.providers.huggingface_provider import HuggingFaceProvider
from gateway.providers.together_provider import TogetherProvider
from gateway.providers.ollama_provider import OllamaProvider
from gateway.providers.cerebras_provider import CerebrasProvider
from gateway.providers.google_provider import GoogleProvider
from gateway.providers.mistral_provider import MistralProvider
from gateway.providers.openrouter_provider import OpenRouterProvider
from gateway.providers.openai_provider import OpenAIProvider
from gateway.providers.anthropic_provider import AnthropicProvider
from gateway.providers.cohere_provider import CohereProvider


# Registry mapping provider IDs to their implementation classes
PROVIDER_CLASSES: dict[str, type[BaseProvider]] = {
    "groq": GroqProvider,
    "huggingface": HuggingFaceProvider,
    "together": TogetherProvider,
    "cerebras": CerebrasProvider,
    "google": GoogleProvider,
    "mistral": MistralProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "cohere": CohereProvider,
}


def _create_provider(provider_config: ProviderConfig) -> BaseProvider:
    """Instantiate a provider from its configuration."""
    cls = PROVIDER_CLASSES.get(provider_config.id)
    if cls is None:
        raise ValueError(f"Unknown provider: {provider_config.id}")

    return cls(
        api_key=provider_config.api_key or "",
        base_url=provider_config.base_url or "",
        model=provider_config.selected_model or (provider_config.models[0] if provider_config.models else ""),
        timeout=provider_config.timeout,
    )


class FailoverOrchestrator:
    """
    Main orchestrator that routes requests through the provider chain.
    Tries free providers first, then paid, with automatic failover on errors.
    """

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.cache = ResponseCache(
            ttl=config.cache_ttl,
            max_size=1000,
        )

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        use_cache: bool = True,
    ) -> dict:
        """
        Generate a response by trying providers in failover order.

        Returns a dict with:
            - response: The generated text
            - provider: Name of the provider that succeeded
            - model: Model used
            - cached: Whether the response came from cache
            - attempts: Number of providers tried
            - request_id: Unique request identifier
        """
        request_id = str(uuid.uuid4())[:8]
        chain_start = time.time()
        prompt_preview = prompt[:80] + "..." if len(prompt) > 80 else prompt

        failover_log = FailoverLog(
            request_id=request_id,
            prompt_preview=prompt_preview,
        )

        # Check cache first
        if use_cache and self.config.cache_enabled:
            ordered = self.config.get_ordered_providers()
            for pc in ordered:
                model = pc.selected_model or (pc.models[0] if pc.models else "")
                cached = self.cache.get(prompt, model)
                if cached:
                    failover_log.success = True
                    failover_log.cached = True
                    failover_log.final_provider = pc.name
                    failover_log.final_model = model
                    failover_log.total_latency_ms = (time.time() - chain_start) * 1000
                    gateway_logger.log_failover(failover_log)
                    return {
                        "response": cached,
                        "provider": pc.name,
                        "model": model,
                        "cached": True,
                        "attempts": 0,
                        "request_id": request_id,
                    }

        # Get ordered provider list (free first, then paid)
        ordered_providers = self.config.get_ordered_providers()

        if not ordered_providers:
            failover_log.total_latency_ms = (time.time() - chain_start) * 1000
            gateway_logger.log_failover(failover_log)
            return {
                "response": None,
                "error": "No providers configured. Add at least one API key.",
                "provider": None,
                "model": None,
                "cached": False,
                "attempts": 0,
                "request_id": request_id,
            }

        # Try each provider in order
        last_error = None
        attempts = 0

        for provider_config in ordered_providers:
            if attempts >= self.config.max_failover_attempts:
                break

            attempts += 1
            provider = None
            try:
                provider = _create_provider(provider_config)
                response_text, attempt_log = await provider.generate(
                    prompt, max_tokens, temperature
                )

                # Success — log and cache
                gateway_logger.log_attempt(attempt_log)
                failover_log.attempts.append(attempt_log)

                model = provider_config.selected_model or ""
                if self.config.cache_enabled:
                    self.cache.put(prompt, model, response_text)

                failover_log.success = True
                failover_log.final_provider = provider_config.name
                failover_log.final_model = model
                failover_log.total_latency_ms = (time.time() - chain_start) * 1000
                gateway_logger.log_failover(failover_log)

                return {
                    "response": response_text,
                    "provider": provider_config.name,
                    "model": model,
                    "cached": False,
                    "attempts": attempts,
                    "request_id": request_id,
                }

            except AuthenticationError as e:
                # Don't retry auth errors — skip to next provider
                attempt_log = APIAttemptLog(
                    timestamp=time.time(),
                    provider=provider_config.name,
                    model=provider_config.selected_model or "",
                    status="auth_error",
                    error_message=str(e),
                    prompt_preview=prompt_preview,
                )
                gateway_logger.log_attempt(attempt_log)
                failover_log.attempts.append(attempt_log)
                last_error = str(e)

            except RateLimitError as e:
                attempt_log = APIAttemptLog(
                    timestamp=time.time(),
                    provider=provider_config.name,
                    model=provider_config.selected_model or "",
                    status="rate_limited",
                    error_message=str(e),
                    prompt_preview=prompt_preview,
                )
                gateway_logger.log_attempt(attempt_log)
                failover_log.attempts.append(attempt_log)
                last_error = str(e)

            except ProviderError as e:
                attempt_log = APIAttemptLog(
                    timestamp=time.time(),
                    provider=provider_config.name,
                    model=provider_config.selected_model or "",
                    status=e.status,
                    error_message=str(e),
                    prompt_preview=prompt_preview,
                )
                gateway_logger.log_attempt(attempt_log)
                failover_log.attempts.append(attempt_log)
                last_error = str(e)

            except Exception as e:
                attempt_log = APIAttemptLog(
                    timestamp=time.time(),
                    provider=provider_config.name,
                    model=provider_config.selected_model or "",
                    status="error",
                    error_message=str(e),
                    prompt_preview=prompt_preview,
                )
                gateway_logger.log_attempt(attempt_log)
                failover_log.attempts.append(attempt_log)
                last_error = str(e)

            finally:
                if provider:
                    await provider.close()

        # All providers failed
        failover_log.total_latency_ms = (time.time() - chain_start) * 1000
        gateway_logger.log_failover(failover_log)

        return {
            "response": None,
            "error": f"All providers failed. Last error: {last_error}",
            "provider": None,
            "model": None,
            "cached": False,
            "attempts": attempts,
            "request_id": request_id,
        }

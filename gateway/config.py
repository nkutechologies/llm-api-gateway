"""
Configuration management for the LLM API Gateway.
Handles loading/saving provider configs, API keys, and user preferences.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

CONFIG_DIR = Path(os.getenv("GATEWAY_CONFIG_DIR", "./data"))
CONFIG_FILE = CONFIG_DIR / "config.json"
KEYS_FILE = CONFIG_DIR / "keys.json"


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""
    id: str = ""  # Provider key (e.g. "groq", "openai")
    name: str
    enabled: bool = True
    priority: int = 0  # Lower = higher priority
    tier: str = "free"  # "free" or "paid"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    models: list[str] = Field(default_factory=list)
    selected_model: Optional[str] = None
    max_retries: int = 2
    timeout: int = 60
    rate_limit_rpm: Optional[int] = None  # Requests per minute


class GatewayConfig(BaseModel):
    """Global gateway configuration."""
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    cache_ttl: int = 3600  # Cache TTL in seconds
    cache_enabled: bool = True
    max_failover_attempts: int = 5
    log_level: str = "INFO"

    def get_ordered_providers(self) -> list[ProviderConfig]:
        """Return enabled providers ordered: free first (by priority), then paid (by priority)."""
        enabled = [p for p in self.providers.values() if p.enabled and p.api_key]
        free = sorted([p for p in enabled if p.tier == "free"], key=lambda p: p.priority)
        paid = sorted([p for p in enabled if p.tier == "paid"], key=lambda p: p.priority)
        return free + paid


# Default provider definitions with their available models
DEFAULT_PROVIDERS: dict[str, dict] = {
    "groq": {
        "name": "Groq",
        "tier": "free",
        "priority": 1,
        "base_url": "https://api.groq.com/openai/v1",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "llama-3.2-1b-preview",
            "llama-3.2-3b-preview",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ],
        "selected_model": "llama-3.3-70b-versatile",
        "rate_limit_rpm": 30,
    },
    "huggingface": {
        "name": "Hugging Face",
        "tier": "free",
        "priority": 2,
        "base_url": "https://api-inference.huggingface.co/models",
        "models": [
            "mistralai/Mistral-7B-Instruct-v0.3",
            "meta-llama/Meta-Llama-3-8B-Instruct",
            "google/gemma-2-2b-it",
            "HuggingFaceH4/zephyr-7b-beta",
            "microsoft/Phi-3-mini-4k-instruct",
        ],
        "selected_model": "mistralai/Mistral-7B-Instruct-v0.3",
        "rate_limit_rpm": 60,
    },
    "together": {
        "name": "Together AI",
        "tier": "free",
        "priority": 3,
        "base_url": "https://api.together.xyz/v1",
        "models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
            "mistralai/Mixtral-8x7B-Instruct-v0.1",
            "google/gemma-2-9b-it",
            "Qwen/Qwen2.5-7B-Instruct-Turbo",
        ],
        "selected_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "rate_limit_rpm": 60,
    },
    "cerebras": {
        "name": "Cerebras",
        "tier": "free",
        "priority": 4,
        "base_url": "https://api.cerebras.ai/v1",
        "models": [
            "llama-3.3-70b",
            "llama-3.1-8b",
            "llama-3.1-70b",
        ],
        "selected_model": "llama-3.3-70b",
        "rate_limit_rpm": 30,
    },
    "google": {
        "name": "Google Gemini",
        "tier": "free",
        "priority": 5,
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "models": [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "selected_model": "gemini-2.0-flash",
        "rate_limit_rpm": 15,
    },
    "mistral": {
        "name": "Mistral",
        "tier": "free",
        "priority": 6,
        "base_url": "https://api.mistral.ai/v1",
        "models": [
            "mistral-small-latest",
            "mistral-medium-latest",
            "mistral-large-latest",
            "open-mistral-7b",
            "open-mixtral-8x7b",
            "open-mixtral-8x22b",
        ],
        "selected_model": "mistral-small-latest",
        "rate_limit_rpm": 60,
    },
    "openrouter": {
        "name": "OpenRouter",
        "tier": "free",
        "priority": 7,
        "base_url": "https://openrouter.ai/api/v1",
        "models": [
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemma-2-9b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "deepseek/deepseek-r1:free",
            "microsoft/phi-3-mini-128k-instruct:free",
        ],
        "selected_model": "meta-llama/llama-3.3-70b-instruct:free",
        "rate_limit_rpm": 20,
    },
    "ollama": {
        "name": "Ollama (Local)",
        "tier": "free",
        "priority": 8,
        "base_url": "http://localhost:11434",
        "models": [
            "llama3.2",
            "llama3.1",
            "mistral",
            "gemma2",
            "phi3",
            "qwen2.5",
        ],
        "selected_model": "llama3.2",
        "rate_limit_rpm": None,
    },
    "openai": {
        "name": "OpenAI",
        "tier": "paid",
        "priority": 1,
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        ],
        "selected_model": "gpt-4o-mini",
        "rate_limit_rpm": 60,
    },
    "anthropic": {
        "name": "Anthropic",
        "tier": "paid",
        "priority": 2,
        "base_url": "https://api.anthropic.com/v1",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
        "selected_model": "claude-sonnet-4-20250514",
        "rate_limit_rpm": 60,
    },
    "cohere": {
        "name": "Cohere",
        "tier": "paid",
        "priority": 3,
        "base_url": "https://api.cohere.ai/v2",
        "models": [
            "command-r-plus",
            "command-r",
            "command",
            "command-light",
        ],
        "selected_model": "command-r",
        "rate_limit_rpm": 60,
    },
}


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _hash_key(key: str) -> str:
    """Create a display-safe hash of an API key (show first 4 + last 4 chars)."""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


def load_config() -> GatewayConfig:
    """Load configuration from disk, merging with defaults."""
    _ensure_config_dir()

    config = GatewayConfig()

    # Initialize with defaults
    for key, defaults in DEFAULT_PROVIDERS.items():
        config.providers[key] = ProviderConfig(id=key, **defaults)

    # Load saved config if exists
    if CONFIG_FILE.exists():
        try:
            saved = json.loads(CONFIG_FILE.read_text())
            for key, provider_data in saved.get("providers", {}).items():
                if key in config.providers:
                    # Merge saved settings into defaults
                    for field, value in provider_data.items():
                        if field != "api_key":  # Keys stored separately
                            setattr(config.providers[key], field, value)
            config.cache_ttl = saved.get("cache_ttl", config.cache_ttl)
            config.cache_enabled = saved.get("cache_enabled", config.cache_enabled)
            config.max_failover_attempts = saved.get("max_failover_attempts", config.max_failover_attempts)
        except (json.JSONDecodeError, Exception):
            pass

    # Load API keys from env vars first, then keys file
    for key in config.providers:
        env_key = os.getenv(f"{key.upper()}_API_KEY")
        if env_key:
            config.providers[key].api_key = env_key

    if KEYS_FILE.exists():
        try:
            keys = json.loads(KEYS_FILE.read_text())
            for key, api_key in keys.items():
                if key in config.providers and not config.providers[key].api_key:
                    config.providers[key].api_key = api_key
        except (json.JSONDecodeError, Exception):
            pass

    # Ollama doesn't need an API key — set a placeholder so it's eligible
    if config.providers["ollama"].enabled and not config.providers["ollama"].api_key:
        config.providers["ollama"].api_key = "local"

    return config


def save_config(config: GatewayConfig):
    """Persist configuration to disk (keys stored separately)."""
    _ensure_config_dir()

    # Save config without API keys
    config_data = {
        "cache_ttl": config.cache_ttl,
        "cache_enabled": config.cache_enabled,
        "max_failover_attempts": config.max_failover_attempts,
        "providers": {},
    }
    keys_data = {}

    for key, provider in config.providers.items():
        provider_dict = provider.model_dump(exclude={"api_key"})
        config_data["providers"][key] = provider_dict
        if provider.api_key and provider.api_key != "local":
            keys_data[key] = provider.api_key

    CONFIG_FILE.write_text(json.dumps(config_data, indent=2))
    KEYS_FILE.write_text(json.dumps(keys_data, indent=2))
    # Restrict permissions on keys file
    KEYS_FILE.chmod(0o600)


def update_api_key(provider_id: str, api_key: str, config: GatewayConfig) -> GatewayConfig:
    """Update a single provider's API key."""
    if provider_id in config.providers:
        config.providers[provider_id].api_key = api_key
        save_config(config)
    return config

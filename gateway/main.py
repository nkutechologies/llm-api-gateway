"""
FastAPI application — The main API gateway server.
Provides /generate endpoint and configuration management routes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from gateway.config import load_config, save_config, update_api_key, remove_api_key, GatewayConfig
from gateway.failover import FailoverOrchestrator
from gateway.logger import gateway_logger


# ---------- Request / Response schemas ----------

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=100_000)
    max_tokens: int = Field(default=1024, ge=1, le=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    use_cache: bool = True


class GenerateResponse(BaseModel):
    response: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    cached: bool = False
    attempts: int = 0
    request_id: str = ""


class UpdateKeyRequest(BaseModel):
    provider: str
    api_key: str = Field(..., min_length=1)


class RemoveKeyRequest(BaseModel):
    provider: str


class ToggleProviderRequest(BaseModel):
    provider: str
    enabled: bool


class SelectModelRequest(BaseModel):
    provider: str
    model: str


# ---------- App lifecycle ----------

_config: GatewayConfig = None  # type: ignore
_orchestrator: FailoverOrchestrator = None  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _config, _orchestrator
    _config = load_config()
    _orchestrator = FailoverOrchestrator(_config)
    gateway_logger.logger.info("LLM Gateway started")
    yield
    gateway_logger.logger.info("LLM Gateway shutting down")


app = FastAPI(
    title="LLM API Gateway",
    description="Unified LLM API with automatic failover — free providers first, paid as fallback",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Endpoints ----------

@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """
    Generate a response from the LLM provider chain.
    Automatically fails over through configured providers (free first, paid fallback).
    """
    result = await _orchestrator.generate(
        prompt=req.prompt,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        use_cache=req.use_cache,
    )

    if result.get("error") and result.get("response") is None:
        raise HTTPException(status_code=502, detail=result["error"])

    return GenerateResponse(**result)


@app.get("/providers")
async def list_providers():
    """List all configured providers with their status."""
    providers = []
    for key, p in _config.providers.items():
        providers.append({
            "id": key,
            "name": p.name,
            "tier": p.tier,
            "enabled": p.enabled,
            "has_key": bool(p.api_key),
            "models": p.models,
            "selected_model": p.selected_model,
            "priority": p.priority,
        })
    return {"providers": providers}


@app.post("/providers/key")
async def set_api_key(req: UpdateKeyRequest):
    """Set or update an API key for a provider."""
    global _config, _orchestrator
    if req.provider not in _config.providers:
        raise HTTPException(status_code=404, detail=f"Provider '{req.provider}' not found")
    _config = update_api_key(req.provider, req.api_key, _config)
    _orchestrator = FailoverOrchestrator(_config)
    return {"status": "ok", "provider": req.provider}


@app.post("/providers/key/remove")
async def remove_key(req: RemoveKeyRequest):
    """Remove an API key for a provider."""
    global _config, _orchestrator
    if req.provider not in _config.providers:
        raise HTTPException(status_code=404, detail=f"Provider '{req.provider}' not found")
    _config = remove_api_key(req.provider, _config)
    _orchestrator = FailoverOrchestrator(_config)
    return {"status": "ok", "provider": req.provider}


@app.post("/providers/toggle")
async def toggle_provider(req: ToggleProviderRequest):
    """Enable or disable a provider."""
    global _config, _orchestrator
    if req.provider not in _config.providers:
        raise HTTPException(status_code=404, detail=f"Provider '{req.provider}' not found")
    _config.providers[req.provider].enabled = req.enabled
    save_config(_config)
    _orchestrator = FailoverOrchestrator(_config)
    return {"status": "ok", "provider": req.provider, "enabled": req.enabled}


@app.post("/providers/model")
async def select_model(req: SelectModelRequest):
    """Select which model to use for a provider."""
    global _config, _orchestrator
    if req.provider not in _config.providers:
        raise HTTPException(status_code=404, detail=f"Provider '{req.provider}' not found")
    p = _config.providers[req.provider]
    if req.model not in p.models:
        raise HTTPException(status_code=400, detail=f"Model '{req.model}' not available for {req.provider}")
    p.selected_model = req.model
    save_config(_config)
    _orchestrator = FailoverOrchestrator(_config)
    return {"status": "ok", "provider": req.provider, "model": req.model}


@app.get("/logs")
async def get_logs(limit: int = 50):
    """Retrieve recent failover logs."""
    return {
        "logs": gateway_logger.get_recent_failovers(limit),
        "stats": gateway_logger.get_stats(),
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "cache_size": _orchestrator.cache.size}


@app.post("/cache/clear")
async def clear_cache():
    """Clear the response cache."""
    _orchestrator.cache.clear()
    return {"status": "ok", "message": "Cache cleared"}

"""
Structured logging for the LLM API Gateway.
Tracks all API attempts, failures, and failover events.
"""

import logging
import time
from dataclasses import dataclass, field
from collections import deque
from typing import Optional


@dataclass
class APIAttemptLog:
    """Record of a single API call attempt."""
    timestamp: float
    provider: str
    model: str
    status: str  # "success", "error", "rate_limited", "timeout", "auth_error"
    latency_ms: float = 0
    error_message: Optional[str] = None
    prompt_preview: str = ""  # First 80 chars of prompt

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)),
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "latency_ms": round(self.latency_ms, 1),
            "error_message": self.error_message,
            "prompt_preview": self.prompt_preview,
        }


@dataclass
class FailoverLog:
    """Record of a complete failover chain for a single request."""
    request_id: str
    prompt_preview: str
    attempts: list[APIAttemptLog] = field(default_factory=list)
    final_provider: Optional[str] = None
    final_model: Optional[str] = None
    total_latency_ms: float = 0
    success: bool = False
    cached: bool = False

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "prompt_preview": self.prompt_preview,
            "attempts": [a.to_dict() for a in self.attempts],
            "final_provider": self.final_provider,
            "final_model": self.final_model,
            "total_latency_ms": round(self.total_latency_ms, 1),
            "success": self.success,
            "cached": self.cached,
        }


class GatewayLogger:
    """Centralized logging for the gateway with in-memory log buffer."""

    MAX_LOGS = 500

    def __init__(self, level: str = "INFO"):
        self.logger = logging.getLogger("llm_gateway")
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self.logger.addHandler(handler)

        # In-memory log buffer for UI display
        self.failover_logs: deque[FailoverLog] = deque(maxlen=self.MAX_LOGS)
        self.attempt_logs: deque[APIAttemptLog] = deque(maxlen=self.MAX_LOGS * 3)

    def log_attempt(self, attempt: APIAttemptLog):
        """Log a single API attempt."""
        self.attempt_logs.append(attempt)
        if attempt.status == "success":
            self.logger.info(
                f"[{attempt.provider}] {attempt.model} — SUCCESS in {attempt.latency_ms:.0f}ms"
            )
        else:
            self.logger.warning(
                f"[{attempt.provider}] {attempt.model} — {attempt.status}: {attempt.error_message}"
            )

    def log_failover(self, failover: FailoverLog):
        """Log a complete failover chain."""
        self.failover_logs.append(failover)
        n = len(failover.attempts)
        if failover.success:
            self.logger.info(
                f"Request {failover.request_id}: Succeeded via {failover.final_provider} "
                f"after {n} attempt(s) in {failover.total_latency_ms:.0f}ms"
            )
        else:
            self.logger.error(
                f"Request {failover.request_id}: FAILED after {n} attempt(s)"
            )

    def get_recent_failovers(self, limit: int = 50) -> list[dict]:
        """Return recent failover logs for UI display."""
        logs = list(self.failover_logs)[-limit:]
        logs.reverse()
        return [log.to_dict() for log in logs]

    def get_stats(self) -> dict:
        """Return aggregate statistics."""
        total = len(self.attempt_logs)
        if total == 0:
            return {"total_attempts": 0, "success_rate": 0, "providers_used": {}}

        successes = sum(1 for a in self.attempt_logs if a.status == "success")
        provider_counts: dict[str, dict[str, int]] = {}
        for a in self.attempt_logs:
            if a.provider not in provider_counts:
                provider_counts[a.provider] = {"success": 0, "failure": 0}
            if a.status == "success":
                provider_counts[a.provider]["success"] += 1
            else:
                provider_counts[a.provider]["failure"] += 1

        return {
            "total_attempts": total,
            "total_successes": successes,
            "success_rate": round(successes / total * 100, 1),
            "providers_used": provider_counts,
            "total_failover_chains": len(self.failover_logs),
        }


# Global logger instance
gateway_logger = GatewayLogger()

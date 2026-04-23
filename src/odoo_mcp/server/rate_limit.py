from __future__ import annotations

import os
import threading
import time
from collections import deque
from dataclasses import dataclass


def _env_truthy(name: str, default: bool) -> bool:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    enabled: bool
    max_calls: int
    window_seconds: int


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    max_calls: int
    remaining: int
    window_seconds: int
    retry_after_seconds: int
    reset_in_seconds: int


class InMemoryRateLimiter:
    """Temporary fixed-window limiter keyed by authenticated user and surface name."""

    def __init__(self, config: RateLimitConfig) -> None:
        self.config = config
        self._entries: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, *, user: str, surface_name: str) -> RateLimitDecision:
        if not self.config.enabled:
            return RateLimitDecision(
                allowed=True,
                max_calls=self.config.max_calls,
                remaining=max(self.config.max_calls - 1, 0),
                window_seconds=self.config.window_seconds,
                retry_after_seconds=0,
                reset_in_seconds=self.config.window_seconds,
            )

        now = time.monotonic()
        window_start = now - self.config.window_seconds
        key = f"{user}:{surface_name}"

        with self._lock:
            events = self._entries.setdefault(key, deque())
            while events and events[0] <= window_start:
                events.popleft()

            if len(events) >= self.config.max_calls:
                retry_after = max(int(events[0] + self.config.window_seconds - now) + 1, 1)
                return RateLimitDecision(
                    allowed=False,
                    max_calls=self.config.max_calls,
                    remaining=0,
                    window_seconds=self.config.window_seconds,
                    retry_after_seconds=retry_after,
                    reset_in_seconds=retry_after,
                )

            events.append(now)
            remaining = max(self.config.max_calls - len(events), 0)
            reset_in_seconds = (
                max(int(events[0] + self.config.window_seconds - now), 0)
                if events
                else self.config.window_seconds
            )
            return RateLimitDecision(
                allowed=True,
                max_calls=self.config.max_calls,
                remaining=remaining,
                window_seconds=self.config.window_seconds,
                retry_after_seconds=0,
                reset_in_seconds=reset_in_seconds,
            )


_RATE_LIMITER: InMemoryRateLimiter | None = None
_RATE_LIMITER_CONFIG: RateLimitConfig | None = None


def get_rate_limit_config() -> RateLimitConfig:
    return RateLimitConfig(
        enabled=_env_truthy("MCP_RATE_LIMIT_ENABLED", True),
        max_calls=max(int(os.environ.get("MCP_RATE_LIMIT_MAX_CALLS", "60")), 1),
        window_seconds=max(int(os.environ.get("MCP_RATE_LIMIT_WINDOW_SECONDS", "60")), 1),
    )


def get_rate_limiter() -> InMemoryRateLimiter:
    config = get_rate_limit_config()
    global _RATE_LIMITER, _RATE_LIMITER_CONFIG
    if _RATE_LIMITER is None or _RATE_LIMITER_CONFIG != config:
        _RATE_LIMITER = InMemoryRateLimiter(config)
        _RATE_LIMITER_CONFIG = config
    return _RATE_LIMITER


def reset_rate_limiter() -> None:
    global _RATE_LIMITER, _RATE_LIMITER_CONFIG
    _RATE_LIMITER = None
    _RATE_LIMITER_CONFIG = None

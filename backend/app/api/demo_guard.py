"""Public demo safety (#12): passcode, per-IP rate limit, daily LLM budget. Owner: Jin.

Only active when PUBLIC_DEMO=1. Locally (and in tests) every check is a no-op.

- Passcode: chat, and any agent run while LLM_MODE=live, need the `X-Demo-Passcode` header.
  With no DEMO_PASSCODE configured those endpoints stay locked (fail closed).
- Rate limit: token bucket per client IP on every POST under /api, except /api/tasks/* (cron, has its own secret).
- Budget: while LLM_MODE=live, refuse new agent runs once today's recorded Gemini spend
  reaches DAILY_LLM_BUDGET_USD. Spend is written by app.agents.llm (namespace `llm_spend`, keyed by UTC day).
"""
from __future__ import annotations

import hmac
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

PASSCODE_HEADER = "X-Demo-Passcode"


def _error(status: int, code: str, message: str, details: dict | None = None) -> HTTPException:
    return HTTPException(status_code=status, detail={"error": {"code": code, "message": message,
                                                               "details": details or {}}})


# ------------------------------------------------------------------ passcode
def require_passcode(request: Request) -> None:
    """Raise 401 unless the request carries the demo passcode. No-op outside the public demo."""
    s = request.app.state.app.settings
    if not s.public_demo:
        return
    given = request.headers.get(PASSCODE_HEADER, "")
    if not s.demo_passcode or not hmac.compare_digest(given.encode(), s.demo_passcode.encode()):
        raise _error(401, "unauthorized", "This needs the demo passcode")


def guard_agent_run(request: Request) -> None:
    """Checks before starting an agent run: passcode + budget when Gemini is live in the public demo."""
    state = request.app.state.app
    if state.recording is not None:
        return  # historical actions select an existing recording, never spend tokens
    s = state.settings
    if not s.public_demo or s.llm_mode != "live":
        return   # fake / replay cost nothing
    require_passcode(request)
    check_budget(state)


# ------------------------------------------------------------------ budget
def spend_today_usd(state) -> float:
    """Gemini spend recorded today across both modes' databases."""
    # Billing day = wall-clock UTC, same as app.agents.llm (real money, not simulated business logic).
    day = datetime.now(UTC).date().isoformat()
    total, seen = 0.0, set()
    for st in {**state.modes, "_": state}.values():
        if id(st.db) in seen:
            continue
        seen.add(id(st.db))
        raw = st.db.get("llm_spend", day)
        if raw:
            total += float(json.loads(raw).get("usd", 0))
    return total


def check_budget(state) -> None:
    limit = state.settings.daily_llm_budget_usd
    spent = spend_today_usd(state)
    if spent >= limit:
        state.events.emit("budget.exceeded", title="Daily LLM budget reached: new live runs refused",
                          payload={"limit": limit, "value": round(spent, 4)})
        raise _error(429, "budget_exceeded", "Today's AI budget for the demo is used up. Try again tomorrow.",
                     {"limit": limit, "value": round(spent, 4)})


# ------------------------------------------------------------------ rate limit
@dataclass
class TokenBucket:
    """In-memory per-key token bucket: `capacity` requests in a burst, refilled at `per_minute`."""
    per_minute: float
    capacity: float
    clock: Callable[[], float] = time.monotonic
    _buckets: dict[str, tuple[float, float]] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        now = self.clock()
        tokens, last = self._buckets.get(key, (self.capacity, now))
        tokens = min(self.capacity, tokens + (now - last) * self.per_minute / 60)
        ok = tokens >= 1
        self._buckets[key] = (tokens - 1 if ok else tokens, now)
        if len(self._buckets) > 10_000:   # forget the oldest idle IPs so memory stays bounded
            for k, _ in sorted(self._buckets.items(), key=lambda kv: kv[1][1])[:5_000]:
                self._buckets.pop(k, None)
        return ok


def client_ip(request: Request) -> str:
    """Real visitor IP. Behind Caddy (the only way in; port 8000 is not published) the last
    X-Forwarded-For entry is the address Caddy saw; earlier entries can be spoofed by the client."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if request.method == "POST" and path.startswith("/api/") and not path.startswith("/api/tasks/"):
            state = getattr(request.app.state, "app", None)
            if state is not None and state.settings.public_demo:
                bucket = getattr(request.app.state, "rate_limiter", None)
                if bucket is None:
                    per_min = state.settings.rate_limit_per_minute
                    bucket = request.app.state.rate_limiter = TokenBucket(per_min, per_min)
                if not bucket.allow(client_ip(request)):
                    return JSONResponse(status_code=429, headers={"Retry-After": "60"}, content={"error": {
                        "code": "rate_limited", "message": "Too many requests. Please wait a minute.",
                        "details": {}}})
        return await call_next(request)

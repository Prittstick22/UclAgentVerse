"""Gemini wrapper: structured output, retries, backup keys, SQLite cache, fake/replay modes. Owner: Dev.

    python -m app.agents.llm --ping      # pings GEMINI_MODEL_DEEP and GEMINI_MODEL_FAST

Only schema-valid replies are cached, so a rerun with the same prompt and as_of costs zero tokens.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ValidationError

from app.config import agents as agents_cfg
from app.core.db import DB
from app.settings import Settings, get_settings

if TYPE_CHECKING:
    from app.agents.fakes import FakeBrain

log = logging.getLogger(__name__)

TRANSIENT_CODES = {408, 429, 500, 502, 503, 504}


@dataclass
class LLMResponse:
    text: str
    tokens: int
    cached: bool
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


class LLMCacheMiss(Exception):
    pass


class LLMError(Exception):
    """Gemini could not be reached after retries (and backup keys), or is not configured."""


class LLMSchemaError(Exception):
    """The model replied, but the reply does not match the schema. Not cached."""

    def __init__(self, error: str, tokens: int, cost_usd: float = 0.0):
        super().__init__(error)
        self.error = error
        self.tokens = tokens
        self.cost_usd = cost_usd


def _status_code(e: Exception) -> int | None:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    return code if isinstance(code, int) else None


def _is_transient(e: Exception) -> bool:
    if isinstance(e, (asyncio.TimeoutError, TimeoutError, ConnectionError)):
        return True
    if type(e).__name__ in ("ConnectError", "ReadTimeout", "ConnectTimeout", "RemoteProtocolError"):
        return True
    return _status_code(e) in TRANSIENT_CODES


def price_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = (agents_cfg().get("pricing") or {}).get(model) or {}
    return (input_tokens * p.get("input_per_m", 0.0) + output_tokens * p.get("output_per_m", 0.0)) / 1_000_000


class LLM:
    def __init__(self, db: DB, settings: Settings | None = None, fake: FakeBrain | None = None,
                 client_factory: Callable[[str], Any] | None = None):
        self.db = db
        self.s = settings or get_settings()
        self.mode = self.s.llm_mode
        self.fake = fake
        backups = [k.strip() for k in (self.s.gemini_api_key_backups or "").split(",") if k.strip()]
        self._keys = [k for k in [self.s.gemini_api_key, *backups] if k]
        self._key_idx = 0
        self._client = None
        self._client_factory = client_factory or self._genai_client
        self.max_retries = 3
        self.backoff_s = 2.0
        self._sleep = asyncio.sleep
        self.live_calls = 0

    def model_for(self, deep: bool) -> str:
        return self.s.gemini_model_deep if deep else self.s.gemini_model_fast

    @staticmethod
    def _genai_client(key: str):
        from google import genai

        return genai.Client(api_key=key)

    def _client_or_raise(self):
        if self._client is None:
            if not self._keys:
                raise LLMError("GEMINI_API_KEY not set (use LLM_MODE=fake for offline dev)")
            self._client = self._client_factory(self._keys[self._key_idx])
        return self._client

    def _rotate_key(self) -> bool:
        if self._key_idx + 1 >= len(self._keys):
            return False
        self._key_idx += 1
        self._client = None
        log.warning("Gemini quota exhausted: switched to backup key %d of %d", self._key_idx + 1, len(self._keys))
        return True

    @staticmethod
    def cache_key(model: str, system: str, prompt: str, schema: type[BaseModel], as_of: str) -> str:
        blob = json.dumps([model, system, prompt, schema.__name__, as_of])
        return hashlib.sha256(blob.encode()).hexdigest()

    async def generate(self, *, model: str, system: str, prompt: str, schema: type[BaseModel], as_of: str,
                       fake_ctx: dict | None = None, use_search: bool = False) -> LLMResponse:
        """Return a schema-valid reply. Raises LLMSchemaError (invalid reply), LLMError, LLMCacheMiss (replay)."""
        if self.mode == "fake":
            if self.fake is None:
                raise LLMError("LLM_MODE=fake but no FakeBrain configured")
            obj = self.fake.respond(fake_ctx or {})
            tokens = (len(system) + len(prompt)) // 4
            try:
                text = schema.model_validate(obj).model_dump_json()
            except ValidationError as e:
                raise LLMSchemaError(str(e)[:500], tokens) from e
            return LLMResponse(text=text, tokens=tokens, cached=False)

        key = self.cache_key(model, system, prompt, schema, as_of)
        rows = self.db.execute("SELECT response, tokens FROM llm_cache WHERE key=?", (key,))
        if rows:
            return LLMResponse(text=rows[0][0], tokens=0, cached=True)
        if self.mode == "replay":
            raise LLMCacheMiss(key)

        resp, latency_ms = await self._call_live(model, system, prompt, schema, use_search)
        text = resp.text or "{}"
        um = resp.usage_metadata
        tokens_in = getattr(um, "prompt_token_count", 0) or 0
        tokens_out = (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        tokens = getattr(um, "total_token_count", 0) or (tokens_in + tokens_out)
        cost = price_usd(model, tokens_in, tokens_out)
        self._record_spend(cost, tokens)
        try:
            schema.model_validate_json(text)
        except ValidationError as e:
            raise LLMSchemaError(str(e)[:500], tokens, cost) from e
        self.db.execute(
            "INSERT OR REPLACE INTO llm_cache(key, response, tokens, created) VALUES (?,?,?,?)",
            (key, text, tokens, datetime.now(UTC).isoformat()),
        )
        return LLMResponse(text=text, tokens=tokens, cached=False, input_tokens=tokens_in, output_tokens=tokens_out,
                           latency_ms=latency_ms, cost_usd=cost)

    async def search(self, query: str, as_of: str) -> dict:
        """Google Search grounding (live mode only; the caller checks the clock). Cached per query and day.

        Grounding can't be combined with response_schema, so this returns plain text plus source links."""
        if self.mode == "fake":
            return {"text": f"[fake search result for: {query}]", "sources": [], "cached": False}
        key = self.cache_key("search", "", query, BaseModel, as_of)
        rows = self.db.execute("SELECT response FROM llm_cache WHERE key=?", (key,))
        if rows:
            return {**json.loads(rows[0][0]), "cached": True}
        if self.mode == "replay":
            raise LLMCacheMiss(key)
        model = self.s.gemini_model_fast
        resp, _ = await self._call_live(model, "Answer briefly and factually, citing sources.", query, None, True)
        sources = []
        for cand in (getattr(resp, "candidates", None) or [])[:1]:
            gm = getattr(cand, "grounding_metadata", None)
            for ch in (getattr(gm, "grounding_chunks", None) or []):
                web = getattr(ch, "web", None)
                if web is not None:
                    sources.append({"title": getattr(web, "title", ""), "url": getattr(web, "uri", "")})
        um = getattr(resp, "usage_metadata", None)
        tin, tout = getattr(um, "prompt_token_count", 0) or 0, getattr(um, "candidates_token_count", 0) or 0
        self._record_spend(price_usd(model, tin, tout), tin + tout)
        out = {"text": resp.text or "", "sources": sources}
        self.db.execute("INSERT OR REPLACE INTO llm_cache(key, response, tokens, created) VALUES (?,?,?,?)",
                        (key, json.dumps(out), tin + tout, datetime.now(UTC).isoformat()))
        return {**out, "cached": False}

    async def _call_live(self, model: str, system: str, prompt: str, schema: type[BaseModel] | None, use_search: bool):
        from google.genai import types

        config = types.GenerateContentConfig(system_instruction=system)  # Argon ignores temperature (deprecation warning)
        if schema is not None:
            config.response_mime_type = "application/json"
            config.response_schema = schema
        if use_search:  # live mode only, enforced by caller (tools.web_search)
            config.tools = [types.Tool(google_search=types.GoogleSearch())]
        while True:
            last: Exception | None = None
            for attempt in range(self.max_retries + 1):
                client = self._client_or_raise()
                t = time.perf_counter()
                try:
                    self.live_calls += 1
                    resp = await client.aio.models.generate_content(model=model, contents=prompt, config=config)
                    return resp, (time.perf_counter() - t) * 1000
                except Exception as e:
                    if not _is_transient(e):
                        raise LLMError(f"{type(e).__name__}: {str(e)[:200]}") from e
                    last = e
                    if attempt < self.max_retries:
                        await self._sleep(self.backoff_s * (2 ** attempt))
            # retries used up: a persistent 429 means this key's quota is gone → try a backup key
            if _status_code(last) == 429 and self._rotate_key():
                continue
            raise LLMError(f"gave up after {self.max_retries + 1} attempts: {type(last).__name__}: {str(last)[:200]}")

    def _record_spend(self, cost: float, tokens: int) -> None:
        # Billing day = wall-clock UTC (this is about real money, not simulated business logic).
        day = datetime.now(UTC).date().isoformat()
        cur = json.loads(self.db.get("llm_spend", day) or '{"usd": 0, "tokens": 0, "calls": 0}')
        before = cur["usd"]
        cur = {"usd": before + cost, "tokens": cur["tokens"] + tokens, "calls": cur["calls"] + 1}
        self.db.put("llm_spend", day, json.dumps(cur))
        if before <= self.s.daily_llm_budget_usd < cur["usd"]:
            log.warning("LLM spend today passed DAILY_LLM_BUDGET_USD=%.2f (now $%.2f, %d calls)",
                        self.s.daily_llm_budget_usd, cur["usd"], cur["calls"])


def _ping() -> None:  # pragma: no cover
    class Pong(BaseModel):
        ok: bool
        model: str

    s = get_settings()
    s.llm_mode = "live"
    llm = LLM(DB(), s)
    for label, model in [("deep", s.gemini_model_deep), ("fast", s.gemini_model_fast)]:
        r = asyncio.run(llm.generate(model=model, system="Reply with JSON.",
                                     prompt=f'Return {{"ok": true, "model": "{model}"}}', schema=Pong, as_of="ping"))
        print(f"OK {label}: {r.text}  {r.latency_ms:.0f} ms, {r.input_tokens} in / {r.output_tokens} out, "
              f"${r.cost_usd:.5f}")


if __name__ == "__main__":  # pragma: no cover
    import sys

    if "--ping" in sys.argv:
        _ping()

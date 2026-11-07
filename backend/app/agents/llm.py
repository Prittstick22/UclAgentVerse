"""Gemini wrapper: structured output, SQLite cache, fake/replay modes. Owner: Dev.

    python -m app.agents.llm --ping      # checks the key can call GEMINI_MODEL_DEEP
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.core.db import DB
from app.settings import Settings, get_settings

if TYPE_CHECKING:
    from app.agents.fakes import FakeBrain


@dataclass
class LLMResponse:
    text: str
    tokens: int
    cached: bool


class LLMCacheMiss(Exception):
    pass


class LLM:
    def __init__(self, db: DB, settings: Settings | None = None, fake: "FakeBrain | None" = None):
        self.db = db
        self.s = settings or get_settings()
        self.mode = self.s.llm_mode
        self.fake = fake
        self._client = None

    def model_for(self, deep: bool) -> str:
        return self.s.gemini_model_deep if deep else self.s.gemini_model_fast

    def _client_or_raise(self):
        if self._client is None:
            if not self.s.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY not set (use LLM_MODE=fake for offline dev)")
            from google import genai

            self._client = genai.Client(api_key=self.s.gemini_api_key)
        return self._client

    @staticmethod
    def cache_key(model: str, system: str, prompt: str, schema: type[BaseModel], as_of: str) -> str:
        blob = json.dumps([model, system, prompt, schema.__name__, as_of])
        return hashlib.sha256(blob.encode()).hexdigest()

    async def generate(self, *, model: str, system: str, prompt: str, schema: type[BaseModel], as_of: str,
                       fake_ctx: dict | None = None, use_search: bool = False) -> LLMResponse:
        if self.mode == "fake":
            if self.fake is None:
                raise RuntimeError("LLM_MODE=fake but no FakeBrain configured")
            obj = self.fake.respond(fake_ctx or {})
            text = schema.model_validate(obj).model_dump_json()
            return LLMResponse(text=text, tokens=(len(system) + len(prompt)) // 4, cached=False)

        key = self.cache_key(model, system, prompt, schema, as_of)
        rows = self.db.execute("SELECT response, tokens FROM llm_cache WHERE key=?", (key,))
        if rows:
            return LLMResponse(text=rows[0][0], tokens=rows[0][1], cached=True)
        if self.mode == "replay":
            raise LLMCacheMiss(key)

        from google.genai import types

        client = self._client_or_raise()
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        )
        if use_search:  # live mode only, enforced by caller (tools.web_search)
            config.tools = [types.Tool(google_search=types.GoogleSearch())]
        resp = await client.aio.models.generate_content(model=model, contents=prompt, config=config)
        text = resp.text or "{}"
        tokens = getattr(resp.usage_metadata, "total_token_count", 0) or 0
        self.db.execute(
            "INSERT OR REPLACE INTO llm_cache(key, response, tokens, created) VALUES (?,?,?,?)",
            (key, text, tokens, datetime.now(timezone.utc).isoformat()),
        )
        return LLMResponse(text=text, tokens=tokens, cached=False)


def _ping() -> None:  # pragma: no cover
    import asyncio

    class Pong(BaseModel):
        ok: bool
        model: str

    s = get_settings()
    s.llm_mode = "live"
    llm = LLM(DB(), s)
    r = asyncio.run(llm.generate(model=s.gemini_model_deep, system="Reply with JSON.",
                                 prompt=f'Return {{"ok": true, "model": "{s.gemini_model_deep}"}}', schema=Pong,
                                 as_of="ping"))
    print("OK:", r.text, "tokens:", r.tokens)


if __name__ == "__main__":  # pragma: no cover
    import sys

    if "--ping" in sys.argv:
        _ping()

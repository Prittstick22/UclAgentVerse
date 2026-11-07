from __future__ import annotations

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    id: str
    tickers: list[str]
    headline: str
    summary: str = ""
    url: str | None = None
    source: str
    published_at: str          # ISO timestamp
    available_at: str          # ISO timestamp; gateway filters on this
    synthetic: bool = False


class Passage(BaseModel):
    id: str
    text: str


class Filing(BaseModel):
    id: str
    company: str
    ticker: str
    form: str
    accepted_at: str
    available_at: str
    url: str | None = None
    passages: list[Passage] = Field(default_factory=list)
    synthetic: bool = False


class Freshness(BaseModel):
    ticker: str
    last_date: str | None
    stale: bool
    source: str

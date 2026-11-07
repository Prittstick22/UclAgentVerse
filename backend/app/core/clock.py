"""The single source of "now". Business logic must never call datetime.now() directly."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
CLOSE = time(16, 30)


class Clock:
    mode: str = "historical"

    def now(self) -> datetime:  # pragma: no cover - interface
        raise NotImplementedError

    def today(self) -> date:
        return self.now().astimezone(LONDON).date()

    def as_of_str(self) -> str:
        return self.today().isoformat()


class SimClock(Clock):
    """Historical clock. Each sim day is observed at the London close (16:30)."""

    mode = "historical"

    def __init__(self, start: date | str):
        self._day = date.fromisoformat(start) if isinstance(start, str) else start

    def set(self, day: date | str) -> None:
        self._day = date.fromisoformat(day) if isinstance(day, str) else day

    def now(self) -> datetime:
        return datetime.combine(self._day, CLOSE, tzinfo=LONDON)


class LiveClock(Clock):
    mode = "live"

    def now(self) -> datetime:
        return datetime.now(timezone.utc).astimezone(LONDON)

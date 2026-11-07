"""Injection guard: external text is data, not instructions. Owner: Dev.

Code regex pass first (cheap). TODO(issue: injection guard): add a Flash classifier for subtler cases.
"""
from __future__ import annotations

import re

PATTERNS = [
    r"ignore (all |any |your )?(previous |prior )?(instructions|rules|limits)",
    r"disregard (the |your )?(system|previous|instructions|limits)",
    r"you are now",
    r"(buy|sell) \d{2,3}\s?% (of|in)",
    r"override (the )?(mandate|limits|risk)",
    r"system prompt",
    r"</?untrusted_source",
]
_RX = re.compile("|".join(PATTERNS), re.I)


def scan(text: str) -> str | None:
    """Return a reason if the text looks like an instruction injection, else None."""
    m = _RX.search(text or "")
    return f"instruction-like content: '{m.group(0)}'" if m else None


def wrap(evidence_id: str, text: str) -> str:
    safe = (text or "").replace("<untrusted_source", "&lt;untrusted_source")
    return f'<untrusted_source id="{evidence_id}">\n{safe}\n</untrusted_source>'

"""Contract guard: every endpoint in docs/04-api-contracts.md exists in the app, and vice versa.

If this fails you changed (or forgot) an endpoint: update docs/04 + backend/app/schemas.py +
frontend/src/lib/types.ts + fixtures in the same PR and post a board `contract-change` message.
"""
import re
from pathlib import Path

from app.main import app

DOC = Path(__file__).resolve().parents[2] / "docs" / "04-api-contracts.md"


def _norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{}", path)


def documented() -> set[tuple[str, str]]:
    out = set()
    for a, b in re.findall(r"^\| `([^`]+)`(?: · `([^`]+)`)? \|", DOC.read_text(encoding="utf-8"), re.M):
        for x in (a, b):
            if x and " /api" in x:
                method, path = x.split(" ", 1)
                out.add((method, _norm(path)))
    return out


def implemented() -> set[tuple[str, str]]:
    return {(m.upper(), _norm(p)) for p, ops in app.openapi()["paths"].items() for m in ops}


def test_every_documented_endpoint_exists():
    missing = documented() - implemented()
    assert not missing, f"In docs/04 but not implemented: {sorted(missing)}"


def test_every_endpoint_is_documented():
    extra = implemented() - documented()
    assert not extra, f"Implemented but missing from docs/04 (contract change!): {sorted(extra)}"

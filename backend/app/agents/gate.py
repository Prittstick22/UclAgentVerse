"""Assurance gate runner. Owner: Dev (LLM gates) + Cem (numbers/mandate/revalidation in engine.checker).

SCAFFOLD: interface + order + proportionality table. Implement in the gate issues.
Order (docs/05-agent-system.md §6): injection_guard → evidence → numbers+mandate → critic → compliance → qa
→ user approval → revalidation.
"""
from __future__ import annotations

import re

from app.schemas import GateResult

FULL_GATE = ["injection_guard", "evidence", "numbers", "mandate", "critic", "compliance", "qa"]
LIGHT_GATE = ["evidence", "compliance"]

BANNED_PHRASES = [r"\bguarantee", r"\brisk[- ]free\b", r"can'?t lose", r"\bwill (definitely )?(rise|go up)\b"]


def gates_for(outcome: str, turnover: float = 0.0) -> list[str]:
    if outcome == "adjust":
        return FULL_GATE
    if outcome == "rebalance":
        return ["numbers", "mandate", "compliance"] + (["critic"] if turnover > 0.05 else [])
    return LIGHT_GATE


def compliance_rules(text: str) -> GateResult:
    """Code half of the compliance gate. The Flash half (wording review) is TODO."""
    issues = [f"banned phrase: {p}" for p in BANNED_PHRASES if re.search(p, text, re.I)]
    if "go down as well as up" not in text.lower():
        issues.append("missing risk warning")
    return GateResult(gate="compliance", status="fail" if issues else "pass", issues=issues)


async def run_gate(run, proposal, outcome: str) -> list[GateResult]:  # pragma: no cover - scaffold
    """TODO(#agents-gate): run each gate in order, emit gate.started/gate.verdict, one revision loop."""
    raise NotImplementedError

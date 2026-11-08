"""Deterministic fake LLM for LLM_MODE=fake (offline dev + tests). Owner: Dev.

respond(ctx) returns a dict matching AgentStep. Extend the scripts as roles/plans are implemented.
"""
from __future__ import annotations

import json


class FakeBrain:
    def respond(self, ctx: dict) -> dict:
        role, kind, step, depth = ctx.get("role"), ctx.get("kind"), ctx.get("step", 0), ctx.get("depth", 0)
        if role == "lead":
            return self._lead(kind, step)
        if role == "filing_reader" and step == 0:
            # demonstrates a refused depth-3 spawn
            return {"message": "Looking for a related news item too.",
                    "spawns": [{"role": "news_analyst", "question": "Any news on this filing?", "purpose": "context"}]}
        if role in ("stock_analyst",) and step == 0 and depth == 1:
            return {"message": "Reading the latest annual report.",
                    "spawns": [{"role": "filing_reader", "question": "Find risk-factor passages", "purpose": "evidence"}]}
        if role == "risk_analyst" and step == 0:
            return {"message": "Checking how the candidates move together.",
                    "tool_calls": [{"tool": "correlation_lattice", "args_json": json.dumps({"lookback": 252})}]}
        return {"message": f"{role} finished.", "final": {"findings": [
            {"claim": f"[fake] {role} finding", "evidence_ids": ["catalogue"], "confidence": "med"}]}}

    def _lead(self, kind: str, step: int) -> dict:
        if step == 0:
            spawns = {"construction": ["equity_scout", "bond_scout", "stock_analyst"],
                      "review": ["risk_analyst"]}.get(kind, ["news_analyst"])
            return {"message": f"Planning the {kind} run.",
                    "spawns": [{"role": r, "question": f"{r} task for {kind}", "purpose": "fake plan"} for r in spawns]}
        if step == 1:
            if kind == "construction":
                return {"message": "Building three portfolio options with the optimiser.",
                        "tool_calls": [{"tool": "build_options", "args_json": "{}"}]}
            return {"message": "Checking correlations before deciding.",
                    "tool_calls": [{"tool": "get_catalogue", "args_json": "{}"}]}
        if step == 2 and kind == "construction":
            return {"message": "Proposing the recommended option for your approval.",
                    "tool_calls": [{"tool": "propose_adjustment", "args_json": json.dumps({"option": "recommended"})}]}
        action = "adjust" if kind in ("drift", "cap_breach", "construction") else "maintain"
        return {"message": f"Decision: {action}.",
                "final": {"decision": {"action": action, "reason": "[fake] scripted decision", "evidence_ids": []}}}

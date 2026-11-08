"""Approval policies. Owner: Cem. Spec: docs/03-how-it-works.md §3, docs/07 §6.

manual:       the proposal waits for POST /api/proposals/{id}/approve (#23). The simulation keeps running.
batch_policy: overnight run only. Auto-approve only if no gate failed, the independent engine checker passes,
              and turnover <= mandate.approval.batch_auto_approve_turnover_max. The very first (construction)
              portfolio is exempt from the turnover limit, since buying from cash is always 100% turnover.
              Always labelled by="batch_policy".
"""
from __future__ import annotations

from typing import Any, Literal

from app.engine import checker
from app.schemas import Mandate, Proposal

ApprovalMode = Literal["manual", "batch_policy"]
PASSING = {"pass", "pass_with_flags", "skipped", "pending"}   # "pending" = gate not wired yet (#32); checker still runs


def batch_allows(gate_passed: bool, turnover: float, mandate: Mandate, construction: bool = False) -> bool:
    return gate_passed and (construction or turnover <= mandate.approval.batch_auto_approve_turnover_max)


def selected_weights(prop: Proposal) -> tuple[dict[str, float], float] | None:
    opt = next((o for o in prop.options if o.label == prop.selected), None)
    if opt is None:
        return None
    return {h.ticker: h.weight for h in opt.holdings if h.weight > 0}, opt.cash_weight


def turnover(target: dict[str, float], current: dict[str, float]) -> float:
    return sum(abs(target.get(k, 0.0) - current.get(k, 0.0)) for k in set(target) | set(current)) / 2


def handle(state: Any, prop: Proposal, mode: ApprovalMode, construction: bool = False
           ) -> tuple[dict[str, float] | None, str]:
    """Apply the approval policy to a fresh proposal: returns (approved target weights or None, outcome).

    Outcomes: "approved" (orders queued for the next close), "awaiting_approval", or "blocked" (the engine
    checker or a gate rejected it; never traded)."""
    ev = state.events
    picked = selected_weights(prop)
    if picked is None:
        return _set(state, prop, "blocked", f"Proposal {prop.id} has no '{prop.selected}' option"), "blocked"
    weights, cash = picked
    rep = checker.check_proposal(weights, cash, state.mandate, state.gw.catalogue())
    gates_ok = all(g.status in PASSING for g in prop.gates)
    if not rep.passed or not gates_ok:
        why = "; ".join(v.message for v in rep.violations[:3]) or "a gate failed"
        _set(state, prop, "blocked", why)
        ev.emit("gate.verdict", run_id=prop.run_id, title=f"Blocked before approval: {why}"[:120], status="failed",
                payload={"gate": "mandate", "status": "fail", "issues": [why], "required_changes": [],
                         "proposal_id": prop.id})
        return None, "blocked"
    to = turnover(weights, state.ledger.weights())
    if mode == "batch_policy" and batch_allows(True, to, state.mandate, construction):
        _set(state, prop, "approved")
        ev.emit("approval.decided", run_id=prop.run_id, title=f"Approved by batch policy (turnover {to:.0%})",
                payload={"proposal_id": prop.id, "decision": "approved", "by": "batch_policy", "turnover": round(to, 4)})
        return weights, "approved"
    _set(state, prop, "awaiting_approval")
    ev.emit("approval.requested", run_id=prop.run_id, title=prop.decision_card.headline[:120],
            payload={"proposal_id": prop.id, "decision": "pending", "by": "user", "turnover": round(to, 4)})
    return None, "awaiting_approval"


def _set(state: Any, prop: Proposal, status: str, note: str | None = None) -> None:
    prop.status = status  # type: ignore[assignment]
    if note and note not in prop.uncertainties:
        prop.uncertainties.append(note)
    state.proposals[prop.id] = prop
    state.db.put("proposals", prop.id, prop.model_dump_json())

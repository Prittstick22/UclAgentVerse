"""Approval policies. Owner: Cem. Spec: docs/03-how-it-works.md §3, docs/07 §6.

manual:       the proposal waits for POST /api/proposals/{id}/approve (#23). The simulation keeps running.
batch_policy: overnight run only. Auto-approve only if no gate failed, the independent engine checker passes,
              and turnover <= mandate.approval.batch_auto_approve_turnover_max. The very first (construction)
              portfolio is exempt from the turnover limit, since buying from cash is always 100% turnover.
              Always labelled by="batch_policy".
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from app.config import params
from app.engine import checker
from app.schemas import Mandate, OrderChange, Proposal

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
    gates_ok = bool(prop.gates) and all(g.status in PASSING for g in prop.gates)   # unchecked = not ok
    if not rep.passed or not gates_ok:
        why = ("; ".join(v.message for v in rep.violations[:3])
               or ("a gate failed" if prop.gates else "not checked by the assurance gate"))
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


# ---------------------------------------------------------------------- user approval (#23)

CTX_NS = "proposal_ctx"
APPROVABLE = {"draft", "awaiting_approval"}


class ApprovalError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def mandate_fingerprint(mandate: Mandate) -> str:
    """Changes whenever the mandate content changes, even if `version` wasn't bumped (e.g. a new quiz result)."""
    raw = json.dumps(mandate.model_dump(mode="json", exclude={"version"}), sort_keys=True)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def attach(state: Any) -> None:
    """Record what the world looked like when each proposal was made, for revalidation at approval time."""
    def on_event(ev: Any) -> None:
        if ev.type != "proposal.created":
            return
        pid = (ev.payload or {}).get("proposal_id")
        if pid:
            state.db.put(CTX_NS, pid, json.dumps({
                "as_of": state.clock.as_of_str(), "mandate_version": state.mandate.version,
                "mandate_fingerprint": mandate_fingerprint(state.mandate),
                "trades": _trade_marker(state.ledger)}))
    state.events.listen(on_event)


def _trade_marker(ledger: Any) -> str:
    """Changes when a trade fills. (Not the units hash: daily fund-fee drag changes units without a trade.)"""
    return f"{len(ledger.fills)}"


def _context(state: Any, prop: Proposal) -> dict:
    raw = state.db.get(CTX_NS, prop.id)
    return json.loads(raw) if raw else {}


def _price_dates(state: Any, tickers: list[str]) -> dict[str, str]:
    px = state.gw.prices(caller="approvals.revalidate")   # all tickers: an unknown one reads as stale, not a 500
    out = {}
    for t in tickers:
        s = px[t].dropna() if t in px.columns else None
        out[t] = s.index[-1].date().isoformat() if s is not None and len(s) else "1900-01-01"
    return out


def _orders(state: Any, weights: dict[str, float]) -> list[OrderChange]:
    led = state.ledger
    nav = led.nav()
    now = led.weights()
    min_trade = float(params()["min_trade_gbp"])   # the ledger skips smaller trades, so don't promise them
    out = []
    for t in sorted(set(weights) | set(now)):
        d = weights.get(t, 0.0) - now.get(t, 0.0)
        if abs(d) * nav >= min_trade:
            out.append(OrderChange(ticker=t, action="buy" if d > 0 else "sell", amount_gbp=round(abs(d) * nav, 2),
                                   from_weight=round(now.get(t, 0.0), 6), to_weight=round(weights.get(t, 0.0), 6)))
    return out


def _next_close(state: Any) -> str | None:
    today = state.clock.as_of_str()
    nxt = [d for d in state.gw.trading_days(today) if d.date().isoformat() > today]
    return nxt[0].date().isoformat() if nxt else None


def approve_by_user(state: Any, proposal_id: str, option: str | None = None) -> dict:
    """Revalidate, then queue the orders for the next close. Raises ApprovalError (404/409/422)."""
    from app.engine import checker as chk

    prop = state.proposals.get(proposal_id)
    if prop is None:
        raise ApprovalError(404, "not_found", "proposal not found")
    if prop.status in ("approved", "executed"):
        raise ApprovalError(409, "duplicate_order", "This proposal was already approved")
    if prop.status not in APPROVABLE:
        raise ApprovalError(409, "conflict", f"This proposal is {prop.status} and can't be approved")
    if not prop.gates:   # never checked (e.g. the run timed out mid-gate): no checks, no approval
        raise ApprovalError(409, "conflict", "This proposal hasn't been through the assurance checks")
    if any(g.status == "fail" for g in prop.gates):   # belt and braces: the gate blocks these already
        raise ApprovalError(409, "conflict", "The assurance checks failed for this proposal; it can't be approved",
                            {"failed_gates": [g.gate for g in prop.gates if g.status == "fail"]})
    chosen = option or prop.selected
    if not any(o.label == chosen for o in prop.options):
        raise ApprovalError(422, "validation_error", f"No option '{chosen}' in this proposal",
                            {"options": [o.label for o in prop.options]})
    picked = selected_weights(prop.model_copy(update={"selected": chosen}))   # only saved once approved
    assert picked is not None
    weights, cash = picked
    led, ctx, today = state.ledger, _context(state, prop), state.clock.as_of_str()

    if ctx.get("mandate_fingerprint") and ctx["mandate_fingerprint"] != mandate_fingerprint(state.mandate):
        raise ApprovalError(409, "mandate_changed", "Your investment rules changed after this proposal was made. "
                            "Ask for a new proposal.")
    pending_keys = {str(o.get("reason", "")) for o in led.pending}
    other = next((k for k in pending_keys if k.startswith("proposal:") and k != f"proposal:{prop.id}"), None)
    if other:   # queue_rebalance would silently replace it
        raise ApprovalError(409, "duplicate_order", f"Another approved order ({other[9:]}) is waiting for the "
                            "next close; approve this one after it fills")
    rep = chk.revalidate(
        proposal_as_of=prop.as_of, price_dates=_price_dates(state, list(weights)), today=today,
        mandate_version_at_proposal=ctx.get("mandate_version", state.mandate.version),
        mandate_version_now=state.mandate.version,
        holdings_hash_at_proposal=ctx.get("trades", _trade_marker(led)), holdings_hash_now=_trade_marker(led),
        pending_order_keys=pending_keys, order_key=f"proposal:{prop.id}")
    if not rep.passed:
        v = rep.violations[0]
        code = {"stale_data": "stale_data", "duplicate_order": "duplicate_order", "mandate_changed": "mandate_changed",
                "holdings_changed": "holdings_changed"}.get(v.code, "conflict")
        raise ApprovalError(409, code, v.message, {"violations": [x.model_dump(exclude_none=True) for x in rep.violations]})
    check = chk.check_proposal(weights, cash, state.mandate, state.gw.catalogue())
    if not check.passed:
        raise ApprovalError(409, "mandate_violation", "; ".join(x.message for x in check.violations[:3]),
                            {"violations": [x.model_dump(exclude_none=True) for x in check.violations]})

    prop.selected = chosen  # type: ignore[assignment]
    orders = _orders(state, weights)
    led.queue_rebalance(weights, f"proposal:{prop.id}")
    sim = getattr(getattr(state, "sim_controller", None), "sim", None)
    if sim is not None and not sim.done:
        sim.targets = weights          # monitors now measure drift against what the user approved
    fill_date = _next_close(state)
    _set(state, prop, "approved")
    state.db.put("proposal_decisions", prop.id, json.dumps({
        "decision": "approved", "by": "user", "option": prop.selected, "at": datetime.now(UTC).isoformat()}))
    state.events.emit("approval.decided", run_id=prop.run_id, title=f"You approved: {prop.decision_card.headline}"[:120],
                      payload={"proposal_id": prop.id, "decision": "approved", "by": "user", "option": prop.selected,
                               "fill_date": fill_date})
    return {"proposal": prop, "orders": orders, "fill_date": fill_date}


def mark_executed(state: Any, reason: str | None, fills: list) -> None:
    """After an approved proposal's orders fill, its status becomes 'executed'."""
    if fills and reason and reason.startswith("proposal:"):
        prop = state.proposals.get(reason[len("proposal:"):])
        if prop is not None and prop.status == "approved":
            _set(state, prop, "executed")


def decline_by_user(state: Any, proposal_id: str, reason: str | None = None) -> dict:
    prop = state.proposals.get(proposal_id)
    if prop is None:
        raise ApprovalError(404, "not_found", "proposal not found")
    if prop.status not in APPROVABLE:
        raise ApprovalError(409, "conflict", f"This proposal is already {prop.status}")
    note = (reason or "").strip()[:500]
    _set(state, prop, "declined", f"Declined: {note}" if note else None)
    state.db.put("proposal_decisions", prop.id, json.dumps({
        "decision": "declined", "by": "user", "reason": note, "at": datetime.now(UTC).isoformat()}))
    state.events.emit("approval.decided", run_id=prop.run_id, title="You declined the proposal",
                      payload={"proposal_id": prop.id, "decision": "declined", "by": "user", "reason": note})
    return {"proposal": prop}

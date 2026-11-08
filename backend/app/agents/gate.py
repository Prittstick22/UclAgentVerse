"""Assurance gate (#32). Owner: Cem (moved from Dev). Spec: docs/05-agent-system.md §6.

Separate checks look at a proposal before the user ever sees it, in this order:
  injection_guard → evidence → numbers → mandate → critic → compliance → qa
then (outside this module) user approval → revalidation → fill.

Every check here is CODE: deterministic, cheap, and it can't be talked round. Numbers and mandate use the
independent engine checker (engine/checker.py), never the optimiser. The supervisor runs the gate on every
proposal, allows ONE revision round, and on a second failure blocks the proposal (investigate_further).
"""
from __future__ import annotations

import re
from typing import Any

from app.agents.guard import scan
from app.schemas import GateResult, Proposal

FULL_GATE = ["injection_guard", "evidence", "numbers", "mandate", "critic", "compliance", "qa"]
LIGHT_GATE = ["evidence", "compliance"]

BANNED_PHRASES = [r"\bguarantee", r"\brisk[- ]free\b", r"can'?t lose", r"\bwill (definitely )?(rise|go up)\b"]
RISK_WARNING = "go down as well as up"
ALWAYS_EVIDENCE = {"catalogue"}          # the gateway catalogue itself
NUM_TOL = 1e-3                           # stats are rounded to 4 dp in the proposal


def gates_for(outcome: str, turnover: float = 0.0) -> list[str]:
    if outcome in ("adjust", "built", "construction"):
        return FULL_GATE
    if outcome == "rebalance":
        return ["numbers", "mandate", "compliance"] + (["critic"] if turnover > 0.05 else [])
    return LIGHT_GATE


def compliance_rules(text: str) -> GateResult:
    """Banned promises and the risk warning (code half of compliance)."""
    issues = [f"banned phrase: {p}" for p in BANNED_PHRASES if re.search(p, text, re.IGNORECASE)]
    if RISK_WARNING not in text.lower():
        issues.append("missing risk warning")
    return GateResult(gate="compliance", status="fail" if issues else "pass", issues=issues)


# ---------------------------------------------------------------------- the checks
def _card_text(p: Proposal) -> str:
    c = p.decision_card
    return " ".join([c.headline, c.body, c.risk_warning, *p.uncertainties,
                     *(h.purpose + " " + h.why_not_alternatives for o in p.options for h in o.holdings)])


def _selected(p: Proposal):
    return next((o for o in p.options if o.label == p.selected), None)


def _run_events(ctx: Any, run_id: str | None) -> list:
    return ctx.events.history(run_id) if run_id else []


def check_injection(ctx: Any, run: Any, p: Proposal) -> GateResult:
    issues = []
    texts = [("proposal", _card_text(p))] + [(f"finding '{f.claim[:40]}'", f.claim) for f in getattr(run, "findings", [])]
    for where, text in texts:
        if reason := scan(text):
            issues.append(f"{where}: {reason}")
    quarantined = {i for e in _run_events(ctx, getattr(run, "run_id", None)) if e.type == "content.quarantined"
                   for i in (e.evidence_ids or [e.payload.get("evidence_id")]) if i}
    cited = {i for f in getattr(run, "findings", []) for i in f.evidence_ids}
    for i in sorted(cited & quarantined):
        issues.append(f"cites quarantined content {i}")
    return GateResult(gate="injection_guard", status="fail" if issues else "pass", issues=issues)


def _known_evidence(ctx: Any, run: Any) -> set[str]:
    """Ids a tool actually returned in this run (the tool wrapper records them), plus the catalogue."""
    seen = set(ALWAYS_EVIDENCE)
    for e in _run_events(ctx, getattr(run, "run_id", None)):
        if e.type in ("tool.result", "source.inspect", "calc.result", "proposal.created"):
            seen.update(e.evidence_ids or [])
            if e.type == "calc.result":
                seen.add(f"calc:{e.id}")
    return seen


def _resolvable(ctx: Any, eid: str) -> bool:
    try:
        from app.api.run_views import find_evidence  # lazy: api imports the container, which imports agents
        return find_evidence(ctx.gw, ctx.state.db, eid) is not None
    except Exception:  # noqa: BLE001 - an unreadable id is simply not evidence
        return False


def unusable_findings(ctx: Any, run: Any) -> list:
    """Findings a revision can't fix by rewording: no or unknown evidence, injected text, or quarantined sources.
    The supervisor removes them before the revision, so one bad claim can't sink every later attempt."""
    known = _known_evidence(ctx, run)
    quarantined = {i for e in _run_events(ctx, getattr(run, "run_id", None)) if e.type == "content.quarantined"
                   for i in (e.evidence_ids or [e.payload.get("evidence_id")]) if i}
    out = []
    for f in getattr(run, "findings", []):
        if f.claim.endswith("could not finish"):
            continue
        unsupported = not f.evidence_ids or any(i not in known and not _resolvable(ctx, i) for i in f.evidence_ids)
        if unsupported or scan(f.claim) or set(f.evidence_ids) & quarantined:
            out.append(f)
    return out


def check_evidence(ctx: Any, run: Any, p: Proposal) -> GateResult:
    """Every claim must cite evidence we actually retrieved (or can look up as of now)."""
    known = _known_evidence(ctx, run)
    unsupported, strong = [], []
    for f in getattr(run, "findings", []):
        if f.claim.endswith("could not finish"):          # the supervisor's own failure note, not a claim
            continue
        bad = [i for i in f.evidence_ids if i not in known and not _resolvable(ctx, i)]
        if not f.evidence_ids or bad:
            why = "no evidence cited" if not f.evidence_ids else f"evidence not found: {', '.join(bad[:3])}"
            unsupported.append(f"'{f.claim[:80]}': {why}")
            if f.confidence == "high":
                strong.append(f.claim[:80])
    total = sum(1 for f in getattr(run, "findings", []) if not f.claim.endswith("could not finish"))
    if strong or (total and len(unsupported) * 2 > total):
        status = "fail"
    else:
        status = "pass_with_flags" if unsupported else "pass"
    return GateResult(gate="evidence", status=status, issues=unsupported[:10])


def check_numbers(ctx: Any, run: Any, p: Proposal) -> GateResult:
    """Recompute every option's numbers with the independent checker and compare with what the card says."""
    from app.engine import checker

    issues = []
    led = ctx.state.ledger
    current = led.weights()
    for o in p.options:
        w = {h.ticker: h.weight for h in o.holdings}
        rep = checker.check_proposal(w, o.cash_weight, ctx.state.mandate, ctx.gw.catalogue(eligible_only=False),
                                     current_weights=current)
        r = rep.recomputed
        if not r:
            issues.append(f"{o.label}: weights are not numbers")
            continue
        if abs(r["sum"] - 1.0) > NUM_TOL:
            issues.append(f"{o.label}: weights + cash add up to {r['sum']:.4f}, not 1")
        if abs(r["ocf_weighted"] - o.stats.ocf_weighted) > NUM_TOL:
            issues.append(f"{o.label}: fund fees {o.stats.ocf_weighted:.4%} but recomputed {r['ocf_weighted']:.4%}")
        if abs(r["turnover"] - o.stats.turnover) > 0.01:
            issues.append(f"{o.label}: turnover {o.stats.turnover:.1%} but recomputed {r['turnover']:.1%}")
    return GateResult(gate="numbers", status="fail" if issues else "pass", issues=issues)


def check_mandate(ctx: Any, run: Any, p: Proposal) -> GateResult:
    from app.engine import checker

    o = _selected(p)
    if o is None:
        return GateResult(gate="mandate", status="fail", issues=[f"no '{p.selected}' option"])
    rep = checker.check_proposal({h.ticker: h.weight for h in o.holdings}, o.cash_weight, ctx.state.mandate,
                                 ctx.gw.catalogue(eligible_only=False))
    return GateResult(gate="mandate", status="pass" if rep.passed else "fail",
                      issues=[v.message for v in rep.violations])


def check_critic(ctx: Any, run: Any, p: Proposal) -> GateResult:
    """Judgement flags a careful reviewer would raise. Never a hard fail: it flags for the lead and the user."""
    flags = []
    o = _selected(p)
    m = ctx.state.mandate
    nav = ctx.state.ledger.nav()
    if o is not None:
        if p.kind == "adjustment" and o.stats.turnover > 0.20:
            flags.append(f"moves {o.stats.turnover:.0%} of the portfolio in one go")
        for h in o.holdings:
            inst = next((i for i in ctx.gw.catalogue(eligible_only=False) if i.ticker == h.ticker), None)
            cap = m.caps.per_stock if inst and inst.kind == "stock" else m.caps.per_fund
            if cap and h.weight >= 0.95 * cap:
                flags.append(f"{h.ticker} is at {h.weight:.0%}, right at its {cap:.0%} limit")
        if nav > 0 and o.stats.cost_gbp > 0.005 * nav:
            flags.append(f"trading cost £{o.stats.cost_gbp:,.2f} is over 0.5% of the portfolio")
    low = [f.claim[:60] for f in getattr(run, "findings", []) if f.confidence == "low"]
    if low:
        flags.append(f"{len(low)} low-confidence finding(s), e.g. '{low[0]}'")
    return GateResult(gate="critic", status="pass_with_flags" if flags else "pass", issues=flags)


def check_compliance(ctx: Any, run: Any, p: Proposal) -> GateResult:
    res = compliance_rules(_card_text(p))
    if not p.decision_card.simulated:
        res.issues.append("decision card is not labelled simulated")
        res.status = "fail"
    return res


def check_qa(ctx: Any, run: Any, p: Proposal) -> GateResult:
    issues, flags = [], []
    o = _selected(p)
    if not p.options or o is None:
        issues.append(f"selected option '{p.selected}' is missing")
    if not p.decision_card.headline.strip() or not p.decision_card.body.strip():
        issues.append("decision card has no headline or body")
    if o is not None:
        missing = [h.ticker for h in o.holdings if not h.purpose.strip()]
        if missing:
            flags.append(f"no purpose given for {', '.join(missing[:5])}")
    status = "fail" if issues else ("pass_with_flags" if flags else "pass")
    return GateResult(gate="qa", status=status, issues=issues + flags)


CHECKS = {"injection_guard": check_injection, "evidence": check_evidence, "numbers": check_numbers,
          "mandate": check_mandate, "critic": check_critic, "compliance": check_compliance, "qa": check_qa}


def run_gate(ctx: Any, run: Any, proposal: Proposal, outcome: str = "adjust") -> list[GateResult]:
    """Run the gates for `outcome` in order; emit gate.started / gate.verdict for each. Returns all results."""
    out = []
    rid = getattr(run, "run_id", None)
    for name in gates_for(outcome):
        ctx.events.emit("gate.started", run_id=rid, title=f"Checking: {name}", status="started",
                        payload={"gate": name, "status": "pending", "issues": [], "required_changes": [],
                                 "proposal_id": proposal.id})
        try:
            res = CHECKS[name](ctx, run, proposal)
        except Exception as e:  # noqa: BLE001 - a broken check must fail closed, not open
            res = GateResult(gate=name, status="fail", issues=[f"check crashed: {type(e).__name__}"])
        required = res.issues if res.status == "fail" else []
        ctx.events.emit("gate.verdict", run_id=rid, title=f"{name}: {res.status}",
                        status="failed" if res.status == "fail" else "ok",
                        payload={"gate": name, "status": res.status, "issues": res.issues,
                                 "required_changes": required, "proposal_id": proposal.id})
        out.append(res)
    return out


def passed(results: list[GateResult]) -> bool:
    return all(r.status != "fail" for r in results)

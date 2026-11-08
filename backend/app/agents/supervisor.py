"""Supervisor: runs agent trees and enforces limits in code. Owner: Dev. Spec: docs/05-agent-system.md §3.

Per agent step: one LLM call (schema-checked, retried once with the error), then the tool calls and spawns it
asked for. Limits (depth, agents, children, tool calls, steps, tokens, wall time) are enforced here, never by the
model. A failed agent is recorded as a low-confidence finding and its parent carries on with what it has.

Prompts are deterministic for a given run (no random ids), so a rerun with the same as_of hits the LLM cache.

    python -m app.agents.supervisor --run construction     # one run with the settings in .env, prints a summary
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from app.agents.llm import LLM, LLMCacheMiss, LLMError, LLMSchemaError
from app.agents.roles import ROLES, TOOL_DOCS
from app.agents.schemas import AgentFinal, AgentStep, Decision, Finding, SpawnRequest
from app.agents.tools import ToolRegistry
from app.config import agents as agents_cfg
from app.core.events import EventBus
from app.schemas import RunSummary

RESULT_CHARS = 1500          # max characters of one tool result fed back to the model
LIST_ITEMS = 10              # max items kept from any list in a tool result
_CALC_ID = re.compile(r"calc:[0-9a-f]{32}|prop_[0-9a-f]{10}")   # random ids -> stable aliases (cache)
_ALIAS = re.compile(r"(?:calc|ref):[\w.]+:\d+")


class SpawnDenied(Exception):
    pass


class AgentFailed(Exception):
    pass


@dataclass
class RunState:
    run_id: str
    kind: str
    trigger_text: str
    agents_started: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    llm_calls: int = 0
    cached_calls: int = 0
    budget_hit: bool = False
    findings: list = field(default_factory=list)
    decision: Decision | None = None
    proposal_id: str | None = None
    scratch: dict = field(default_factory=dict)        # tool outputs shared within the run (e.g. built options)
    evidence_map: dict[str, str] = field(default_factory=dict)   # stable alias → real evidence id


class AgentResult(BaseModel):
    agent_id: str
    role: str
    final: AgentFinal | None = None
    denied: str | None = None
    failed: str | None = None


class Supervisor:
    def __init__(self, llm: LLM, tools: ToolRegistry, events: EventBus):
        self.llm = llm
        self.tools = tools
        self.events = events
        self.cfg = agents_cfg()
        self._sem = asyncio.Semaphore(self.cfg["max_parallel"])

    # ------------------------------------------------------------------ public
    async def start(self, kind: str, trigger_text: str, question: str | None = None, *,
                    run_id: str | None = None) -> RunState:
        run = RunState(run_id=run_id or f"run_{uuid.uuid4().hex[:10]}", kind=kind, trigger_text=trigger_text)
        t0 = time.monotonic()
        started_at = datetime.now(UTC).isoformat()
        limits = {"max_depth": self.cfg["max_depth"], "max_agents": self._max_agents(kind),
                  "token_budget": self._budget(kind)}
        self._save_summary(run, "running", None, started_at, None)
        self.events.emit("run.started", run_id=run.run_id, title=f"{kind.title()} run started", status="started",
                         trigger_kind=kind, trigger_text=trigger_text, payload={"kind": kind, "limits": limits})
        status = "ok"
        try:
            await asyncio.wait_for(
                self._run_agent(run, "lead", question or f"{kind}: {trigger_text}", "Lead this run", None, 0, "lead"),
                timeout=self.cfg["run_wall_time_s"],
            )
        except TimeoutError:
            status = "failed"
            self.events.emit("budget.exceeded", run_id=run.run_id, title="Run hit its wall-time limit",
                             payload={"limit": "wall_time_s", "value": self.cfg["run_wall_time_s"]})
        except (Exception, asyncio.CancelledError):
            status = "failed"
            raise
        finally:
            # TODO(#32): run app.agents.gate.run_gate on run.proposal_id before marking awaiting_approval
            outcome = run.decision.action if run.decision else "investigate_further"
            if kind == "construction" and run.proposal_id:
                outcome = "built"
            duration = round(time.monotonic() - t0, 2)
            self.events.emit("run.completed", run_id=run.run_id, title=f"Run finished: {outcome}", status=status,
                             trigger_kind=kind,
                             payload={"outcome": outcome, "proposal_id": run.proposal_id, "tokens": run.tokens,
                                      "cost_estimate_usd": round(run.cost_usd, 4), "duration_s": duration,
                                      "llm_calls": run.llm_calls, "cached_calls": run.cached_calls,
                                      "budget_exceeded": run.budget_hit})
            self._save_summary(run, "completed" if status == "ok" else "failed", outcome, started_at,
                               datetime.now(UTC).isoformat())
        return run

    # ------------------------------------------------------------------ limits
    def _max_agents(self, kind: str) -> int:
        m = self.cfg["max_agents_per_run"]
        return m.get(kind, m.get("trigger", 8))

    def _budget(self, kind: str) -> int:
        b = self.cfg["run_token_budget"]
        return b.get(kind, b.get("trigger", 100000))   # drift / price_move / news / ... are trigger runs

    def check_spawn(self, run: RunState, parent_role: str, req: SpawnRequest, parent_depth: int,
                    children_so_far: int) -> None:
        role = ROLES.get(req.role)
        if role is None or req.role not in ROLES[parent_role].can_spawn:
            raise SpawnDenied("role_not_allowed")
        if parent_depth + 1 > self.cfg["max_depth"]:
            raise SpawnDenied("max_depth")
        if run.agents_started >= self._max_agents(run.kind):
            raise SpawnDenied("max_agents")
        max_children = self.cfg["max_children_lead"] if parent_role == "lead" else self.cfg["max_children_per_agent"]
        if children_so_far >= max_children:
            raise SpawnDenied("max_children")
        if run.tokens >= self._budget(run.kind):
            raise SpawnDenied("budget")

    def _over_budget(self, run: RunState, common: dict) -> bool:
        if run.tokens < self._budget(run.kind):
            return False
        if not run.budget_hit:
            run.budget_hit = True
            self.events.emit("budget.exceeded", title="Run hit its token budget",
                             payload={"limit": "tokens", "value": run.tokens, "budget": self._budget(run.kind)},
                             **common)
        return True

    # ------------------------------------------------------------------ prompt helpers
    def _header(self, run: RunState, role_name: str, tool_calls_left: int) -> str:
        clock = self.events.clock
        head = (f"AS_OF: {clock.as_of_str()} (you know nothing after this date) · MODE: {clock.mode} · "
                f"RUN: {run.kind} · YOUR ROLE: {role_name} · TOOL CALLS LEFT: {tool_calls_left}")
        lines = [head, self._mandate_line()]
        if run.kind != "construction":
            lines.append(self._portfolio_line())
        return "\n".join(lines)

    def _portfolio_line(self) -> str:
        """Current holdings vs targets, made by code (agents can't reason about what they can't see)."""
        state = getattr(self.tools.ctx, "state", None)
        led = getattr(state, "ledger", None)
        if led is None or led.nav() <= 0:
            return "PORTFOLIO: not invested yet"
        targets: dict[str, float] = {}
        try:
            from app.engine.portfolio import checkpoints
            marks = checkpoints(state.db, self.events.clock.mode)
            targets = marks[-1].targets if marks else {}
        except Exception:  # noqa: BLE001 - context only, never fail a run over it
            targets = {}
        w = led.weights()
        nav = led.nav()
        held = ", ".join(f"{t} {x:.1%}" + (f" (target {targets[t]:.1%})" if t in targets else "")
                         for t, x in sorted(w.items(), key=lambda kv: -kv[1]))
        return f"PORTFOLIO: £{nav:,.0f} · cash £{led.cash_gbp:,.0f} ({led.cash_gbp / nav:.1%}) · holdings: {held}"

    def _mandate_line(self) -> str:
        """The user's mandate in one line, made by code (agents never see it otherwise)."""
        state = getattr(self.tools.ctx, "state", None)
        m = getattr(state, "mandate", None)
        if m is None:
            return "MANDATE: unknown"
        stocks = (f"single stocks allowed up to {m.caps.stocks_total:.0%} in total, {m.caps.per_stock:.0%} each"
                  if m.caps.stocks_total > 0 else "NO single stocks (funds only)")
        g = m.goal
        return (f"MANDATE (v{m.version}): profile {m.profile} · shares {m.ranges.equity[0]:.0%}-{m.ranges.equity[1]:.0%} · "
                f"bonds {m.ranges.bond[0]:.0%}-{m.ranges.bond[1]:.0%} · cash at least {m.ranges.cash_min:.0%} · "
                f"max {m.caps.per_fund:.0%} per fund · {stocks} · exclusions: {', '.join(m.exclusions) or 'none'} · "
                f"£{g.starting_amount_gbp:,.0f} now + £{g.monthly_contribution_gbp:,.0f}/month · goal: {g.name}")

    def _capabilities(self, role_name: str, depth: int = 0) -> str:
        """Exact spawnable roles + callable tools (with arguments), generated from code so they're always right."""
        role = ROLES[role_name]
        implemented = set(getattr(self.tools, "_tools", {}))
        tools = [t for t in role.tools if t in implemented]
        spawnable = role.can_spawn if depth + 1 <= self.cfg["max_depth"] else []   # deepest level can't spawn
        lines = ["", "", "## What you can do (generated from code; anything else is refused)",
                 "Roles you may spawn: " + (", ".join(f"`{r}`" for r in spawnable) if spawnable
                                            else "none (do not spawn)"),
                 "Tools you may call (put arguments in `args_json` as a JSON object string):"]
        lines += [f"- `{t}`: {TOOL_DOCS.get(t, 'see tool result')}" for t in tools]
        return "\n".join(lines)

    def _compact(self, run: RunState, out: dict, alias_prefix: str) -> str:
        """Short, deterministic view of a tool result for the model. Full results stay in the events."""
        def alias(s: str) -> str:
            def rep(m: re.Match) -> str:
                real = m.group(0)
                for k, v in run.evidence_map.items():
                    if v == real:
                        return k
                kind = "calc" if real.startswith("calc:") else "ref"
                n = sum(1 for x in run.evidence_map if x.startswith(f"{kind}:{alias_prefix}:")) + 1
                k = f"{kind}:{alias_prefix}:{n}"
                run.evidence_map[k] = real
                return k
            return _CALC_ID.sub(rep, s)

        def trim(v):
            if isinstance(v, list):
                return [trim(x) for x in v[:LIST_ITEMS]] + ([f"... {len(v) - LIST_ITEMS} more"] if len(v) > LIST_ITEMS else [])
            if isinstance(v, dict):
                return {k: trim(x) for k, x in v.items()}
            return v

        text = alias(json.dumps(trim(out), sort_keys=True, default=str))
        return text if len(text) <= RESULT_CHARS else text[:RESULT_CHARS] + " ...(truncated)"

    def _real_ids(self, run: RunState, ids: list[str]) -> list[str]:
        """Aliases back to real ids, also inside composite ids such as `proposal:ref:lead.3:1`."""
        return [_ALIAS.sub(lambda m: run.evidence_map.get(m.group(0), m.group(0)), i) for i in ids]

    # ------------------------------------------------------------------ one LLM step (schema retry)
    async def _step(self, run: RunState, model: str, system: str, prompt: str, fake_ctx: dict) -> AgentStep:
        attempts = 1 + int(self.cfg.get("schema_retry", 1))
        last_error = ""
        for attempt in range(attempts):
            p = prompt if attempt == 0 else (
                f"{prompt}\n\nYOUR LAST REPLY DID NOT MATCH THE AgentStep SCHEMA: {last_error[:400]}\n"
                "Reply again with valid JSON only.")
            try:
                async with self._sem:
                    resp = await self.llm.generate(model=model, system=system, prompt=p, schema=AgentStep,
                                                   as_of=self.events.clock.as_of_str(),
                                                   fake_ctx={**fake_ctx, "attempt": attempt})
            except LLMSchemaError as e:
                run.tokens += e.tokens
                run.cost_usd += e.cost_usd
                run.llm_calls += 1
                last_error = e.error
                continue
            except (LLMError, LLMCacheMiss) as e:
                raise AgentFailed(f"{type(e).__name__}: {str(e)[:200]}") from e
            run.tokens += resp.tokens
            run.cost_usd += resp.cost_usd
            run.llm_calls += 1
            run.cached_calls += int(resp.cached)
            try:
                return AgentStep.model_validate_json(resp.text)
            except ValidationError as e:  # only possible for an old cache row
                last_error = str(e)[:400]
        raise AgentFailed(f"reply did not match the schema after {attempts} attempts: {last_error[:200]}")

    # ------------------------------------------------------------------ agent loop
    async def _run_agent(self, run: RunState, role_name: str, question: str, purpose: str,
                         parent_id: str | None, depth: int, path: str) -> AgentResult:
        role = ROLES[role_name]
        agent_id = f"{role_name}_{uuid.uuid4().hex[:6]}"
        run.agents_started += 1
        common = {"run_id": run.run_id, "agent_id": agent_id, "parent_agent_id": parent_id, "depth": depth,
                  "role": role_name}
        model = self.llm.model_for(role.deep)
        self.events.emit("agent.spawned", title=f"{role_name} started", purpose=purpose, status="started",
                         payload={"role": role_name, "model": model, "question": question}, **common)
        history: list[str] = [f"QUESTION: {question}", f"RUN TRIGGER: {run.kind}: {run.trigger_text}"]
        max_tools = self.cfg["max_tool_calls_per_agent"]
        tool_calls_used = children = 0
        final: AgentFinal | None = None
        system = role.prompt() + self._capabilities(role_name, depth)
        for step_idx in range(self.cfg["max_steps_per_agent"]):
            if self._over_budget(run, common):
                history.append("BUDGET: the run's token budget is used up.")
                break
            prompt = "\n\n".join([self._header(run, role_name, max_tools - tool_calls_used), *history])
            try:
                step = await self._step(run, model, system, prompt,
                                        {"role": role_name, "kind": run.kind, "step": step_idx, "depth": depth,
                                         "scratch": run.scratch})
            except AgentFailed as e:
                return self._fail(run, role_name, agent_id, str(e), common)
            if step.message:
                self.events.emit("agent.message", title=step.message[:120], payload={"text": step.message}, **common)
            if step.final:
                final = step.final
                break
            if self._over_budget(run, common):
                break
            for call in step.tool_calls:
                if tool_calls_used >= max_tools:
                    history.append(f"TOOL {call.tool}: REFUSED (max_tool_calls_per_agent)")
                    continue
                tool_calls_used += 1
                try:
                    args = json.loads(call.args_json or "{}")
                    if not isinstance(args, dict):
                        raise ValueError("args_json must be a JSON object")  # noqa: TRY004 - handled below
                except ValueError as e:
                    history.append(f"TOOL {call.tool}: BAD ARGS ({e}); args_json must be a JSON object string.")
                    continue
                out = await self.tools.call(call.tool, args, role=role_name, run=run, agent=common)
                history.append(f"TOOL {call.tool} {call.args_json} → "
                               f"{self._compact(run, out, f'{path}.{tool_calls_used}')}")
            child_tasks = []
            for req in step.spawns:
                self.events.emit("agent.spawn_requested", title=f"{role_name} asks for {req.role}",
                                 purpose=req.purpose, payload=req.model_dump(), **common)
                try:
                    self.check_spawn(run, role_name, req, depth, children)
                except SpawnDenied as e:
                    self.events.emit("agent.spawn_denied", title=f"Refused {req.role}: {e}", status="denied",
                                     payload={"role": req.role, "reason": str(e)}, **common)
                    history.append(f"SPAWN {req.role}: DENIED ({e}); conclude with what you have.")
                    continue
                children += 1
                child_tasks.append(self._run_agent(run, req.role, req.question, req.purpose, agent_id, depth + 1,
                                                   f"{path}.{req.role}{children}"))
            for child in await asyncio.gather(*child_tasks):
                if child.failed:
                    history.append(f"RESULT from {child.role}: FAILED ({child.failed}); record this as an uncertainty.")
                else:
                    history.append(f"RESULT from {child.role}: "
                                   f"{self._compact(run, child.final.model_dump() if child.final else {}, path)}")
        if final:
            for f in final.findings:
                f = f.model_copy(update={"evidence_ids": self._real_ids(run, f.evidence_ids)})
                run.findings.append(f)
                self.events.emit("finding", title=f.claim[:120], evidence_ids=f.evidence_ids,
                                 payload=f.model_dump(), **common)
            if role_name == "lead" and final.decision:
                d = final.decision.model_copy(update={"evidence_ids": self._real_ids(run, final.decision.evidence_ids)})
                run.decision = d
                self.events.emit("decision.made", title=f"Decision: {d.action}", evidence_ids=d.evidence_ids,
                                 payload=d.model_dump(), **common)
        self.events.emit("agent.status", title=f"{role_name} done", status="ok", payload={"status": "done"}, **common)
        return AgentResult(agent_id=agent_id, role=role_name, final=final)

    def _fail(self, run: RunState, role_name: str, agent_id: str, reason: str, common: dict) -> AgentResult:
        f = Finding(claim=f"{role_name} could not finish", confidence="low",
                    uncertainties=[f"agent {role_name} failed: {reason}"])
        run.findings.append(f)
        self.events.emit("finding", title=f.claim, payload=f.model_dump(), **common)
        self.events.emit("agent.status", title=f"{role_name} failed", status="failed",
                         payload={"status": "failed", "reason": reason}, **common)
        return AgentResult(agent_id=agent_id, role=role_name, failed=reason)

    # ------------------------------------------------------------------ run record
    def _save_summary(self, run: RunState, status: str, outcome: str | None, started_at: str,
                      finished_at: str | None) -> None:
        try:
            s = RunSummary(run_id=run.run_id, kind=run.kind, trigger_text=run.trigger_text,
                           as_of=self.events.clock.as_of_str(), status=status, outcome=outcome,
                           started_at=started_at, finished_at=finished_at, proposal_id=run.proposal_id)
        except ValidationError:
            return  # unknown kind: events still have everything
        self.events.db.put("runs", run.run_id, s.model_dump_json())


def _cli() -> None:  # pragma: no cover - manual live check
    import argparse

    from app.container import build_state

    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="construction")
    ap.add_argument("--trigger", default="User asked to build a portfolio")
    a = ap.parse_args()
    state = build_state()
    run = asyncio.run(state.supervisor.start(a.run, a.trigger))
    done = [e for e in state.events.history(run.run_id) if e.type == "run.completed"][-1]
    print(json.dumps({"run_id": run.run_id, "llm_mode": state.settings.llm_mode, **done.payload}, indent=2))
    for e in state.events.history(run.run_id):
        if e.type in ("agent.status", "budget.exceeded", "decision.made", "agent.spawn_denied"):
            print(f"  {e.type:18} {e.role or '':14} {e.title}")


if __name__ == "__main__":  # pragma: no cover
    _cli()

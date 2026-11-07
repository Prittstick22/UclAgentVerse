"""Supervisor: runs agent trees and enforces limits in code. Owner: Dev. Spec: docs/05-agent-system.md §3.

SCAFFOLD: limit enforcement + event emission + a minimal agent loop are wired so the app boots in
LLM_MODE=fake. The real behaviour (prompts, tools, plans, gate, proposals) is tracked in GitHub issues.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field

from pydantic import BaseModel

from app.agents.llm import LLM
from app.agents.roles import ROLES
from app.agents.schemas import AgentFinal, AgentStep, Decision, SpawnRequest
from app.agents.tools import ToolRegistry
from app.config import agents as agents_cfg
from app.core.events import EventBus


class SpawnDenied(Exception):
    pass


@dataclass
class RunState:
    run_id: str
    kind: str
    trigger_text: str
    agents_started: int = 0
    tokens: int = 0
    findings: list = field(default_factory=list)
    decision: Decision | None = None
    proposal_id: str | None = None
    scratch: dict = field(default_factory=dict)        # tool outputs shared within the run (e.g. built options)


class AgentResult(BaseModel):
    agent_id: str
    role: str
    final: AgentFinal | None = None
    denied: str | None = None


class Supervisor:
    def __init__(self, llm: LLM, tools: ToolRegistry, events: EventBus):
        self.llm = llm
        self.tools = tools
        self.events = events
        self.cfg = agents_cfg()
        self._sem = asyncio.Semaphore(self.cfg["max_parallel"])

    # ------------------------------------------------------------------ public
    async def start(self, kind: str, trigger_text: str, question: str | None = None) -> RunState:
        run = RunState(run_id=f"run_{uuid.uuid4().hex[:10]}", kind=kind, trigger_text=trigger_text)
        limits = {"max_depth": self.cfg["max_depth"], "max_agents": self._max_agents(kind),
                  "token_budget": self.cfg["run_token_budget"].get(kind, 100000)}
        self.events.emit("run.started", run_id=run.run_id, title=f"{kind.title()} run started", status="started",
                         trigger_kind=kind, trigger_text=trigger_text, payload={"kind": kind, "limits": limits})
        try:
            await asyncio.wait_for(
                self._run_agent(run, "lead", question or f"{kind}: {trigger_text}", "Lead this run", None, 0),
                timeout=self.cfg["run_wall_time_s"],
            )
        except asyncio.TimeoutError:
            self.events.emit("budget.exceeded", run_id=run.run_id, title="Run hit its wall-time limit",
                             payload={"limit": "wall_time_s", "value": self.cfg["run_wall_time_s"]})
        # TODO(#agents-gate): run app.agents.gate.run_gate on run.proposal_id before marking awaiting_approval
        outcome = run.decision.action if run.decision else "investigate_further"
        if kind == "construction" and run.proposal_id:
            outcome = "built"
        self.events.emit("run.completed", run_id=run.run_id, title=f"Run finished: {outcome}", status="ok",
                         trigger_kind=kind, payload={"outcome": outcome, "proposal_id": run.proposal_id,
                                                     "tokens": run.tokens})
        return run

    # ------------------------------------------------------------------ limits
    def _max_agents(self, kind: str) -> int:
        m = self.cfg["max_agents_per_run"]
        return m.get(kind, m.get("trigger", 8))

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
        if run.tokens >= self.cfg["run_token_budget"].get(run.kind, 100000):
            raise SpawnDenied("budget")

    # ------------------------------------------------------------------ agent loop
    async def _run_agent(self, run: RunState, role_name: str, question: str, purpose: str,
                         parent_id: str | None, depth: int) -> AgentResult:
        role = ROLES[role_name]
        agent_id = f"{role_name}_{uuid.uuid4().hex[:6]}"
        run.agents_started += 1
        common = {"run_id": run.run_id, "agent_id": agent_id, "parent_agent_id": parent_id, "depth": depth,
                  "role": role_name}
        model = self.llm.model_for(role.deep)
        self.events.emit("agent.spawned", title=f"{role_name} started", purpose=purpose, status="started",
                         payload={"role": role_name, "model": model, "question": question}, **common)
        history: list[str] = [f"QUESTION: {question}", f"RUN: {run.kind}: {run.trigger_text}"]
        tool_calls_used = children = 0
        final: AgentFinal | None = None
        for step_idx in range(self.cfg["max_steps_per_agent"]):
            async with self._sem:
                resp = await self.llm.generate(
                    model=model, system=role.prompt(), prompt="\n\n".join(history), schema=AgentStep,
                    as_of=self.events.clock.as_of_str(),
                    fake_ctx={"role": role_name, "kind": run.kind, "step": step_idx, "depth": depth,
                              "scratch": run.scratch},
                )
            run.tokens += resp.tokens
            step = AgentStep.model_validate_json(resp.text)
            if step.message:
                self.events.emit("agent.message", title=step.message[:120], payload={"text": step.message}, **common)
            for call in step.tool_calls:
                if tool_calls_used >= self.cfg["max_tool_calls_per_agent"]:
                    history.append(f"TOOL {call.tool}: REFUSED (max_tool_calls_per_agent)")
                    continue
                tool_calls_used += 1
                out = await self.tools.call(call.tool, json.loads(call.args_json or "{}"), role=role_name, run=run,
                                            agent=common)
                history.append(f"TOOL {call.tool} → {out}")
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
                child_tasks.append(self._run_agent(run, req.role, req.question, req.purpose, agent_id, depth + 1))
            for child in await asyncio.gather(*child_tasks):
                history.append(f"RESULT from {child.role}: {child.final.model_dump_json() if child.final else 'none'}")
            if step.final:
                final = step.final
                break
        if final:
            for f in final.findings:
                run.findings.append(f)
                self.events.emit("finding", title=f.claim[:120], evidence_ids=f.evidence_ids,
                                 payload=f.model_dump(), **common)
            if role_name == "lead" and final.decision:
                run.decision = final.decision
                self.events.emit("decision.made", title=f"Decision: {final.decision.action}",
                                 evidence_ids=final.decision.evidence_ids, payload=final.decision.model_dump(), **common)
        self.events.emit("agent.status", title=f"{role_name} done", status="ok", payload={"status": "done"}, **common)
        return AgentResult(agent_id=agent_id, role=role_name, final=final)

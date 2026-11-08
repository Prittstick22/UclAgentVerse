"""Read models for recorded and live run events."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import get_args

from app.agents.guard import scan
from app.core.clock import SimClock
from app.core.db import DB
from app.core.events import Event
from app.data.gateway import DataGateway
from app.schemas import AgentNode, Badge, Evidence, RunSummary, TriggerKind


def summarize(start: Event, completed: Event | None) -> RunSummary:
    kind = start.trigger_kind or start.payload.get("kind")
    status = "running"
    if completed:
        status = "failed" if completed.status == "failed" else "completed"
    return RunSummary(
        run_id=start.run_id,
        kind=kind if kind in get_args(TriggerKind) else "manual",
        trigger_text=start.trigger_text or start.payload.get("trigger_text") or "",
        as_of=start.as_of,
        status=status,
        started_at=start.ts_wall,
        finished_at=completed.ts_wall if completed else None,
        outcome=completed.payload.get("outcome") if completed else None,
        proposal_id=completed.payload.get("proposal_id") if completed else None,
    )


def agent_tree(events: list[Event], max_depth: int) -> list[AgentNode]:
    nodes: dict[str, AgentNode] = {}
    pending: dict[tuple[str | None, str], Event] = {}
    for event in events:
        actor = event.agent_id
        if event.type == "agent.spawn_requested":
            pending[actor, event.payload.get("role", "")] = event
        elif event.type == "agent.spawned" and actor:
            nodes[actor] = AgentNode(
                agent_id=actor, parent_agent_id=event.parent_agent_id, depth=event.depth or 0,
                role=event.role or event.payload.get("role", ""), model=event.payload.get("model") or "",
                question=event.payload.get("question") or "", purpose=event.purpose or "", status="running",
            )
        elif event.type == "agent.spawn_denied":
            # Refusal events identify the requester. Give the attempted spawn a separate leaf.
            role = event.payload.get("role") or ""
            request = pending.pop((actor, role), None)
            nodes[event.id] = AgentNode(
                agent_id=event.id, parent_agent_id=actor, depth=min((event.depth or 0) + 1, max_depth),
                role=role, model="", question=request.payload.get("question", "") if request else "",
                purpose=(request.purpose or request.payload.get("purpose") or "") if request else "",
                status="denied",
            )
        elif event.type == "agent.status" and actor in nodes:
            status = event.payload.get("status")
            if status in ("queued", "running", "done", "failed"):
                nodes[actor].status = status
            elif event.status == "failed":
                nodes[actor].status = "failed"
            elif event.status == "ok":
                nodes[actor].status = "done"
        elif event.type == "run.completed" and event.status == "failed":
            for node in nodes.values():
                if node.status == "running":
                    node.status = "failed"

    def add_badge(actors: Iterable[str | None], badge: Badge) -> None:
        for actor in actors:
            if actor in nodes and badge not in nodes[actor].badges:
                nodes[actor].badges.append(badge)

    sources: set[str] = set()
    for event in events:
        if event.type == "source.inspect":
            sources.update(event.evidence_ids)
            if source_id := event.payload.get("evidence_id"):
                sources.add(source_id)
            add_badge((event.agent_id,), "source_retrieved")

    lead = next((node.agent_id for node in nodes.values() if node.parent_agent_id is None), None)
    findings = [event for event in events if event.type == "finding"]
    for event in events:
        if event.type == "tool.result" and sources.intersection(event.evidence_ids):
            add_badge((event.agent_id,), "source_retrieved")
        if event.type == "gate.verdict" and (badge := _verdict_badge(event)):
            cited_ids = set(event.evidence_ids)
            actors = {f.agent_id for f in findings if cited_ids.intersection(f.evidence_ids)}
            add_badge(actors or (event.agent_id or lead,), badge)
    return list(nodes.values())


def _verdict_badge(event: Event) -> Badge | None:
    gate = event.payload.get("gate")
    verdict = event.payload.get("status")
    if gate == "evidence" and verdict == "pass":
        return "claim_supported"
    if gate == "numbers" and verdict in ("pass", "pass_with_flags"):
        return "calculation_recomputed"
    if gate == "critic" and verdict in ("pass_with_flags", "fail"):
        return "judgement_uncertain"
    return None


def _event_available_at(event: Event) -> datetime:
    if event.mode == "historical":
        return SimClock(event.as_of).now()
    return datetime.fromisoformat(event.ts_wall)


def find_evidence(gw: DataGateway, db: DB, evidence_id: str) -> Evidence | None:
    if evidence_id.startswith("calc:"):
        rows = db.execute(
            "SELECT json FROM events WHERE id = ? AND type = 'calc.result' AND mode = ?",
            (evidence_id.removeprefix("calc:"), gw.clock.mode),
        )
        if not rows:
            return None
        event = Event.model_validate_json(rows[0][0])
        available_at = _event_available_at(event)
        if available_at > gw.clock.now():
            return None
        return Evidence(id=evidence_id, kind="calc", title=event.title, source="engine",
                        available_at=available_at.isoformat(), data=event.payload)

    for news in gw.news(caller="api.evidence"):
        if news.id == evidence_id and datetime.fromisoformat(news.published_at) <= gw.clock.now():
            evidence = Evidence(id=news.id, kind="news", title=news.headline, source=news.source, url=news.url,
                                published_at=news.published_at, available_at=news.available_at,
                                excerpt=news.summary, data={"tickers": news.tickers})
            return _quarantine(evidence, gw, db, f"{news.headline} {news.summary}")

    for filing in gw.filings(caller="api.evidence"):
        passage = next((passage for passage in filing.passages if passage.id == evidence_id), None)
        if (filing.id == evidence_id or passage) and datetime.fromisoformat(filing.accepted_at) <= gw.clock.now():
            excerpt = passage.text if passage else None
            evidence = Evidence(
                id=evidence_id, kind="filing", title=f"{filing.company} {filing.form}",
                source="synthetic" if filing.synthetic else "sec_edgar", url=filing.url,
                published_at=filing.accepted_at, available_at=filing.available_at, excerpt=excerpt,
                data={"ticker": filing.ticker, "form": filing.form, "filing_id": filing.id},
            )
            return _quarantine(evidence, gw, db, excerpt or "")
    return None


def _quarantine(evidence: Evidence, gw: DataGateway, db: DB, text: str) -> Evidence:
    rows = db.execute(
        """SELECT json FROM events WHERE type = 'content.quarantined' AND mode = ?
           AND json_extract(json, '$.payload.evidence_id') = ?""",
        (gw.clock.mode, evidence.id),
    )
    if scan(text) or any(_event_available_at(Event.model_validate_json(row[0])) <= gw.clock.now() for row in rows):
        evidence.quarantined = True
        evidence.excerpt = None
    return evidence

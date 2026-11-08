"""Read models for recorded and live run events."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import get_args

from app.agents.guard import scan
from app.agents.schemas import InvestmentCase
from app.core.clock import SimClock
from app.core.db import DB
from app.core.events import Event
from app.data.gateway import DataGateway
from app.schemas import AgentNode, Badge, Evidence, Proposal, RunSummary, TriggerKind


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


def _retrieved_event(gw: DataGateway, db: DB, evidence_id: str) -> Event | None:
    """A saved artefact is visible only after a successful retrieval in this mode."""
    rows = db.execute(
        """SELECT json FROM events WHERE mode = ? AND type IN ('tool.result', 'source.inspect')
           AND EXISTS (SELECT 1 FROM json_each(events.json, '$.evidence_ids') WHERE value = ?)
           ORDER BY as_of, ts_wall, rowid""",
        (gw.clock.mode, evidence_id),
    )
    for (raw,) in rows:
        event = Event.model_validate_json(raw)
        if (event.status not in ("failed", "denied") and event.payload.get("ok") is not False
                and _event_available_at(event) <= gw.clock.now()):
            return event
    return None


def _saved_evidence(gw: DataGateway, db: DB, evidence_id: str) -> Evidence | None:
    if evidence_id == "catalogue":
        items = [item.model_dump() for item in gw.catalogue()]
        return Evidence(
            id=evidence_id, kind="catalogue", title="Eligible investment catalogue", source="project_catalogue",
            available_at=gw.clock.now().isoformat(),
            excerpt="\n".join(f"{item['ticker']}: {item['name']} ({item['asset_class']}, {item['sleeve']})" for item in items),
            data={"items": items},
        )

    event = _retrieved_event(gw, db, evidence_id)
    if event is None:
        return None
    available_at = _event_available_at(event).isoformat()
    if evidence_id.startswith("case:"):
        ticker, separator, version = evidence_id.removeprefix("case:").rpartition(":v")
        if not separator or not version.isdigit():
            return None
        raw = db.get("case_versions", f"{gw.clock.mode}:{evidence_id}") or db.get("cases", ticker)
        if not raw:
            return None
        case = InvestmentCase.model_validate_json(raw)
        # Older recordings store only the latest version. Never substitute it for another citation.
        if case.ticker != ticker or case.version != int(version):
            return None
        details = [case.purpose]
        details.extend(f"Assumption: {text}" for text in case.assumptions)
        details.extend(f"Reconsider if: {text}" for text in case.reconsider_if)
        return _quarantine(Evidence(
            id=evidence_id, kind="case", title=f"Investment case for {ticker} · version {case.version}",
            source="agent_investment_case", available_at=available_at, excerpt="\n".join(details), data=case.model_dump(),
        ), gw, db, "\n".join(details))
    if evidence_id.startswith("proposal:"):
        raw = db.get("proposals", evidence_id.removeprefix("proposal:"))
        if not raw:
            return None
        proposal = Proposal.model_validate_json(raw)
        if proposal.as_of > gw.clock.as_of_str():
            return None
        # Approval status/selection/gates may have changed after creation; this is the original proposal content.
        return Evidence(
            id=evidence_id, kind="proposal", title=proposal.decision_card.headline, source="agent_proposal",
            available_at=available_at,
            excerpt=f"{proposal.decision_card.body}\n{proposal.decision_card.risk_warning}",
            data={"proposal_id": proposal.id, "run_id": proposal.run_id,
                  "options": [option.model_dump() for option in proposal.options]},
        )
    if evidence_id.startswith("earnings:"):
        ticker = evidence_id.removeprefix("earnings:")
        dates = sorted({str(row["date"]) for row in gw.earnings([ticker], caller="api.evidence")
                        if str(row["date"])[:10] <= event.as_of})[-4:]
        if not dates:
            return None
        return Evidence(
            id=evidence_id, kind="earnings", title=f"Past earnings dates for {ticker}",
            source="snapshot_earnings_calendar", available_at=available_at,
            excerpt="\n".join(dates), data={"ticker": ticker, "past_dates": dates},
        )
    if evidence_id.startswith("web:"):
        # tool.result has only a summary; source.inspect retains the actual source links.
        rows = db.execute(
            """SELECT json FROM events WHERE mode = ? AND type = 'source.inspect'
               AND json_extract(json, '$.payload.evidence_id') = ? ORDER BY ts_wall, rowid""",
            (gw.clock.mode, evidence_id),
        )
        for (raw,) in rows:
            source = Event.model_validate_json(raw)
            if _event_available_at(source) > gw.clock.now():
                continue
            links = source.payload.get("sources", [])
            return _quarantine(Evidence(
                id=evidence_id, kind="web", title=source.payload.get("title") or source.title,
                source=source.payload.get("source") or "google_search",
                available_at=_event_available_at(source).isoformat(),
                excerpt="\n".join(f"{link.get('title', '')}: {link.get('url', '')}" for link in links),
                url=links[0].get("url") if links else None, data={"sources": links},
            ), gw, db, " ".join(str(link) for link in links))
    return None


def find_evidence(gw: DataGateway, db: DB, evidence_id: str) -> Evidence | None:
    if evidence_id == "catalogue" or evidence_id.startswith(("case:", "proposal:", "earnings:", "web:")):
        return _saved_evidence(gw, db, evidence_id)
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

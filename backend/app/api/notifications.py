"""Portfolio activity and the notification inbox, projected from the event log."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from threading import Lock
from typing import TYPE_CHECKING

from app.core.events import Event
from app.schemas import Counters, HomeStatus, Notification, Proposal

if TYPE_CHECKING:
    from app.container import AppState


@dataclass
class Activity:
    status: HomeStatus
    counters: Counters
    last_review_date: str | None
    items: dict[str, Notification]


class PortfolioActivity:
    def __init__(self, state: AppState):
        self.state = state
        self._notification_lock = Lock()
        state.events.listen(self._on_event)

    def _proposal(self, proposal_id: str) -> Proposal | None:
        raw = self.state.db.get("proposals", proposal_id)
        return Proposal.model_validate_json(raw) if raw else self.state.proposals.get(proposal_id)

    def _decision(self, event: Event) -> Notification | None:
        proposal_id = event.payload.get("proposal_id")
        if event.type == "notification.created":
            notification_id = event.payload.get("notification_id", "")
            proposal_id = notification_id.removeprefix("decision:")
        if not proposal_id:
            return None
        proposal = self._proposal(proposal_id)
        if proposal and proposal.as_of > event.as_of:
            proposal = None
        if event.type == "proposal.created":
            status = event.payload.get("status")
            if status is None and proposal and event.as_of == self.state.clock.as_of_str():
                status = proposal.status
            if status != "awaiting_approval":
                return None
        elif event.payload.get("by") == "batch_policy":
            return None
        card = proposal.decision_card if proposal else None
        return Notification(
            id=f"decision:{proposal_id}",
            kind="decision",
            title=card.headline if card else event.title,
            body=card.body if card else "A paper portfolio proposal is ready for your decision.",
            proposal_id=proposal_id,
            run_id=event.run_id,
            created_at=event.ts_wall,
        )

    def _signal(self, notification_id: str, kind: str, title: str, run_id: str | None = None) -> None:
        state = self.state
        clock = state.events.clock
        with self._notification_lock:
            exists = state.db.execute(
                """SELECT 1 FROM events WHERE type='notification.created' AND mode=? AND as_of<=?
                   AND json_extract(json, '$.payload.notification_id')=? LIMIT 1""",
                (clock.mode, clock.as_of_str(), notification_id),
            )
            if not exists:
                state.events.emit(
                    "notification.created",
                    title=title,
                    run_id=run_id,
                    payload={"notification_id": notification_id, "kind": kind},
                )

    def _on_event(self, event: Event) -> None:
        if event.type == "clock.tick":
            self._record_coverage()
        elif event.type in ("proposal.created", "approval.requested"):
            decision = self._decision(event)
            if decision:
                self._signal(decision.id, decision.kind, decision.title, decision.run_id)

    def _stale_quotes(self) -> dict[str, str | None]:
        held = sorted(t for t, position in self.state.ledger.positions.items() if position.units > 0)
        if not held:
            return {}
        freshness = self.state.gw.freshness()
        return {
            t: freshness[t].last_date if t in freshness else None
            for t in held
            if t not in freshness or freshness[t].stale
        }

    def read(self, notification_id: str, mode: str) -> None:
        self.state.db.put(f"notification_reads:{mode}", notification_id, "true")

    def _record_coverage(self) -> bool:
        stale_quotes = self._stale_quotes()
        for ticker, last_date in stale_quotes.items():
            fingerprint = sha256(f"{ticker}:{last_date}".encode()).hexdigest()[:16]
            message = (
                f"The last available price for {ticker} is from {last_date}."
                if last_date
                else f"No price is available for {ticker}."
            )
            self._signal(f"coverage:{fingerprint}", "coverage", message)
        return bool(stale_quotes)

    def snapshot(self, mode: str) -> Activity:
        state = self.state
        degraded = mode == state.clock.mode and self._record_coverage()
        rows = state.db.execute(
            """SELECT json FROM events WHERE mode=? AND as_of<=? AND type IN
               ('run.started', 'run.completed', 'decision.made', 'proposal.created', 'approval.requested',
                'approval.decided', 'order.filled', 'notification.created') ORDER BY as_of, rowid""",
            (mode, state.clock.as_of_str()),
        )
        read_ids = {key for key, _ in state.db.list(f"notification_reads:{mode}")}
        items: dict[str, Notification] = {}
        running: dict[str, str | None] = {}
        reviews: dict[str, str] = {}
        checks: set[str] = set()
        pending: set[str] = set()
        resolved: set[str] = set()
        reasons: dict[str, str] = {}
        adjustment_runs: dict[str, str] = {}
        adjusted: set[str] = set()

        for (row,) in rows:
            event = Event.model_validate_json(row)
            run_id = event.run_id
            payload = event.payload
            proposal_id = payload.get("proposal_id")
            if event.type == "run.started" and run_id:
                running[run_id] = event.trigger_kind or payload.get("kind")
            elif event.type == "decision.made" and run_id and payload.get("action") == "maintain":
                reasons[run_id] = payload.get("reason") or "No change was needed."
            elif event.type == "run.completed" and run_id:
                started_kind = running.pop(run_id, None)
                kind = event.trigger_kind or payload.get("kind") or started_kind
                if event.status == "failed" or kind in ("construction", "chat", "retrospective"):
                    continue
                if kind == "review":
                    reviews[run_id] = event.as_of
                else:
                    checks.add(run_id)
                if payload.get("outcome") == "maintain":
                    notification = Notification(
                        id=f"digest:{run_id}",
                        kind="digest",
                        title="Portfolio unchanged",
                        body=reasons.get(run_id, "No change was needed."),
                        run_id=run_id,
                        created_at=event.ts_wall,
                    )
                    items.setdefault(notification.id, notification)
            elif (
                event.type in ("proposal.created", "approval.requested")
                or event.type == "notification.created"
                and payload.get("kind") == "decision"
            ):
                if (
                    event.type == "proposal.created"
                    and payload.get("kind") == "adjustment"
                    and run_id
                    and proposal_id
                ):
                    adjustment_runs[run_id] = proposal_id
                notification = self._decision(event)
                if notification:
                    items.setdefault(notification.id, notification)
                    if notification.proposal_id and notification.proposal_id not in resolved:
                        pending.add(notification.proposal_id)
            elif event.type == "approval.decided" and proposal_id:
                pending.discard(proposal_id)
                resolved.add(proposal_id)
            elif event.type == "order.filled":
                run_proposal = adjustment_runs.get(run_id) if run_id else None
                adjustment_id = run_proposal if not proposal_id or proposal_id == run_proposal else None
                if proposal_id and not adjustment_id:
                    proposal = self._proposal(proposal_id)
                    if proposal and proposal.kind == "adjustment" and proposal.as_of <= event.as_of:
                        adjustment_id = proposal_id
                if adjustment_id:
                    adjusted.add(adjustment_id)
                if filled_id := proposal_id or adjustment_id:
                    pending.discard(filled_id)
                    resolved.add(filled_id)
            elif event.type == "notification.created" and payload.get("kind") == "coverage":
                notification_id = payload["notification_id"]
                items.setdefault(
                    notification_id,
                    Notification(
                        id=notification_id,
                        kind="coverage",
                        title="Price coverage degraded",
                        body=event.title,
                        created_at=event.ts_wall,
                    ),
                )

        status: HomeStatus = "monitoring_normally"
        if running:
            status = "investigating"
        elif pending:
            status = "awaiting_approval"
        elif degraded:
            status = "monitoring_degraded"
        counters = Counters(
            reviews=len(reviews),
            checks=len(checks),
            decisions_asked=sum(item.kind == "decision" for item in items.values()),
            adjustments=len(adjusted),
        )
        for item in items.values():
            item.read = item.id in read_ids
        return Activity(status, counters, max(reviews.values(), default=None), items)

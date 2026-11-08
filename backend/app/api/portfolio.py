"""Portfolio projections over paper-ledger checkpoints and recorded events."""
from __future__ import annotations

from collections import defaultdict
from copy import copy

import pandas as pd

from app.agents.schemas import InvestmentCase
from app.config import params
from app.container import AppState
from app.core.events import Event
from app.engine import portfolio as engine
from app.engine.ledger import Ledger
from app.schemas import (
    Counters,
    Holding,
    Mode,
    OrderChange,
    PnlPeriod,
    Portfolio,
    PortfolioHistory,
    PortfolioPnl,
    PortfolioPoint,
    PortfolioRebalances,
    Proposal,
    Rebalance,
)


class PortfolioView:
    def __init__(self, state: AppState, mode: Mode | None):
        self.state = state
        self.mode = mode or state.clock.mode
        self.as_of = state.clock.as_of_str()
        checkpoints = engine.checkpoints(state.db, self.mode)
        self.recorded = [mark for mark in checkpoints if mark.date <= self.as_of]
        self.latest = self.recorded[-1] if self.recorded else None
        self.can_use_ledger = self.mode == state.clock.mode and len(self.recorded) == len(checkpoints)

    def _current(self) -> engine.LedgerCheckpoint:
        ledger = self.state.ledger
        if self.can_use_ledger and (ledger.positions or ledger.contributions_gbp):
            marked = copy(ledger)
            marked.last_prices = ledger.last_prices.copy()
            visible = self.state.gw.prices(end=self.as_of, caller="api.portfolio")
            if not visible.empty:
                marked.mark_to_market(visible.iloc[-1].to_dict())
            targets = self.latest.targets if self.latest else {}
            return engine.capture(marked, self.as_of, targets)
        return self.latest or engine.capture(Ledger(catalogue={}), self.as_of)

    def _proposal(self, proposal_id: str | None) -> Proposal | None:
        if not proposal_id:
            return None
        proposal = self.state.proposals.get(proposal_id)
        if proposal is None and (raw := self.state.db.get("proposals", proposal_id)):
            proposal = Proposal.model_validate_json(raw)
        return proposal if proposal and proposal.as_of <= self.as_of else None

    def events(self, *types: str) -> list[Event]:
        placeholders = ",".join("?" for _ in types)
        rows = self.state.db.execute(
            f"SELECT json FROM events WHERE mode=? AND as_of<=? AND type IN ({placeholders}) "
            "ORDER BY as_of, ts_wall, rowid",
            (self.mode, self.as_of, *types),
        )
        return [Event.model_validate_json(row[0]) for row in rows]

    def _points(self) -> dict[str, PortfolioPoint]:
        # Older recordings have a tick rather than a checkpoint. Preserve their NAV and weights.
        points = {
            event.as_of: PortfolioPoint(
                date=event.as_of, nav_gbp=event.payload["nav_gbp"], weights=event.payload.get("weights", {}),
                contributions_gbp=event.payload.get("contributions_gbp"),
            )
            for event in self.events("clock.tick") if event.payload.get("nav_gbp") is not None
        }
        points.update({mark.date: PortfolioPoint.model_validate(mark, from_attributes=True)
                       for mark in self.recorded})
        return points

    def history(self, start: str | None, end: str | None) -> PortfolioHistory:
        points = self._points()
        return PortfolioHistory(points=[points[day] for day in sorted(points)
                                        if (start is None or day >= start) and (end is None or day <= end)])

    def pnl(self, period: PnlPeriod) -> PortfolioPnl:
        names = {ticker: inst.name for ticker, inst in self.state.ledger.catalogue.items()}
        current = self._current()
        if not current.positions and not self.latest and any(point.weights for point in self._points().values()):
            raise engine.PortfolioDataUnavailable("Recorded ticks do not contain the ledger's cost basis or realised P&L")
        rows = engine.pnl_rows(current, self.recorded, period, names, as_of=self.as_of)
        return PortfolioPnl(period=period, rows=rows, total_pnl_gbp=round(sum(row.pnl_gbp for row in rows), 2))

    def _cases(self, tickers: list[str]) -> dict[str, InvestmentCase]:
        cases = {
            ticker: InvestmentCase.model_validate_json(raw) for ticker in tickers
            if (raw := self.state.db.get("cases", ticker))
        }
        if not cases:
            return {}
        evidence = {ref for event in self.events("tool.result") for ref in event.evidence_ids}
        # The current case store has no date or mode. A tool event proves the visible version.
        return {ticker: case for ticker, case in cases.items() if f"case:{ticker}:v{case.version}" in evidence}

    def summary(self) -> Portfolio:
        mark = self._current()
        if not mark.contributions_gbp and not self.latest and any(point.nav_gbp for point in self._points().values()):
            raise engine.PortfolioDataUnavailable("Recorded ticks contain history but no complete ledger snapshot")
        events = self.events("run.started", "run.completed", "approval.requested", "approval.decided", "order.filled")
        approved = next((e for e in reversed(events) if e.type == "approval.decided"
                         and e.payload.get("decision") in ("approve", "approved")), None)
        proposal = self._proposal(approved.payload.get("proposal_id")) if approved else None
        targets = mark.targets
        if proposal:
            selected = approved.payload.get("option", proposal.selected)
            option = next((option for option in proposal.options if option.label == selected), None)
            if option:
                targets = {holding.ticker: holding.weight for holding in option.holdings}
        tickers = list(mark.weights)
        cases = self._cases(tickers)
        quotes = self.state.gw.last_quote_dates(tickers, end=mark.date) if tickers else {}
        stale_limit = params()["risk"]["stale_after_days"]
        holdings = []
        for ticker in sorted(tickers):
            row = mark.positions[ticker]
            inst = self.state.ledger.catalogue[ticker]
            case = cases.get(ticker)
            quote_date = quotes.get(ticker)
            stale = not quote_date or len(pd.bdate_range(quote_date, self.as_of, inclusive="right")) > stale_limit
            holdings.append(Holding(
                **row.model_dump(), name=inst.name, asset_class=inst.asset_class,
                price_gbp=mark.prices.get(ticker, 0.0), weight=mark.weights[ticker],
                target_weight=targets.get(ticker, 0.0), price_as_of=quote_date or "", stale=stale,
                purpose=case.purpose if case else None, case_id=case.case_id if case else None,
            ))
        started = {e.run_id for e in events if e.type == "run.started"}
        completed = [e for e in events if e.type == "run.completed"]
        reviews = [e for e in completed if e.trigger_kind == "review" and e.status != "failed"]
        requested = {e.payload.get("proposal_id") for e in events if e.type == "approval.requested"}
        decisions = {e.payload.get("proposal_id") for e in events if e.type == "approval.decided"}
        status = "monitoring_normally"
        if started - {e.run_id for e in completed}:
            status = "investigating"
        elif requested - decisions - {None}:
            status = "awaiting_approval"
        elif any(holding.stale for holding in holdings):
            status = "monitoring_degraded"
        last_review = reviews[-1].as_of if reviews else None
        next_review = None
        if last_review:
            days = self.state.gw.trading_days(last_review)
            interval = self.state.mandate.review_every_n_days
            if 0 < interval < len(days):
                next_review = days[interval].date().isoformat()
        returns = [point for point in self.recorded if point.date < mark.date] + [mark]
        return Portfolio(
            mode=self.mode, as_of=self.as_of, nav_gbp=round(mark.nav_gbp, 2), cash_gbp=round(mark.cash_gbp, 2),
            invested_gbp=round(mark.nav_gbp - mark.cash_gbp, 2), contributions_gbp=mark.contributions_gbp,
            total_return=engine.total_return(returns), status=status, last_review_date=last_review,
            next_review_date=next_review, holdings=holdings, counters=Counters(
                reviews=len(reviews), checks=sum(e.trigger_kind not in ("construction", "chat", "retrospective")
                                                 for e in completed), decisions_asked=len(requested - {None}),
                adjustments=len({e.run_id for e in events if e.type == "order.filled" and e.run_id}),
            ),
        )

    def rebalances(self, limit: int) -> PortfolioRebalances:
        events = self.events("run.started", "approval.decided", "order.filled")
        runs = {e.run_id: e for e in events if e.type == "run.started"}
        approval_by_run: dict[str, str | None] = {}
        approval_by_proposal: dict[str, str] = {}
        fills: dict[tuple[str, str, str | None], list[Event]] = defaultdict(list)
        for event in events:
            proposal_id = event.payload.get("proposal_id")
            if event.type == "approval.decided" and event.payload.get("decision") in ("approve", "approved"):
                proposal = self._proposal(proposal_id) if not event.run_id else None
                run_id = event.run_id or (proposal.run_id if proposal else None)
                if run_id:
                    approval_by_run[run_id] = proposal_id
                    if proposal_id:
                        approval_by_proposal[proposal_id] = run_id
            elif event.type == "order.filled":
                if proposal_id:
                    run_id = approval_by_proposal.get(proposal_id)
                    if event.run_id and event.run_id != run_id:
                        continue
                else:
                    run_id = event.run_id if event.run_id in approval_by_run else None
                    proposal_id = approval_by_run.get(run_id) if run_id else None
                if run_id:
                    fills[event.payload.get("date", event.as_of), run_id, proposal_id].append(event)

        points = self._points()
        days = sorted(points)
        result = []
        for (day, run_id, proposal_id), events in reversed(list(fills.items())):
            run = runs.get(run_id)
            proposal = self._proposal(proposal_id)
            if proposal and proposal.as_of > day:
                proposal = None
            planned = {change.ticker: change for change in proposal.decision_card.changes} if proposal else {}
            previous = next((points[d] for d in reversed(days) if d < day), None)
            after = points.get(day)
            changes = []
            cost = 0.0
            for event in events:
                payload = event.payload
                ticker = payload["ticker"]
                if "from_weight" in payload and "to_weight" in payload:
                    before_weight, after_weight = payload["from_weight"], payload["to_weight"]
                elif previous is not None and after is not None:
                    before_weight, after_weight = previous.weights.get(ticker, 0.0), after.weights.get(ticker, 0.0)
                elif ticker in planned:
                    before_weight, after_weight = planned[ticker].from_weight, planned[ticker].to_weight
                else:
                    break  # This recording cannot support a complete rebalance without allocation data.
                changes.append(OrderChange(ticker=ticker, action=payload["action"], amount_gbp=payload["amount_gbp"],
                                           from_weight=before_weight, to_weight=after_weight))
                cost += payload["cost_gbp"]
            if len(changes) == len(events):
                result.append(Rebalance(date=day, run_id=run_id, trigger_kind=(run.trigger_kind if run else None)
                                        or "manual", trigger_text=(run.trigger_text if run else None) or "",
                                        changes=changes, cost_gbp=round(cost, 2)))
                if len(result) == limit:
                    break
        return PortfolioRebalances(items=result)

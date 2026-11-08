"""Shared API models. CONTRACT FILE: mirror of docs/04-api-contracts.md §1 and frontend/src/lib/types.ts."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["historical", "live"]
AssetClass = Literal["equity", "bond", "cash", "commodity"]
ProfileName = Literal["cautious", "balanced", "growth", "adventurous"]
HomeStatus = Literal["monitoring_normally", "investigating", "awaiting_approval", "monitoring_degraded"]
TriggerKind = Literal[
    "construction", "review", "drift", "cap_breach", "price_move", "nav_drop", "news",
    "corr_regime", "chat", "retrospective", "manual",
]
GateName = Literal["injection_guard", "evidence", "numbers", "mandate", "critic", "compliance", "qa", "revalidation"]
GateStatus = Literal["pending", "pass", "pass_with_flags", "fail", "skipped"]
Badge = Literal["source_retrieved", "claim_supported", "relationship_uncertain", "calculation_recomputed", "judgement_uncertain"]


class Instrument(BaseModel):
    ticker: str
    name: str
    isin: str | None = None
    asset_class: AssetClass
    sleeve: str
    currency: Literal["GBP", "USD", "EUR"]
    quote_unit: Literal["GBP", "GBX", "USD"]
    ocf: float
    accumulating: bool
    kind: Literal["etf", "stock"]
    eligible: bool = True
    verified: bool = False
    data_source: str = "unknown"


class Goal(BaseModel):
    name: str = "Long-term savings"
    target_date: str = "2040-01-01"
    starting_amount_gbp: float = 10000
    monthly_contribution_gbp: float = 200


class Ranges(BaseModel):
    equity: tuple[float, float]
    bond: tuple[float, float]
    cash_min: float


class Caps(BaseModel):
    per_fund: float
    per_stock: float
    stocks_total: float


class Triggers(BaseModel):
    drift_pp: float = 0.05
    price_move_day: float = 0.05
    price_move_since_review: float = 0.10
    nav_drop: float = 0.05
    news_relevance: float = 0.7


class Approval(BaseModel):
    require_user_approval: bool = True
    batch_auto_approve_turnover_max: float = 0.10


class Mandate(BaseModel):
    version: int = 1
    profile: ProfileName
    goal: Goal = Field(default_factory=Goal)
    ranges: Ranges
    caps: Caps
    exclusions: list[str] = Field(default_factory=list)
    review_every_n_days: int = 10
    triggers: Triggers = Field(default_factory=Triggers)
    approval: Approval = Field(default_factory=Approval)


class ProfileResult(BaseModel):
    name: ProfileName
    tolerance_score: float
    capacity_score: float
    conflict: bool
    follow_up_question: str | None
    explanation: str


class DemoProfile(BaseModel):
    name: str
    age: int
    story: str
    profile: ProfileName
    goal: Goal
    answers: dict[str, str]
    synthetic: Literal[True]
    result: ProfileResult
    mandate: Mandate


class Holding(BaseModel):
    ticker: str
    name: str
    asset_class: AssetClass
    units: float
    price_gbp: float
    value_gbp: float
    weight: float
    target_weight: float
    cost_basis_gbp: float
    unrealised_pnl_gbp: float
    unrealised_pnl_pct: float
    realised_pnl_gbp: float
    contribution_to_return: float
    price_as_of: str
    stale: bool = False
    purpose: str | None = None
    case_id: str | None = None


class Counters(BaseModel):
    reviews: int = 0
    checks: int = 0
    decisions_asked: int = 0
    adjustments: int = 0


class Notification(BaseModel):
    id: str
    kind: Literal["decision", "digest", "coverage"]
    title: str
    body: str
    proposal_id: str | None = None
    run_id: str | None = None
    created_at: str
    read: bool = False


class Notifications(BaseModel):
    items: list[Notification]


class Portfolio(BaseModel):
    mode: Mode
    as_of: str
    nav_gbp: float
    cash_gbp: float
    invested_gbp: float
    contributions_gbp: float
    total_return: float
    status: HomeStatus = "monitoring_normally"
    last_review_date: str | None = None
    next_review_date: str | None = None
    holdings: list[Holding] = Field(default_factory=list)
    counters: Counters = Field(default_factory=Counters)


PnlPeriod = Literal["since_purchase", "1m", "3m", "ytd", "sim_year"]


class PortfolioPoint(BaseModel):
    date: str
    nav_gbp: float
    weights: dict[str, float]
    contributions_gbp: float | None


class PortfolioHistory(BaseModel):
    points: list[PortfolioPoint]


class PnlRow(BaseModel):
    ticker: str
    name: str
    pnl_gbp: float
    pnl_pct: float
    realised_gbp: float
    unrealised_gbp: float
    contribution_to_return: float


class PortfolioPnl(BaseModel):
    period: PnlPeriod
    rows: list[PnlRow]
    total_pnl_gbp: float


class Evidence(BaseModel):
    id: str
    kind: Literal["price", "news", "filing", "calc", "catalogue", "web"]
    title: str
    source: str
    url: str | None = None
    published_at: str | None = None
    available_at: str
    excerpt: str | None = None
    data: dict | None = None
    quarantined: bool = False


class ProposedHolding(BaseModel):
    ticker: str
    weight: float
    purpose: str = ""
    why_not_alternatives: str = ""
    evidence_ids: list[str] = Field(default_factory=list)


class OptionStats(BaseModel):
    vol_annual: float
    ocf_weighted: float
    turnover: float
    cost_gbp: float
    max_drawdown_backtest: float | None = None


class PortfolioOption(BaseModel):
    label: Literal["recommended", "lower_cost", "lower_risk", "current", "proposed"]
    holdings: list[ProposedHolding]
    cash_weight: float = 0.0
    stats: OptionStats


class GateResult(BaseModel):
    gate: GateName
    status: GateStatus
    issues: list[str] = Field(default_factory=list)
    agent_id: str | None = None


class OrderChange(BaseModel):
    ticker: str
    action: Literal["buy", "sell"]
    amount_gbp: float
    from_weight: float
    to_weight: float


class Rebalance(BaseModel):
    date: str
    run_id: str
    trigger_kind: TriggerKind
    trigger_text: str
    changes: list[OrderChange]
    cost_gbp: float


class PortfolioRebalances(BaseModel):
    items: list[Rebalance]


class DecisionCard(BaseModel):
    headline: str
    body: str
    changes: list[OrderChange] = Field(default_factory=list)
    risk_warning: str = "The value of investments can go down as well as up. Paper portfolio, not personal advice."
    simulated: bool = True


class Proposal(BaseModel):
    id: str
    run_id: str
    kind: Literal["construction", "adjustment"]
    as_of: str
    created_at: str
    options: list[PortfolioOption]
    selected: str = "recommended"
    gates: list[GateResult] = Field(default_factory=list)
    decision_card: DecisionCard
    uncertainties: list[str] = Field(default_factory=list)
    status: Literal["draft", "awaiting_approval", "approved", "declined", "blocked", "expired", "executed"] = "draft"


class AgentNode(BaseModel):
    agent_id: str
    parent_agent_id: str | None
    depth: int
    role: str
    model: str
    question: str
    purpose: str
    status: Literal["queued", "running", "done", "failed", "denied"] = "queued"
    badges: list[Badge] = Field(default_factory=list)


class RunSummary(BaseModel):
    run_id: str
    kind: TriggerKind
    trigger_text: str
    as_of: str
    status: Literal["running", "completed", "failed", "cancelled"] = "running"
    outcome: Literal["maintain", "adjust", "investigate_further", "built", "answered"] | None = None
    started_at: str
    finished_at: str | None = None
    agents: list[AgentNode] = Field(default_factory=list)
    proposal_id: str | None = None


class ApiError(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)

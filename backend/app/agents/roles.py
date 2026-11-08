"""Role registry: model tier, tools, spawn permissions, prompt file. Owner: Dev. Spec: docs/05-agent-system.md §4–5."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent / "prompts"

READ_TOOLS = ["get_catalogue", "get_prices", "correlation_lattice", "risk_stats", "search_news", "search_filings",
              "get_investment_case"]


@dataclass(frozen=True)
class Role:
    name: str
    deep: bool                                  # True = GEMINI_MODEL_DEEP (Argon), False = fast (Flash)
    tools: list[str] = field(default_factory=list)
    can_spawn: list[str] = field(default_factory=list)
    allow_deep_override: bool = False
    group: str = "research"                     # research | assurance | learning | interface

    def prompt(self) -> str:
        f = PROMPTS / f"{self.name}.md"
        base = (PROMPTS / "_base.md").read_text(encoding="utf-8")
        return base + "\n\n" + (f.read_text(encoding="utf-8") if f.exists() else f"You are the {self.name} agent.")


TOOL_DOCS: dict[str, str] = {
    "get_catalogue": "{} -> eligible instruments (ticker, name, asset_class, sleeve, ocf, kind). Evidence id `catalogue`.",
    "get_prices": '{"tickers": ["VWRP.LSE"], "start"?: "YYYY-MM-DD"} -> last price, 1m/3m/1y return, vol per ticker.',
    "correlation_lattice": '{"tickers"?: [..], "lookback"?: 504} -> average correlation + plain-English callouts.',
    "risk_stats": '{"weights": {"VWRP.LSE": 0.5, ...}} or {"option": "recommended"} -> vol, max drawdown, beta, '
                  'concentration.',
    "backtest": '{"weights": {...}} or {"option": "lower_risk"}, "rebalance"?: "quarterly" -> past behaviour '
                '(simulated, not a forecast).',
    "forecast": '{"tickers": [..]} -> 2-week estimate per ticker (estimate, not a promise).',
    "build_options": '{"tickers"?: [..shortlist..]} -> 3 optimiser options (recommended, lower_cost, lower_risk). '
                     'Omit tickers to use every eligible fund. If it says infeasible, call it again without tickers.',
    "cost_turnover": '{"option": "recommended"} or {"weights": {...}} -> trades, cost in £, turnover.',
    "check_proposal": '{"option": "recommended"} or {"weights": {...}, "cash_weight": 0.03} -> mandate check.',
    "exposure": '{"entity": "NVDA.US", "option"?: "recommended"} -> look-through ownership exposure.',
    "search_news": '{"tickers": ["AAPL.US"], "since"?: "YYYY-MM-DD"} -> dated headlines up to today (ids = evidence).',
    "search_filings": '{"ticker": "NVDA.US", "query"?: "supplier risk"} -> SEC filing passages (ids = evidence).',
    "earnings_calendar": '{"tickers": ["AAPL.US"]} -> past earnings dates (up to today only).',
    "get_investment_case": '{"ticker": "VWRP.LSE"} -> the saved case, if any.',
    "save_investment_case": '{"cases": [{"ticker": "VWRP.LSE", "purpose": "...", "evidence_ids": [..], '
                            '"assumptions": [..], "reconsider_if": [..]}, ...]} -> saves ALL cases in ONE call.',
    "propose_adjustment": '{"option": "recommended", "why_not": {"VWRP.LSE": "why this rather than the '
                          'alternative"}} -> creates the proposal for the user to approve. Purposes and evidence come '
                          'from the saved investment cases.',
    "web_search": '{"query": "..."} -> live mode only.',
}

RESEARCH_SPAWNABLE = ["equity_scout", "bond_scout", "stock_analyst", "risk_analyst", "news_analyst",
                      "filing_reader", "monitor_designer", "scenario_analyst"]

ROLES: dict[str, Role] = {r.name: r for r in [
    Role("lead", True, READ_TOOLS + ["build_options", "check_proposal", "cost_turnover", "backtest",
                                     "propose_adjustment", "save_investment_case", "exposure", "forecast"],
         can_spawn=RESEARCH_SPAWNABLE),
    Role("profiler", False, [], group="interface"),
    Role("equity_scout", False, ["get_catalogue", "get_prices", "overlap"], can_spawn=["filing_reader"]),
    Role("bond_scout", False, ["get_catalogue", "get_prices"], can_spawn=["filing_reader"]),
    Role("stock_analyst", False, ["get_catalogue", "get_prices", "search_news", "search_filings", "earnings_calendar"],
         can_spawn=["filing_reader", "news_analyst"], allow_deep_override=True),
    Role("risk_analyst", False, ["get_prices", "correlation_lattice", "risk_stats", "backtest", "overlap", "forecast"]),
    Role("news_analyst", False, ["search_news", "search_filings", "get_prices", "exposure", "web_search"],
         can_spawn=["filing_reader"]),
    Role("filing_reader", False, ["search_filings"], can_spawn=["news_analyst"]),   # depth-2 → always refused
    Role("monitor_designer", False, ["get_investment_case", "create_monitor"], can_spawn=["tester"]),
    Role("scenario_analyst", False, ["build_options", "backtest", "cost_turnover"]),
    # assurance
    Role("evidence_checker", False, ["search_news", "search_filings"], group="assurance"),
    Role("critic", True, READ_TOOLS + ["earnings_calendar"], group="assurance"),
    Role("compliance", False, [], group="assurance"),
    Role("qa_reviewer", True, [], group="assurance"),
    Role("tester", False, [], group="assurance"),
    # learning (T3)
    Role("retrospective", True, READ_TOOLS, can_spawn=["rule_tester"], group="learning"),
    Role("rule_tester", False, [], group="learning"),
    # interface
    Role("explainer", False, ["cost_turnover"], group="interface"),
    Role("chat", True, READ_TOOLS + ["pnl_breakdown", "get_run_history"], can_spawn=["scenario_analyst"],
         group="interface"),
]}

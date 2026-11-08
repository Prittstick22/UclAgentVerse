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
        base = (PROMPTS / "_base.md").read_text()
        return base + "\n\n" + (f.read_text() if f.exists() else f"You are the {self.name} agent.")


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

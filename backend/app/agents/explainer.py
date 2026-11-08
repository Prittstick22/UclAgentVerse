"""Explainer (#34): turn a proposal into a plain-English decision card a first-time investor can act on.

Problem 1 from the spec: first-time investors need £, not jargon. Rules this module guarantees:
- every percentage on the card has a £ amount next to it (in the same sentence);
- every number comes from code (the option's stats, the trade list, the ledger), never from a model;
- the card carries the risk warning and says "simulated, not a forecast" wherever it shows past results.
The compliance gate (agents/gate.py) re-checks the finished card text independently.
"""
from __future__ import annotations

import re

from app.schemas import DecisionCard, OrderChange, PortfolioOption

# "8%", "8 %", "%8", "8 percent", "8 per cent"
PCT = re.compile(r"\d+(?:\.\d+)?\s?(?:%|per\s?cent\b)|%\s?\d", re.IGNORECASE)
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def gbp(x: float) -> str:
    """£1,234 for whole-pound amounts, £3.20 below £100 so small costs don't round to £0."""
    x = abs(float(x))
    return f"£{x:,.2f}" if x < 100 else f"£{x:,.0f}"


def pct(fraction: float) -> str:
    """8% for normal sizes, 0.08% for small ones (fees) so they never show as 0%."""
    f = abs(fraction)
    return f"{f:.2%}" if 0 < f < 0.01 else f"{f:.0%}"


def pct_with_gbp(fraction: float, base_gbp: float) -> str:
    """'8% (about £800 of £10,000)': the % never travels without its £."""
    return f"{pct(fraction)} (about {gbp(abs(fraction) * base_gbp)} of {gbp(base_gbp)})"


def percent_without_pound(text: str) -> list[str]:
    """Sentences that show a percentage but no £ amount (the compliance rule for cards)."""
    return [s.strip() for s in SENTENCE.split(text or "") if PCT.search(s) and "£" not in s]


def decision_figures(option: PortfolioOption, changes: list[OrderChange], capital_gbp: float) -> dict[str, float]:
    """Deterministic amounts behind the decision copy and the evidence drawer."""
    buys = sum(change.amount_gbp for change in changes if change.action == "buy")
    sells = sum(change.amount_gbp for change in changes if change.action == "sell")
    return {
        "invested_gbp": (1 - option.cash_weight) * capital_gbp,
        "cash_gbp": option.cash_weight * capital_gbp,
        "buy_total_gbp": buys,
        "sell_total_gbp": sells,
        "amount_moved_gbp": max(buys, sells),
        "annual_fund_fees_gbp": option.stats.ocf_weighted * capital_gbp,
    }


def decision_card(kind: str, option: PortfolioOption, changes: list[OrderChange], capital_gbp: float,
                  cost_gbp: float, lookback_days: int) -> DecisionCard:
    """Build the card from code numbers only. `kind` is 'construction' or 'adjustment'."""
    n = len(option.holdings)
    figures = decision_figures(option, changes, capital_gbp)
    invested, cash = figures["invested_gbp"], figures["cash_gbp"]
    buys, sells = figures["buy_total_gbp"], figures["sell_total_gbp"]
    s = option.stats
    fees_year = figures["annual_fund_fees_gbp"]

    holdings = f"{n} holding{'s' if n != 1 else ''}"
    if kind == "construction":
        headline = f"Your starting portfolio: {gbp(capital_gbp)} across {holdings}"
        what = f"Invests {gbp(invested)} in {holdings} and keeps {gbp(cash)} in cash."
    elif not changes:
        headline = "No trades needed: your portfolio already matches this option"
        what = "Keeps your holdings as they are; nothing would be bought or sold."
    else:
        moved = figures["amount_moved_gbp"]
        headline = (f"Suggested change: {len(changes)} trade{'s' if len(changes) != 1 else ''}, "
                    f"about {gbp(moved)} moved")
        what = (f"Sells {gbp(sells)} and buys {gbp(buys)}, so about {pct_with_gbp(moved / capital_gbp, capital_gbp)} "
                "of your portfolio changes." if capital_gbp else f"Sells {gbp(sells)} and buys {gbp(buys)}.")
    costs = (f"One-off trading cost about {gbp(cost_gbp)}. Fund fees about {gbp(fees_year)} a year, "
             f"which is {pct(s.ocf_weighted)} of {gbp(capital_gbp)}.")
    sentences = [what, costs]
    if s.max_drawdown_backtest is not None:
        sentences.append(f"Over the past {lookback_days} trading days a mix like this had a worst fall of "
                         f"{pct_with_gbp(s.max_drawdown_backtest, capital_gbp)}. Simulated on past prices, "
                         "not a forecast.")
    if s.vol_annual:
        sentences.append(f"In a typical year its value moved up or down by about "
                         f"{pct_with_gbp(s.vol_annual, capital_gbp)}. That is an estimate from past prices, "
                         "not a promise.")
    sentences.append("Nothing is bought or sold until you approve.")
    return DecisionCard(headline=headline, body=" ".join(sentences), changes=changes)

"""Explainer (#34): plain-English decision cards in £, every % with its £, risk warning always."""
import asyncio

import pytest

from app.agents import explainer, gate
from app.schemas import OptionStats, OrderChange, PortfolioOption, ProposedHolding

OPT = PortfolioOption(label="recommended", cash_weight=0.05,
                      holdings=[ProposedHolding(ticker="VWRP.LSE", weight=0.55), ProposedHolding(ticker="VAGS.LSE", weight=0.40)],
                      stats=OptionStats(vol_annual=0.09, ocf_weighted=0.0016, turnover=0.12, cost_gbp=3.2,
                                        max_drawdown_backtest=-0.084))


def _card(kind="construction", changes=None):
    return explainer.decision_card(kind, OPT, changes or [], 10_000, 3.2, 504)


def test_construction_card_is_plain_english_in_pounds():
    c = _card()
    assert c.headline == "Your starting portfolio: £10,000 across 2 holdings"
    assert "Invests £9,500 in 2 holdings and keeps £500 in cash." in c.body
    assert "trading cost about £3.20" in c.body and "Fund fees about £16.00 a year, which is 0.16% of £10,000." in c.body
    assert "worst fall of 8% (about £840 of £10,000)" in c.body and "not a forecast" in c.body
    assert "about 9% (about £900 of £10,000)" in c.body and "not a promise" in c.body
    assert explainer.percent_without_pound(f"{c.headline}. {c.body}") == []
    assert "go down as well as up" in c.risk_warning and c.simulated is True


def test_adjustment_card_shows_the_trades_in_pounds():
    changes = [OrderChange(ticker="VWRP.LSE", action="sell", amount_gbp=600, from_weight=0.6, to_weight=0.55),
               OrderChange(ticker="VAGS.LSE", action="buy", amount_gbp=590, from_weight=0.35, to_weight=0.40)]
    c = _card("adjustment", changes)
    assert c.headline == "Suggested change: 2 trades, about £600 moved"
    assert "Sells £600 and buys £590, so about 6% (about £600 of £10,000) of your portfolio changes." in c.body
    assert c.changes == changes and explainer.percent_without_pound(c.body) == []


def test_small_percentages_never_show_as_zero():
    assert explainer.pct(0.0008) == "0.08%" and explainer.pct(0.084) == "8%" and explainer.pct(-0.2) == "20%"
    assert explainer.gbp(3.2) == "£3.20" and explainer.gbp(12345.6) == "£12,346"


@pytest.mark.parametrize("text,flagged", [
    ("Your portfolio fell 8% last month.", True),
    ("Fees are 0.2% a year.", True),
    ("It fell 8% (about £800 of £10,000).", False),
    ("Fund fees about £16 a year, which is 0.16% of £10,000.", False),
    ("No numbers here.", False),
])
def test_percent_without_pound_rule(text, flagged):
    assert bool(explainer.percent_without_pound(text)) is flagged


def test_compliance_fails_a_card_with_a_bare_percentage(state):
    run = asyncio.run(state.supervisor.start("construction", "test"))
    prop = state.proposals[run.proposal_id]
    ctx = state.supervisor.tools.ctx
    assert gate.check_compliance(ctx, run, prop).status == "pass"
    prop.decision_card.body += " Expect returns of around 7% a year."
    res = gate.check_compliance(ctx, run, prop)
    assert res.status == "fail" and any("without a £" in i for i in res.issues)


def test_real_card_numbers_come_from_the_option_not_a_model(state):
    run = asyncio.run(state.supervisor.start("construction", "test"))
    prop = state.proposals[run.proposal_id]
    opt = next(o for o in prop.options if o.label == prop.selected)
    body = prop.decision_card.body
    capital = 10_000
    assert explainer.gbp((1 - opt.cash_weight) * capital) in body
    assert explainer.gbp(opt.stats.ocf_weighted * capital) in body
    assert explainer.percent_without_pound(f"{prop.decision_card.headline}. {body}") == []
    assert "go down as well as up" in prop.decision_card.risk_warning
    assert next(g for g in prop.gates if g.gate == "compliance").status == "pass"


def test_one_holding_and_no_trades_read_correctly():
    one = OPT.model_copy(update={"holdings": [ProposedHolding(ticker="VWRP.LSE", weight=0.95)]})
    assert explainer.decision_card("construction", one, [], 10_000, 0, 504).headline.endswith("across 1 holding")
    c = explainer.decision_card("adjustment", one, [], 10_300, 0, 504)
    assert c.headline.startswith("No trades needed") and "£0.00 moved" not in c.headline


@pytest.mark.parametrize("text", ["Fees are 0.2 percent a year.", "Fees are 0.2 per cent a year.", "Returns of %5."])
def test_percentages_written_as_words_are_caught_too(text):
    assert explainer.percent_without_pound(text)


def test_percentage_points_and_percentiles_are_not_percentages():
    assert not explainer.percent_without_pound("It moved 5 percentage points. The 90th percentile.")

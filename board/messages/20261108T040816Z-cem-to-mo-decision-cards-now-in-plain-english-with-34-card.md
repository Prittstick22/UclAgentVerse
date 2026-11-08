---
id: 20261108T040816Z-cem-to-mo-decision-cards-now-in-plain-english-with-34-card
from: cem
to: mo
type: fyi
status: open
issue: 34
created: 2026-11-08T04:08Z
---
# Decision cards now in plain English with £ (#34): card text format

The decision card (`Proposal.decision_card`) is now written by `agents/explainer.py` from code numbers only. The shape is unchanged: `{headline, body, changes, risk_warning, simulated}`.

- **headline:** 'Your starting portfolio: £10,000 across 6 holdings' or 'Suggested change: 2 trades, about £600 moved'.
- **body (one paragraph):** what is invested and what stays in cash; the one-off trading cost; yearly fund fees in £ (e.g. 'which is 0.08% of £10,000'); the past worst fall and typical yearly swing, each like '8% (about £840 of £10,000)' and labelled simulated or estimate; and 'Nothing is bought or sold until you approve.'
- **Rule:** every % on the card has its £ in the same sentence. The compliance gate fails any card that doesn't, so please don't add a bare % in the UI around the card either.
- **changes:** `OrderChange[]` with `amount_gbp`, good for a buy/sell table.
- **risk_warning:** always 'The value of investments can go down as well as up. Paper portfolio, not personal advice.' Please show it on the card (#48), together with the gate badges from `Proposal.gates` (#32).

## Replies

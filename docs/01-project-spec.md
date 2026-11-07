# 01 · Project spec (weekend build)

## 1. One-liner

**An AI investment team for first-time UK investors.** A quiz sets your limits, supervised Gemini agents build and watch a paper portfolio, and you're only asked to decide when something actually needs you. Every decision can be traced back to its evidence and maths.

**Pitch:** "Start investing in five minutes. Then forget about it. We'll tell you when something needs your decision."
**Alternative opener (from the original spec):** "Your broker shows what you own. We investigate whether you should still own it."

## 2. Problems we solve

1. **Most UK adults don't invest.** The FCA's 2024 survey found about 35% of UK adults hold investment products (see the original spec). The blockers are not knowing what to choose, not trusting yourself to judge research, and not having the time.
2. **People who do invest buy and forget.** Portfolios drift, and the reasons for owning something change, but nobody looks.

**Our answer:**
- A goal-first, plain-English start, with every holding explained.
- Then the user can forget about it. Reviews and triggers run in the background, and the user is prompted *only* for decisions, each one already checked by independent reviewer agents.

## 3. Users

- **Primary:** UK adult, has some savings, has never invested, low confidence.
- **Secondary:** early investor with a few holdings they never review.
- **For the hackathon:** fictional profiles and amounts only (default £10,000 start, £200/month).

## 4. Scope: what the product does

1. **Quiz → profile → mandate.**
   - About 8 plain questions; code scores *tolerance* (willingness) and *capacity* (ability to absorb loss) separately, and the profile is the lower of the two.
   - That gives one of 4 profiles (Cautious, Balanced, Growth, Adventurous) and an editable mandate: asset ranges, caps, exclusions, review cadence, triggers.
   - If the two scores conflict, Argon asks one follow-up question. Argon explains; code scores.
2. **Portfolio construction by agents.**
   - The lead agent spawns specialists (scouts, stock analyst, risk analyst).
   - They choose from a verified catalogue of about 15–25 instruments.
   - The optimiser (code) produces **one recommended portfolio + two alternatives** (lower cost, lower risk).
   - Each holding gets a one-line purpose, "why this rather than the alternatives", and `reconsider_if` conditions.
   - Every proposal passes the **assurance gate** before the user sees it.
3. **Correlation lattice:** a heatmap of how each pair of holdings moves together, with a date slider and plain-English callouts.
4. **Historical simulation:**
   - Start 7 Jul 2026 and step day by day to 6 Nov 2026 (4 months, entirely after Argon's reported Mar 2026 knowledge cutoff).
   - Daily mark-to-market (code); **fortnightly agent reviews**; **ad hoc triggers**: drift ≥ 5 percentage points, a holding moving ≥ 5% in a day or ≥ 10% since the last review, NAV ≥ 5% below the last review, relevant news.
   - Monthly £200 contributions.
5. **Decisions:**
   - "Maintain" is silent and goes into a digest.
   - "Adjust" sends a notification and a **decision card**: what changed, the suggestion in £, Approve / Keep / Why?
   - "Why?" replays the agent tree, evidence, maths and checks.
6. **Portfolio views:** holdings, **gains and losses per asset** (£ and %, realised/unrealised, contribution to return), **recent rebalances**, status (Monitoring normally / Investigating / Awaiting approval / Monitoring degraded).
7. **Benchmarking** against buy-and-hold, quarterly rebalance, a single global ETF and mechanical 5% rebalancing, all after costs. The development and held-out periods are shown separately (see 10-evaluation).
8. **AI chat:** "Why did you sell X?", "What if I add £1,000?". Read-only, cites evidence; any suggested change becomes a normal decision card.
9. **Live mode:** the same code on today's data with a persistent paper portfolio and a few API calls a day.
10. **Controls we show judges:**
    - concentration-limit block
    - an injected instruction in a news item quarantined by the guard
    - a refused depth-3 sub-agent spawn
    - a future-data request refused by the gateway

## 5. Tiers (what to build first)

**Tier 1, the spine:**
- quiz → mandate
- agent construction run visible in the workspace
- correlation → optimiser → numbers/mandate checks
- approve → paper ledger
- deterministic year simulation with drift/cap rebalancing, contributions, costs and benchmarks
- timeline, home, P&L, correlation lattice
- deployed hello-world

**Tier 2, the differentiator:**
- agent runs during the simulation (fortnightly reviews + triggers), recorded and replayable
- full assurance gate with badges
- two alternative portfolios
- decision cards, notifications and digest
- recent rebalances
- chat
- agent-designed monitors (templates + tester + shadow mode)
- live mode
- the four controls on film
- eval table

**Tier 3, only if ahead:**
- retrospective reviewer + one tested memory rule
- dependency look-through with passage-cited edges
- candidate-instrument review queue
- correlation network view
- scenario branches

**Out of scope / cut:**
- real money, broker integration, user accounts or logins
- generated-code tools in a sandbox
- GLiNER, BGE, FinBERT
- mutual funds (no free reliable daily NAVs)
- intraday strategies, reinforcement learning
- a five-year backtest

## 6. Hard constraints (from the hackathon rules and our own)

- Paper trading only; no real financial records, account details or logins.
- Synthetic inputs labelled. Backtests are never presented as live performance.
- **Walk-forward only:** every simulated day/week sees only data up to that day (proven by `test_no_peeking`). The 2-week outlook is **estimated by code from past data** (labelled 'estimate'); the LLM never invents numbers. Agents may express views that code turns into capped tilts.
- Historical mode never sees data after `as_of`, and blocks web search.

## 7. Judging rubric → where we score

| Criterion | Weight | Our evidence |
|---|---|---|
| Traceable reasoning | 25% | Event log, replay, evidence → claim → calculation links, separate badges, code-only maths |
| Unseen-data testing | 25% | Benchmarks after costs; the whole Jul–Nov 2026 window is after Argon's reported Mar 2026 knowledge cutoff (held-out); agents vs same-engine-without-agents shows what Gemini adds; params frozen before the run |
| Relevance and impact | 20% | Two concrete problems; "26 reviews, N checks, only Z decisions asked of you" |
| Controls and oversight | 15% | Coded limits, gateway firewall, injection guard, approval gate, refused spawns, all logged |
| Ambition and technical quality | 15% | Lead-decided sub-agent trees, assurance roles, agent-designed monitors, tested memory rule |

## 8. Success for the weekend

- The public demo link opens a replay of the full 4-month simulation with at least one adjustment (and its full gate) and at least one "alarming but maintain" case.
- One live investigation can be run on request.
- The deck has the eval table with both periods.
- A 3-minute video shows the demo storyline (11-demo-and-pitch).

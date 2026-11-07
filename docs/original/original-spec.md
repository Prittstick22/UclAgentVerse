# Original product spec (teammate draft)

> Text extracted automatically from `original-spec.pdf` in this folder. Tables lost some formatting; open the PDF for the exact layout.
> This is the **long-term vision**. What we are building this weekend is defined in [`../01-project-spec.md`](../01-project-spec.md). Where they differ, `01-project-spec.md` wins.

```text
Your broker shows what you own. We investigate whether you should still own it.

We are building an AI investment team for everyday investors, delivered through a
beautiful financial terminal that works on their behalf.

The user explains their goals. The system researches and constructs a portfolio, remembers
why each holding belongs, and monitors the evidence behind those decisions. When
something material changes, specialist agents investigate, calculate the portfolio exposure
and prepare adjustments within the user’s limits.

The user can watch an investigation unfold or return later and replay it. Every decision
connects to evidence, calculations, uncertainties and an approval record. The system can
create targeted monitoring tools and improve its research procedures through tested
memory.

The promise: start investing without becoming your own analyst, while being able to
understand and verify what happens to your portfolio.

This is the consolidated specification. It incorporates the QA corrections. Where an
implementation choice is still unresolved, it is explicitly identified rather than presented as
settled.



1. Who the product serves

The primary audience is UK adults with money available to invest who have not started
because they lack confidence, knowledge or time. Early-stage investors who already
hold a few investments are a natural secondary audience.

The FCA’s 2024 survey found that 35% of UK adults held investment products under its
measure excluding people whose only investments were property or other real assets. This
establishes context for the participation gap; it does not mean everyone outside that group
should invest immediately. www.fca.org.uk

The user’s problem is:

      “I want to invest, but I do not know what to choose, how to judge the research,
      or when something has changed enough that I should act.”

The product handles the complete lifecycle:

Understand the person → construct a portfolio → monitor its investment cases →
investigate changes → maintain or adjust → review and improve.

It is approachable without removing depth. Someone can read the outcome or explore the
agents’ work and gradually learn through actual decisions. Education is a useful
consequence, rather than a separate product.
The current scope is ongoing, goal-constrained portfolio management. Intraday strategy
generation, correlation-only trading rules and reinforcement learning are outside this version.



2. One functioning system, with an integrated historical demo

The product must operate against current markets. Historical demo mode is an environment
inside that same application.

 Behaviour              Historical demo                    Current-market operation

 Clock         Selected date; can pause or           Actual current time
               accelerate

 Information   Available by the selected             Latest available connected-source
               historical date                       information

 Agents        Real agents performing the work       The same agents

 Monitoring    Scheduled against the simulated       Scheduled against the real clock
               clock

 Calculation   Shared portfolio engine               Shared portfolio engine
 s

 Portfolio     Separate fictional historical         Persistent current-market paper
               portfolio                             portfolio

 Memory        Isolated demo memory                  Persistent current-market memory

 Execution     Historical paper fills                Current-market paper execution

 Label         “Historical demo · As of…”            “Current markets · Paper portfolio”

Turning off the demo changes the clock and data adapters. It must not replace prerecorded
animations with an entirely different system.

Implementation requirements:

   ●​ Every time-sensitive service uses a shared clock.
   ●​ Data requests accept an as_of time.
   ●​ Records distinguish when an event occurred from when information became
      available.
   ●​ Historical mode blocks unrestricted current web retrieval.
   ●​ Historical holdings, dependencies and memories are versioned.
   ●​ Demo outcomes never enter current-market memory.
   ●​ Switching modes opens the corresponding portfolio and history.
   ●​ Every source shows freshness, delay and coverage.

Two different controls are needed:
   ●​ Replay investigation: revisit recorded events without rerunning the agents.
   ●​ Run historical simulation: execute the system through a historical period.

Current-market mode should genuinely research and monitor today’s information.
Real-money execution is a separate integration and deployment stage. The hackathon
explicitly requires paper trading and prohibits real financial records, account details and
logins.



3. The first-time user flow

The user begins with a goal, not a ticker.

Onboarding collects:

   ●​    Goal and target date.
   ●​    Starting amount and expected contributions.
   ●​    Potential need to withdraw early.
   ●​    Investment experience.
   ●​    Ability to absorb losses.
   ●​    Willingness to tolerate losses.
   ●​    Asset or sector exclusions.
   ●​    Notification preferences.

For the hackathon, these are fictional profiles and amounts.

Use concrete questions:

        “If this portfolio fell from £5,000 to £4,000, would that prevent you from meeting
        your goal?”

The system distinguishes psychological tolerance from financial capacity.

It converts the answers into an editable mandate:

         Mandate field                         What it controls

 Goal and horizon                Supported allocation policy

 Access-to-cash needs            Liquidity and cash requirements

 Risk capacity and               Allowed exposure ranges
 tolerance

 Asset restrictions              Instrument eligibility

 Concentration limits            Maximum direct and underlying exposures

 Contributions                   Purchases and rebalancing opportunities
 Approval rules                 Preparation versus execution authority

 Review triggers                Circumstances requiring reassessment

The initial mapping must be a documented policy. Argon can explain it and identify
contradictions; it should not invent a precise risk score.

If answers conflict, ask a relevant follow-up. If no supported policy fits, explain that rather
than forcing a portfolio.

The user reviews the mandate and selects Build my portfolio.

Unresolved: the precise questionnaire-to-allocation mapping. The prototype needs an
explicit, labelled policy; it must not be presented as a validated suitability assessment.



4. Where actual funds and stocks come from

The system selects from a verified instrument catalogue.

For the weekend, a proposed scope is approximately 20–40 instruments across broad
equities, bonds and cash-like exposure, with a small separately constrained stock universe if
included. This is an implementation limit, not the permanent product boundary.

Each record contains:

   ●​   ISIN and exact share class.
   ●​   Exchange-specific ticker.
   ●​   Issuer identity.
   ●​   Quote currency and fund base currency.
   ●​   Accumulating or distributing status.
   ●​   Asset class, objective and benchmark.
   ●​   Fees.
   ●​   Dated underlying holdings.
   ●​   Supporting documents and source references.
   ●​   Historical-data coverage.
   ●​   Eligibility and verification status.

Sources include:

               Source                                           Purpose

 Issuer product pages and                Objective, fees, share class, restrictions and
 documents                               disclosures

 Issuer holdings files                   Underlying company, sector and geographic
                                         exposures
 Public exchange/broker listings         Listing identity and availability

 Market-data provider                    Prices, distributions, corporate actions and FX

 Official announcements                  Material changes to an instrument

For example, Vanguard’s FTSE All-World accumulating ETF page supplies documents,
portfolio information and purchase details. It illustrates a source-backed catalogue entry, not
a universal recommendation. www.vanguard.co.uk

Agents extract fields. Code validates identifiers, units, dates and consistency. Unresolved
identity conflicts or essential missing information block eligibility.

Ticker alone is insufficient. Different listings can represent the same share class, while
similarly named funds can have different exposures. A GBP listing does not automatically
hedge underlying currency risk.

If research discovers a candidate outside the catalogue, it enters candidate review. It
becomes selectable only after the same identity, document, exposure and data-coverage
checks. An agent cannot bypass the catalogue by inserting a new ticker directly into an
order.



5. How the first portfolio is selected and calculated

Three jobs remain separate.

First: choose the intended exposure policy.

The mandate determines allowable equity, bond and cash ranges, plus concentration and
liquidity requirements.

Second: compare eligible instruments.

Apply hard eligibility filters before comparison. Then assess:

   ●​    Whether the instrument provides the intended exposure.
   ●​    Overlap with other holdings.
   ●​    Fees and implementation characteristics.
   ●​    Exact share class and availability.
   ●​    Quality and freshness of supporting data.
   ●​    Restrictions and material risks.

The UI should answer:

        “Why this fund rather than the other eligible alternatives?”

Avoid a mysterious universal “AI quality score.”
Third: calculate weights.

The proposed MVP optimiser balances:

   ●​    Distance from intended asset exposures.
   ●​    Estimated portfolio risk.
   ●​    Ongoing costs.
   ●​    Transaction costs.
   ●​    Unnecessary turnover.

Constraints include:

   ●​    Weights and cash sum to 100%.
   ●​    No shorting or leverage.
   ●​    Asset-class ranges.
   ●​    Holding and underlying concentration limits.
   ●​    Available cash.
   ●​    Supported order sizes and instruments.

CVXPY is suitable for constrained optimisation. Ledoit–Wolf covariance estimation is a
reasonable initial numerical component for estimating risk from historical returns.
www.cvxgrp.org

Independent code recomputes weights, cash, fees, currency conversions, overlap and
constraint compliance. Checks run again after allocations become paper orders.

If no feasible portfolio exists, explain the conflict. Do not silently weaken the mandate.

This remains active management: research can change eligible instruments or proposed
target ranges. However, the optimiser does not manufacture an investment advantage, and
the model must not supply invented return forecasts as facts.

Unresolved: exact comparison weights, optimiser coefficients and policy ranges. These
must be selected before final evaluation and kept fixed during it.



6. The initial research experience

The lead agent opens the main workspace:

        Building your portfolio​
        Selecting eligible investments for your goal, comparing alternatives and verifying
        the allocation.

As tasks are delegated, the lead moves into the left half of the screen. Specialists appear on
the right.

They work on concrete questions:
   ●​    Which instruments meet the mandate?
   ●​    Which candidates duplicate exposure?
   ●​    What do their documents establish?
   ●​    How has this allocation behaved historically?
   ●​    Which claims or assumptions remain unsupported?

The result is one recommended portfolio and, where useful, up to two alternatives with
meaningful trade-offs.

The proposal shows:

   ●​    Allocation and each holding’s purpose.
   ●​    Candidate comparisons.
   ●​    Costs and exposures.
   ●​    Historical behaviour, explicitly labelled.
   ●​    Material uncertainties.
   ●​    Passed and failed checks.

Actions:

Explore research · Compare alternatives · Change preferences · Approve paper
portfolio

Approval saves the holdings and their investment cases: why each belongs, supporting
evidence, material assumptions and conditions that could justify reconsideration.



7. How the system discovers portfolio dependencies

This happens during initial research and continues afterwards.

        Step                         Operation                                 Output

 Resolve            Identify exact funds and companies; load Portfolio → fund → underlying
 holdings           dated fund constituents                  company links

 Gather             Retrieve filings, risk disclosures,    Relationship-bearing source
 evidence           announcements and relevant operational documents
                    material

 Extract            Identify organisations, products, facilities   Possible dependency records
 candidates         and locations

 Resolve            Check aliases, parents, subsidiaries and       Correct entity identities
 entities           similar names

 Verify             Check whether a source actually                Documented, reported,
 relationships      supports the proposed connection               inferred or unresolved
                                                                   relationship
 Prioritise        Assess relevance, ownership exposure          Relationships worth further
                   and evidence quality                          research

 Create            Configure an existing monitor or request      Executable monitoring
 watches           a new tool                                    programme

A source might establish:

        Company B purchases a particular component from Supplier A.

That supports a relationship. It does not establish the effect of a disruption.

Each graph edge stores:

   ●​    Relationship type and direction.
   ●​    Exact supporting passage.
   ●​    Source and publication date.
   ●​    Date first known to the system.
   ●​    Applicable period.
   ●​    Verification status.
   ●​    Limitations and contrary evidence.

The graph is an evidence-backed research record, not established causal truth merely
because an agent drew a line.

Undisclosed or unresolved dependencies remain unknown.



8. How relevant events are found

There are two routes.

Known-relationship monitoring

   1.​ Research establishes a supplier relationship.
   2.​ A saved watch detects a new announcement.
   3.​ Entity matching connects it to the relationship.
   4.​ A specialist investigates whether it changes the investment case.

New-relationship discovery

   1.​ Broader ingestion finds an event involving a company, product, location or regulation.
   2.​ Retrieval searches portfolio-company documents for potentially relevant exposure.
   3.​ The lead asks:​
       “Do any holdings depend on this facility, component or location?”
   4.​ Specialists investigate candidate connections.
   5.​ Supported relationships enter the graph.
   6.​ New targeted monitors are created when useful.
The second route is essential. Without it, the system only detects risks it already anticipated.

Broader reviews and samples of discarded alerts also help measure what the filtering layer
misses. No architecture should claim complete awareness of every possible dependency.



9. Exactly how monitoring is created

There are three monitor types:

            Type                         Creation                            Execution

 Standard checks         Developers implement tested functions        Normal scheduled code

 Portfolio-specific      Argon configures existing templates          Standard monitor
 checks                                                               runner

 New capabilities        A coding agent implements a missing          Restricted, versioned
                         adapter or function                          execution

Standard checks include allocation drift, new filings, stale data and numerical limit breaches.

The creation pipeline is:

Investment assumption → observable evidence → monitor specification → template
or generated tool → independent tests → activation → scheduled observations →
investigation.

A monitor specification contains:

      ●​   The question being watched.
      ●​   Related investment case.
      ●​   Sources and entities.
      ●​   Extraction method.
      ●​   Trigger condition.
      ●​   Schedule.
      ●​   Review/expiry date.
      ●​   Resource budget.
      ●​   Escalation task.

For example:


  None‎
  {
       "monitor_id": "supplier_status_01",
       "investment_case_id": "case_17",
       "question": "Has the supplier's operating status changed?",
       "source_ids": ["supplier_announcements"],
       "runner": "announcement_change_detector",
       "entity_ids": ["supplier_a", "held_company_b"],
       "schedule": "every_6_hours",
       "event_types": [
         "production_suspension",
         "capacity_reduction",
         "reopening"
       ],
       "on_trigger": "launch_dependency_investigation",
       "review_after_days": 30
  }


The schedule is illustrative.

A cheap runner checks for new material. A smaller model may assess relevance. Argon
handles deeper interpretation.

For generated tools:

      1.​ The lead specifies the evidence need.
      2.​ A tool builder produces code, a manifest and sample outputs.
      3.​ A restricted runner executes it.
      4.​ Independent checks verify source identity, dates, units and extracted meaning.
      5.​ Known examples test detection behaviour.
      6.​ The monitor initially runs in shadow mode, recording detections without triggering
          downstream investigations.
      7.​ An activation policy determines whether it can begin escalating.
      8.​ Parser failures, excessive alerts or expired relevance can disable it.

Self-authored tests passing is insufficient. Use independently specified expected outputs.

Generated tools cannot alter portfolio limits, trading permissions or the independent financial
engine.

Unresolved: exact activation thresholds, shadow period and cost limits. These are policy
settings to test, not financial truths.



10. What happens while the user is away

Monitors run against the selected clock. Shared ingestion avoids fetching the same
announcement separately for every portfolio.
Research begins when:

   ●​    Evidence may invalidate an investment case.
   ●​    An agreed numerical limit is breached.
   ●​    A scheduled review is due.
   ●​    The user changes their goals.
   ●​    An uncertainty becomes answerable.

Each run records its trigger:

        “Started because monitor M17 found a new announcement relevant to holding
        H4.”

The home screen reports:

Monitoring normally · Investigating · Awaiting approval · Monitoring degraded

Frequent monitoring does not require frequent trading.

After several quiet days, a returning user sees:

   ●​    Last completed review.
   ●​    Active watches.
   ●​    Source coverage and outages.
   ●​    Unresolved questions.
   ●​    A concise explanation of why no adjustment was proposed.

Notifications are reserved for meaningful decisions or material coverage problems. Routine
activity can appear in a digest.



11. From an event to portfolio materiality

Keep three quantities separate:

           Quantity                                       Meaning

 Ownership exposure             How much the portfolio owns the affected company

 Dependency severity            How important the affected relationship is

 Possible investment            What the event could mean for the investment case and
 impact                         returns

Example:

   ●​ Portfolio holds 30% in Fund C.
   ●​ Fund C holds 4% in Company B.
   ●​ Portfolio also holds 2% directly in Company B.
Total exposure is:

\[ 30\%\times4\%+2\%=3.2\% \]

That is 3.2% ownership exposure, not a predicted 3.2% loss.

The investigation considers:

   ●​   Whether the relationship is current.
   ●​   Importance of the affected product/process.
   ●​   Duration.
   ●​   Inventory and substitutes.
   ●​   Mitigation and contrary evidence.
   ●​   Direct and fund-overlap exposure.
   ●​   Whether the issue was already part of the original assessment.

Numerical exposure is recomputable. Economic significance remains a source-backed
judgement with uncertainty.



12. How research becomes a proposed adjustment

The lead retrieves the mandate, portfolio, original investment case, triggering evidence and
applicable memories.

It delegates specific questions and may launch child agents where uncertainty remains.

Possible outcomes:

Maintain · Investigate further · Prepare adjustment

Research can propose changes to:

   ●​   Instrument eligibility.
   ●​   Target allocation ranges.
   ●​   Exposure caps within the user’s overall mandate.
   ●​   Scenario assumptions.
   ●​   Monitoring intensity or review dates.

Every proposed change cites its evidence.

The optimiser calculates a feasible implementation. The decision view compares current
holdings, proposed holdings and no change.

Before proposing a trade, the policy should consider:

   ●​   Whether evidence is sufficient.
   ●​   Whether the change is material.
   ●​   Costs and turnover.
   ●​   Whether contributions can resolve drift.
   ●​ Minimum trade size.
   ●​ Recent related proposals and cooldowns.
   ●​ Uncertainty that warrants waiting.

Unresolved: the exact decision thresholds, no-action bands, trade-size bounds and
cooldowns. These must be explicitly configured and evaluated.

The user sees:

Approve paper adjustment · Keep current portfolio · Ask a question · Request
alternative

Before execution, revalidate holdings, prices and mandate version. Prevent duplicate
execution. Record no-change decisions as carefully as trades.



13. Memory that changes future behaviour

Store four distinct memory types:

          Type                              Contents

 User mandate             Goals, preferences and limits

 Investment cases         Holding rationale and invalidation conditions

 Investigation            Evidence, findings, decisions and outcomes
 episodes

 Research procedures      Tested rules that change later behaviour

A later review asks:

   ●​   Was the original decision defensible with available information?
   ●​   Was relevant, obtainable evidence missed?
   ●​   Was the interpretation flawed?
   ●​   Was the process reasonable but the outcome unlucky?
   ●​   Would a proposed correction help elsewhere?

A worked example:

   1.​ An investigation missed an available supplier disclosure.
   2.​ Review identifies that specific omission.
   3.​ A candidate rule requires a supplier-capacity check before increasing certain
       exposed holdings.
   4.​ The rule is tested on other relevant and irrelevant cases.
   5.​ It is assessed for useful detections, false alarms, cost and regressions.
   6.​ If accepted, it becomes an active trigger.
   7.​ A later proposed increase launches the supplier specialist automatically.
The rule stores its origin, scope, exceptions, tests, version and review date. It can be retired
or rolled back.

The claim is tested procedural improvement, not automatic improvement merely from
storing more memories.

Unresolved: promotion criteria and evaluation case sets.



14. Specific non-Gemini models

  Model            Input → output                 Useful role                 Boundary

 GLiNER       Text and entity types →       Find company,              Does not
              entity spans                  product, facility and      independently establish
                                            location names             relationships or identity

 BGE-M3       Questions/documents →         Find relevant evidence     Similarity is not truth
              retrieval representations     and memories despite
                                            different wording

 BGE          Question and passages →       Remove noisy retrieval     Relevance is not
 reranker     relevance ordering            results                    financial confidence

 FinBERT      Financial text → sentiment    Optional routing           Sentiment is not a
              scores                        feature and                trade signal
                                            comparison baseline

These roles follow the models’ documented capabilities. huggingface.co

Suggested starting choice: BGE-M3, with GLiNER if entity extraction needs it. Add the
reranker if retrieval is noisy. FinBERT is useful as a conventional sentiment baseline.

Time-series models such as Amazon’s Chronos family could be evaluated for suitable
operational-series forecasts, but should not be added merely to claim stock-price prediction.
github.com

Argon remains the lead investigator. Flash handles bounded parallel tasks. Numerical
engines perform calculations. Each component has a defined job.



15. Suggested APIs and sources

            Need              Suggested source                       Qualification

 Prices and instrument     Twelve Data                  Verify exact listings, history,
 discovery                                              adjustments and plan access
 News and optional          Alpha Vantage               Test coverage for selected UK
 ETF metadata                                           instruments

 Broad news discovery       GDELT                       Verify original evidence and archive
                                                        availability

 US company                 SEC EDGAR                   Use filing-specific availability in
 disclosures                                            historical tests

 Economic data and          FRED/ALFRED                 Distinguish information available then
 vintages                                               from later revisions

 Fund characteristics       Issuer                      Exact share-class and dated
 and holdings               documents/downloads         exposure verification

 Public listing checks      Trading 212 catalogue       Identity and availability checks without
                                                        account access

 Evaluation                 AgentVerse finance kit      Supplied cases, price history and
                                                        hidden tests where applicable

The providers document these capabilities; that does not guarantee every selected
instrument is supported on an available plan. twelvedata.com

Start with issuer documents, one price provider, one news source, SEC where relevant and
the event’s test data.

Test a representative equity ETF, bond ETF and stock before committing. Check identity,
currencies, distributions, freshness, historical coverage and licence.

An internal paper ledger is sufficient. Broker integration is not required for current-market
operation.

Unresolved: exact instrument universe and provider entitlements.



16. The beautiful visual workspace

The design reference is a financial terminal operated by agents. It contains persistent
surfaces for portfolio data, prices, news, filings, dependencies, monitors and history.

The interface should feel approachable through hierarchy, not through removing information.

    State                                          Layout

 Start         Lead agent occupies the main canvas

 Delegation    Lead takes the left half; specialists appear on the right
 Work            Up to three readable specialist panels; additional branches in a compact
                 rail

 Inspection      Selected specialist expands, retaining its parent question

 Child task      Enter the branch with clear ancestry

 Review          Findings and contradictions return to the lead

 Completion      Specialists collapse into accessible cards; lead expands with the result

 Replay          Restore the workspace at a recorded event

Each panel shows:

Question → purpose → current action → evidence/output → finding and uncertainty.

Visual components:

          Work                                          Display

 News investigation       Headline, publisher, timestamp, permitted imagery and
                          excerpt

 Filing review            Document preview and highlighted passage

 Claim checking           Supporting and contradicting evidence

 Exposure calculation     Inputs, calculation and result

 Dependency               Labelled graph with source-backed edges
 research

 Tool creation            Purpose, output preview and expandable code

 Tool testing             Test cases and results

 Memory retrieval         Prior case/rule and why it applies

 Scenario analysis        Assumptions and portfolio comparisons

 Decision preparation     Options, checks and uncertainty

Clicking a finding should reveal which source supported it, which calculation used it and
which part of the proposal it affected.

Do not use one generic “verified” badge. Separate:

   ●​   Source retrieved.
   ●​   Claim supported.
   ●​   Relationship current or uncertain.
   ●​   Calculation recomputed.
      ●​ Investment judgement uncertain.

Replay controls:

Previous · Next · Play · Jump to finding · Parent task · Open source · Compare
versions

Changing an assumption creates a new branch. Completed branches remain accessible.

Use a restrained palette, strong typography, precise charts and deliberate motion. Source
imagery must remain identifiable as source material. The interface represents observable
work and concise explanations, not raw hidden model thoughts.



17. Structured events and screens

The backend emits typed events:


  None‎
  {
       "type": "source.inspect",
       "mode": "current_market",
       "run_id": "run_042",
       "agent_id": "supplier_analyst",
       "parent_agent_id": "lead",
       "sequence": 18,
       "title": "Checking alternative suppliers",
       "purpose": "Determine whether the disruption changes the
  investment case",
       "investment_case_id": "case_17",
       "evidence_ids": ["filing_07", "announcement_12"],
       "status": "running"
  }


The renderer selects the component. Actual tool execution produces lifecycle events; the
model cannot fabricate a successful tool return.

Persist timestamps, ancestry, source versions, calculation inputs and results. Technical
drawers can expose code, token usage and latency.

Required screens:

          Screen                              Main interactions

 Workspace entry          Open current portfolio or historical demo
 Goals and mandate       Edit answers, resolve conflicts, begin research

 Agent workspace         Inspect, follow branches, pause/cancel, replay

 Portfolio proposal      Compare, revise, approve

 Portfolio home          Open holding, review investigation, change goal

 Data/research           Search, filter, inspect source, ask
 explorer

 Decision review         Approve, decline, question, request alternative

 History                 Replay runs, compare portfolio versions, review
                         outcomes

 Demo controls           Pause, advance, reset, exit historical mode

Reusable details cover holdings, fund comparisons, evidence, monitors, memory and
settings.

The future scenario explorer lets users change assumptions and compare conditional
portfolio paths. These are scenarios, not promised predictions.



18. Architecture and controls

A practical stack is React/TypeScript, Python/FastAPI, a database, background workers and
isolated execution for generated code.

Required services:

   ●​   Shared clock and mode configuration.
   ●​   Data adapters and evidence storage.
   ●​   Instrument catalogue.
   ●​   Mandate and allocation engines.
   ●​   Agent orchestration.
   ●​   Dependency graph.
   ●​   Monitor compiler and scheduler.
   ●​   Restricted tool execution.
   ●​   Memory and procedure validation.
   ●​   Event store and streaming.
   ●​   Paper ledger and approval service.
   ●​   Evaluation harness.

Controls must cover:

   ●​ Unsupported instruments.
   ●​ Stale prices, holdings or mandates.
   ●​    Currency/unit mismatches.
   ●​    Concentration and cash limits.
   ●​    Costs and rounding.
   ●​    Duplicate orders.
   ●​    Missing data and outages.
   ●​    Generated-tool permissions.
   ●​    External content attempting to issue instructions.

The agents cannot alter the independent risk engine or grant themselves execution authority.

Argon’s documented shared context capacity is 1,048,576 tokens. Use it for the relevant
mandate, cases, filings, memories and specialist findings, while reserving capacity for
outputs. docs.cloud.google.com

The compelling technical demonstration is a connection across time: an earlier filing
establishes a dependency, a new announcement changes it, a tested memory rule identifies
a missing check, and the lead launches that check before preparing a response.



19. Previous winners compared with this product

These comparisons use published descriptions, not independently verified investment
performance.

        Project         Published capability       Verified result        Comparison with
                                                                              yours

 Counterfactual        Dependency graphs,        Winner, AI Broker      Closest visual
                       hypothetical portfolio    Hackathon,             reference. Yours
                       shocks, news impact       Amsterdam, 18          proposes a broader
                       and proposed paper        June 2026.             lifecycle: onboarding,
                       hedges/trims              Five-person team;      construction,
                                                 entrant count and      persistent cases,
                                                 prize amount not       generated monitors
                                                 stated                 and specialist replay

 OrbitSatellite        Satellite imagery and     First place, London,   Strong reference for
                       news for commodity        19 September           distinctive evidence.
                       forecasts and             2026. 43 projects;     Yours focuses
                       supply-chain/procurem     €3,000 + US$2,000      research around
                       ent warnings              DeepMind credits       personal portfolio
                                                                        exposures

 Autonomous            Multi-agent finance       First place,           Demonstrates that this
 Finance Portfolio     platform using Google     in-person              category can win. Your
 Decision-Support      ADK for Java              category, AI           differentiation must be
 Agent & Web                                     DevCamp;               observable workflow
 Platform
                                                 organiser praises       quality, not agent
                                                 architecture            count

 Lancaster              Flags weakening or       Winner, CFA AI          Reference for a
 Disclosure             vague company and        Investment              focused specialist
 Degradation            supplier disclosures     Challenge, 30 April     capability. This was an
 Detection System                                2026. 28 teams, 15      investment
                                                 universities;           competition, not a
                                                 £2,000, plus finalist   weekend hackathon
                                                 scholarships

Sources establish the results and published descriptions. Unknown counts remain unknown;
projects and teams are not participant counts. quantcompetitions.com

Counterfactual’s opening is:

      “Bloomberg shows what happened. Counterfactual shows what happens next.”
      quantcompetitions.com

Your opening uses that direct structure while describing your actual promise:

      “Your broker shows what you own. We investigate whether you should
      still own it.”

Counterfactual has a cleaner single demonstration; Lancaster has a sharper narrow
analytical claim. Your broader lifecycle becomes an advantage only if it works coherently.
The visual investigation system can make that breadth understandable.



20. Evaluation and the actual judging requirements

The Finance slides specify:

            Criterion               Weight                  Required evidence

 Traceable reasoning                25%        Raw evidence to output, with maths separated

 Unseen-data testing                25%        Suitable benchmark, costs and uncertainty

 Controls and oversight             15%        Coded limits, logged actions, one control
                                               shown

 Relevance and impact               20%        Specific user and consequential failure handled

 Ambition and technical quality     15%        Adaptive work beyond a fixed workflow

The slides require paper trading, no real account details/logins, labelled synthetic inputs and
no presentation of backtests as live performance.
Every team is assessed from its deck; only the top three pitch. Evaluation evidence belongs
in the submission and a separate internal interface.

External comparisons:

    Capability                    Baseline                              Measures

 Portfolio          Buy-and-hold, fixed rebalancing,         Net returns, risk, drawdown,
 management         suitable investable benchmark            costs and turnover

 Monitoring         Conventional price/entity/news alerts    Material detections, misses,
                                                             false alerts and delay

 Research           Generic assistant with comparable        Evidence accuracy, coverage
                    data and budget                          and unsupported claims

 Adaptive           Fixed monitor library                    Additional useful detections
 monitors                                                    versus cost and false alerts

 Traceability       Conventional reports/dashboard           Time and accuracy when
                                                             verifying decisions

The planned historical experiment can span approximately five years where the required
data is available.

It needs:

   ●​   Chronological development, validation and final-test periods.
   ●​   Historically eligible instruments and dated holdings.
   ●​   Evidence available at each simulated decision time.
   ●​   Frozen policy/model/monitor versions.
   ●​   Memory learned only from earlier information.
   ●​   Consistent contributions and cashflows across comparisons.
   ●​   Distributions, fees, FX, spreads and execution assumptions.
   ●​   Transparent missing-data handling.
   ●​   Uncertainty reporting and disclosure of tuning attempts.

Five years of prices alone is insufficient for five years of news-driven, dependency-aware
evaluation.

Date filtering cannot erase subsequent events from model training knowledge. Historical
replay and genuinely unseen testing must be reported separately. Use the event’s hidden
tests where applicable, plus current-market forward paper operation.

Memory/no-memory testing supports the procedural-improvement claim internally. The
headline comparison remains the complete product versus existing approaches.



21. What is settled, what is proposed and what remains open
                        Decision                                        Status

 Audience, product lifecycle and visual workspace          Agreed direction

 Persistent cases, adaptive monitors and tested memory Core requirements

 Historical/current modes using the same system            Core requirement

 Paper execution and human approval for the event          Required

 Roughly 20–40 supported instruments                       Proposed weekend scope

 Constrained allocation rather than invented return        Proposed MVP approach
 forecasts

 BGE retrieval and optional GLiNER/reranker                Suggested implementation
                                                           choices

 Exact onboarding allocation policies                      Unresolved

 Candidate ranking and optimiser coefficients              Unresolved

 Trade thresholds, no-action bands and cooldowns           Unresolved

 Monitor activation and resource limits                    Unresolved

 Memory promotion criteria                                 Unresolved

 Exact instrument/provider coverage                        Must be tested

 Five-year evidence dataset and held-out cases             Must be assembled and
                                                           checked

These open choices should be written into configuration and fixed before final testing. They
should not be improvised by agents during evaluation.



22. The weekend build and demonstration

Preserve the complete lifecycle while narrowing breadth:

   1.​ Open a clearly labelled historical scenario.
   2.​ Establish a fictional mandate.
   3.​ Show real instrument candidates and selection evidence.
   4.​ Construct and independently verify the portfolio.
   5.​ Approve paper holdings.
   6.​ Show how a dependency was discovered and supported.
   7.​ Advance to a held-out event.
   8.​ Show the monitor that detected it and how it was created.
   9.​ Split the workspace into specialist investigations.
   10.​Create and test one useful new monitoring capability.
   11.​Compare maintain versus adjust.
   12.​Demonstrate a coded limit blocking an invalid proposal.
   13.​Approve a valid paper adjustment.
   14.​Replay the decision back to its evidence.
   15.​Show a tested memory rule affecting a later investigation.
   16.​Exit historical mode and run the same system against current inputs.

Include a no-action case: an alarming headline that fails the materiality test should leave the
portfolio unchanged.

The defining product moment: the user returns to a portfolio that has remained under
active research, opens a proposed decision, and can visually follow what the team
discovered, investigated, calculated, challenged and concluded.

```

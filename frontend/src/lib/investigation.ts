import type { AgentEvent, RunSummary } from "./types";

const toolLabels: Record<string, string> = {
  get_prices: "Compare price movements", search_news: "Search cached news", get_catalogue: "Review eligible investments",
  correlation_lattice: "Compare holding movements", build_options: "Build portfolio options",
  check_proposal: "Check the investment plan", risk_stats: "Measure portfolio risk", backtest: "Test historical performance",
  exposure: "Measure indirect exposure", overlap: "Check overlapping holdings", cost_turnover: "Estimate trade costs",
  forecast: "Estimate two-week movement", propose_adjustment: "Prepare a portfolio proposal",
  search_filings: "Search company filings", web_search: "Search the web", earnings_calendar: "Check earnings dates",
  get_investment_case: "Review the investment case", save_investment_case: "Save the investment case",
};
export const sourceTools = new Set(["search_news", "search_filings", "web_search"]);
export const outcomeLabels: Record<NonNullable<RunSummary["outcome"]>, string> = {
  built: "Starting portfolio prepared", adjust: "Change proposed", maintain: "Portfolio kept as is",
  investigate_further: "More investigation needed", answered: "Review answered",
};

const number = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value);
const money = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP" });
const percent = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 2 });
export const text = (value: unknown) => typeof value === "string" ? value.trim() : "";
export const record = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
const strings = (value: unknown) => Array.isArray(value) ? value.map(text).filter(Boolean) : [];
const ticker = (value: unknown) => text(value).split(".")[0];
export const roleLabel = (value: unknown) => text(value).replaceAll("_", " ").replace(/\b[a-z]/g, c => c.toUpperCase());
const knownLabel = (labels: Record<string, string>, value: unknown) => {
  const key = text(value);
  return Object.hasOwn(labels, key) ? labels[key] : "";
};
export const outcomeLabel = (value: unknown) => knownLabel(outcomeLabels, value);
export const toolLabel = (value: unknown) => knownLabel(toolLabels, value);

export function recordedValuePoints(values: unknown, asOf?: string) {
  if (!Array.isArray(values)) return [];
  const end = asOf?.slice(0, 10);
  return values.flatMap(row => {
    if (!Array.isArray(row) || typeof row[0] !== "string" || !number(row[1]) || row[1] <= 0) return [];
    const date = row[0].slice(0, 10);
    const time = Date.parse(date);
    return Number.isFinite(time) && (!end || date <= end) ? [{ time, date, value: row[1] }] : [];
  }).sort((a, b) => a.time - b.time);
}

export type Fact = { label: string; value: string };
export type ReportTable = { heading: string; columns: string[]; rows: string[][] };
export type PublicStep = {
  id: string; who: string; heading: string; notes: string[]; method?: string[]; facts: Fact[]; tables: ReportTable[]; sources: string[]; calculations: string[];
};

export function searchScope(event: AgentEvent | undefined): Fact[] {
  if (event?.type !== "tool.call") return [];
  const tool = text(event.payload.tool);
  if (!sourceTools.has(tool)) return [];
  const args = record(event.payload.args);
  const terms = tool !== "search_news" ? text(args.query) : "";
  const instruments = [text(args.ticker), ...strings(args.tickers)].filter(Boolean);
  const since = text(args.since);
  const facts: Fact[] = [];
  if (terms) facts.push({ label: "Search terms", value: terms });
  if (instruments.length && tool !== "web_search") facts.push({ label: "Looking at", value: [...new Set(instruments)].map(ticker).join(", ") });
  if (since && tool !== "web_search") facts.push({ label: "Since", value: since.slice(0, 10) });
  if (!instruments.length && tool === "search_news") facts.unshift({ label: "Looking at", value: "All cached news" });
  return facts;
}

export function searchForStep(event: AgentEvent | undefined, prior: AgentEvent[]) {
  if (event?.type === "tool.call") return searchScope(event);
  if (event?.type !== "tool.result" || event.status === "denied" || !sourceTools.has(text(event.payload.tool))) return [];
  for (let i = prior.length - 1; i >= 0; i--) {
    const step = prior[i];
    if (step.seq >= event.seq || step.agent_id !== event.agent_id || step.payload.tool !== event.payload.tool) continue;
    if (step.type === "tool.call") return searchScope(step);
    if (step.type === "tool.result") break;
  }
  return [];
}

export function safeUrl(value: unknown) {
  try {
    const url = new URL(text(value));
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch { return null; }
}

const calcLabels: Record<string, string> = {
  price_summary: "Price comparison", correlation_lattice: "How the investments move together",
  forecast_2w: "Two-week estimates", agent_view_tilt: "Agent views applied to the estimates", optimise: "Candidate portfolio", check_proposal: "Investment-plan check",
  backtest: "Historical simulation", risk_stats: "Risk comparison", exposure: "Indirect ownership",
  overlap: "Shared investments", cost_turnover: "Trading costs and proposed trades",
};
const methods: Record<string, string[]> = {
  price_summary: ["The comparison uses adjusted closes in GBP. Return = last close ÷ earlier close − 1, using 21, 63, or 252 trading sessions for one month, three months, or one year."],
  correlation_lattice: ["The engine estimates covariance from daily log returns using Ledoit–Wolf shrinkage. It divides each pair’s covariance by the product of their standard deviations to express how closely they move together on a −1 to +1 scale."],
  risk_stats: [
    "Annualised portfolio volatility = √(wᵀΣw), where w is the holding weights and Σ is the Ledoit–Wolf covariance matrix scaled to 252 trading days.",
    "The drawdown calculation compounds daily returns at the given weights and measures the worst value ÷ previous peak − 1. Cash is treated as earning zero in this calculation.",
    "Market sensitivity (beta) = covariance with the global equity reference ÷ variance of that reference. Concentration is the sum of squared holding weights, excluding cash.",
  ],
  forecast_2w: [
    "The forecast gives recent daily log returns more weight. Observation weight is proportional to 0.5 raised to age ÷ half-life.",
    "The weighted mean is shrunk toward zero, then multiplied by 252 for the annualised estimate. When recorded, the range scales log-return mean by the forecast horizon and standard deviation by its square root.",
  ],
  agent_view_tilt: ["Recorded agent views adjust the price-based forecast. Each view contributes its direction × confidence weight × the configured cap. The combined adjustment for each investment is limited to that same cap."],
  optimise: [
    "The optimiser seeks weights with a low combined score for portfolio variance, squared distance from the target shares and bonds mix, estimated trading costs on weight changes, and annual fund fees.",
    "When the return forecast is enabled, the engine subtracts a bounded expected-return term over the forecast horizon. The weight constraints enforce the investment plan’s allocation ranges, cash minimum, and holding caps.",
    "The lower-cost option gives fund fees five times the base weight. The lower-risk option doubles the variance penalty and moves the target toward the lower end of the allowed shares range.",
  ],
  cost_turnover: [
    "The engine estimates costs by applying the proposed trades to a temporary copy of the portfolio.",
    "Turnover = half the sum of the absolute differences between the starting and target weights.",
  ],
  check_proposal: ["The engine checks the proposed weights against the allowed investment list, allocation ranges, holding caps and other recorded investment-plan rules."],
  backtest: [
    "The simulation values the portfolio as the sum of units held × adjusted GBP close. It resets the units to the tested weights at the stated interval.",
    "Returns compound across closes. The worst fall compares each close with the highest value reached so far.",
  ],
  exposure: ["Known indirect exposure adds each fund’s portfolio weight multiplied by its recorded weight in the company. Direct ownership is counted separately when available."],
  overlap: ["For each fund pair, the engine adds the lower of the two fund weights for each shared constituent. A missing constituents list makes the overlap unavailable."],
};
const metricLabels: [string, string, (value: number) => string][] = [
  ["total_return", "Historical return", percent.format], ["vol_annual", "Annualised volatility", percent.format],
  ["max_drawdown", "Worst historical fall", percent.format], ["max_drawdown_backtest", "Worst historical fall", percent.format],
  ["cash_weight", "Cash allocation", percent.format], ["ocf_weighted", "Estimated annual fund fee rate", percent.format],
  ["turnover", "Share of the portfolio traded", percent.format], ["cost_gbp", "Estimated trading cost", money.format],
  ["total", "Total exposure", percent.format], ["known_total", "Known portion of exposure", percent.format],
  ["direct", "Direct exposure", percent.format], ["beta_vs_global_equity", "Market sensitivity (beta)", value => value.toFixed(2)],
  ["herfindahl", "Concentration score", value => value.toFixed(3)], ["sharpe", "Return per unit of risk (Sharpe)", value => value.toFixed(2)],
  ["avg_pairwise", "Average movement together (−1 to +1)", value => value.toFixed(2)], ["history_days", "Trading days in the analysis", String],
];
const gates: Record<string, string> = {
  injection_guard: "Source safety", evidence: "Evidence", numbers: "Calculations", mandate: "Investment plan",
  critic: "Independent review", compliance: "Compliance", qa: "Final review", revalidation: "Recheck before trading",
};
const verdicts: Record<string, string> = {
  pass: "Passed", pass_with_flags: "Passed with notes", fail: "Needs attention", skipped: "Skipped", pending: "Pending",
};
const confidenceLabel = (value: unknown) => knownLabel({ low: "Low", med: "Medium", high: "High" }, value);
const price = (value: unknown) => number(value) ? money.format(value) : "Unavailable";
const rate = (value: unknown) => number(value) ? percent.format(value) : "Unavailable";

function calculation(step: PublicStep, payload: AgentEvent["payload"], asOf: string) {
  const name = text(payload.name);
  const output = record(payload.outputs);
  const input = record(payload.inputs);
  step.heading = knownLabel(calcLabels, name) || "Recorded calculation";
  if (Object.hasOwn(methods, name)) step.method = methods[name];
  const option = ({ recommended: "Recommended option", lower_cost: "Lower-cost option", lower_risk: "Lower-risk option" } as Record<string, string>)[text(input.variant ?? input.option)];
  if (name === "optimise" && option) step.heading += " · " + option;
  const instruments = strings(input.tickers ?? input.candidates).map(ticker);
  if (instruments.length) step.facts.push({ label: "Investments considered", value: instruments.join(", ") });
  for (const [value, label] of [[input.lookback, "Requested history (trading days)"], [output.horizon_days ?? input.horizon, "Forecast horizon (trading days)"],
    [output.halflife_days, "Forecast half-life (trading days)"]] as const) if (number(value)) step.facts.push({ label, value: String(value) });
  for (const [value, label] of [[output.start ?? input.start, "Start date"], [output.end ?? input.end, "End date"],
    [output.rebalance, "Rebalance interval"], [input.entity, "Company checked"]] as const) if (text(value)) step.facts.push({ label, value: text(value) });
  if (name === "agent_view_tilt" && number(output.cap)) step.facts.push({ label: "Maximum annualised forecast adjustment", value: rate(output.cap) });
  for (const [key, label, format] of metricLabels) {
    const value = output[key];
    if (number(value)) step.facts.push({ label, value: format(value) });
  }
  if (name === "exposure" && output.total === null) step.notes.push("Total exposure could not be measured because some fund constituent data was unavailable.");
  if (name === "backtest") step.notes.push("This result comes from a simulation on historical prices.");
  if (name === "forecast_2w") step.notes.push("These are model estimates, which can differ from future returns.");
  if (output.short_history === true) step.notes.push("This calculation used a shorter price history.");
  if (output.passed === false) step.notes.push("The candidate needed changes to fit the investment plan.");
  if (output.passed === true) step.notes.push("The candidate fit the investment plan.");
  if (Array.isArray(output.violations)) step.notes.push(...output.violations.map(issue => text(record(issue).message)).filter(Boolean));
  function table(heading: string, columns: string[], rows: string[][]) {
    if (rows.length) step.tables.push({ heading, columns, rows });
  }
  if (name === "price_summary" && Array.isArray(output.rows)) table("Prices the agent compared",
    ["Investment", "Last close", "1-month move", "3-month move", "1-year move", "Annual volatility"],
    output.rows.map(record).filter(row => ticker(row.ticker)).map(row => [
      ticker(row.ticker), price(row.last_gbp), rate(row.ret_1m), rate(row.ret_3m), rate(row.ret_1y), rate(row.vol_annual),
    ]));
  if (name === "forecast_2w" && Array.isArray(output.assets)) table("Recorded forecast ranges",
    ["Investment", "10th percentile", "Median", "90th percentile", "Observations"], output.assets.map(record).filter(row => ticker(row.ticker))
      .map(row => [ticker(row.ticker), rate(record(row.band).p10), rate(record(row.band).p50), rate(record(row.band).p90), number(row.obs) ? String(row.obs) : "Unavailable"]));
  if (name === "agent_view_tilt" && Array.isArray(output.tilts)) table("Effect of the agent views",
    ["Investment", "Before", "Adjustment", "After"], output.tilts.map(record).filter(row => ticker(row.ticker))
      .map(row => [ticker(row.ticker), rate(row.mu_before), rate(row.tilt), rate(row.mu_after)]));
  if (name === "agent_view_tilt" && Array.isArray(input.views)) table("Recorded views",
    ["Investment", "Agent", "Direction", "Confidence"], input.views.map(record).filter(row => ticker(row.ticker))
      .map(row => [ticker(row.ticker), roleLabel(row.role), text(row.direction), confidenceLabel(row.confidence)]));
  const path = recordedValuePoints(output.backtest_nav ?? output.nav, asOf);
  if (path.length > 1) {
    const sample = [path[0], ...(path.length > 2 ? [path[Math.floor(path.length / 2)]] : []), path[path.length - 1]];
    table("Selected points from the historical simulation", ["Date", "Simulated value"], sample.map(point => [point.date, price(point.value)]));
  }
  if (name === "overlap" && Array.isArray(output.pairs)) table("Common investments", ["First holding", "Second holding", "Shared weight"],
    output.pairs.map(record).filter(row => ticker(row.a) && ticker(row.b)).map(row => [ticker(row.a), ticker(row.b), rate(row.overlap)]));
  if (Array.isArray(output.trades)) table("Trades considered", ["Investment", "Action", "Amount"],
    output.trades.map(record).filter(row => ticker(row.ticker) && (row.action === "buy" || row.action === "sell"))
      .map(row => [ticker(row.ticker), row.action === "buy" ? "Buy" : "Sell", price(row.amount_gbp)]));
  for (const [value, heading, column] of [
    [output.weights, "Candidate allocation", "Target weight"], [input.weights, "Weights used in the calculation", "Weight"],
    [output.via_funds, "Exposure through funds", "Measured share"],
    [output.mu, "Estimated returns by investment", "Annualised estimate"],
  ] as const) table(heading, ["Investment", column], Object.entries(record(value)).filter(([, amount]) => number(amount))
    .map(([symbol, amount]) => [ticker(symbol), rate(amount)]));
  if (name === "correlation_lattice" && Array.isArray(output.matrix)) {
    const tickers = strings(output.tickers);
    const matrix = output.matrix;
    const pairs = tickers.flatMap((symbol, i) => tickers.slice(i + 1).flatMap((other, j) => {
      const row = matrix[i];
      const value: unknown = Array.isArray(row) ? row[i + j + 1] : undefined;
      return number(value) ? [{ symbol, other, value }] : [];
    }));
    table("Strongest recorded relationships", ["First holding", "Second holding", "Correlation"], pairs
      .sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, 10)
      .map(row => [ticker(row.symbol), ticker(row.other), row.value.toFixed(2)]));
  }
  if (name === "correlation_lattice" && Array.isArray(output.callouts)) {
    step.notes.push(...output.callouts.map(callout => text(record(callout).text)).filter(Boolean));
  }
}

export function publicSteps(events: AgentEvent[]) {
  const roles = new Map(events.filter(event => event.type === "agent.spawned").map(event =>
    [event.agent_id, roleLabel(event.role || event.payload.role)]));
  const calcOwners = new Map(events.filter(event => event.type === "tool.result" && event.agent_id)
    .flatMap(event => event.evidence_ids.filter(id => id.startsWith("calc:")).map(id => [id.slice(5), event.agent_id] as const)));
  const steps: PublicStep[] = [];
  for (const event of [...events].sort((a, b) => a.seq - b.seq)) {
    const p = event.payload;
    const refs = [...new Set([...(event.evidence_ids ?? []), ...strings(p.evidence_ids)])];
    const owner = event.agent_id ?? (event.type === "calc.result" ? calcOwners.get(event.id) : null);
    const step: PublicStep = {
      id: event.id, who: roleLabel(event.role) || roles.get(owner ?? null) || "Investigation",
      heading: "", notes: [], facts: [], tables: [],
      sources: refs.filter(id => !id.startsWith("calc:")), calculations: refs.filter(id => id.startsWith("calc:")).map(id => id.slice(5)),
    };
    const note = (value: unknown) => { if (text(value)) step.notes.push(text(value)); };
    switch (event.type) {
      case "agent.spawn_requested":
        step.heading = "Asked " + (roleLabel(p.role) || "a specialist") + " to investigate";
        note(p.question); note(p.purpose);
        break;
      case "agent.spawned":
        step.heading = "Joined the investigation"; note(event.purpose || p.question); break;
      case "agent.message":
        step.heading = "Explained the next step"; note(p.text); break;
      case "tool.call": {
        const tool = text(p.tool);
        step.heading = toolLabel(tool) || "Reviewed portfolio information";
        step.facts.push(...searchScope(event));
        const instruments = strings(record(p.args).tickers);
        if (!sourceTools.has(tool) && instruments.length) step.facts.push({ label: "Investments", value: instruments.map(ticker).join(", ") });
        break;
      }
      case "tool.result": {
        const tool = text(p.tool);
        step.heading = (toolLabel(tool) || "Portfolio review") + (p.ok === false ? " · Unavailable" : " · Result");
        if (p.ok === false) note("This step could not be completed.");
        else if (step.sources.length) note(step.sources.length + (step.sources.length === 1 ? " recorded source." : " recorded sources."));
        else if (sourceTools.has(tool)) note("No matching sources were returned.");
        else note("The check completed.");
        break;
      }
      case "calc.result": calculation(step, p, event.as_of); break;
      case "source.inspect": step.heading = "Reviewed a source"; note(p.title); break;
      case "finding":
        step.heading = "Finding"; note(p.claim);
        if (text(p.recommendation)) note("Recommendation. " + (outcomeLabel(p.recommendation) || text(p.recommendation)));
        if (confidenceLabel(p.confidence)) step.facts.push({ label: "Agent confidence", value: confidenceLabel(p.confidence) });
        for (const uncertainty of strings(p.uncertainties)) note("Uncertainty. " + uncertainty);
        break;
      case "decision.made":
        step.heading = outcomeLabel(p.action) || "Lead decision"; note(p.reason); break;
      case "proposal.created":
        step.heading = "Prepared a portfolio proposal"; note("This records the recommendation for review."); break;
      case "approval.requested": step.heading = "Asked for approval"; break;
      case "approval.decided":
        step.heading = p.decision === "approve" || p.decision === "approved" ? "Proposal approved" :
          p.decision === "decline" || p.decision === "declined" ? "Proposal declined" : "Approval decision recorded";
        if (p.by === "batch_policy") note("Decision made by the recorded simulation policy.");
        if (p.by === "user_policy") note("Decision made under the saved approval limit.");
        if (text(p.fill_date)) note("Scheduled trading date. " + text(p.fill_date));
        note(p.reason);
        break;
      case "gate.verdict":
        step.heading = (knownLabel(gates, p.gate) || "Assurance check") + " · " + (knownLabel(verdicts, p.status) || "Recorded");
        step.notes.push(...strings(p.issues), ...strings(p.required_changes));
        break;
      case "revision.requested":
        step.heading = "Asked for a revised proposal"; step.notes.push(...strings(p.points)); break;
      case "order.filled":
        step.heading = (p.action === "sell" ? "Sold " : "Bought ") + (ticker(p.ticker) || "investment");
        step.facts.push({ label: "Amount", value: price(p.amount_gbp) }, { label: "Trading cost", value: price(p.cost_gbp) });
        break;
      case "rule.proposed": case "rule.tested": case "rule.promoted": case "rule.applied":
        step.heading = event.type === "rule.proposed" ? "Suggested a review rule" : event.type === "rule.tested" ? "Tested a review rule" :
          event.type === "rule.promoted" ? "Adopted a review rule" : "Applied a review rule";
        note(p.text); break;
      case "content.quarantined":
        step.heading = "Set aside an unsafe source"; step.sources = []; step.calculations = []; break;
      case "run.completed":
        step.heading = event.status === "failed" ? "Investigation stopped" : outcomeLabel(p.outcome) || "Investigation completed"; break;
    }
    if (step.heading) steps.push(step);
  }
  return steps;
}

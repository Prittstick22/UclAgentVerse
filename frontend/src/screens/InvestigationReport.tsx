import { useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { FilledAllocation, RecordedValuePath } from "../components/InvestigationFigures";
import { get, mockEvents, MOCK } from "../lib/api";
import { investigationTitle, outcomeLabel, publicNarrative, publicSteps, record, roleLabel, safeUrl, text } from "../lib/investigation";
import type { AgentEvent, DecisionCard, NewsFeed, PortfolioRebalances, RunSummary } from "../lib/types";
import { useResource } from "../lib/useResource";
import { gbp, pct, recordedFixture } from "./Decisions";
import "./investigation-report.css";

type Source = { title: string; publisher: string; url: string | null; date?: string; excerpt?: string; unavailable?: boolean; news?: boolean };
type Proposal = { decision_card: DecisionCard; kind?: string };

const modelDocs = new Map([
  ["gemini-4-argon", "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/4-argon"],
  ["gemini-3.8-flash", "https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash"],
]);
const covarianceDocs = ["Covariance estimator · scikit-learn", "https://scikit-learn.org/stable/modules/generated/sklearn.covariance.LedoitWolf.html"];
const calculationDocs = new Map([
  ["optimise", ["Quadratic optimisation · CVXPY", "https://www.cvxpy.org/examples/basic/quadratic_program.html"]],
  ["risk_stats", covarianceDocs],
  ["correlation_lattice", covarianceDocs],
]);

async function optionalRead(path: string, signal: AbortSignal) {
  try {
    const response = await fetch("/api" + path, { signal });
    return response.ok ? await response.json() as unknown : null;
  } catch { return null; }
}

async function loadSources(ids: string[], events: AgentEvent[], signal: AbortSignal) {
  const sources = new Map<string, Source[]>();
  const inspected = new Map(events.filter(event => event.type === "source.inspect")
    .flatMap(event => event.evidence_ids.map(id => [id, event.payload] as const)));
  const mockNews = MOCK ? await get<NewsFeed>("/news", "news", signal) : null;
  for (let i = 0; i < ids.length && !signal.aborted; i += 6) {
    await Promise.all(ids.slice(i, i + 6).map(async id => {
      const details = inspected.get(id);
      const web = id.startsWith("web:") && Array.isArray(details?.sources) ? details.sources.flatMap(value => {
        const item = record(value);
        const url = safeUrl(item.url);
        if (!url) return [];
        const publisher = new URL(url).hostname;
        return [{ title: text(item.title) || publisher, publisher, url }];
      }) : [];
      if (web.length) { sources.set(id, web); return; }
      const saved = mockNews?.items.find(item => item.id === id);
      const item = MOCK ? record(saved ? {
        kind: "news", title: saved.headline, source: saved.source, published_at: saved.published_at, url: saved.url, excerpt: saved.summary,
      } : null) : id.startsWith("web:") ? {} : record(await optionalRead("/evidence/" + encodeURIComponent(id), signal));
      const url = item.quarantined ? null : safeUrl(item.url) ?? safeUrl(details?.url);
      sources.set(id, [{
        title: text(item.title || details?.title) || "Recorded source",
        publisher: item.quarantined ? "Set aside by the source safety check" : text(item.source || details?.source),
        date: text(item.published_at || details?.published_at).slice(0, 10),
        excerpt: item.quarantined ? "" : text(item.excerpt),
        url, news: item.kind === "news" || details?.kind === "news", unavailable: !item.quarantined && !Object.keys(item).length && !details,
      }]);
    }));
  }
  return sources;
}

function formatDate(date: string) {
  const parsed = new Date(date);
  return Number.isFinite(parsed.getTime()) ? new Intl.DateTimeFormat("en-GB", { dateStyle: "long", timeZone: "UTC" }).format(parsed) : date;
}

export default function InvestigationReport({ source }: { source?: string }) {
  const { runId = "" } = useParams();
  const path = "/runs/" + encodeURIComponent(runId);
  const report = useResource(path, async signal => {
    const [run, events] = await Promise.all([
      get<RunSummary>(path, "run_detail", signal),
      MOCK ? Promise.resolve({ items: mockEvents().filter(event => event.run_id === runId) }) :
        get<{ items: AgentEvent[] }>(path + "/events?format=json", "", signal),
    ]);
    if (run.run_id !== runId || !events.items.length) throw new Error("No recorded steps were found for this investigation.");
    return { run, events: events.items };
  });
  const steps = useMemo(() => publicSteps(report.value?.events ?? []), [report.value]);
  const recordedCalculations = useMemo(() => new Map(report.value?.events.filter(event => event.type === "calc.result")
    .map(event => [event.id, event])), [report.value]);
  const sourceIds = [...new Set(steps.flatMap(step => step.sources))];
  const stepNumber = new Map(steps.map((step, index) => [step.id, index + 1]));
  const sources = useResource(report.value ? path + ":sources" : "", signal =>
    report.value ? loadSources(sourceIds, report.value.events, signal) : Promise.resolve(new Map<string, Source[]>()));
  const run = report.value?.run;
  const proposalId = run?.proposal_id;
  const changes = useResource(run ? path + ":changes" : "", async signal => {
    if (!run) return { proposal: null, filled: [] };
    if (MOCK) {
      const rebalances = await get<PortfolioRebalances>("/portfolio/rebalances", "rebalances", signal);
      const hasProposal = report.value?.events.some(event => event.type === "proposal.created" && event.payload.proposal_id === proposalId);
      return { proposal: proposalId && hasProposal ? recordedFixture(proposalId) : null,
        filled: rebalances.items.filter(item => item.run_id === runId) };
    }
    const [proposal, rebalances] = await Promise.all([
      proposalId ? optionalRead("/proposals/" + encodeURIComponent(proposalId), signal) : Promise.resolve(null),
      optionalRead("/portfolio/rebalances?limit=500", signal),
    ]);
    return { proposal: proposal as Proposal | null,
      filled: ((rebalances as PortfolioRebalances | null)?.items ?? []).filter(item => item.run_id === runId) };
  });
  const ready = Boolean(run && sources.value && changes.value);
  const reason = report.value?.events.slice().reverse().find(event => event.type === "decision.made")?.payload.reason;
  const filledInEvents = report.value?.events.some(event => event.type === "order.filled");
  const proposed = changes.value?.proposal?.decision_card;
  const latestFill = changes.value?.filled.reduce<PortfolioRebalances["items"][number] | undefined>(
    (latest, fill) => !latest || fill.date > latest.date ? fill : latest, undefined);
  const outcome = run?.status === "failed" ? "Investigation stopped" : run?.status === "running" ? "Investigation still in progress" :
    run?.status === "cancelled" ? "Investigation cancelled" : outcomeLabel(run?.outcome) || "Investigation completed";

  return <div className="investigation-report">
    <nav className="investigation-report-actions" aria-label="Report actions">
      <Link className="mvp-action" to={path + (run?.status === "running" ? "?live=1" : "?replay=1")}>Back to investigation</Link>
      <button className="mvp-action primary" type="button" disabled={!ready} onClick={() => window.print()}>Print / Save as PDF</button>
    </nav>
    <article className="investigation-report-paper" aria-busy={!report.error && !ready}>
      <header>
        <h1>Investigation report</h1>
        {run && <p>{formatDate(run.as_of)} · {report.value?.events[0]?.mode === "live" ? "Live paper portfolio" : "Recorded paper portfolio"}
          {(MOCK || source === "synthetic") && " · Synthetic data"}</p>}
      </header>
      {report.error ? <p role="alert">{report.error}</p> : !run ? <p role="status">Loading the recorded investigation…</p> : <>
        <section>
          <h2>Why the investigation started</h2>
          <p>{run.trigger_text ? investigationTitle(run.trigger_text, run.kind) : "The reason for starting this investigation was not recorded."}</p>
        </section>
        <section>
          <h2>What the lead concluded</h2>
          <p><strong>{outcome}</strong></p>
          {publicNarrative(reason) && <p>{publicNarrative(reason)}</p>}
          {run.status === "running" && <p>This report includes the steps recorded when it was opened.</p>}
        </section>
        <section>
          <h2>Portfolio decisions and trades</h2>
          {proposed && <><p><strong>{publicNarrative(proposed.headline)}</strong></p><p>{publicNarrative(proposed.body)}</p>
            {proposed.changes.length > 0 && <table><caption>Proposed changes</caption>
              <thead><tr><th>Investment</th><th>Action</th><th>Estimated amount</th><th>Weight before</th><th>Target weight</th></tr></thead>
              <tbody>{proposed.changes.map((change, index) => <tr key={change.ticker + index}>
                <th scope="row">{change.ticker}</th><td>{change.action === "sell" ? "Sell" : "Buy"}</td><td>{gbp.format(change.amount_gbp)}</td>
                <td>{pct.format(change.from_weight)}</td><td>{pct.format(change.to_weight)}</td>
              </tr>)}</tbody>
            </table>}
          </>}
          <FilledAllocation fill={latestFill} />
          {changes.value?.filled.length ? <table><caption>Completed paper trades</caption>
            <thead><tr><th>Date</th><th>Investment</th><th>Action</th><th>Amount</th><th>Weight after</th></tr></thead>
            <tbody>{changes.value.filled.flatMap(fill => fill.changes.map((change, index) => <tr key={fill.date + change.ticker + index}>
              <td>{formatDate(fill.date)}</td><th scope="row">{change.ticker}</th><td>{change.action === "sell" ? "Sell" : "Buy"}</td>
              <td>{gbp.format(change.amount_gbp)}</td><td>{pct.format(change.to_weight)}</td>
            </tr>))}</tbody>
          </table> : <p>{!changes.value ? "Checking recorded trades…" :
            filledInEvents ? "Recorded trades are listed in the investigation steps below." : "No filled changes are recorded for this investigation."}</p>}
        </section>
        {run.agents.length > 0 && <section>
          <h2>Agents and models</h2>
          <p>These are the recorded assignments and models. The calculation methods appear alongside the results each agent considered.</p>
          <table><thead><tr><th scope="col">Agent</th><th scope="col">Recorded model</th><th scope="col">Assignment</th></tr></thead>
            <tbody>{run.agents.map(agent => <tr key={agent.agent_id}><th scope="row">{roleLabel(agent.role)}</th>
              <td>{modelDocs.has(agent.model)
                ? <a href={modelDocs.get(agent.model)} target="_blank" rel="noreferrer">{agent.model}</a>
                : agent.model || "Unavailable"}</td><td>{agent.purpose || agent.question}</td></tr>)}</tbody>
          </table>
        </section>}
        <section>
          <h2>How the investigation unfolded</h2>
          <ol className="investigation-report-steps">{steps.map(step => {
            const calculation = recordedCalculations.get(step.id);
            const reference = calculationDocs.get(text(calculation?.payload.name));
            return <li key={step.id} id={"report-step-" + stepNumber.get(step.id)}>
            <h3>{step.heading}</h3><p className="investigation-report-byline">{step.who}</p>
            {step.notes.map(publicNarrative).filter(Boolean).map((note, index) => <p key={index}>{note}</p>)}
            {step.method && <div className="investigation-report-method"><strong>How the calculation works</strong>
              {step.method.map(note => <p key={note}>{note}</p>)}
              {reference && <a href={reference[1]} target="_blank" rel="noreferrer">{reference[0]}</a>}
            </div>}
            {step.facts.length > 0 && <dl>{step.facts.map((fact, index) => <div key={index}><dt>{fact.label}</dt><dd>{fact.value}</dd></div>)}</dl>}
            <RecordedValuePath event={calculation} asOf={run.as_of} />
            {step.tables.map(table => <table key={table.heading}><caption>{table.heading}</caption>
              <thead><tr>{table.columns.map(column => <th key={column} scope="col">{column}</th>)}</tr></thead>
              <tbody>{table.rows.map((row, index) => <tr key={index}>{row.map((cell, col) => <td key={col}>{cell}</td>)}</tr>)}</tbody>
            </table>)}
            {step.calculations.some(id => stepNumber.has(id)) && <p className="investigation-report-citations">See calculation {step.calculations
              .filter(id => stepNumber.has(id)).map(id => <a key={id} href={"#report-step-" + stepNumber.get(id)}>{stepNumber.get(id)}</a>)}</p>}
            {step.sources.length > 0 && <p className="investigation-report-citations">Evidence {step.sources.map(id => {
              const citation = sourceIds.indexOf(id) + 1;
              return <a key={id} href={"#report-source-" + citation}>[{citation}]</a>;
            })}</p>}
            </li>;
          })}</ol>
        </section>
        {sourceIds.length > 0 && <section>
          <h2>Sources considered</h2>
          {!sources.value ? <p role="status">Loading recorded source details…</p> : <ol className="investigation-report-sources">
            {sourceIds.map((id, index) => <li id={"report-source-" + (index + 1)} key={id}>
              {sources.value?.get(id)?.map((item, j) => <div key={j}>
                <p><strong>{item.title}</strong>{item.publisher && " · " + item.publisher}{item.date && " · " + formatDate(item.date)}</p>
                {item.excerpt && <blockquote>{item.excerpt}</blockquote>}
                {item.url && <a className="investigation-report-url" href={item.url} target="_blank" rel="noreferrer">{item.news ? "Read original article" : "Open original source"} · {new URL(item.url).hostname}</a>}
                {item.unavailable && <p>Source details are unavailable in this recording.</p>}
              </div>)}
            </li>)}
          </ol>}
        </section>}
      </>}
    </article>
  </div>;
}

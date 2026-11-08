import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import AgentAvatar from "../components/AgentAvatar";
import { ShellIcon } from "../components/TerminalShellUi";
import { api, ApiError, get, MOCK, put } from "../lib/api";
import { useResource } from "../lib/useResource";
import type { DemoPersona, DemoProfile, Mandate, Mode, ProfileResult, Question } from "../lib/types";
import "./mvp.css";

type Profile = { profile: ProfileResult; mandate: Mandate };

const percentField = (value: number) => Math.round(value * 100) + "%";
const loadDemoProfile = (signal: AbortSignal) => get<DemoProfile>("/profile/demo", "demo_profile", signal);
const demoPersonas: DemoPersona[] = ["priya", "caroline"];

export default function Quiz({ mode, liveRunsEnabled, changing, onMode, complete }: {
  mode?: Mode; liveRunsEnabled: boolean; changing: boolean; onMode: (mode: Mode, persona?: DemoPersona) => Promise<boolean>; complete: (mode: Mode, room: string) => void;
}) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Profile | null>(null);
  const [entry, setEntry] = useState<Mode>("historical");
  const demos = useResource("demo-profiles", api.demos);
  const [persona, setPersona] = useState<DemoPersona>("priya");
  const demo = entry === "historical" ? demos.value?.[persona] : undefined;
  const [busy, setBusy] = useState(false);
  const [confirmingAnswer, setConfirmingAnswer] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef<number>();
  const title = useRef<HTMLHeadingElement>(null);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requestedDemo = useRef(params.get("demo"));

  useEffect(() => {
    if (!demos.value || !requestedDemo.current) return;
    const selected = demoPersonas.find(id => id === requestedDemo.current);
    requestedDemo.current = null;
    if (selected && demos.value[selected] && step === 0 && entry === "historical") {
      setPersona(selected);
      setStep(1);
    }
  }, [demos.value, entry, step]);

  useEffect(() => {
    const abort = new AbortController();
    get<{ questions: Question[] }>("/profile/questions", "questions", abort.signal).then(({ questions }) => setQuestions(questions))
      .catch((e: Error) => { if (!abort.signal.aborted) setError(e.message); });
    return () => { abort.abort(); window.clearTimeout(timer.current); };
  }, []);

  async function enterMode(next: Mode) {
    setBusy(true);
    setError("");
    try {
      if (!await onMode(next, next === "historical" ? persona : undefined)) throw new Error("Couldn’t open this workspace. Try again.");
      if (next === "historical") {
        complete("historical", "/timeline");
        navigate("/");
      } else setStep(1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function choose(question: Question, option: string) {
    if (timer.current !== undefined || busy) return;
    const next = { ...answers, [question.id]: option };
    setAnswers(next);
    setError("");
    setConfirmingAnswer(true);
    timer.current = window.setTimeout(async () => {
      setConfirmingAnswer(false);
      if (step < questions.length) {
        timer.current = undefined;
        setStep(step + 1);
        return;
      }
      setBusy(true);
      try { setResult(await api.quiz(next)); setStep(step + 1); }
      catch (e) { setError((e as Error).message); }
      finally { timer.current = undefined; setBusy(false); }
    }, 160);
  }

  async function build(mandate: Mandate) {
    setError("");
    setBusy(true);
    try {
      const saved = await put("/mandate", mandate, "mandate");
      setResult(previous => previous && { ...previous, mandate: saved });
      const { run_id } = await api.build();
      const room = "/runs/" + encodeURIComponent(run_id) + "?live=1";
      complete("live", room);
      navigate(room);
    } finally { setBusy(false); }
  }

  const question = questions[step - 1];
  const answerLocked = confirmingAnswer || busy;
  const isDemo = step > 0 && demo;
  const count = isDemo ? 2 : questions.length + 2;
  const heading = step === 0 ? "Welcome to Stead" : isDemo ? "Meet " + demo.name :
    question ? question.text : "Review your investment plan";
  useEffect(() => { title.current?.focus(); }, [step, heading]);

  return <div className="onboard">
    {step > 0 && <div className="onboard-progress" aria-label={"Step " + (step + 1) + " of " + count}>
      {Array.from({ length: count }, (_, i) => <span key={i} data-state={i === step ? "current" : i < step ? "done" : "next"} />)}
    </div>}
    <section key={step} className="onboard-step mvp-enter" data-welcome={step === 0 || undefined} aria-busy={busy || changing}>
      <svg className="onboard-outline" viewBox="0 0 180 180" fill="none" stroke="currentColor" aria-hidden="true">
        <rect x="28" y="47" width="112" height="94" rx="12" /><path d="M62 47V34a8 8 0 0 1 8-8h28a8 8 0 0 1 8 8v13M28 79h112M71 79v14h26V79M58 119l17-14 15 7 20-18" />
      </svg>
      <AgentAvatar role="lead" />
      <h1 ref={title} tabIndex={-1}>{heading}</h1>
      {step === 0 ? <>
        <p>Your AI investment team builds and monitors a paper portfolio around your goals and how much risk you’re comfortable taking.</p>
        {liveRunsEnabled && <fieldset className="onboard-entry" disabled={busy || changing}>
          <legend>We recommend trying the demo first</legend>
          <div>
            <label className="glass-feedback">
              <input type="radio" name="onboarding-mode" checked={entry === "historical"} aria-labelledby="entry-demo-title" aria-describedby="entry-demo-description"
                onChange={() => { setEntry("historical"); setError(""); }} />
              <ShellIcon name="clock" />
              <strong id="entry-demo-title">Watch a demo</strong>
              <span id="entry-demo-description">Replay a completed simulation, including the agents’ recorded model calls. Pause or speed up the timeline to inspect their decisions.</span>
            </label>
            <label className="glass-feedback">
              <input type="radio" name="onboarding-mode" checked={entry === "live"} aria-labelledby="entry-live-title" aria-describedby="entry-live-description"
                onChange={() => { setEntry("live"); setError(""); }} />
              <ShellIcon name="chart" />
              <strong id="entry-live-title">Use the app live</strong>
              <span id="entry-live-description">Skip the demo and set up your own paper portfolio with current market data. Live research takes longer because the agents run their checks in real time.</span>
            </label>
          </div>
        </fieldset>}
        {entry === "historical" && <section className="onboard-demo-list mvp-enter" aria-labelledby="onboard-demo-heading">
          <h2 id="onboard-demo-heading">Choose a demo profile</h2>
          {demos.value ? <div className="onboard-options">{demoPersonas.map(id => {
            const profile = demos.value?.[id];
            return profile && <button key={id} className="glass-feedback" disabled={busy || changing}
              onClick={() => { setPersona(id); setError(""); setStep(1); }}>
              <strong>{profile.name}</strong>
              <span>{profile.profile === "aggressive" ? "Higher-risk portfolio" : "Lower-risk portfolio"} · Full portfolio replay</span>
            </button>;
          })}</div> : demos.error ? <>
            <p role="alert">Couldn’t load the demo profiles.</p>
            <button type="button" className="mvp-action" onClick={() => window.location.reload()}>Try again</button>
          </> : <p role="status">Loading demo profiles…</p>}
        </section>}
        {liveRunsEnabled && entry === "live" && <button className="mvp-action onboard-start mvp-enter" disabled={busy || changing || !mode}
          onClick={() => void enterMode("live")}>{busy || changing ? "Opening live setup…" : "Let’s go"}</button>}
      </> : isDemo ? <>
        <p>{demo.story}</p>
        <dl className="onboard-demo-scores">
          <div><dt>Comfort with risk</dt><dd>{percentField(demo.result.tolerance_score)}</dd></div>
          <div><dt>Ability to absorb a loss</dt><dd>{percentField(demo.result.capacity_score)}</dd></div>
          <div><dt>Investment profile</dt><dd>{demo.profile}</dd></div>
        </dl>
        {demo.mandate.caps.stocks_min != null && <>
          <p>Target allocation · Shares {demo.mandate.ranges.equity.map(percentField).join("–")} · Bonds {demo.mandate.ranges.bond.map(percentField).filter((value, index, values) => index === 0 || value !== values[0]).join("–")}
            {" · Individual stocks " + [demo.mandate.caps.stocks_min, demo.mandate.caps.stocks_total].map(percentField).join("–")}</p>
          {questions.length > 0 && <details className="desk-disclosure onboard-demo-answers">
            <summary>See {demo.name}’s answers</summary>
            <dl>{questions.map(question => <div key={question.id}>
              <dt>{question.text}</dt><dd>{question.options.find(option => option.id === demo.answers[question.id])?.label}</dd>
            </div>)}</dl>
          </details>}
        </>}
        <button className="mvp-action primary" disabled={busy || changing || !mode}
          onClick={() => void enterMode("historical")}>{busy ? "Opening demo…" : "Explore demo"}</button>
      </> : question ? <>
        <p>{question.help}</p>
        <div className="onboard-options" role="group" aria-label="Answer choices">{question.options.map(option => {
          const selected = answers[question.id] === option.id;
          return <button key={option.id} aria-pressed={selected} disabled={answerLocked && !selected}
            aria-disabled={answerLocked && selected || undefined}
            onClick={() => choose(question, option.id)}>{option.label}</button>;
        })}</div>
      </> : result ? <MandateReview mandate={result.mandate} profile={result.profile} busy={busy} submit={build} /> : <p role="status">Loading questions…</p>}
      {error && <p className="mvp-error" role="alert">{error}</p>}
      {step > 0 && <button className="mvp-action" disabled={busy} onClick={() => {
        window.clearTimeout(timer.current); timer.current = undefined;
        setConfirmingAnswer(false); setError(""); setStep(step - 1);
      }}>Back</button>}
    </section>
  </div>;
}

const planFieldLabels: Record<string, string> = {
  "ranges.equity": "Shares range",
  "ranges.bond": "Bonds range",
  "ranges.cash_min": "Cash minimum",
  "caps.per_fund": "Fund cap",
  "caps.per_stock": "Stock cap",
  "caps.stocks_total": "All stocks cap",
  "caps.stocks_min": "Stocks minimum",
  "goal.starting_amount_gbp": "Starting amount",
  "goal.monthly_contribution_gbp": "Monthly contribution",
  "approval.batch_auto_approve_turnover_max": "Maximum turnover per proposal",
  review_every_n_days: "Review frequency",
  exclusions: "Exclusions",
};

const formatPlanPercent = new Intl.NumberFormat("en-GB", { style: "percent", maximumFractionDigits: 6 });
function planErrors(error: unknown): string[] {
  const fields = error instanceof ApiError ? (error.details as { fields?: Record<string, unknown> } | undefined)?.fields : undefined;
  const messages = fields && typeof fields === "object" ? Object.entries(fields).flatMap(([field, message]) => {
    if (typeof message !== "string") return [];
    const label = planFieldLabels[field.replace(/\.[01]$/, "")];
    const readable = message
      .replace(/within \[([\d.]+), ([\d.]+)\]/, (_, min, max) => "within " + formatPlanPercent.format(Number(min)) + "–" + formatPlanPercent.format(Number(max)))
      .replace(/between ([\d.]+) and (\d+(?:\.\d+)?)/, (_, min, max) => "between " + formatPlanPercent.format(Number(min)) + " and " + formatPlanPercent.format(Number(max)))
      .replace("Minimum equity, bond and cash weights cannot total more than 1.", "Minimum shares, bonds and cash must add up to 100% or less.");
    return [label ? label + ". " + readable : readable];
  }) : [];
  return messages.length ? messages : [error instanceof Error ? error.message : "Couldn’t save your investment plan."];
}

function MandateReview({ mandate, profile, busy, submit, saveOnly = false }: {
  mandate: Mandate; profile?: ProfileResult; busy: boolean; submit: (mandate: Mandate) => Promise<void>; saveOnly?: boolean;
}) {
  const [autoApprove, setAutoApprove] = useState(!mandate.approval.require_user_approval);
  const [errors, setErrors] = useState<string[]>([]);
  const percentage = (name: string, label: string, value: number, inactive = false) =>
    <label>{label}<input className="terminal-field" name={name} type="number" min="0" max="100" step="any" required
      defaultValue={Number((value * 100).toPrecision(15))} disabled={busy || inactive} /></label>;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const fields = new FormData(form);
    const number = (name: string) => (form.elements.namedItem(name) as HTMLInputElement).valueAsNumber;
    const fraction = (name: string) => number(name) / 100;
    const submitted: Mandate = {
      ...mandate,
      goal: {
        ...mandate.goal,
        starting_amount_gbp: number("starting_amount_gbp"),
        monthly_contribution_gbp: number("monthly_contribution_gbp"),
      },
      ranges: {
        equity: [fraction("sharesMin"), fraction("sharesMax")],
        bond: [fraction("bondsMin"), fraction("bondsMax")],
        cash_min: fraction("cashMin"),
      },
      caps: {
        ...mandate.caps,
        per_fund: fraction("per_fund"),
        per_stock: fraction("per_stock"),
        stocks_total: fraction("stocks_total"),
      },
      review_every_n_days: number("reviewDays"),
      exclusions: String(fields.get("exclusions") ?? "").split(",").map(value => value.trim()).filter(Boolean),
      approval: {
        require_user_approval: !autoApprove,
        batch_auto_approve_turnover_max: fields.has("turnoverMax") ? fraction("turnoverMax") : mandate.approval.batch_auto_approve_turnover_max,
      },
    };
    setErrors([]);
    try { await submit(submitted); }
    catch (error) { setErrors(planErrors(error)); }
  }

  return <form className="mandate-review" onSubmit={save} onChange={() => { if (errors.length) setErrors([]); }}>
    {profile && <>
      <p>{profile.explanation}</p>
      <p className="mvp-muted">Your risk score uses the lower of how comfortable you are with a fall ({profile.tolerance_score}) and how much of a loss you could absorb ({profile.capacity_score}).</p>
      {profile.follow_up_question && <p>{profile.follow_up_question}</p>}
    </>}
    <div className="mandate-fields">
      {percentage("sharesMin", "Shares min (%)", mandate.ranges.equity[0])}
      {percentage("sharesMax", "Shares max (%)", mandate.ranges.equity[1])}
      {percentage("bondsMin", "Bonds min (%)", mandate.ranges.bond[0])}
      {percentage("bondsMax", "Bonds max (%)", mandate.ranges.bond[1])}
      {percentage("cashMin", "Cash minimum (%)", mandate.ranges.cash_min)}
      {percentage("per_fund", "Fund cap (%)", mandate.caps.per_fund)}
      {percentage("per_stock", "Stock cap (%)", mandate.caps.per_stock)}
      {percentage("stocks_total", "All stocks cap (%)", mandate.caps.stocks_total)}
      <label>Review every (trading days)<input className="terminal-field" name="reviewDays" type="number" min="1" step="1" required
        defaultValue={mandate.review_every_n_days} disabled={busy} />
        <small>10 trading days is roughly two weeks. A review checks the portfolio and can propose a change.</small></label>
      <label>Starting amount (£)<input className="terminal-field" name="starting_amount_gbp" type="number" min="0" step="0.01"
        required defaultValue={mandate.goal.starting_amount_gbp} disabled={busy} /></label>
      <label>Monthly contribution (£)<input className="terminal-field" name="monthly_contribution_gbp" type="number" min="0" step="0.01"
        required defaultValue={mandate.goal.monthly_contribution_gbp} disabled={busy} /></label>
      <label>Exclusions (comma separated)<input className="terminal-field" name="exclusions" defaultValue={mandate.exclusions.join(", ")} disabled={busy} />
        <small>Enter exact tickers or catalogue groups, separated by commas. Leave blank for no exclusions.</small></label>
    </div>
    {saveOnly && !MOCK && <fieldset className="approval-preferences">
      <legend>Paper trade approval</legend>
      <label className="approval-toggle">
        <input type="checkbox" checked={autoApprove} disabled={busy} onChange={event => setAutoApprove(event.target.checked)} />
        Automatically approve eligible proposals
      </label>
      <p className="mvp-muted">Only applies to new live paper proposals that pass the assurance checks and stay within your turnover limit. Anything larger still asks for your approval.</p>
      <div className="approval-limit mvp-enter" hidden={!autoApprove}>
        {percentage("turnoverMax", "Maximum turnover per proposal (%)", mandate.approval.batch_auto_approve_turnover_max, !autoApprove)}
        <p className="mvp-muted">Turnover is the share of the portfolio that would move between investments or cash. Switch off auto-approval and save to require approval for future proposals.</p>
      </div>
    </fieldset>}
    {errors.length > 0 && <ul className="mandate-errors mvp-error" role="alert">
      {errors.map((message, index) => <li key={index}>{message}</li>)}
    </ul>}
    <button type="submit" className="mvp-action primary" disabled={busy}>{busy ? "Saving…" : saveOnly ? "Save investment plan" : "Build my paper portfolio"}</button>
    {MOCK && <p className="mvp-muted">Fixture preview</p>}
  </form>;
}

export function ProfileScreen({ mode, restartTour }: { mode?: Mode; restartTour: () => void }) {
  const resource = useResource("profile:" + mode, signal => mode === "live" ? get<Mandate>("/mandate", "mandate", signal) : Promise.resolve(null));
  const demo = useResource("demo:" + mode, signal => mode === "historical" ? loadDemoProfile(signal) : Promise.resolve(null));
  const [message, setMessage] = useState("");
  const [saved, setSaved] = useState<Mandate>();
  const [busy, setBusy] = useState(false);
  const mandate = saved ?? resource.value;
  async function save(mandate: Mandate) {
    setBusy(true);
    setMessage("");
    try {
      setSaved(await put("/mandate", mandate, "mandate"));
      setMessage("Investment plan saved");
    } finally { setBusy(false); }
  }
  return <div className="onboard onboard-step mvp-enter">
    <AgentAvatar role="lead" />
    <h1>Your profile</h1>
    <p>{mode === "historical" ? demo.value ? `Demo · ${demo.value.name}’s recorded paper portfolio` : "Demo · Recorded paper portfolio" : "Live · Paper portfolio using current markets"}</p>
    {mode === "live" && mandate && <MandateReview mandate={mandate} busy={busy} submit={save} saveOnly />}
    {mode === "live" && !resource.value && !resource.error && <p role="status">Loading your investment plan…</p>}
    {message && <p role="status">{message}</p>}
    {resource.error && <p role="alert" className="mvp-error">{resource.error}</p>}
    <div className="mvp-toolbar"><Link className="mvp-action" to="/onboarding">Change mode or retake questions</Link>
      {mode && <button type="button" className="mvp-action" onClick={restartTour}>Guided tour</button>}</div>
  </div>;
}

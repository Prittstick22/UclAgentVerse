import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AgentAvatar from "../components/AgentAvatar";
import { ShellIcon } from "../components/TerminalShellUi";
import { api, get, MOCK, put } from "../lib/api";
import { useResource } from "../lib/useResource";
import type { DemoProfile, Mandate, Mode, ProfileResult, Question } from "../lib/types";
import "./mvp.css";

type Profile = { profile: ProfileResult; mandate: Mandate };
type ExampleProfile = Pick<DemoProfile, "name" | "story" | "profile" | "result" | "answers"> & { ranges: Mandate["ranges"]; recording: boolean; stockRange?: [number, number] };

// The higher-risk scenario uses the aggressive policy. Its quiz answers score as adventurous.
const caroline: ExampleProfile = {
  name: "Caroline", profile: "aggressive", recording: false,
  story: "Caroline invests regularly and is saving for a goal more than 15 years away. She has an emergency fund and would invest more during a market fall.",
  answers: { horizon: "gt15", emergency: "yes", loss_goal: "no", income: "steady", reaction: "buy", swings: "widest", experience: "yes", worry: "rarely" },
  result: { name: "adventurous", tolerance_score: 1, capacity_score: 1, conflict: false, follow_up_question: null,
    explanation: "Caroline’s answers reach the quiz’s highest risk band. This example uses a separate, stock-heavy investment plan." },
  ranges: { equity: [.95, .98], bond: [0, 0], cash_min: .02 },
  stockRange: [.57, .60],
};

const percentField = (value: number) => Math.round(value * 100) + "%";

export default function Quiz({ mode, changing, onMode, complete }: {
  mode?: Mode; changing: boolean; onMode: (mode: Mode) => Promise<boolean>; complete: (mode: Mode, room: string) => boolean;
}) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Profile | null>(null);
  const [entry, setEntry] = useState<Mode>("historical");
  const [demo, setDemo] = useState<ExampleProfile | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmingAnswer, setConfirmingAnswer] = useState(false);
  const [error, setError] = useState("");
  const timer = useRef<number>();
  const title = useRef<HTMLHeadingElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const abort = new AbortController();
    get<{ questions: Question[] }>("/profile/questions", "questions", abort.signal).then(({ questions }) => setQuestions(questions))
      .catch((e: Error) => { if (!abort.signal.aborted) setError(e.message); });
    return () => { abort.abort(); window.clearTimeout(timer.current); };
  }, []);

  async function chooseMode(next: Mode) {
    setBusy(true);
    setError("");
    try {
      if (!await onMode(next)) throw new Error("Couldn’t change the market mode. Try again.");
      if (next === "historical") {
        const profile = await get<DemoProfile>("/profile/demo", "demo_profile");
        setDemo({ ...profile, ranges: profile.mandate.ranges, recording: true });
      } else setDemo(null);
      setStep(1);
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
      await put("/mandate", mandate, "mandate");
      const { run_id } = await api.build();
      const room = "/runs/" + encodeURIComponent(run_id) + "?live=1";
      navigate(complete("live", room) ? "/" : room);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const question = questions[step - 1];
  const answerLocked = confirmingAnswer || busy;
  const isDemo = step > 0 && demo;
  const count = isDemo ? 2 : questions.length + 2;
  const heading = step === 0 ? "Welcome to your AI investment team" : isDemo ? "Meet " + demo.name :
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
        <p>The team builds and monitors a paper portfolio around your goals and how much risk you’re comfortable taking.</p>
        <fieldset className="onboard-entry" disabled={busy || changing}>
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
        </fieldset>
        {entry === "historical" && <section className="onboard-demo-list mvp-enter" aria-labelledby="onboard-demo-heading">
          <h2 id="onboard-demo-heading">Choose a demo profile</h2>
          <div className="onboard-options">
            <button className="glass-feedback" disabled={busy || changing || !mode} onClick={() => void chooseMode("historical")}><strong>Priya</strong>
              <span>Lower risk tolerance · Full portfolio replay</span></button>
            <button className="glass-feedback" disabled={busy || changing} onClick={() => { setDemo(caroline); setError(""); setStep(1); }}><strong>Caroline</strong>
              <span>Higher risk tolerance · Profile walkthrough</span></button>
          </div>
        </section>}
        {entry === "live" && <button className="mvp-action onboard-start mvp-enter" disabled={busy || changing || !mode}
          onClick={() => void chooseMode("live")}>{busy || changing ? "Opening live setup…" : "Let’s go"}</button>}
      </> : isDemo ? <>
        <p>{demo.story}</p>
        <dl className="onboard-demo-scores">
          <div><dt>Comfort with risk</dt><dd>{percentField(demo.result.tolerance_score)}</dd></div>
          <div><dt>Ability to absorb a loss</dt><dd>{percentField(demo.result.capacity_score)}</dd></div>
          <div><dt>Investment profile</dt><dd>{demo.profile}</dd></div>
        </dl>
        {demo.recording ? <Link className="mvp-action primary" to="/" onClick={() => complete("historical", "/timeline")}>Explore demo</Link> : <>
          <p>{demo.result.explanation}</p>
          <p>Example allocation · Shares {demo.ranges.equity.map(percentField).join("–")} · Bonds {percentField(demo.ranges.bond[1])}
            {demo.stockRange && " · Individual stocks " + demo.stockRange.map(percentField).join("–")}</p>
          {questions.length > 0 && <details className="desk-disclosure onboard-demo-answers">
            <summary>See Caroline’s answers</summary>
            <dl>{questions.map(question => <div key={question.id}>
              <dt>{question.text}</dt><dd>{question.options.find(option => option.id === demo.answers[question.id])?.label}</dd>
            </div>)}</dl>
          </details>}
        </>}
      </> : question ? <>
        <p>{question.help}</p>
        <div className="onboard-options" role="group" aria-label="Answer choices">{question.options.map(option => {
          const selected = answers[question.id] === option.id;
          return <button key={option.id} aria-pressed={selected} disabled={answerLocked && !selected}
            aria-disabled={answerLocked && selected || undefined}
            onClick={() => choose(question, option.id)}>{option.label}</button>;
        })}</div>
      </> : result ? <MandateReview key={`${result.mandate.version}:${result.profile.name}`} mandate={result.mandate} profile={result.profile} busy={busy} submit={build} /> : <p role="status">Loading questions…</p>}
      {error && <p className="mvp-error" role="alert">{error}</p>}
      {step > 0 && <button className="mvp-action" disabled={busy} onClick={() => {
        window.clearTimeout(timer.current); timer.current = undefined;
        setConfirmingAnswer(false); setError(""); setStep(step - 1);
      }}>Back</button>}
    </section>
  </div>;
}

function MandateReview({ mandate: initial, profile, busy, submit, saveOnly = false }: {
  mandate: Mandate; profile?: ProfileResult; busy: boolean; submit: (mandate: Mandate) => void; saveOnly?: boolean;
}) {
  // Seeded once per mandate: the parent passes key={version} so a new quiz result rebuilds the form with its values.
  const [mandate, setMandate] = useState(initial);
  const percentage = (label: string, value: number, change: (value: number) => Mandate) =>
    <label>{label}<input className="terminal-field" type="number" min="0" max="100" step="0.1"
      value={Number((value * 100).toFixed(2))} onChange={e => setMandate(change(Number(e.target.value) / 100))} /></label>;
  return <form className="mandate-review" onSubmit={e => { e.preventDefault(); submit(mandate); }}>
    {profile && <>
      <p>{profile.explanation}</p>
      <p className="mvp-muted">Your risk score uses the lower of how comfortable you are with a fall ({profile.tolerance_score}) and how much of a loss you could absorb ({profile.capacity_score}).</p>
      {profile.follow_up_question && <p>{profile.follow_up_question}</p>}
    </>}
    <div className="mandate-fields">
      {(["equity", "bond"] as const).flatMap(asset => ([0, 1] as const).map(index =>
        <div key={asset + index}>{percentage((asset === "equity" ? "Shares" : "Bonds") + (index ? " max (%)" : " min (%)"), mandate.ranges[asset][index], value => {
          const range: [number, number] = [...mandate.ranges[asset]];
          range[index] = value;
          return { ...mandate, ranges: { ...mandate.ranges, [asset]: range } };
        })}</div>))}
      {percentage("Cash minimum (%)", mandate.ranges.cash_min, value => ({ ...mandate, ranges: { ...mandate.ranges, cash_min: value } }))}
      {(["per_fund", "per_stock", "stocks_total"] as const).map((cap, i) =>
        <div key={cap}>{percentage(["Fund cap (%)", "Stock cap (%)", "All stocks cap (%)"][i], mandate.caps[cap],
          value => ({ ...mandate, caps: { ...mandate.caps, [cap]: value } }))}</div>)}
      <label>Review every (trading days)<input className="terminal-field" type="number" min="1" required value={mandate.review_every_n_days}
        onChange={e => setMandate({ ...mandate, review_every_n_days: Number(e.target.value) })} />
        <small>10 trading days is roughly two weeks. A review checks the portfolio and can propose a change.</small></label>
      <label>Exclusions (comma separated)<input className="terminal-field" defaultValue={mandate.exclusions.join(", ")}
        onChange={e => setMandate({ ...mandate, exclusions: e.target.value.split(",").map(x => x.trim()).filter(Boolean) })} />
        <small>Enter exact tickers or catalogue groups, separated by commas. Leave blank for no exclusions.</small></label>
    </div>
    {saveOnly && !MOCK && <fieldset className="approval-preferences">
      <legend>Paper trade approval</legend>
      <label className="approval-toggle">
        <input type="checkbox" checked={!mandate.approval.require_user_approval}
          onChange={event => setMandate({ ...mandate, approval: { ...mandate.approval, require_user_approval: !event.target.checked } })} />
        Automatically approve eligible proposals
      </label>
      <p className="mvp-muted">Only applies to new live paper proposals that pass the assurance checks and stay within your turnover limit. Anything larger still asks for your approval.</p>
      {!mandate.approval.require_user_approval && <div className="approval-limit mvp-enter">
        {percentage("Maximum turnover per proposal (%)", mandate.approval.batch_auto_approve_turnover_max,
          value => ({ ...mandate, approval: { ...mandate.approval, batch_auto_approve_turnover_max: value } }))}
        <p className="mvp-muted">Turnover is the share of the portfolio that would move between investments or cash. Switch off auto-approval and save to require approval for future proposals.</p>
      </div>}
    </fieldset>}
    <button className="mvp-action primary" disabled={busy}>{busy ? "Saving…" : saveOnly ? "Save investment plan" : "Build my paper portfolio"}</button>
    {MOCK && <p className="mvp-muted">Fixture preview</p>}
  </form>;
}

export function ProfileScreen({ mode, restartTour }: { mode?: Mode; restartTour: () => void }) {
  const resource = useResource("profile:" + mode, signal => get<Mandate>("/mandate", "mandate", signal));
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(mandate: Mandate) {
    setBusy(true);
    setError("");
    setMessage("");
    try { await put("/mandate", mandate, "mandate"); setMessage("Investment plan saved"); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="onboard onboard-step mvp-enter">
    <AgentAvatar role="lead" />
    <h1>Your profile</h1>
    <p>{mode === "historical" ? "Demo · Priya’s recorded paper portfolio" : "Real · Paper portfolio using current markets"}</p>
    {mode === "live" && resource.value && <MandateReview key={resource.value.version} mandate={resource.value} busy={busy} submit={save} saveOnly />}
    {mode === "live" && !resource.value && !resource.error && <p role="status">Loading your investment plan…</p>}
    {message && <p role="status">{message}</p>}
    {(error || resource.error) && <p role="alert" className="mvp-error">{error || resource.error}</p>}
    <div className="mvp-toolbar"><Link className="mvp-action" to="/onboarding">Change mode or retake questions</Link>
      {mode && <button type="button" className="mvp-action" onClick={restartTour}>Guided tour</button>}</div>
  </div>;
}

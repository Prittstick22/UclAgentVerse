import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AgentAvatar from "../components/AgentAvatar";
import { api, get, MOCK, put } from "../lib/api";
import { useResource } from "../lib/useResource";
import type { DemoProfile, Mandate, Mode, ProfileResult, Question } from "../lib/types";
import "./mvp.css";

type Profile = { profile: ProfileResult; mandate: Mandate };

export default function Quiz({ mode, changing, onMode, complete }: {
  mode?: Mode; changing: boolean; onMode: (mode: Mode) => Promise<boolean>; complete: () => void;
}) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<Profile | null>(null);
  const [demo, setDemo] = useState<DemoProfile | null>(null);
  const [busy, setBusy] = useState(false);
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
  useEffect(() => { title.current?.focus(); }, [step]);

  async function chooseMode(next: Mode) {
    setBusy(true);
    setError("");
    try {
      if (!await onMode(next)) throw new Error("Couldn’t change the market mode. Try again.");
      if (next === "historical") setDemo(await get<DemoProfile>("/profile/demo", "demo_profile"));
      setStep(1);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  function choose(question: Question, option: string) {
    if (timer.current !== undefined || busy) return;
    const next = { ...answers, [question.id]: option };
    setAnswers(next);
    setError("");
    timer.current = window.setTimeout(async () => {
      timer.current = undefined;
      if (step < questions.length) { setStep(step + 1); return; }
      setBusy(true);
      try { setResult(await api.quiz(next)); setStep(step + 1); }
      catch (e) { setError((e as Error).message); }
      finally { setBusy(false); }
    }, 160);
  }

  async function build(mandate: Mandate) {
    setError("");
    setBusy(true);
    try {
      await put("/mandate", mandate, "mandate");
      const { run_id } = await api.build();
      complete();
      navigate("/runs/" + encodeURIComponent(run_id) + "?live=1");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const question = questions[step - 1];
  const isDemo = step > 0 && mode === "historical" && demo;
  const count = isDemo ? 2 : questions.length + 2;
  const heading = step === 0 ? "How would you like to start?" : isDemo ? "Meet " + demo.name :
    question ? question.text : "Review your investment plan";

  return <div className="onboard">
    <div className="onboard-progress" aria-label={"Step " + (step + 1) + " of " + count}>
      {Array.from({ length: count }, (_, i) => <span key={i} data-state={i === step ? "current" : i < step ? "done" : "next"} />)}
    </div>
    <section key={step} className="onboard-step mvp-enter" aria-busy={busy || changing}>
      <svg className="onboard-outline" viewBox="0 0 180 180" fill="none" stroke="currentColor" aria-hidden="true">
        <rect x="28" y="47" width="112" height="94" rx="12" /><path d="M62 47V34a8 8 0 0 1 8-8h28a8 8 0 0 1 8 8v13M28 79h112M71 79v14h26V79M58 119l17-14 15 7 20-18" />
      </svg>
      <AgentAvatar role="lead" />
      <h1 ref={title} tabIndex={-1}>{heading}</h1>
      {step === 0 ? <>
        <p>Both routes use a paper portfolio. Your answers guide the plan and no real money is invested.</p>
        <div className="onboard-options">
          <button disabled={busy || changing || !mode} onClick={() => void chooseMode("historical")}><strong>Demo</strong><span>Follow Priya’s recorded portfolio through four months of reviews.</span></button>
          <button disabled={busy || changing || !mode} onClick={() => void chooseMode("live")}><strong>Real · Paper portfolio</strong><span>Answer a few questions and use current market data.</span></button>
        </div>
      </> : isDemo ? <>
        <p>{demo.story}</p>
        <p className="mvp-muted">Fictional investor · {demo.profile} plan · Recorded paper portfolio</p>
        <Link className="mvp-action primary" to="/timeline" onClick={complete}>Open demo timeline</Link>
      </> : question ? <>
        <p>{question.help}</p>
        <div className="onboard-options" role="group" aria-label="Answer choices">{question.options.map(option =>
          <button key={option.id} aria-pressed={answers[question.id] === option.id} disabled={busy}
            onClick={() => choose(question, option.id)}>{option.label}</button>)}</div>
      </> : result ? <MandateReview mandate={result.mandate} profile={result.profile} busy={busy} submit={build} /> : <p role="status">Loading questions…</p>}
      {error && <p className="mvp-error" role="alert">{error}</p>}
      {step > 0 && <button className="mvp-action" disabled={busy} onClick={() => {
        window.clearTimeout(timer.current); timer.current = undefined; setError(""); setStep(step - 1);
      }}>Back</button>}
    </section>
  </div>;
}

function MandateReview({ mandate: initial, profile, busy, submit, saveOnly = false }: {
  mandate: Mandate; profile?: ProfileResult; busy: boolean; submit: (mandate: Mandate) => void; saveOnly?: boolean;
}) {
  const [mandate, setMandate] = useState(initial);
  const percentage = (label: string, value: number, change: (value: number) => Mandate) =>
    <label>{label}<input className="terminal-field" type="number" min="0" max="100" step="0.1"
      value={Number((value * 100).toFixed(2))} onChange={e => setMandate(change(Number(e.target.value) / 100))} /></label>;
  return <form className="mandate-review" onSubmit={e => { e.preventDefault(); submit(mandate); }}>
    {profile && <>
      <p>{profile.explanation}</p>
      <p className="mvp-muted">Risk score uses the lower of comfort ({profile.tolerance_score}) and capacity ({profile.capacity_score}).</p>
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
      <label>Review every (days)<input className="terminal-field" type="number" min="1" required value={mandate.review_every_n_days}
        onChange={e => setMandate({ ...mandate, review_every_n_days: Number(e.target.value) })} /></label>
      <label>Exclusions (comma separated)<input className="terminal-field" defaultValue={mandate.exclusions.join(", ")}
        onChange={e => setMandate({ ...mandate, exclusions: e.target.value.split(",").map(x => x.trim()).filter(Boolean) })} /></label>
    </div>
    <button className="mvp-action primary" disabled={busy}>{busy ? "Saving…" : saveOnly ? "Save investment plan" : "Build my paper portfolio"}</button>
    {MOCK && <p className="mvp-muted">Fixture preview</p>}
  </form>;
}

export function ProfileScreen({ mode }: { mode?: Mode }) {
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
    {mode === "live" && resource.value && <MandateReview mandate={resource.value} busy={busy} submit={save} saveOnly />}
    {mode === "live" && !resource.value && !resource.error && <p role="status">Loading your investment plan…</p>}
    {message && <p role="status">{message}</p>}
    {(error || resource.error) && <p role="alert" className="mvp-error">{error || resource.error}</p>}
    <Link className="mvp-action" to="/onboarding">Change mode or retake questions</Link>
  </div>;
}

"""Capture a fresh, validated local demo without replacing existing evidence."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import threading
import time
from pathlib import Path

from app.agents.llm import LLMError
from app.api.run_views import find_evidence
from app.container import build_state
from app.profile.demo import demo_mandate, persona_name
from app.schemas import Mandate
from app.settings import Settings
from app.sim.evaluate import BENCHMARKS
from app.sim.runner import Simulation


class CaptureError(LLMError):
    pass


PROVIDER_FAILURE = ("LLMError", "LLMCacheMiss")   # agent.status reasons that mean Gemini/keys failed (or a dry-run miss)


def is_fatal(event: dict, *, agents: bool) -> bool:
    """Stop a recording only for real API/key failures, a crashed run, or the construction engine fallback.
    A run that uses up its token budget ends safely ('investigate further') and a reply that fails the schema twice
    ends that agent: both are recorded outcomes, not technical failures (Dev, 8 Nov)."""
    kind, status = event.get("type"), event.get("status")
    if kind == "agent.status" and status == "failed":
        return str((event.get("payload") or {}).get("reason", "")).startswith(PROVIDER_FAILURE)
    if kind == "run.completed" and status == "failed":
        return not (event.get("payload") or {}).get("budget_exceeded")
    return bool(agents and event.get("title") == "Initial portfolio built by the engine")


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


class CaptureBudget:
    """One durable estimated-spend ledger shared by all attempts in a campaign."""

    def __init__(self, path: Path, limit: float):
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError("Capture budget must be finite and positive")
        self.path, self.limit = Path(path), limit
        self.lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            write_json(self.path, {"limit_usd": limit, "usd": 0.0, "tokens": 0, "calls": 0})
        if self.read()["limit_usd"] != limit:
            raise ValueError("Existing campaign budget has a different limit")

    def read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def check(self) -> None:
        if self.read()["usd"] >= self.limit:
            raise CaptureError("Capture estimated-spend threshold reached")

    def record(self, cost: float, tokens: int) -> None:
        with self.lock:
            current = self.read()
            current.update(usd=current["usd"] + cost, tokens=current["tokens"] + tokens, calls=current["calls"] + 1)
            write_json(self.path, current)


def input_hashes(path: Path) -> dict[str, str]:
    return {item.name: hashlib.sha256(item.read_bytes()).hexdigest()
            for item in sorted(path.iterdir()) if item.is_file() and item.name != ".gitkeep"}


def check_real_inputs(state) -> None:
    snapshot = state.gw.snapshot
    if snapshot.source_label != "eodhd":
        raise CaptureError("Capture requires the verified EODHD snapshot")
    for frame in (snapshot.prices, snapshot.fx):
        if "source" not in frame or set(frame["source"]) != {"eodhd"}:
            raise CaptureError("Market rows must have EODHD provenance")
    if any(item.synthetic or item.source == "synthetic" for item in snapshot.news):
        raise CaptureError("Synthetic news is excluded from the final capture")
    if any(item.synthetic for item in snapshot.filings):
        raise CaptureError("Synthetic filings are excluded from the final capture")
    # Validate raw constituent provenance: the loader intentionally stores only their holdings.
    for name in ("earnings.jsonl", "etf_holdings.jsonl"):
        path = state.settings.snapshot_dir / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row.get("synthetic") or row.get("source") == "synthetic" or row.get("as_of_download") == "synthetic":
                    raise CaptureError("Synthetic reference evidence is excluded from the final capture")


def validate_state(state, start: str, end: str, *, agents: bool) -> dict:
    days = [str(day.date()) for day in state.gw.trading_days(start, end)]
    events = [json.loads(raw) for (raw,) in state.db.execute("SELECT json FROM events ORDER BY rowid")]
    ticks = [event["as_of"] for event in events if event["type"] == "clock.tick"]
    marks = [row[0] for row in state.db.list("ledger_checkpoints:historical")]
    result = json.loads(state.db.get("sim_results", "latest") or "{}")
    if ticks != days or sorted(marks) != days or result.get("days") != len(days):
        raise CaptureError("Recording has incomplete or duplicate trading-day checkpoints")
    if (result.get("start") != start or result.get("end") != end
            or set(result.get("strategies", {})) != {"ours", *BENCHMARKS}):
        raise CaptureError("Recording window or benchmark coverage is incomplete")
    if not state.ledger.fills or not state.ledger.positions:
        raise CaptureError("Recording has no invested portfolio")
    raw = state.db.get("sim_mandate", "initial")
    persona = state.settings.demo_persona
    if not raw or Mandate.model_validate_json(raw) != demo_mandate(persona):
        raise CaptureError(f"Initial mandate does not match {persona_name(persona)}")
    if any(is_fatal(event, agents=False) for event in events):
        raise CaptureError("Recording contains a provider failure or a crashed run")
    if agents and any(event["title"] == "Initial portfolio built by the engine" for event in events):
        raise CaptureError("Agent construction used the engine fallback")
    refs = {ref for event in events for ref in event.get("evidence_ids", [])}
    refs.update("calc:" + event["id"] for event in events if event["type"] == "calc.result")
    def citations(value):
        if isinstance(value, dict):
            refs.update(value.get("evidence_ids", []))
            for item in value.values():
                citations(item)
        elif isinstance(value, list):
            for item in value:
                citations(item)
    for namespace in ("cases", "case_versions", "proposals"):
        for _, raw in state.db.list(namespace):
            citations(json.loads(raw))
    missing = [ref for ref in sorted(refs) if find_evidence(state.gw, state.db, ref) is None]
    if missing:
        raise CaptureError("Unresolved evidence IDs: " + ", ".join(missing[:10]))
    runs = [event for event in events if event["type"] == "run.completed"]
    models = sorted({event["payload"].get("model") for event in events
                     if event["type"] == "agent.spawned" and event["payload"].get("model")})
    if agents and (not runs or not set(models) <= {"gemini-4-argon", "gemini-3.8-flash"}):
        raise CaptureError("Unexpected or absent capture model attribution")
    return {"start": start, "end": end, "days": len(days), "evidence_ids": len(refs),
            "models": models, "agent_runs": len(runs), "fills": len(state.ledger.fills),
            "final_nav_gbp": state.ledger.nav(), "contributions_gbp": state.ledger.contributions_gbp,
            "benchmarks": sorted(result["strategies"]), "runs": [
                {"run_id": event["run_id"], "as_of": event["as_of"], **event["payload"]} for event in runs]}


async def capture(settings: Settings, out: Path, budget_file: Path, limit: float,
                  start: str, end: str, *, agents: bool = True, replay_cache_from: Path | None = None,
                  fixes_from: str | None = None, dry_run_replay: bool = False,
                  review_every_from: tuple[str, int] | None = None) -> dict:
    """A failed attempt remains inspectable and never receives READY.json.

    Continue an earlier attempt without paying again (`replay_cache_from` = its attempt dir): its saved Gemini answers
    are copied in and the days before `fixes_from` run with the old behaviour (`compat.legacy`), so prompts match and
    the agents' calls are cache hits. The fixes take over at `fixes_from`, or earlier at the first call the cache
    can't answer (reported as `fixes_from_actual`). `dry_run_replay` = replay mode only, stop at `fixes_from`, $0.
    `review_every_from` = (date, n): review every n trading days from that date (fallback; recorded in the report)."""
    from app.sim import compat
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    state = None
    lock_path = Path(budget_file).with_suffix(".lock")
    lock_file = None
    report = {"status": "incomplete", "start": start, "end": end, "agents": agents}
    try:
        budget = CaptureBudget(budget_file, limit)
        # A second capture cannot race the shared ledger; an interrupted process leaves this lock for diagnosis.
        lock_file = lock_path.open("x", encoding="utf-8")
        lock_file.write(str(out))
        lock_file.flush()
        if agents:
            budget.check()
            if settings.llm_mode != "live":
                raise CaptureError("Final agent capture requires LLM_MODE=live")
        settings = settings.model_copy(update={"app_mode": "historical", "recorded_run": None,
                                               "public_demo": False, "state_db": out / "recording.sqlite"})
        state = build_state(settings, db_path=str(out / "recording.sqlite"))
        state.mandate = demo_mandate(settings.demo_persona)
        # A recording has no visitor waiting, so slow provider latency must not cut a run short: capture only, no
        # wall-time limit (copy, so the cached frozen config and Live mode keep run_wall_time_s). Step/token limits stay.
        state.supervisor.cfg = {**state.supervisor.cfg, "run_wall_time_s": None}
        report["run_wall_time_s"] = "off (capture only)"
        state.db.put("sim_mandate", "initial", state.mandate.model_dump_json())
        if replay_cache_from is not None:
            source = (Path(replay_cache_from) / "recording.sqlite").resolve()
            state.db.execute("ATTACH DATABASE ? AS prior", (str(source),))
            state.db.execute("INSERT OR IGNORE INTO llm_cache SELECT * FROM prior.llm_cache")
            report["replayed_answers"] = state.db.execute("SELECT count(*) FROM llm_cache")[0][0]
            state.db.execute("DETACH DATABASE prior")
            report["resumed_from_attempt"] = str(replay_cache_from)
            compat.legacy = fixes_from is not None
        if dry_run_replay:
            state.llm.mode = "replay"
        check_real_inputs(state)
        before = input_hashes(settings.snapshot_dir)
        fatal = []
        def on_event(event):
            if is_fatal(event.model_dump(), agents=agents):
                fatal.append(f"{event.as_of} {event.type}: {(event.payload or {}).get('reason', event.title)}"[:300])
        def before_call():
            if fatal:
                raise CaptureError("Capture stopped after a provider failure")
            if compat.legacy:   # the saved answers ran out before fixes_from: fixes on from today, live from here
                compat.legacy = False
                report["fixes_from_actual"] = state.clock.as_of_str()
            budget.check()
        state.events.listen(on_event)
        state.llm.before_live_call = before_call
        state.llm.on_spend = budget.record
        sim = Simulation(state, start, end, agents=agents, approvals="batch_policy")
        if review_every_from is not None:
            sim.set_review_every_from(*review_every_from)
            report["review_every_from"] = list(review_every_from)
        while not sim.done:
            today = str(sim.days[sim.i].date())
            if fixes_from is not None and today >= fixes_from:
                if dry_run_replay:
                    report.update(status="dry_run_reached", replayed_until=today, live_calls=state.llm.live_calls)
                    return report
                if compat.legacy:
                    compat.legacy = False
                    report.setdefault("fixes_from_actual", today)
            await sim.step()
            if fatal:
                report["fatal"] = fatal[:3]
                raise CaptureError("Capture stopped after a provider failure or a crashed run")
            if agents and sim.i == 1 and not sim.targets:
                raise CaptureError("Agent construction did not produce an approved starting portfolio")
            print(json.dumps({"date": state.clock.as_of_str(), "progress": sim.progress,
                              "estimated_campaign_usd": budget.read()["usd"]}), flush=True)
        if input_hashes(settings.snapshot_dir) != before:
            raise CaptureError("Capture inputs changed during the attempt")
        report.update(validate_state(state, start, end, agents=agents))
        report.update(input_hashes=before, estimated_campaign_spend=budget.read(),
                      llm_calls=state.llm.live_calls, status="validated" if agents else "preflight_passed")
        state.db.conn.close()
        state = None
        recording = out / "recording.sqlite"
        report["recording_sha256"] = hashlib.sha256(recording.read_bytes()).hexdigest()
        report["duration_s"] = round(time.monotonic() - started, 2)
        if agents:
            # Exercise the actual replay constructor before marking the candidate ready.
            replay = build_state(settings.model_copy(update={"recorded_run": recording, "llm_mode": "replay"}))
            replay.db.conn.close()
            write_json(out / "READY.json", report)
        return report
    except (Exception, asyncio.CancelledError) as error:
        report["status"] = "incomplete"
        report["error_type"] = type(error).__name__
        report["reason"] = str(error) if isinstance(error, CaptureError) else "Attempt failed; inspect saved events."
        raise
    finally:
        compat.legacy = False
        if state is not None:
            state.db.conn.close()
        report["duration_s"] = round(time.monotonic() - started, 2)
        write_json(out / "attempt.json", report)
        if lock_file is not None:
            lock_file.close()
            lock_path.unlink()

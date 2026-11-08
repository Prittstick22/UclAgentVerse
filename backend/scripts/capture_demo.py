"""Create a new full-window recording; never replace an existing attempt."""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.settings import Settings
from app.sim.capture import capture


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="New attempt directory; must not exist")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--budget-file", type=Path, required=True)
    parser.add_argument("--budget-usd", type=float, default=5.0)
    parser.add_argument("--start", default="2026-07-07")
    parser.add_argument("--end", default="2026-11-06")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--persona", choices=["priya", "caroline"], default="priya",
                        help="whose fixed mandate to record (Priya is the finished balanced demo)")
    parser.add_argument("--engine-only", action="store_true")
    parser.add_argument("--replay-cache-from", type=Path, help="earlier attempt dir: reuse its saved Gemini answers")
    parser.add_argument("--fixes-from", help="date the 8 Nov fixes take over when continuing an attempt (YYYY-MM-DD)")
    parser.add_argument("--dry-run-replay", action="store_true", help="replay only (no Gemini), stop at --fixes-from")
    parser.add_argument("--review-every-from", nargs=2, metavar=("DATE", "N"),
                        help="fallback: from DATE review every N trading days (e.g. 20 = monthly)")
    args = parser.parse_args()
    if os.environ.get("PYTHONHASHSEED") is None:
        print("Note: set PYTHONHASHSEED=0 so this attempt can be continued exactly later.", file=sys.stderr)
    kwargs = {"_env_file": args.env_file} if args.env_file else {}
    settings = Settings(**kwargs, app_mode="historical", llm_mode="fake" if args.engine_only else "live",
                        snapshot_dir=args.snapshot, demo_persona=args.persona, gemini_model_deep="gemini-4-argon",
                        gemini_model_fast="gemini-3.8-flash")
    try:
        report = asyncio.run(capture(settings, args.out, args.budget_file, args.budget_usd,
                                     args.start, args.end, agents=not args.engine_only,
                                     replay_cache_from=args.replay_cache_from, fixes_from=args.fixes_from,
                                     dry_run_replay=args.dry_run_replay,
                                     review_every_from=(args.review_every_from[0], int(args.review_every_from[1]))
                                     if args.review_every_from else None))
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 - sanitize provider errors at the CLI boundary
        # Provider exceptions can contain credential-bearing request URLs. Never print their text.
        print(f"Capture incomplete ({type(error).__name__}); preserved attempt: {args.out}", file=sys.stderr)
        raise SystemExit(1) from None
    if report["status"] == "dry_run_reached":
        print(f"dry run reached {report['replayed_until']} with {report['live_calls']} live calls; {args.out}")
        return
    print(f"{report['status']}: {report['days']} days, {report['agent_runs']} agent runs; {args.out}")


if __name__ == "__main__":
    main()

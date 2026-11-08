"""Create a new full-window recording; never replace an existing attempt."""
from __future__ import annotations

import argparse
import asyncio
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
    parser.add_argument("--engine-only", action="store_true")
    args = parser.parse_args()
    kwargs = {"_env_file": args.env_file} if args.env_file else {}
    settings = Settings(**kwargs, app_mode="historical", llm_mode="fake" if args.engine_only else "live",
                        snapshot_dir=args.snapshot, gemini_model_deep="gemini-4-argon",
                        gemini_model_fast="gemini-3.8-flash")
    try:
        report = asyncio.run(capture(settings, args.out, args.budget_file, args.budget_usd,
                                     args.start, args.end, agents=not args.engine_only))
    except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001 - sanitize provider errors at the CLI boundary
        # Provider exceptions can contain credential-bearing request URLs. Never print their text.
        print(f"Capture incomplete ({type(error).__name__}); preserved attempt: {args.out}", file=sys.stderr)
        raise SystemExit(1) from None
    print(f"{report['status']}: {report['days']} days, {report['agent_runs']} agent runs; {args.out}")


if __name__ == "__main__":
    main()

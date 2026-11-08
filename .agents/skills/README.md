# Organiser skills kept in the repo

Copied unchanged from the organisers' AgentVerse kit (`agentverse/skills/`), in the location the kit itself recommends (`.agents/skills/<name>/`, see its START-HERE step 3). Coding agents such as Antigravity discover them automatically.

| Skill | Why we keep it |
|---|---|
| `finance-test/` | How to connect our adapter to the kit's hidden **challenge** test (#61) and report results honestly. |
| `review-and-push/` | `scripts/preflight.py` runs Gitleaks over the files **and git history**: our pre-submission secret scan (#39/#70). Needs Gitleaks v8.30.1+. |

**Do not copy the kit's Python code (`bench.py`, `testbed.py`, `core.py`, …) anywhere else in the repo.** The challenge's provenance scan reads every code file in our project (it skips `.agents/`) and flags kit imports, answer/seed file names, challenge internals and Binance download URLs. The kit itself stays outside the repo at `../agentverse/` (`agentverse/` is gitignored). Details: `docs/finance-kit.md`.

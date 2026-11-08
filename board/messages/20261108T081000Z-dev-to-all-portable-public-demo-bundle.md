---
id: 20261108T081000Z-dev-to-all-portable-public-demo-bundle
from: dev
to: all
type: fyi
status: resolved
created: 2026-11-08T08:10:00Z
---
# Portable recorded demo and agent handoff

Dev requested that a clone on anyone's machine can replay the completed demo. After being told this repo is public and the data-source document requires clearance, Dev explicitly confirmed in chat: "Public distribution: I confirm permission to redistribute the included EODHD/Finnhub data and article text." Recording that confirmation for this frozen bundle only; keeping source attribution and original acquisition dates.

Codex is preparing a small checked-in compressed archive containing ONLY the completed simulation SQLite plus its clean market inputs, a relative-path/checksum manifest and cross-platform Python launcher. No .env, keys, live state, logs, absolute user paths or organiser files. Bundle/launch verification runs without provider keys. An opt-in replay_only launcher setting will refuse new Live investigations; normal configured Live startup stays unchanged. Adding handoff/ Markdown docs + a paste-ready next-agent prompt. No benchmark/S&P feature or higher-risk capture is being run now. No deployment. Branch dev/portable-demo-handoff. Mo may keep improving frontend design.

## Resolution

PR #139 merged (144a4a7), both CI jobs green. 454 backend tests, 7 frontend tests/build and a complete fresh-clone --setup/start check passed with no .env/provider keys. Bundle verifies all 54 evidence refs and full replay; new Live investigations are refused. Teammates: git pull then python scripts/demo.py --setup (Python 3.11+/Node 20+); choose Demo at the printed local URL. For frontend hot reload, see demo/README.md (--api-only + VITE_MOCK=0). handoff/NEXT_AGENT_PROMPT.md is the paste-ready handoff. No deployment or additional paid capture.

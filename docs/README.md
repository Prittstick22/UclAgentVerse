# Docs index

| # | Doc | What it answers |
|---|---|---|
| 01 | [Project spec](01-project-spec.md) | What we're building this weekend, for whom, which features, and what's out of scope |
| 02 | [Architecture](02-architecture.md) | Layers, components, data flow, folder map, diagrams |
| 03 | [How it works](03-how-it-works.md) | User journey, day-by-day simulation, triggers, pipelines, modes |
| 04 | [API contracts](04-api-contracts.md) | Every REST endpoint, the SSE event schema, shared models. **Contract file** |
| 05 | [Agent system](05-agent-system.md) | Supervisor, sub-agent limits, roles, tools per role, assurance gate, monitors, memory |
| 06 | [Data plan](06-data-plan.md) | Historical snapshot, live data, providers, call budgets, `as_of` rules |
| 07 | [Engine and config](07-engine-and-config.md) | Risk, optimiser, checker, ledger, metrics, frozen config values |
| 08 | [Team and roles](08-team-and-roles.md) | Who owns what, interfaces between people, handoffs |
| 09 | [Build plan](09-build-plan.md) | Timeline, milestones, tiers, feature freeze, sleep shifts |
| 10 | [Evaluation](10-evaluation.md) | Benchmarks, development vs held-out periods, metrics, caveats |
| 11 | [Demo and pitch](11-demo-and-pitch.md) | Problem, pitch, demo script, deck outline, judging rubric mapping |
| 12 | [Hosting and deploy](12-hosting-and-deploy.md) | DigitalOcean droplet, docker compose + Caddy, costs, secrets, protecting the public link |
| 13 | [Dev workflow](13-dev-workflow.md) | Local setup, branches, PRs, CI, env vars, fake LLM mode |
| — | [Original spec](original/original-spec.md) ([PDF](original/original-spec.pdf)) | The teammate's long-term vision this is cut down from |

**Precedence when docs disagree:** 04 (contracts) > 01 (spec) > 05/06/07 > the rest > original spec.

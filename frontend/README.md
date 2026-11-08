# Frontend (Mo)

React + TypeScript + Vite + Tailwind v4 + Recharts.

```bash
npm install
npm run dev            # http://localhost:5173, mock mode (fixtures/) by default
VITE_MOCK=0 npm run dev  # use the real backend on :8000 (proxied /api)
npm test                # API client checks with intercepted requests
npm run build
```

- `src/lib/types.ts` is a **contract file** that mirrors `docs/04-api-contracts.md`.
- `src/lib/api.ts` is the API client; in mock mode it reads `../fixtures/*.json` (regenerate with `make fixtures`).
- `src/lib/sse.ts` subscribes to run events (in mock mode it replays the fixture events).
- Screens are in `src/screens/`. Placeholders name the GitHub issue that builds them.
- Every screen shows the mode badge and the "Paper portfolio · Not financial advice" footer. Label anything synthetic or simulated.

## Portfolio Home

The desktop Home places the holdings watchlist and allocation on the left, performance and holding connections in the centre, and portfolio status, review history and agent activity on the right. Performance markers come from recorded reviews. The positions table uses the selected P&L period and dates each quote so carried-forward prices are visible.

The holding connections view uses the portfolio's current tickers. Matrix cells can be inspected by pointer or keyboard. In historical mode, the date slider fetches a report at the selected date and keeps the last loaded report visible while the request completes. The fixture preview has one correlation date and one P&L period.

Change between historical demo and current paper markets on the Investor profile screen. Protected requests may prompt for the public demo passcode, which is kept in memory until the page reloads.

## First visit and investigations

First visit opens setup. Demo shows the locked fictional Priya profile and opens Timeline inside Agents. Real mode runs the risk questionnaire and saves a paper-portfolio mandate before requesting construction. Return to Profile to edit the mandate or revisit setup.

Home review links and portfolio history markers open the Agent Room. Active runs follow incoming events. Saved runs expose the shared replay player and support event deep links with `/runs/:id?seq=n`. Each agent pane has its own step arrows. In a development build, append `debug=1` to a room URL to inspect raw events and calculation payloads.

The Agent Room and Home can open the same proposal dialog. Current-market decisions use the manual approve or decline endpoint. The historical recording is read-only.

Home's Latest news tab reads the active mode's existing news cache and can filter it to current holdings. In Agents, Timeline groups investigations, cached news and filled trades by date. Portfolio history adds allocation and benchmark charts. Recorded investigations include shared playback controls. During a live investigation each agent follows incoming events and has its own step arrows.

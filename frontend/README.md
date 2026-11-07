# Frontend (Mo)

React + TypeScript + Vite + Tailwind v4 + Recharts.

```bash
npm install
npm run dev            # http://localhost:5173, mock mode (fixtures/) by default
VITE_MOCK=0 npm run dev  # use the real backend on :8000 (proxied /api)
npm run build
```

- `src/lib/types.ts` is a **contract file** that mirrors `docs/04-api-contracts.md`.
- `src/lib/api.ts` is the API client; in mock mode it reads `../fixtures/*.json` (regenerate with `make fixtures`).
- `src/lib/sse.ts` subscribes to run events (in mock mode it replays the fixture events).
- Screens are in `src/screens/`. Placeholders name the GitHub issue that builds them.
- Every screen shows the mode badge and the "Paper portfolio · Not financial advice" footer. Label anything synthetic or simulated.

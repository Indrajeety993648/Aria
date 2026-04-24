# ARIA frontend

Live dashboard for the ARIA agent: voice, environment, reward, and event trace.

Stack: Next.js 15 (App Router) + React 19 + TypeScript 5 (strict) + Tailwind v4. No UI or state libraries. The radar is hand-rolled SVG.

## Run

```bash
npm install
npm run dev       # http://localhost:3000
npm run build
npm start
```

## Environment variables

| Variable                    | Default                                 | Purpose                                                                         |
| --------------------------- | --------------------------------------- | ------------------------------------------------------------------------------- |
| `NEXT_PUBLIC_GATEWAY_WS_URL` | `ws://localhost:8000/ws/session/demo`   | Gateway WebSocket. If unreachable within 2s, the UI falls back to a canned replay so the demo is viewable offline. |

## Docker

```bash
docker build -t aria-frontend -f Dockerfile .
docker run --rm -p 3000:3000 aria-frontend
```

The image is a multi-stage build producing a minimal `node:20-alpine` runner that serves Next.js in standalone mode.

## Layout

- `app/` — App Router pages and global CSS
- `components/` — `VoiceDock`, `EnvInspector`, `RewardRadar`, `EventTrace`
- `lib/contracts/` — TypeScript mirrors of `aria-contracts` (snake_case fields)
- `lib/ws.ts` — `useSession()` hook with mock-replay fallback
- `lib/mockData.ts` — canned observation / reward / event stream

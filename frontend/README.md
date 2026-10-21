# Docify frontend

Single-page app for Docify: Vite + React 19 + TypeScript + Tailwind CSS v4 + React Router 7 + TanStack Query 5,
Radix UI primitives, `motion`, `lucide-react`, `react-markdown` + `remark-gfm`. Spec: Master Doc §5.1.

## Scripts

| Command | What it does |
| --- | --- |
| `npm ci` | Install exact versions from `package-lock.json` |
| `npm run dev` | Dev server on http://localhost:5173 (proxies `/api` → backend) |
| `npm run gen-api` | Regenerate `src/api/schema.d.ts` from `openapi.json` (export it from the backend first) |
| `npm run lint` | ESLint (typescript-eslint, react-hooks, react-refresh) |
| `npm run typecheck` | `tsc --noEmit` (strict) |
| `npm test` | Vitest + Testing Library (jsdom); `npm test -- --run` for a single run |
| `npm run build` | Typecheck + production build into `dist/` |
| `npm run preview` | Serve `dist/` locally (also proxies `/api`) |

## How the API is reached

The SPA only ever calls **same-origin** `/api/*` with the `docify_session` cookie.

- **Dev:** Vite proxies `/api` to `http://localhost:8000` (override: `DOCIFY_API_URL=http://host:port npm run dev`).
  Start the backend with `docker compose up` or `cd backend && uv run docify api`.
- **Cloud:** CloudFront serves `dist/` and routes `/api/*` to the origin, so no CORS is needed.

Every non-GET request sends `X-Docify-CSRF: 1`. Errors are RFC 9457 problem+json → `ApiError` (`src/api/client.ts`);
a 401 on a private page redirects to `/login?next=…`. Chat uses `fetch` + a streaming SSE parser (`src/api/sse.ts`).

## Runtime config

`/config.json` is loaded at startup (`public/config.json` locally; a per-env file is uploaded at deploy, served
with `no-cache`) and merged with `GET /api/config` (feature flags: GitHub/Google sign-in, GitHub App, demo slug).

```json
{ "env": "local", "version": "dev" }
```

## Layout

```text
src/
  api/          client.ts (fetch wrapper), sse.ts, endpoints.ts, types.ts, schema.d.ts (generated)
  components/   ui/ (design-system kit — see ui/README.md), layout/ (shell, sidebar, ⌘K), Markdown, guards
  hooks/        useMe, useWorkspace, useRepos (5 s polling), usePageMeta (title + breadcrumbs)
  lib/          config, formatting, labels, markdown/url safety, health probe
  pages/        one lazy-loaded chunk per route; pages/dev/UiGallery is dev-only (/dev/ui)
  styles/       tokens.css (design tokens), motion.css, markdown.css
```

Light/dark follow `prefers-color-scheme`; animations respect `prefers-reduced-motion`.

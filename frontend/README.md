# NEXUS Console

The NEXUS Console is a React, TypeScript, and Vite client of the NEXUS HTTP API. It does not call
LangGraph directly. JSON requests go through `src/lib/apiClient.ts`; streamed execution events go
through `src/lib/sseClient.ts` and the shared trace reducer.

## Local development

Prerequisites: Python and project dependencies for the API, plus Node.js and npm.

From the repository root, start the API in one terminal:

```bash
uvicorn api:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev
```

The default API URL is `http://127.0.0.1:8000`. If the API uses bearer-token authentication, set
`VITE_NEXUS_API_TOKEN` in `frontend/.env.local`. Configure `NEXUS_CONSOLE_ORIGINS` on the API if
the Console uses a different origin.

Vite embeds all `VITE_*` values into the browser bundle. They are visible to browser users and are
not secrets. The token setting is only for a trusted local/demo browser. Do not use a shared or
production credential in a frontend build.

## Checks

```bash
npm test
npm run build
```

The frontend uses Vitest and React Testing Library. UI tests use mocked API responses; they do not
replace browser verification against a running API, including CORS and SSE checks.

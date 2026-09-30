/**
 * Local development configuration for the NEXUS Console.
 *
 * Phase 6.1 deliberately does not build a login system (see CLAUDE.md
 * section 9.7 / section 41): the backend's own auth is a single
 * configured bearer token, not a multi-user credential system, so a
 * login UI would be misleading here. Instead this reads two Vite env
 * vars, both optional, from `.env.local` (gitignored -- see
 * .env.example) or the environment `npm run dev`/`vite build` was
 * invoked with:
 *
 * - VITE_NEXUS_API_BASE_URL: where the NEXUS API is running.
 * - VITE_NEXUS_API_TOKEN: only needed if that backend was started with
 *   NEXUS_API_TOKEN configured (see the backend's auth.py). Never
 *   hardcoded, never committed -- see .gitignore.
 */

export interface NexusConfig {
  apiBaseUrl: string
  apiToken: string | null
}

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000'

export function loadConfig(): NexusConfig {
  const rawBaseUrl = import.meta.env.VITE_NEXUS_API_BASE_URL?.trim()
  const apiBaseUrl = rawBaseUrl && rawBaseUrl.length > 0 ? rawBaseUrl.replace(/\/+$/, '') : DEFAULT_API_BASE_URL

  const rawToken = import.meta.env.VITE_NEXUS_API_TOKEN?.trim()
  const apiToken = rawToken && rawToken.length > 0 ? rawToken : null

  return { apiBaseUrl, apiToken }
}

export const nexusConfig: NexusConfig = loadConfig()

/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_NEXUS_API_BASE_URL?: string
  readonly VITE_NEXUS_API_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

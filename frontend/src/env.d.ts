/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_NOVELWRITER_API_TOKEN?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

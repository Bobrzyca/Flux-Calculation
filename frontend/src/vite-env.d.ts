/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the FastAPI backend (default http://localhost:8000/api). */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

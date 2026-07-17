/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import { fileURLToPath, URL } from 'node:url'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { sentryVitePlugin } from '@sentry/vite-plugin'

// Source maps are uploaded to Sentry (for readable stack traces) ONLY when a
// SENTRY_AUTH_TOKEN is present at build time. They are generated as "hidden"
// (no sourceMappingURL comment) and deleted from dist after upload, so the maps
// are never served publicly by nginx. Without the token, no maps are emitted.
const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN
const uploadSourceMaps = Boolean(sentryAuthToken)

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(uploadSourceMaps
      ? [
          sentryVitePlugin({
            org: process.env.SENTRY_ORG,
            project: process.env.SENTRY_PROJECT,
            authToken: sentryAuthToken,
            release: { name: process.env.VITE_SENTRY_RELEASE },
            // Delete the emitted .map files after upload so they are NOT public.
            sourcemaps: { filesToDeleteAfterUpload: ['./dist/**/*.map'] },
          }),
        ]
      : []),
  ],
  build: {
    // "hidden" emits maps without a sourceMappingURL comment; the plugin uploads
    // then deletes them. Off entirely when we are not uploading.
    sourcemap: uploadSourceMaps ? 'hidden' : false,
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    // Vitest runs the co-located unit tests under src/ only. Playwright specs
    // in tests/e2e/ (*.spec.ts) are driven by `npm run test:e2e`, not Vitest.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // Keep the app logger quiet during tests (it resolves its level at import).
    // The logger's own test overrides this per-case via createLogger(level).
    env: { VITE_LOG_LEVEL: 'silent' },
  },
})

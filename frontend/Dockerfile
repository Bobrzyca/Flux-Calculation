# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Build stage — compile the production bundle with Node (matches the server's
# Node 24 toolchain). Vite inlines VITE_* vars at BUILD time, so the API base
# URL is baked here via a build ARG.
# ---------------------------------------------------------------------------
FROM node:24-slim AS build

WORKDIR /app

# Install deps from the lockfile first for better layer caching. `npm ci`
# needs devDependencies too (tsc, vite), so we don't pass --omit=dev.
COPY package.json package-lock.json ./
RUN npm ci

# Where the browser should send API calls. Default "/api" is relative, so the
# nginx server below proxies it to the backend over the shared network — the
# app is same-origin and needs no CORS in production.
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Sentry (browser) config, inlined by Vite at build time. Monitoring is off when
# VITE_SENTRY_DSN is empty; the DSN is not secret (it ships in the bundle).
ARG VITE_SENTRY_DSN=
ARG VITE_SENTRY_ENVIRONMENT=production
ARG VITE_SENTRY_RELEASE=
ARG VITE_SENTRY_TRACES_SAMPLE_RATE=0
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN \
    VITE_SENTRY_ENVIRONMENT=$VITE_SENTRY_ENVIRONMENT \
    VITE_SENTRY_RELEASE=$VITE_SENTRY_RELEASE \
    VITE_SENTRY_TRACES_SAMPLE_RATE=$VITE_SENTRY_TRACES_SAMPLE_RATE

# Source-map upload to Sentry (readable stack traces). Only happens when
# SENTRY_AUTH_TOKEN is set; maps are generated "hidden" and deleted after upload
# so they are never served by nginx. The token is SECRET — see report.md.
ARG SENTRY_AUTH_TOKEN=
ARG SENTRY_ORG=
ARG SENTRY_PROJECT=
ENV SENTRY_AUTH_TOKEN=$SENTRY_AUTH_TOKEN \
    SENTRY_ORG=$SENTRY_ORG \
    SENTRY_PROJECT=$SENTRY_PROJECT

COPY . .
RUN npm run build            # tsc -b && vite build -> /app/dist

# ---------------------------------------------------------------------------
# Production stage — serve the static bundle with nginx and proxy /api.
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA routing + /api reverse proxy to the backend service.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

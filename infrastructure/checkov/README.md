# Checkov — IaC / container / CI security scanning

[Checkov](https://www.checkov.io/) statically scans this repo's container images,
GitHub Actions workflows, and the tree for hardcoded secrets.

## Run locally

```bash
pip install checkov
cd <repo-root>
checkov --config-file infrastructure/checkov/.checkov.yaml
```

CI runs the same command (`.github/workflows/test.yml`, job `checkov`).

## What it covers

| Framework | Scans |
|---|---|
| `dockerfile` | `backend/Dockerfile`, `frontend/Dockerfile` |
| `github_actions` | `.github/workflows/*.yml` |
| `secrets` | hardcoded credentials anywhere (minus vendored dirs) |

Checkov has **no docker-compose scanner**, so `docker-compose.yml` is not covered
here — its security posture is reviewed by hand (internal-only services, no host
ports except Traefik's 80/443, named volumes, log rotation).

## Suppressions

All skips live in `.checkov.yaml` with a justification comment. Current:

- **`CKV_DOCKER_3`** (non-root user) — frontend `nginx:alpine` master needs root to
  bind `:80`; the container is internal-only behind Traefik. Backend runs non-root.

To suppress a finding inline instead, add a comment above the line:
`# checkov:skip=CKV_XXX_YY: <reason>`.

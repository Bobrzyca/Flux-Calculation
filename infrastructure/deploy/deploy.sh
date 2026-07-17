#!/usr/bin/env bash
#
# Safe production deploy for the Flux Calculation stack.
#
# Invoked by CI over SSH, e.g.:  ssh deploy@host <git-sha>
# (with a forced-command key the SHA arrives in $SSH_ORIGINAL_COMMAND).
#
# Guarantees:
#   * deploys a specific, validated commit (no arbitrary command execution),
#   * migrations run idempotently (backend applies them on startup),
#   * health-checks backend + frontend + the Traefik edge,
#   * rolls back to the previous commit if the health-check fails.
#
# The deploy path is CI-MANAGED: do not hand-edit tracked files there. Untracked/
# git-ignored files (`.env`, `traefik/htpasswd`, `data/`) are preserved across
# checkouts. Config that must survive a deploy has to live in git (or be
# git-ignored on the server), never as an uncommitted edit to a tracked file.
set -Eeuo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/root/Flux-Calculation}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-150}"
HEALTH_URL="${HEALTH_URL:-https://flux-calculation.aibr.cz/api/health}"

log() { printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"; }
die() { log "ERROR: $*"; exit 3; }

# --- Resolve + validate the target ref (injection-safe) --------------------
# Accept it from the first arg, else SSH_ORIGINAL_COMMAND (forced-command key),
# else origin/main. Only a hex SHA or origin/main is allowed.
REF="${1:-${SSH_ORIGINAL_COMMAND:-origin/main}}"
REF="${REF#deploy }"   # tolerate a "deploy <sha>" forced command
if ! [[ "$REF" =~ ^[0-9a-fA-F]{7,40}$ || "$REF" == "origin/main" ]]; then
  die "refusing to deploy unrecognised ref: '$REF'"
fi

cd "$DEPLOY_PATH" || die "deploy path not found: $DEPLOY_PATH"
command -v docker >/dev/null || die "docker not available to the deploy user"

PREV_SHA="$(git rev-parse HEAD)"
log "Deploy start: path=$DEPLOY_PATH prev=$PREV_SHA target=$REF"

git fetch --all --prune --tags --quiet
git checkout --force "$REF" --quiet
NEW_SHA="$(git rev-parse HEAD)"
log "Checked out $NEW_SHA"

deploy_stack() {
  # SENTRY_RELEASE flows to the backend env and the frontend build-arg via
  # docker-compose interpolation. Migrations run on backend startup, idempotently.
  local sha="$1"
  SENTRY_RELEASE="$sha" docker compose up -d --build --remove-orphans
}

healthcheck() {
  local deadline svc cid status running code
  deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
  for svc in backend frontend; do
    cid="$(docker compose ps -q "$svc" || true)"
    [ -n "$cid" ] || { log "HEALTH FAIL: no container for $svc"; return 1; }
    while :; do
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || echo missing)"
      if [ "$status" = "healthy" ]; then log "HEALTH OK: $svc"; break; fi
      if [ "$status" = "none" ]; then
        running="$(docker inspect -f '{{.State.Running}}' "$cid" 2>/dev/null || echo false)"
        [ "$running" = "true" ] && { log "HEALTH OK (running, no healthcheck): $svc"; break; }
      fi
      if [ "$(date +%s)" -ge "$deadline" ]; then
        log "HEALTH FAIL: $svc status=$status after ${HEALTH_TIMEOUT}s"; return 1
      fi
      sleep 3
    done
  done
  # Edge check: Traefik must answer. 401 = up behind the access gate; 200 = open.
  code="$(curl -sk -o /dev/null -w '%{http_code}' "$HEALTH_URL" || echo 000)"
  case "$code" in
    200|401) log "EDGE OK: Traefik responded $code" ; return 0 ;;
    *)       log "EDGE FAIL: Traefik responded $code" ; return 1 ;;
  esac
}

log "Deploying $NEW_SHA ..."
deploy_stack "$NEW_SHA"

if healthcheck; then
  log "DEPLOY OK: live on $NEW_SHA"
  exit 0
fi

# --- Rollback --------------------------------------------------------------
if [ "$NEW_SHA" = "$PREV_SHA" ]; then
  log "CRITICAL: health-check failed and there is no previous commit to roll back to."
  exit 2
fi
log "Health-check failed -> rolling back to $PREV_SHA"
git checkout --force "$PREV_SHA" --quiet
deploy_stack "$PREV_SHA"
if healthcheck; then
  log "ROLLED BACK: restored $PREV_SHA. Deploy of $NEW_SHA FAILED."
  exit 1
fi
log "CRITICAL: rollback ALSO failed. Manual intervention required (stack left running)."
exit 2

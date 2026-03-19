#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
WEB_SERVICE="${WEB_SERVICE:-AgenikPredict}"
WORKER_SERVICE="${WORKER_SERVICE:-AgenikPredictWorker}"
CANARY_SERVICE="${CANARY_SERVICE:-AgenikPredictWebCanary}"

note() { printf '\n== %s ==\n' "$*"; }
fail() { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }

require_env_example_key() {
  local key="$1"
  rg -n "^${key}=" .env.example >/dev/null 2>&1 || fail ".env.example is missing ${key}"
}

need git
need rg
need curl
need python3
need railway
need uv
need npm

railway_recent() {
  local service="$1"
  local raw
  raw="$(railway deployment list -s "$service" --json 2>/dev/null)" || {
    echo "railway deployment list failed for $service"
    return 0
  }
  RAW_DEPLOYMENTS="$raw" python3 - <<'PY'
import json
import os

try:
    items = json.loads(os.environ["RAW_DEPLOYMENTS"])
except Exception as exc:
    print(f"Could not parse deployment JSON: {exc}")
    raise SystemExit(0)

for item in items[:5]:
    meta = item.get("meta") or {}
    print(
        json.dumps(
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "createdAt": item.get("createdAt"),
                "commitHash": meta.get("commitHash"),
                "branch": meta.get("branch"),
                "reason": meta.get("reason"),
            },
            ensure_ascii=False,
        )
    )
PY
}

cd "$REPO"

note "0. Scope freeze"
git rev-parse --show-toplevel
git rev-parse HEAD
git status --short
git diff --stat -- \
  backend/app/api/report.py \
  backend/app/config.py \
  backend/app/services/report_agent.py \
  backend/app/services/perplexity_provider.py \
  backend/app/services/source_manifest.py \
  backend/app/services/task_handlers.py \
  frontend/src/api/report.js \
  frontend/src/components/GraphPanel.vue \
  frontend/src/components/Step3Simulation.vue \
  frontend/src/views/SimulationRunView.vue \
  backend/tests/test_report_upgrade.py

note "1. Env documentation audit"
test -f .env.example || fail ".env.example missing"
require_env_example_key "PERPLEXITY_API_KEY"
require_env_example_key "REPORT_AGENT_MAX_TOOL_CALLS"
require_env_example_key "REPORT_AGENT_MAX_REFLECTION_ROUNDS"
rg -n "PERPLEXITY_API_KEY|REPORT_AGENT_MAX_TOOL_CALLS|REPORT_AGENT_MAX_REFLECTION_ROUNDS" \
  .env.example \
  backend/app/config.py

note "2. Local verification"
(
  cd backend
  uv run python -m compileall app worker.py run.py
  uv run pytest tests/test_report_upgrade.py
)
(
  cd frontend
  npm run build
)

note "3. Contract audit"
rg -n "analysis_mode" \
  backend/app/api/report.py \
  backend/app/services/task_handlers.py \
  backend/app/services/report_agent.py \
  frontend/src/components/GraphPanel.vue \
  frontend/src/components/Step3Simulation.vue \
  frontend/src/views/SimulationRunView.vue \
  frontend/src/api/report.js

rg -n "PerplexityProvider|SourceManifest|why_this_conclusion|basis_summary|source_attribution|source_manifest_summary" \
  backend/app/services/report_agent.py \
  backend/app/services/perplexity_provider.py \
  backend/app/services/source_manifest.py \
  backend/tests/test_report_upgrade.py

note "4. Artifact persistence audit"
rg -n "source_manifest\\.json|save_source_manifest|get_source_manifest|meta\\.json|prediction_summary\\.json" \
  backend/app/services/report_agent.py \
  backend/app/services/source_manifest.py \
  backend/tests/test_report_upgrade.py

note "5. Railway state before deploy"
HEAD_SHA="$(git rev-parse HEAD)"
echo "HEAD_SHA=$HEAD_SHA"
railway_recent "$WEB_SERVICE"
railway_recent "$WORKER_SERVICE" || true
railway_recent "$CANARY_SERVICE" || true

note "6. Push when ready"
echo "If all green, deploy with:"
echo "  cd $REPO && git push origin HEAD"
# Uncomment only when ready:
# git push origin HEAD

note "7. Poll Railway after push"
cat <<'POLL'
cd /Users/alexanderivenski/Projects/AgenikPredict
railway deployment list -s AgenikPredict --json | python3 - <<'PY'
import json, sys
items = json.load(sys.stdin)
for item in items[:5]:
    meta = item.get("meta") or {}
    print(json.dumps({
        "id": item.get("id"),
        "status": item.get("status"),
        "createdAt": item.get("createdAt"),
        "commitHash": meta.get("commitHash"),
        "branch": meta.get("branch"),
        "reason": meta.get("reason"),
    }, ensure_ascii=False))
PY
railway deployment list -s AgenikPredictWorker --json 2>/dev/null | python3 - <<'PY' || true
import json, sys
items = json.load(sys.stdin)
for item in items[:5]:
    meta = item.get("meta") or {}
    print(json.dumps({
        "id": item.get("id"),
        "status": item.get("status"),
        "createdAt": item.get("createdAt"),
        "commitHash": meta.get("commitHash"),
        "branch": meta.get("branch"),
        "reason": meta.get("reason"),
    }, ensure_ascii=False))
PY
railway deployment list -s AgenikPredictWebCanary --json 2>/dev/null | python3 - <<'PY' || true
import json, sys
items = json.load(sys.stdin)
for item in items[:5]:
    meta = item.get("meta") or {}
    print(json.dumps({
        "id": item.get("id"),
        "status": item.get("status"),
        "createdAt": item.get("createdAt"),
        "commitHash": meta.get("commitHash"),
        "branch": meta.get("branch"),
        "reason": meta.get("reason"),
    }, ensure_ascii=False))
PY
POLL

note "8. Observability checklist after deploy"
cat <<'OBSERVE'
Confirm in Railway logs or dashboard before go-live:
- web startup has no boot/config errors
- worker startup has no task-claim or import errors
- report generation logs do not show uncaught provider exceptions
- Perplexity warnings, if any, are degraded warnings rather than task-fatal crashes
OBSERVE

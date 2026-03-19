#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROD_URL="${PROD_URL:-https://app.agenikpredict.com}"

# REQUIRED FOR SUCCESS-PATH SMOKE
SIM_ID_QUICK="${SIM_ID_QUICK:-}"
SIM_ID_GLOBAL="${SIM_ID_GLOBAL:-}"

# OPTIONAL: set this to a real simulation_id if you want explicit conflict behavior
SIM_ID_CONFLICT="${SIM_ID_CONFLICT:-}"

note() { printf '\n== %s ==\n' "$*"; }
fail() { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "Missing command: $1"; }

json_pretty() {
  python3 -m json.tool
}

extract_field() {
  local payload="$1"
  local path="$2"
  PAYLOAD="$payload" PATH_EXPR="$path" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["PAYLOAD"])
path = os.environ["PATH_EXPR"].split(".")
cur = payload
for key in path:
    if isinstance(cur, dict) and key in cur:
        cur = cur[key]
    else:
        raise SystemExit(1)
if cur is None:
    raise SystemExit(1)
print(cur)
PY
}

post_json() {
  local url="$1"
  local token="$2"
  local data="$3"
  if [[ -n "$token" ]]; then
    curl --fail-with-body -sS -X POST "$url" \
      -H "Authorization: Bearer $token" \
      -H 'Content-Type: application/json' \
      -d "$data"
  else
    curl --fail-with-body -sS -X POST "$url" \
      -H 'Content-Type: application/json' \
      -d "$data"
  fi
}

get_json() {
  local url="$1"
  local token="${2:-}"
  if [[ -n "$token" ]]; then
    curl --fail-with-body -sS "$url" -H "Authorization: Bearer $token"
  else
    curl --fail-with-body -sS "$url"
  fi
}

request_with_status() {
  local method="$1"
  local url="$2"
  local token="$3"
  local data="${4:-}"
  local tmp_body
  tmp_body="$(mktemp)"
  local http_code

  if [[ "$method" == "POST" ]]; then
    http_code="$(
      curl -sS -o "$tmp_body" -w '%{http_code}' -X POST "$url" \
        -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' \
        -d "$data"
    )"
  else
    http_code="$(
      curl -sS -o "$tmp_body" -w '%{http_code}' "$url" \
        -H "Authorization: Bearer $token"
    )"
  fi

  printf '%s\n' "$http_code"
  cat "$tmp_body"
  rm -f "$tmp_body"
}

wait_for_report_completion() {
  local report_id="$1"
  local token="$2"
  local label="$3"
  local attempts="${4:-40}"
  local sleep_seconds="${5:-15}"
  local status=""

  for ((attempt=1; attempt<=attempts; attempt++)); do
    local progress_json
    progress_json="$(get_json "$PROD_URL/api/report/$report_id/progress" "$token")"
    echo "$progress_json" | json_pretty | sed -n '1,120p'
    status="$(extract_field "$progress_json" "data.status" || true)"
    echo "${label}_PROGRESS_STATUS=${status:-unknown}"
    if [[ "$status" == "completed" ]]; then
      return 0
    fi
    if [[ "$status" == "failed" ]]; then
      fail "$label report entered failed state"
    fi
    sleep "$sleep_seconds"
  done

  fail "$label report did not complete within polling window"
}

need curl
need python3

cd "$REPO"

note "8. Public health smoke"
HEALTH_JSON="$(get_json "$PROD_URL/health")"
echo "$HEALTH_JSON" | json_pretty

note "9. Demo auth"
DEMO_JSON="$(post_json "$PROD_URL/api/auth/demo" "" '{}')"
echo "$DEMO_JSON" | json_pretty

ACCESS_TOKEN="$(
  DEMO_JSON="$DEMO_JSON" python3 - <<'PY'
import json
import os

data = json.loads(os.environ["DEMO_JSON"])
for candidate in [
    data.get("token"),
    data.get("access_token"),
    (data.get("data") or {}).get("token"),
    (data.get("data") or {}).get("access_token"),
]:
    if candidate:
        print(candidate)
        break
PY
)"
test -n "${ACCESS_TOKEN:-}" || fail "Could not extract demo token"
echo "DEMO TOKEN OK"

note "10. Optional public API smoke"
get_json "$PROD_URL/api/report/backtest/cases" | json_pretty | sed -n '1,80p'
get_json "$PROD_URL/api/report/backtest/metrics" | json_pretty | sed -n '1,140p'

note "11. Quick success-path smoke"
test -n "$SIM_ID_QUICK" || fail "Set SIM_ID_QUICK"
QUICK_PAYLOAD="{\"simulation_id\":\"$SIM_ID_QUICK\",\"analysis_mode\":\"quick\",\"language\":\"en\"}"
QUICK_JSON="$(post_json "$PROD_URL/api/report/generate" "$ACCESS_TOKEN" "$QUICK_PAYLOAD")"
echo "$QUICK_JSON" | json_pretty

QUICK_TASK_ID="$(extract_field "$QUICK_JSON" "data.task_id" || true)"
QUICK_REPORT_ID="$(extract_field "$QUICK_JSON" "data.report_id" || true)"

echo "QUICK_TASK_ID=${QUICK_TASK_ID:-}"
echo "QUICK_REPORT_ID=${QUICK_REPORT_ID:-}"
test -n "${QUICK_REPORT_ID:-}" || fail "Quick smoke did not return report_id"

note "12. Quick status/progress endpoints"
QUICK_STATUS_PAYLOAD="{\"task_id\":\"${QUICK_TASK_ID:-}\",\"simulation_id\":\"$SIM_ID_QUICK\",\"analysis_mode\":\"quick\",\"language\":\"en\"}"
QUICK_STATUS_JSON="$(post_json "$PROD_URL/api/report/generate/status" "$ACCESS_TOKEN" "$QUICK_STATUS_PAYLOAD")"
echo "$QUICK_STATUS_JSON" | json_pretty | sed -n '1,200p'
echo "QUICK_STATUS_LANGUAGE=$(extract_field "$QUICK_STATUS_JSON" "data.language_used" || true)"
echo "QUICK_STATUS_MODE=$(extract_field "$QUICK_STATUS_JSON" "data.analysis_mode" || true)"

wait_for_report_completion "$QUICK_REPORT_ID" "$ACCESS_TOKEN" "QUICK"

note "13. Global success-path smoke"
test -n "$SIM_ID_GLOBAL" || fail "Set SIM_ID_GLOBAL"
GLOBAL_PAYLOAD="{\"simulation_id\":\"$SIM_ID_GLOBAL\",\"analysis_mode\":\"global\",\"language\":\"en\"}"
GLOBAL_JSON="$(post_json "$PROD_URL/api/report/generate" "$ACCESS_TOKEN" "$GLOBAL_PAYLOAD")"
echo "$GLOBAL_JSON" | json_pretty

GLOBAL_TASK_ID="$(extract_field "$GLOBAL_JSON" "data.task_id" || true)"
GLOBAL_REPORT_ID="$(extract_field "$GLOBAL_JSON" "data.report_id" || true)"

echo "GLOBAL_TASK_ID=${GLOBAL_TASK_ID:-}"
echo "GLOBAL_REPORT_ID=${GLOBAL_REPORT_ID:-}"
test -n "${GLOBAL_REPORT_ID:-}" || fail "Global smoke did not return report_id"

note "14. Global status/progress endpoints"
GLOBAL_STATUS_PAYLOAD="{\"task_id\":\"${GLOBAL_TASK_ID:-}\",\"simulation_id\":\"$SIM_ID_GLOBAL\",\"analysis_mode\":\"global\",\"language\":\"en\"}"
GLOBAL_STATUS_JSON="$(post_json "$PROD_URL/api/report/generate/status" "$ACCESS_TOKEN" "$GLOBAL_STATUS_PAYLOAD")"
echo "$GLOBAL_STATUS_JSON" | json_pretty | sed -n '1,200p'
echo "GLOBAL_STATUS_LANGUAGE=$(extract_field "$GLOBAL_STATUS_JSON" "data.language_used" || true)"
echo "GLOBAL_STATUS_MODE=$(extract_field "$GLOBAL_STATUS_JSON" "data.analysis_mode" || true)"

wait_for_report_completion "$GLOBAL_REPORT_ID" "$ACCESS_TOKEN" "GLOBAL"

note "15. Optional explicit conflict-path smoke"
if [[ -n "$SIM_ID_CONFLICT" ]]; then
  FIRST_CONFLICT_JSON="$(post_json "$PROD_URL/api/report/generate" "$ACCESS_TOKEN" "{\"simulation_id\":\"$SIM_ID_CONFLICT\",\"analysis_mode\":\"quick\",\"language\":\"en\"}")"
  echo "$FIRST_CONFLICT_JSON" | json_pretty | sed -n '1,120p'

  mapfile -t CONFLICT_RESPONSE < <(request_with_status "POST" "$PROD_URL/api/report/generate" "$ACCESS_TOKEN" "{\"simulation_id\":\"$SIM_ID_CONFLICT\",\"analysis_mode\":\"global\",\"language\":\"en\"}")
  CONFLICT_STATUS="${CONFLICT_RESPONSE[0]:-}"
  SECOND_CONFLICT_JSON="$(printf '%s\n' "${CONFLICT_RESPONSE[@]:1}")"
  echo "CONFLICT_HTTP_STATUS=${CONFLICT_STATUS:-unknown}"
  echo "$SECOND_CONFLICT_JSON" | json_pretty | sed -n '1,160p'
  [[ "${CONFLICT_STATUS:-}" == "409" || "${CONFLICT_STATUS:-}" == "200" ]] || fail "Conflict-path smoke returned unexpected HTTP status: ${CONFLICT_STATUS:-unknown}"

  echo "Expect the second call to show conflict/reuse behavior, not a second independent active task."
else
  echo "SIM_ID_CONFLICT not set; skipping explicit conflict-path smoke."
fi

note "16. Completed report retrieval"
echo "Quick report payload:"
QUICK_REPORT_JSON="$(get_json "$PROD_URL/api/report/$QUICK_REPORT_ID" "$ACCESS_TOKEN")"
echo "$QUICK_REPORT_JSON" | json_pretty | sed -n '1,260p'
[[ "$(extract_field "$QUICK_REPORT_JSON" "data.analysis_mode")" == "quick" ]] || fail "Quick report payload missing quick analysis_mode"
extract_field "$QUICK_REPORT_JSON" "data.source_manifest_summary.source_count" >/dev/null
extract_field "$QUICK_REPORT_JSON" "data.explainability.why_this_conclusion" >/dev/null
extract_field "$QUICK_REPORT_JSON" "data.explainability.basis_summary" >/dev/null
extract_field "$QUICK_REPORT_JSON" "data.explainability.source_attribution" >/dev/null

echo "Global report payload:"
GLOBAL_REPORT_JSON="$(get_json "$PROD_URL/api/report/$GLOBAL_REPORT_ID" "$ACCESS_TOKEN")"
echo "$GLOBAL_REPORT_JSON" | json_pretty | sed -n '1,260p'
[[ "$(extract_field "$GLOBAL_REPORT_JSON" "data.analysis_mode")" == "global" ]] || fail "Global report payload missing global analysis_mode"
extract_field "$GLOBAL_REPORT_JSON" "data.source_manifest_summary.source_count" >/dev/null
extract_field "$GLOBAL_REPORT_JSON" "data.explainability.why_this_conclusion" >/dev/null
extract_field "$GLOBAL_REPORT_JSON" "data.explainability.basis_summary" >/dev/null
extract_field "$GLOBAL_REPORT_JSON" "data.explainability.source_attribution" >/dev/null

note "17. What must be present in report payload"
echo "- analysis_mode"
echo "- source_manifest_summary"
echo "- explainability.why_this_conclusion"
echo "- explainability.basis_summary"
echo "- explainability.source_attribution"

note "18. Go/No-Go gates"
echo "GO only if all are true:"
echo "  1) .env.example contains new keys"
echo "  2) backend compileall passed"
echo "  3) pytest tests/test_report_upgrade.py passed"
echo "  4) frontend build passed"
echo "  5) /health is green after deploy"
echo "  6) quick path works"
echo "  7) global path works"
echo "  8) no-key Perplexity path does not break generation"
echo "  9) report payload contains analysis_mode + provenance/explainability fields"
echo " 10) conflict path does not violate one-active-task-per-simulation"

note "19. Handoff template"
cat <<'HANDOFF'
DEPLOYED_COMMIT=<sha>
WEB_DEPLOY=<deployment-id>
WORKER_DEPLOY=<deployment-id>
CANARY_DEPLOY=<deployment-id or n/a>

ENV_APPLIED:
- PERPLEXITY_API_KEY=<set|unset>
- REPORT_AGENT_MAX_TOOL_CALLS=<value>
- REPORT_AGENT_MAX_REFLECTION_ROUNDS=<value>

PASSED:
- env example audit
- compileall
- pytest tests/test_report_upgrade.py
- frontend build
- /health
- quick smoke
- global smoke
- status/progress endpoints
- payload metadata verification
- optional conflict-path verification

BLOCKERS:
- <none or exact blocker>

ROLLBACK:
- revert to <sha>
- unset PERPLEXITY_API_KEY if needed
- redeploy previous healthy commit

NEXT_STEP:
- expose source_manifest_summary + explainability in report UI
- add retrieval tests for multiple completed variants per simulation
HANDOFF

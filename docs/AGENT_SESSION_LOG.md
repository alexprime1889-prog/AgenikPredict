# Agent Session Log

## [2026-03-17 18:05] - Start: Production failure investigation and stabilization

**Agent/Tool:** Codex CLI

**Started:**
- Investigate why Railway/production runs do not process results end-to-end.
- Reproduce critical failures locally.
- Fix blocking auth, billing, account, and processing pipeline issues.
- Verify with build/runtime/API checks before reporting completion.

**Not finished:**
- Root cause confirmation for production processing failure.
- Code fixes and regression verification.
- Deployment-readiness summary.

**Known issues:**
- Magic-link auth logic is internally inconsistent.
- Billing frontend/backend contract is broken and frontend build fails.
- Stripe webhook is non-idempotent and pack-credit logic is inconsistent.
- Production environment assumptions appear incomplete.

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/api/auth.py` | Fixed magic-link auth flow and added compatibility billing status endpoint |
| `backend/app/api/billing.py` | Added billing status endpoint, restored pack helpers, aligned Stripe crediting metadata, added webhook idempotency guard |
| `backend/app/api/graph.py` | Enabled URL-only ontology input and removed misplaced ontology billing gate |
| `backend/app/api/report.py` | Persist placeholder report/progress before background generation starts |
| `backend/app/models/user.py` | Aligned trial/billing semantics and added Stripe webhook event tracking |
| `backend/app/services/ontology_generator.py` | Enabled fallback-aware ontology JSON generation |
| `backend/app/services/report_agent.py` | Persisted `generating` report state earlier |
| `backend/app/config.py` | Added production JWT secret validation |
| `backend/run.py` | Exposed `run:app` and prepared production WSGI startup path |
| `backend/pyproject.toml` | Added `gunicorn` runtime dependency |
| `backend/uv.lock` | Refreshed lockfile for `gunicorn` |
| `Dockerfile.production` | Switched production container command to `gunicorn` |
| `frontend/src/api/billing.js` | Restored missing billing API helpers |
| `frontend/src/api/report.js` | Pointed report status helper to report progress endpoint |
| `frontend/src/components/BillingBadge.vue` | Fixed billing status fetch contract |
| `frontend/src/router/index.js` | Added `/account` route |
| `frontend/src/store/auth.js` | Clear billing state on logout |
| `frontend/src/views/Home.vue` | Added Account navigation link |
| `frontend/src/views/MainView.vue` | Forwarded pending URLs and market-data flag into ontology request |

**Next steps:**
- Wait for Railway deployment `159eddb4-3341-4f6c-a242-65b9ebd6e98f` to finish.
- Run live smoke tests against `app.agenikpredict.com`.
- Summarize restored behavior and remaining production hardening gaps.

## [2026-03-17 21:20] - Checkpoint: Railway production stabilization audit refresh

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Re-validated current Railway service state and logs for production failure path.
- Re-checked current code (latest worktree) for auth/billing/report/simulation/runtime behavior.
- Re-ran local verification:
  - `npm run build` (pass)
  - `uv run python -c "from app import create_app; ..."` (pass, with JWT secret warning when unset locally)

**Key evidence captured:**
- Railway logs show ontology request blocked with `402` on 2026-03-17 after `=== Starting ontology generation ===`.
- Runtime still starts Flask development server in production (`run.py` entrypoint).
- Async report generation and simulation execution still rely on daemon thread + subprocess lifecycle in web service process.
- Frontend pending-upload URL/market-data options are not forwarded in `MainView` upload request.

**Files changed:**
| File | Change |
|------|--------|
| `docs/plan-comparison-log.md` | Added Item 5 execution comparison entry |

**Pending:**
- Final user-facing concise audit with severity ordering and production-ready priority sequence.

## [2026-03-17 22:16] - Checkpoint: Live repair, durability, and production smoke verification

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Added persistent Railway volume for `/app/backend/uploads` and confirmed it is attached to service `AgenikPredict`.
- Hardened ontology fallback behavior so JSON generation no longer dies when the cheap secondary model returns `429 insufficient balance`.
- Reworked report generation billing from `check -> generate -> deduct later` into reservation/finalize/refund flow.
- Removed incorrect report-chat paywall and replaced it with completed-report gating.
- Added ownership checks to report and simulation endpoints that previously leaked status/log data or allowed cross-tenant control by `simulation_id` / `report_id`.
- Added repository verification script `scripts/verify_production_fixes.sh` and ran it successfully.
- Deployed live fixes to Railway (`840d87c8-1bdf-4c0c-87ba-0fcdf097fbe5`, then `dbcd8206-e513-4483-a13c-153c48bfd105`, then hotfix `e4b0af76-98ee-4d2c-8655-59442922e687`).
- Re-ran full live smoke after the hotfix:
  - demo auth ok
  - ontology generate ok
  - graph build ok
  - simulation create ok
  - simulation prepare ok
  - simulation start/run ok (`max_rounds=1`)
  - report generation starts and progress endpoint responds

**Verified Evidence**
```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ npm run build
# success
```

```bash
$ cd backend && uv run python -m compileall app && uv run gunicorn --check-config run:app
# success
```

```bash
$ railway volume list --json
# volume 7daea671-804b-444a-8de1-76dea8ed83cc mounted at /app/backend/uploads
```

```bash
$ railway deployment list -s AgenikPredict --json
# latest deployment e4b0af76-98ee-4d2c-8655-59442922e687 -> SUCCESS
```

```bash
$ live smoke
LIVE_SMOKE_OK {"project_id":"proj_551ec0f0de4c","graph_id":"agenikpredict_b1267e60cb314326","simulation_id":"sim_397537230812","report_id":"report_df6e603b6cf1"}
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/api/report.py` | Added reservation-based billing, fixed report chat gating, added report access checks and failure handling |
| `backend/app/api/simulation.py` | Added simulation ownership checks across read/control endpoints and fixed prepare regression |
| `backend/app/models/user.py` | Added reservation/finalize/refund helpers for report billing |
| `backend/app/utils/llm_client.py` | Added robust secondary->primary fallback chain and JSON text-repair parsing |
| `scripts/verify_production_fixes.sh` | Added regression verification script for auth/billing/access hardening |
| `docs/plan-comparison-log.md` | Added execution evidence for live hardening and smoke |

**Remaining risks:**
- `TaskManager` is still in-memory; task IDs do not survive restart/redeploy.
- Graph task endpoints are still not fully ownership-scoped by task metadata.
- Long-running in-process jobs can delay zero-downtime deploys, as seen during the report-generation drain window.

**Next steps:**
- Wait for final reviewer pass and then deliver concise production status + residual-risk summary to user.

## [2026-03-17 22:28] - Checkpoint: UI source-of-truth mapping

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Verified that the current production frontend bundle matches the current local dirty workspace exactly, not just `origin/main`.
- Verified that a second worktree exists at `claude/funny-villani` and contains a different UI/backend slice.
- Confirmed that `claude/funny-villani` does not currently build as a frontend bundle because its `billing.js` API layer is incomplete.
- Created an exact map showing which UI/API files come from `origin/main`, current local `main`, and `claude/funny-villani`.

**Verified Evidence**
```bash
$ curl https://app.agenikpredict.com
# serves /assets/index-CkYmH1Ba.js and /assets/index-DyQi3PGL.css
```

```bash
$ npm run build
# current local main build produces the same asset names:
# index-CkYmH1Ba.js, index-DyQi3PGL.css, AccountView-D3tfCVMU.js, AdminView-Bf5dw1XZ.js
```

```bash
$ sha256(prod assets) == sha256(local current-main assets)
# exact match for index js/css and Account/Admin dynamic chunks
```

```bash
$ git worktree list
# /Users/alexanderivenski/projects/AgenikPredict/.claude/worktrees/funny-villani  7de8790 [claude/funny-villani]
```

```bash
$ cd .../funny-villani && npm run build
# fails: "getBillingPrices" is not exported by src/api/billing.js
```

**Files changed:**
| File | Change |
|------|--------|
| `docs/ui_source_of_truth_map_2026-03-18.md` | Added exact production vs current-main vs worktree UI map |
| `docs/plan-comparison-log.md` | Added execution evidence for UI source-of-truth mapping |

**Key conclusion:**
- Production UI is not stale relative to the local workspace used for direct deploy.
- The perceived “old UI” comes from divergence between multiple local sources of truth:
  - `origin/main`
  - current dirty `main` workspace
  - `claude/funny-villani`
  - possibly another YAI-edited workspace not yet inspected

## [2026-03-17 23:47] - Checkpoint: Task lease, dedupe, and reaper hardening

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Added DB-backed task execution metadata for `execution_key`, lease ownership, heartbeat timestamps, attempt counts, and started/finished timestamps.
- Wrapped `graph_build`, `simulation_prepare`, and `report_generate` background jobs with `claim_task()` and heartbeat-backed leases so duplicate workers cannot blindly execute the same task instance.
- Added execution-key dedupe on the hot API paths so repeated triggers now return the active task instead of spawning another background path.
- Started a lightweight task reaper in app startup to reconcile expired/abandoned tasks in addition to the existing startup recovery.
- Expanded the verification script to cover lease claim exclusivity, task persistence of execution metadata, and duplicate `simulation_prepare` requests returning the original active task.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"
backend_boot_ok
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/models/task.py` | Added persistent lease metadata, claim/heartbeat helpers, active-task lookup, and background reaper |
| `backend/app/api/graph.py` | Added execution-key dedupe and lease-guarded graph build execution |
| `backend/app/api/simulation.py` | Added duplicate prepare-task reuse and lease-guarded simulation preparation |
| `backend/app/api/report.py` | Added active report-task reuse and lease-guarded report generation |
| `backend/app/config.py` | Added task lease/heartbeat configuration |
| `backend/app/__init__.py` | Starts task reaper alongside task DB initialization |
| `scripts/verify_production_fixes.sh` | Added lease/dedupe assertions for the new runtime layer |

**Remaining risks:**
- Background execution still originates from the web process; this slice prevents duplicate claims but is not yet a true separate worker service.
- Task recovery is still conservative terminalization, not retry/backoff/DLQ semantics.
- Lease metadata is persisted, but there is not yet a queue-level dispatcher for cross-instance job stealing or resume.

**Next steps:**
- Run reviewer pass on the new lease/reaper code.
- If clean, move to the next runtime slice: explicit worker loop / queue semantics and retry policy.

## [2026-03-17 23:58] - Checkpoint: Expert-analysis comparison and roadmap merge

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Compared the provided expert interim analysis against the existing production/fidelity audit and the 7-day execution roadmap.
- Distinguished which expert findings are already covered, which are stronger than our current plan, and which are partially outdated because the local workspace has already fixed the original UX/API gaps.
- Wrote a merged-priority memo so the team can keep the current runtime-hardening order while explicitly adding the expert’s strongest product-science gaps right after that phase.

**Verified Evidence**
```bash
$ sed -n '1,260p' docs/7_day_execution_roadmap.md
$ sed -n '1,260p' docs/agenikpredict_production_and_fidelity_audit.md
$ rg -n "billing-status|/account|getBillingPrices|createCheckout|backtest|seed|probability|confidence" backend frontend docs
# used to verify current roadmap coverage and current local-state corrections
```

## [2026-03-18 07:32] - Checkpoint: Single-platform simulation runtime hotfix

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Proved that the previous weak live smoke was an input-quality problem, then built a high-signal Helios fixture that produced a real graph (`15 nodes / 31 edges`, `12 qualifying entities`).
- Isolated two concrete single-platform defects from that stronger smoke:
  - `_check_simulation_prepared()` incorrectly required `twitter_profiles.csv` even when `enable_twitter=false`.
  - `SimulationRunner.start_simulation(platform='reddit'|'twitter')` launched legacy single-platform scripts while the monitor only understood the unified `run_parallel_simulation.py` action-log contract.
- Fixed platform-aware preparation readiness and switched single-platform starts to the unified parallel runner with `--reddit-only` / `--twitter-only`.
- Extended regression coverage:
  - reddit-only readiness check without `twitter_profiles.csv`
  - twitter-only readiness check with `twitter_profiles.csv`
  - stubbed single-platform runs that emit `actions.jsonl` and are observed end-to-end by `SimulationRunner`
- Triggered Railway deployment `ace15292-8a37-42bc-9638-6ef605c4e3e8` with the final hotfix; deployment status was still `BUILDING` at this checkpoint.

**Verified Evidence**
```bash
$ cd backend && uv run python -m py_compile app/api/simulation.py app/services/simulation_runner.py
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
# verify_production_fixes: PASS (assertion suite passed)
```

```bash
$ live diagnostic smoke on https://app.agenikpredict.com
# high-signal Helios project produced graph_id=agenikpredict_d368692c16914205
# entities endpoint returned filtered_count=12 with real labels:
# MediaOutlet, Executive, OnlineCommunity, AdvocacyGroup, InvestmentFirm, GovernmentAgency, UtilityCompany, Person
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/api/simulation.py` | Made readiness checks platform-aware and fixed single-platform `profiles_count` reporting |
| `backend/app/services/simulation_runner.py` | Routed single-platform starts through `run_parallel_simulation.py` with platform-only flags |
| `scripts/verify_production_fixes.sh` | Added single-platform readiness and runner-behavior regressions |

**Next steps:**
- Wait for Railway deploy `ace15292-8a37-42bc-9638-6ef605c4e3e8` to finish.
- Run a live reddit-only smoke on the Helios fixture and confirm `prepare -> start -> run-status completed`.
- If green, continue to report generation smoke on the same fixture.

**Files changed:**
| File | Change |
|------|--------|
| `docs/expert_analysis_comparison_2026-03-17.md` | Added expert-analysis vs current-roadmap comparison and merged priority order |

**Key conclusion:**
- The expert analysis is stronger on product-science gaps: `live evidence tools`, `structured probability outputs`, `Prediction Ledger`, and `parallel scenario modeling`.
- The current roadmap is stronger on execution order for the next week: `runtime durability -> determinism -> market grounding -> calibration`.
- The right move is to keep the current runtime-hardening sequence and elevate the expert’s product-science items to the very next layer after worker/queue durability is finished.

## [2026-03-18 00:04] - Checkpoint: Day 3.5 worker-split foundation

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Created a dedicated execution-block doc for `Day 3.5 / Day 4`.
- Added reusable long-running task handlers in `backend/app/services/task_handlers.py`.
- Added `TASK_EXECUTION_MODE`, worker poll/batch config, DB-backed `claim_next_task()`, and a new polling worker loop in `backend/app/services/task_worker.py`.
- Added separate worker entrypoint `backend/worker.py`.
- Switched API task dispatch to `enqueue + dispatch-by-mode`; `report_generate` is now explicitly validated in `worker` mode, while `graph_build` and `simulation_prepare` were smoke-tested at handler level after the refactor.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app worker.py run.py
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ worker-mode report smoke
worker_mode_report_ok
```

```bash
$ graph handler smoke
graph_handler_ok
```

```bash
$ simulation handler smoke
simulation_handler_ok
```

**Files changed:**
| File | Change |
|------|--------|
| `docs/day_3_5_day_4_execution_block.md` | Added concrete Day 3.5 / Day 4 execution block |
| `backend/app/config.py` | Added execution-mode and worker polling config |
| `backend/app/models/task.py` | Added `claim_next_task()` for DB-backed worker polling |
| `backend/app/services/task_handlers.py` | Added reusable execution handlers for graph/simulation/report tasks |
| `backend/app/services/task_worker.py` | Added dispatch helper and polling worker loop |
| `backend/worker.py` | Added dedicated worker entrypoint |
| `backend/app/api/graph.py` | Switched graph task path to dispatcher-based execution |
| `backend/app/api/simulation.py` | Switched prepare task path to dispatcher-based execution |
| `backend/app/api/report.py` | Switched report generation to dispatcher-based execution and persisted worker metadata |

**Remaining risks:**
- `graph_build` and `simulation_prepare` now use the shared dispatcher path, but only handler-level smokes were run; no full worker-mode end-to-end for those two yet.
- Retry/backoff, DLQ and true resume semantics are still not implemented.
- Railway rollout and second-process orchestration are still pending.

**Next steps:**
- Add retry/backoff policy and explicit worker-run smoke for graph/simulation in worker mode.
- Then move into the first scientific layer: `ReportAgent live evidence + structured probabilities + Prediction Ledger`.

## [2026-03-17 23:10] - Start: Day 1 execution roadmap implementation

**Agent/Tool:** Codex CLI

**Started:**
- Execute Day 1 of the 7-day roadmap.
- Close remaining owner-scoping leaks in graph/simulation/report/task endpoints.
- Add minimal CI and smoke guardrails before persistent task migration work.
- Write the task-store cutover plan artifact required for Day 2.

**Not finished:**
- Verification of new access-control coverage.
- CI workflow addition and smoke-script expansion.
- Task-store cutover plan document.

**Known issues:**
- `TaskManager` is still in-memory and current task IDs do not survive restart.
- Graph/task endpoints still had partial metadata-based access blind spots at the start of this stage.
- Repository currently has only a Docker image workflow and no mandatory PR safety gate.

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/models/task.py` | Added task filtering support for scoped task listing |
| `backend/app/models/project.py` | Added lookup helpers for `graph_id` and `graph_build_task_id` |
| `backend/app/api/graph.py` | Started owner-scoping hardening for graph/task endpoints and task metadata |
| `backend/app/api/simulation.py` | Started graph/task access verification for entity/profile/prepare endpoints |
| `backend/app/api/report.py` | Started task/graph access verification for report status and debug endpoints |

**Next steps:**
- Finish Day 1 backend access hardening.
- Expand `verify_production_fixes.sh` to cover the new guarded endpoints.
- Add CI workflow for build/sanity/security smoke.

**Finished:**
- Closed the highest-risk owner leaks for `graph`, `simulation`, and `report` endpoints that previously accepted raw `task_id` or `graph_id` without strong ownership verification.
- Added project lookup helpers for `graph_id` and `graph_build_task_id`, and added richer task metadata (`owner_id`, `project_id`, `graph_id`) when new graph/simulation/report tasks are created.
- Added a Day 1 CI workflow with three guardrails: frontend build, backend boot sanity, and security smoke.
- Expanded the verification script to cover the new access-control cases for graph tasks, graph data, simulation graph-driven endpoints, and report debug tools.
- Wrote the task-store cutover plan required before the persistent task migration.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ npm run build
# success
```

```bash
$ cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"
backend_boot_ok
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/models/task.py` | Added task filtering support for scoped task listing |
| `backend/app/models/project.py` | Added graph/project lookup helpers for access verification |
| `backend/app/api/graph.py` | Closed task and graph ownership gaps, added owner-aware graph task metadata |
| `backend/app/api/simulation.py` | Closed graph/task ownership gaps for entity, profile, and prepare-status endpoints |
| `backend/app/api/report.py` | Closed task and debug-tool ownership gaps, added owner-aware report task metadata |
| `scripts/verify_production_fixes.sh` | Added assertions for new owner-scoping guards |
| `.github/workflows/ci.yml` | Added frontend build, backend sanity, and security smoke jobs |
| `docs/task_store_cutover_plan.md` | Added task-store cutover, rollback, and acceptance criteria plan |

**Next steps:**
- Move into Day 2 persistent task-store implementation using the new cutover plan.
- Keep the new CI and security smoke as the minimum merge gate for subsequent runtime changes.

## [2026-03-17 23:15] - Checkpoint: Day 2 initial persistent task-store implementation

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Added task-store feature flags (`TASK_STORE_MODE`, `TASK_READ_SOURCE`) with default `dual`/`fallback`.
- Implemented DB-backed task persistence for `TaskManager` with task table initialization, dual-write support, fallback-read behavior, and cleanup of old persisted tasks.
- Wired task DB initialization into app startup so the task table is created automatically alongside the user DB.
- Closed a reviewer-found P0 in `simulation/create`: foreign `graph_id` can no longer be attached to a project the caller owns.
- Extended the verification script to assert task survival after `TaskManager` reset and to block cross-tenant `simulation/create` with чужим `graph_id`.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"
backend_boot_ok
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/config.py` | Added task-store feature flags |
| `backend/app/models/task.py` | Added DB-backed task persistence, dual-write/fallback-read, and persisted cleanup |
| `backend/app/__init__.py` | Initialized task DB on startup |
| `backend/app/api/simulation.py` | Blocked foreign `graph_id` attachment during simulation creation |
| `scripts/verify_production_fixes.sh` | Added persistence and foreign-graph abuse assertions |
| `docs/task_store_cutover_plan.md` | Clarified multi-instance cutover constraints |

**Remaining risks:**
- Persistent task store is implemented, but not yet deployed or live-smoked on Railway.
- Dual-write/fallback mode exists, but queue/worker durability and lease semantics are still upcoming work.
- Legacy ownerless projects remain a separate access-policy decision and are not yet migrated.

**Next steps:**
- Roll the new task persistence through a wider regression pass and prepare a controlled deploy plan.
- Continue Day 2 by validating task reads across restart/redeploy semantics closer to production behavior.

## [2026-03-18 00:37] - Checkpoint: Day 4 retry/backoff + worker-mode runtime verification

**Agent/Tool:** Codex CLI

**Completed in this checkpoint:**
- Completed persistent retry/backoff metadata for tasks with `max_attempts`, `next_retry_at`, `dead_letter_reason`, retry gating in `claim_task()` / `claim_next_task()`, and `fail_or_retry_task()` with exponential backoff.
- Hardened report-task billing semantics so reservations are released on early terminal exits, route-start exceptions release held credits before dispatch, and successful report billing is finalized only after lease-validated `complete_task()` succeeds.
- Removed the handler-level stale-success overreach that could finalize billing or overwrite failure state after lease loss, and aligned graph/simulation terminal state mutation with actual task outcome.
- Expanded runtime verification to full worker-mode `graph_build` and `simulation_prepare` smokes, plus report retry scheduling, DLQ exhaustion, stale-lease no-op, route exception refund, and stale-success no-finalize coverage.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app worker.py run.py
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"
backend_boot_ok
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/models/task.py` | Added retry/DLQ persistence fields, retry scheduling, claim gating by `next_retry_at`, and in-flight-only recovery semantics |
| `backend/app/services/task_handlers.py` | Added retry classification, safe reservation handling, lease-aware billing finalization, and stale-worker guards |
| `backend/app/api/report.py` | Released held reservation on pre-dispatch exceptions and set report-generate tasks to `max_attempts=3` |
| `scripts/verify_production_fixes.sh` | Added worker-mode graph/simulation smokes and report retry, DLQ, stale-success, stale-lease, and route-exception billing checks |

**Remaining risks:**
- `ReportAgent.generate_report()` still writes progress/report artifacts internally, so a truly stale worker can still emit some file-side effects before the handler discovers lease loss.
- Retry classification is still heuristic and should eventually move from message matching to provider/error-type taxonomy.
- Separate worker process rollout on Railway is not done yet; current safety is verified locally only.

**Next steps:**
- Roll the worker loop behind `TASK_EXECUTION_MODE=worker` in a controlled Railway canary.
- After runtime rollout, move into the first scientific-product layer: live evidence tools, structured probabilities, and a prediction ledger.

## [2026-03-18 01:16] - Checkpoint: Atomic report admission and pre-dispatch failure cleanup

**Agent/Tool:** Codex CLI + reviewer pass

**Completed in this checkpoint:**
- Added DB-level uniqueness for active `execution_key` admission and startup reconciliation for pre-existing duplicate active tasks.
- Added `TaskManager.create_or_reuse_task(...)` so report-task admission is atomic under concurrent requests instead of relying on best-effort fast-path checks.
- Hardened `/api/report/generate` so failures after reservation/task creation but before dispatch now deterministically:
  - release the pending billing reservation,
  - fail the created task,
  - fail the placeholder report/progress artifact.
- Extended the verification script with explicit regressions for:
  - duplicate-admission reuse,
  - route exception before task admission,
  - dispatch failure after task creation.
- Completed an independent reviewer pass on this slice; no blocking findings remained in the implemented scope.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app worker.py run.py
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"
backend_boot_ok
```

```bash
$ npm run build
# success
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/models/task.py` | Added active execution-key unique index, duplicate-active startup reconciliation, and atomic `create_or_reuse_task(...)` admission |
| `backend/app/api/report.py` | Made report task startup failure unwind billing/task/report state deterministically and reuse active tasks atomically |
| `scripts/verify_production_fixes.sh` | Added duplicate-admission and dispatch-failure cleanup regressions |
| `docs/plan-comparison-log.md` | Added execution evidence for the report-admission correctness slice |

**Residual risks:**
- Concurrency guarantees still rely on DB-backed task mode; `memory` mode remains single-process only.
- Regression coverage is still SQLite-first and does not yet exercise true Postgres constraint races at HTTP level.
- Worker service rollout on Railway is still pending; current web runtime remains the active execution surface.

**Next steps:**
- Add `SERVICE_ROLE=worker` runtime support and a worker health surface.
- Verify both web-role and worker-role behavior locally.
- Prepare a safe Railway canary rollout for a dedicated worker service before switching production task dispatch mode.

## [2026-03-18 01:32] - Checkpoint: Reviewer-driven worker-role hardening and canary-plan correction

**Agent/Tool:** Codex CLI + reviewer pass + Railway CLI inspection

**Completed in this checkpoint:**
- Implemented stricter runtime validation for `SERVICE_ROLE`, `TASK_STORE_MODE`, `TASK_READ_SOURCE`, and `TASK_EXECUTION_MODE`.
- Added explicit `WORKER_STANDBY=true` guard so a worker can report `standby` intentionally, instead of silently looking healthy while not consuming tasks.
- Changed `dispatch_task()` to fail fast on unsupported execution modes instead of silently enqueueing.
- Reworked `backend/worker.py` to build the app directly from `app.create_app()` + `Config.validate()`, removing the `run.py` double-initialization path.
- Enriched worker/web health payloads with role/execution-mode metadata and `worker_consumer_active`.
- Reverted the Docker entrypoint back to fixed web startup so shared/global `SERVICE_ROLE=worker` can no longer take the web API down while still passing health checks.
- Extended `verify_production_fixes.sh` with role-split regressions:
  - web `/health` payload,
  - invalid worker mode validation,
  - standby worker requires explicit opt-in,
  - standby worker `/health`,
  - active worker `/health`.
- Created Railway service `AgenikPredictWorker` with service-scoped vars for later canary work, but did not switch live traffic to it.

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app worker.py run.py
# success
```

```bash
$ bash scripts/verify_production_fixes.sh
verify_production_fixes: PASS
```

```bash
$ npm run build
# success
```

```bash
$ railway variable list -s AgenikPredictWorker --json
# service exists with SERVICE_ROLE=worker and TASK_EXECUTION_MODE=inline
```

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/config.py` | Added stricter runtime validation and explicit worker standby flag |
| `backend/app/__init__.py` | Added richer health payload metadata |
| `backend/app/services/task_worker.py` | Fail-fast on unsupported execution modes |
| `backend/worker.py` | Removed double-init path, added explicit standby/active health semantics |
| `Dockerfile.production` | Reverted to fixed web entrypoint to avoid false-green API outages |
| `scripts/verify_production_fixes.sh` | Added worker-role validation and health regressions |
| `docs/plan-comparison-log.md` | Added deviation note and updated recovery path |

**Important deviation:**
- The initial idea of selecting `web` vs `worker` purely through Docker `CMD` + `SERVICE_ROLE` was rejected after reviewer findings because it could create false-green deployments and silent task-processing outages.

**Remaining blocker:**
- A fully active dedicated Railway worker is still blocked by current storage topology and service configuration:
  - report/simulation artifacts live under `/app/backend/uploads`,
  - the Railway volume is attached only to `AgenikPredict`,
  - current repo config does not yet encode a per-service worker start command.

**Next steps:**
- Deploy the safer web-runtime changes to production.
- Keep the Railway worker service out of active task consumption until per-service start-command wiring and shared artifact-access strategy are solved.
- Then resume the canary plan or pivot to the first scientific-product layer if the infrastructure blocker remains. 

## [2026-03-18 01:44] - Checkpoint: Railway rollout started, active worker canary still infra-blocked

**Agent/Tool:** Codex CLI + Railway CLI

**Completed in this checkpoint:**
- Started a new production deployment for the safer web runtime:
  - `AgenikPredict` -> `884037d6-459d-48dd-a4fe-535546c97c79`
- Created a separate Railway service `AgenikPredictWorker` with service-scoped vars:
  - `SERVICE_ROLE=worker`
  - `TASK_EXECUTION_MODE=inline`
- Started a dormant worker-service deployment:
  - `AgenikPredictWorker` -> `d06ed70a-a5e7-44ec-a864-442942f3db16`
- Verified from build logs that both deployments reached the heavy dependency/image-packaging phase without a code-level build error.

**Current status at log time:**
- `AgenikPredict` deployment: `BUILDING`
- `AgenikPredictWorker` deployment: `BUILDING`

**Important constraint still in force:**
- Even after build success, the dedicated worker cannot be turned into an active task consumer yet without solving two separate infra issues:
  - current artifacts live under `/app/backend/uploads` on a volume attached only to the web service,
  - current repo config does not yet encode a per-service worker start command.

**Next steps:**
- Wait for Railway to finish the current builds.
- If `AgenikPredict` succeeds, run live production smoke on the new web deployment.
- Keep `AgenikPredictWorker` dormant until storage/start-command constraints are explicitly resolved.

## [2026-03-18 03:55] - Checkpoint: Production recovery after Postgres boot regression

**Agent/Tool:** Codex CLI + Railway CLI

**Completed in this checkpoint:**
- Diagnosed failed deploy `884037d6-459d-48dd-a4fe-535546c97c79` from live Railway runtime logs:
  - `TaskManager.init_db()` executed `PRAGMA table_info(tasks)` against Postgres and crashed gunicorn boot.
- Fixed `TaskManager` schema bootstrap to use a DB-agnostic probe (`SELECT * FROM tasks LIMIT 0`) instead of SQLite-only `PRAGMA`.
- Added a regression in `verify_production_fixes.sh` that patches `app.models.task.get_db` with a Postgres-like fake connection and asserts no `PRAGMA` usage.
- Re-ran local verification:
  - `cd backend && uv run python -m compileall app worker.py run.py`
  - `bash scripts/verify_production_fixes.sh`
  - `npm run build`
- Redeployed web service with the fix:
  - `AgenikPredict` -> `c3f953fd-ec85-43fc-bf3b-901d230a71c6`
- Confirmed live web recovery:
  - `https://app.agenikpredict.com/health` responds again with healthy JSON.
- Ran live API smoke past:
  - demo auth,
  - ontology generation,
  - graph build.

**Important finding from live smoke:**
- The service is restored, but weak synthetic smoke inputs can still produce poor entity graphs (`entities_count=0` or graph with a single node), which then fails later at simulation-quality level. This is separate from the production outage and should not be confused with runtime instability.

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/models/task.py` | Replaced SQLite-only schema inspection with DB-agnostic task table probe |
| `scripts/verify_production_fixes.sh` | Added Postgres bootstrap regression for `TaskManager.init_db()` |
| `docs/plan-comparison-log.md` | Added recovery evidence and live-validation boundary |

**Next steps:**
- Keep worker rollout deferred.
- Use a higher-signal smoke fixture or curated seed dataset so live e2e validation reliably reaches `prepare -> start -> report`.

## [2026-03-18 08:08] - Checkpoint: Railway worker recovered into healthy standby

**Agent/Tool:** Codex CLI + Railway CLI + multi-agent review

**Completed in this checkpoint:**
- Ran independent `system_context`, `explorer`, `worker`, and `reviewer` passes focused on `AgenikPredictWorker`.
- Confirmed the previous worker failure was a runtime contract mismatch, not a Docker build failure:
  - Docker image defaulted to web startup,
  - worker service ran with `SERVICE_ROLE=worker` and `TASK_EXECUTION_MODE=inline`,
  - `WORKER_STANDBY=true` was missing.
- Updated [`backend/worker.py`](/Users/alexanderivenski/Projects/AgenikPredict/backend/worker.py) so explicit standby skips full app bootstrap and still exposes `/health`.
- Updated [`Dockerfile.production`](/Users/alexanderivenski/Projects/AgenikPredict/Dockerfile.production) so container startup dispatches by `SERVICE_ROLE`:
  - `worker` -> `uv run python worker.py`
  - default/web -> `uv run gunicorn ... run:app`
- Re-ran local verification:
  - `cd backend && uv run python -m compileall app worker.py run.py`
  - `npm run build`
  - local standby worker smoke
  - local web health smoke
- Added `WORKER_STANDBY=true` to Railway service `AgenikPredictWorker`.
- Deployed only the worker service:
  - `AgenikPredictWorker` -> `213140f5-432e-4448-95e4-d54a1bdce78d`
- Confirmed Railway runtime logs now show:
  - `Worker health server listening on 0.0.0.0:8080/health`
  - `Worker process is in standby because TASK_EXECUTION_MODE=inline`
- Confirmed deployment status:
  - `railway deployment list -s AgenikPredictWorker` -> `213140f5-432e-4448-95e4-d54a1bdce78d | SUCCESS`

**Files changed:**
| File | Change |
|------|--------|
| `backend/worker.py` | Allowed explicit standby without full app bootstrap |
| `Dockerfile.production` | Added role-aware container entrypoint dispatch |
| `docs/plan-comparison-log.md` | Added Item 26 for Railway worker recovery |

**Residual risk:**
- Worker is healthy but intentionally non-consuming.
- To activate real background execution later, the worker still needs:
  - full runtime secrets/env at worker scope,
  - shared access to artifacts now living under `/app/backend/uploads`,
  - an explicit cutover from `TASK_EXECUTION_MODE=inline` to `TASK_EXECUTION_MODE=worker`.

**Next steps:**
- Leave `AgenikPredictWorker` in standby.
- Continue the main roadmap on runtime hardening / scientific layer without touching UI.
- When ready for active worker rollout, solve shared artifact storage first and then switch queue consumption deliberately.

## [2026-03-18 08:22] - Checkpoint: 5-day battle plan locked

**Agent/Tool:** Codex CLI + multi-agent revalidation

**Completed in this checkpoint:**
- Compressed the broader roadmap into a 5-day execution plan aimed specifically at eliminating dangerous tech debt while accelerating prediction quality.
- Revalidated ordering against current repo state and prior audits:
  - worker is healthy but still standby,
  - runtime substrate exists but is not fully cut over,
  - `ReportAgent` still lacks live evidence,
  - structured probabilities and `Prediction Ledger` are still absent,
  - objective quality baseline still does not exist.
- Wrote the plan as an operator document:
  - [docs/5_day_battle_plan.md](/Users/alexanderivenski/Projects/AgenikPredict/docs/5_day_battle_plan.md)

**Plan order locked:**
1. `Day 1` — active worker cutover prep
2. `Day 2` — real worker activation
3. `Day 3` — live evidence layer for `ReportAgent`
4. `Day 4` — structured probabilities + `Prediction Ledger`
5. `Day 5` — backtest pilot + quality baseline

**Why this order:**
- Without `Day 1-2`, scientific features would sit on an unstable execution substrate.
- Without `Day 3-4`, the product remains a narrative simulator rather than a measurable prediction system.
- Without `Day 5`, there is still no proof that changes improved prediction quality.

**Files changed:**
| File | Change |
|------|--------|
| `docs/5_day_battle_plan.md` | Added the new 5-day battle plan |
| `docs/plan-comparison-log.md` | Added Item 27 mapping the new plan to current state |

**Next steps:**
- Start `Day 1` immediately:
  - decide and implement shared artifact strategy for `web + worker`,
  - make a full `web env` vs `worker env` checklist,
  - prepare the safe active-worker switch procedure.

## [2026-03-18 08:38] - Checkpoint: Day 1 guardrails and artifact-root hardening started

**Agent/Tool:** Codex CLI + multi-agent audit

**Completed in this checkpoint:**
- Re-audited the actual Day 1 blockers with `system_context` and `explorer`.
- Confirmed the three real hard-gates before active worker cutover:
  - `storage gate`
  - `env parity gate`
  - `task-store gate`
- Added explicit config guardrails so active worker cannot be enabled unsafely:
  - `ARTIFACT_STORAGE_MODE=local|shared_fs|object_store`
  - `ARTIFACT_ROOT`
  - fail-fast when `TASK_EXECUTION_MODE=worker` but:
    - `ARTIFACT_STORAGE_MODE=local`
    - `TASK_STORE_MODE!=db`
    - `TASK_READ_SOURCE!=db`
- Replaced the most dangerous hardcoded `../../uploads/...` paths with config-driven roots in simulation and report-adjacent paths.
- Added a separate Day 1 operator checklist:
  - [docs/day1_active_worker_cutover_checklist.md](/Users/alexanderivenski/Projects/AgenikPredict/docs/day1_active_worker_cutover_checklist.md)
- Updated the verification harness to assert:
  - active worker on local artifacts is rejected
  - active worker on transitional task-store flags is rejected
  - active worker health only passes with `db/db + shared_fs`

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/config.py` | Added artifact storage mode/root and active-worker cutover guardrails |
| `backend/app/services/simulation_manager.py` | Switched simulation data root to config-driven path |
| `backend/app/services/simulation_runner.py` | Switched run-state root to config-driven path |
| `backend/app/api/simulation.py` | Replaced direct `../../uploads/...` reads with config-driven roots |
| `backend/app/services/zep_tools.py` | Replaced direct simulation path building with config-driven root |
| `scripts/verify_production_fixes.sh` | Added guardrail checks for unsafe active-worker cutover |
| `docs/day1_active_worker_cutover_checklist.md` | Added Day 1 storage/env/task-store checklist |
| `docs/plan-comparison-log.md` | Added Item 28 for this checkpoint |

**Verification:**
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> success
- `bash scripts/verify_production_fixes.sh` -> prints `verify_production_fixes: PASS`

**Known follow-up:**
- The verify script still exits non-zero due to a pre-existing shell harness quirk, even though the assertions pass. This is not new to this checkpoint.
- Day 1 is not finished yet: storage/env parity is still not closed on Railway.

**Next steps:**
- Close the remaining Day 1 operator gates on Railway:
  - determine the production-safe shared artifact mode,
  - derive the exact `web -> worker` env parity diff,
  - pin the intended cutover target for `db/db`.

**Plan correction after independent review:**
- `Day 1` must validate shared artifacts in runtime, not only on paper.
- `Day 4` must define outcome-resolution policy together with `Prediction Ledger`.
- `Day 5` must treat determinism as a hard prerequisite before any backtest baseline.

**Additional operator artifact produced:**
- [docs/day1_worker_env_parity_diff.md](/Users/alexanderivenski/Projects/AgenikPredict/docs/day1_worker_env_parity_diff.md) now captures the exact current env gap between `web` and `worker`.

## [2026-03-18 08:42] - Checkpoint: Independent Day 1 cutover review (findings-first)

**Agent/Tool:** Codex CLI review pass (line-level + runtime probes + Railway env check)

**Scope reviewed:**
- Artifact storage mode validation
- Worker standby/cutover safety
- Env parity readiness for active worker

**High-signal findings:**
1. `ARTIFACT_ROOT` and simulation artifact root are still split:
   - `UPLOAD_FOLDER` follows `ARTIFACT_ROOT`
   - `OASIS_SIMULATION_DATA_DIR` remains pinned to `backend/uploads/simulations`
2. Active worker still boots without `DATABASE_URL`:
   - runtime falls back to local SQLite, which is unsafe for cross-service queue/task ownership.
3. Invalid execution mode can be hidden by standby:
   - `TASK_EXECUTION_MODE=bogus WORKER_STANDBY=true` still reports healthy standby `/health`.
4. `object_store` is accepted by config but not implemented by runtime file I/O paths.

**Runtime probes captured:**
- `TASK_EXECUTION_MODE=bogus WORKER_STANDBY=true uv run python worker.py` -> healthy standby payload with bogus mode.
- `TASK_EXECUTION_MODE=worker TASK_STORE_MODE=db TASK_READ_SOURCE=db` without `DATABASE_URL` -> worker app boot succeeds.
- `ARTIFACT_ROOT=/tmp/shared-artifacts` -> `UPLOAD_FOLDER` changes, `OASIS_SIMULATION_DATA_DIR` does not.
- `railway variable list` confirms production worker still has standby-only env profile.

**Log linkage:**
- `docs/plan-comparison-log.md` -> Item 31 (`DEVIATION`)

**Next step (before Day 2):**
- close the four blockers above in code and verification harness, then re-run Day 1 go/no-go checks.

## [2026-03-18 08:49] - Checkpoint: Day 1 hardening published, env parity staged, cutover still intentionally blocked

**Agent/Tool:** Codex CLI + Railway CLI

**Completed in this checkpoint:**
- Closed all four code-level Day 1 blockers from the independent review:
  - unified simulation/report/project artifact roots under `ARTIFACT_ROOT`
  - required `DATABASE_URL` for production active worker mode
  - blocked standby from hiding invalid `TASK_EXECUTION_MODE`
  - blocked `object_store` from pretending to be cutover-ready before implementation
- Enriched `/health` for both web and worker with:
  - `artifact_storage_mode`
  - `artifact_root`
  - `simulation_data_dir`
  - `task_read_source`
- Hardened the verification harness:
  - root coherence assertion
  - standby invalid-mode rejection
  - production active-worker missing-DB rejection
  - random-port worker health checks to avoid false failures from stale local processes
- Updated operator docs and `.env.example` for the new cutover flags.
- Staged full app-level env parity on Railway for `AgenikPredictWorker` without enabling worker consumption:
  - copied runtime/auth/model/data/billing vars
  - pinned explicit standby/runtime flags (`ARTIFACT_*`, `TASK_*`, `SERVICE_ROLE`, `TASK_EXECUTION_MODE`)
- Deployed the guarded Day 1 state to `AgenikPredict` live.

**Live production result:**
- `https://app.agenikpredict.com/health` now returns the new Day 1 guardrail fields and confirms safe inline runtime:
  - `artifact_root=/app/backend/uploads`
  - `artifact_storage_mode=local`
  - `simulation_data_dir=/app/backend/uploads/simulations`
  - `task_execution_mode=inline`
  - `task_read_source=fallback`
- `AgenikPredictWorker` env profile is now staged correctly, but the newest standby deployment is still stuck in Railway `BUILDING/stopped=true`, despite the last known good standby deployment previously being healthy.

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/config.py` | Unified artifact roots, added production active-worker DB requirement, blocked fake object-store readiness, added standby validation |
| `backend/app/__init__.py` | Enriched web `/health` payload |
| `backend/worker.py` | Enriched worker `/health` payload and validated standby structurally |
| `backend/app/models/project.py` | Project root now uses config constant |
| `backend/app/services/report_agent.py` | Report paths now use config report root |
| `backend/app/api/simulation.py` | Report lookup now uses config report root |
| `Dockerfile.production` | Runtime artifact directories created after mount |
| `scripts/verify_production_fixes.sh` | Added new guardrail assertions and random ports |
| `.env.example` | Added task/worker/artifact env guidance |
| `docs/day1_active_worker_cutover_checklist.md` | Day 1 rules updated for current storage reality |
| `docs/day1_worker_env_parity_diff.md` | Updated after staged Railway env parity |
| `docs/plan-comparison-log.md` | Added Items 32 and 33 |

**Verification:**
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- `ARTIFACT_ROOT=/tmp/shared-artifacts uv run python - <<'PY' ...` -> all artifact roots align under one shared root
- `npm run build` -> success
- `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
- `railway service status -s AgenikPredict --json` -> `SUCCESS`
- `curl https://app.agenikpredict.com/health` -> new Day 1 payload live
- `railway variable list -s AgenikPredictWorker --json` -> env parity staged

**Current Day 1 verdict:**
- `GO` for moving into the shared-artifact backend workstream.
- `NO-GO` for actual active worker cutover today.

**Why Day 2 is still blocked:**
- storage gate is still open on Railway
- `object_store` backend is not implemented yet
- latest standby worker deploy is currently platform-blocked in Railway `BUILDING`

**Next steps:**
- stop trying to force `TASK_EXECUTION_MODE=worker` on the current storage topology
- start implementing the real shared-artifact backend path needed for Day 2

## [2026-03-18 09:12] - Checkpoint: Artifact-store foundation is green, Day 2 remains cutover-blocked until real object-store canary

**Agent/Tool:** Codex CLI + sub-agent audit + local verification harness

**Completed in this checkpoint:**
- Implemented the shared-artifact storage foundation for `project/report/simulation` resources:
  - added `artifact_store.py` with `LocalArtifactStore` and `ObjectArtifactStore`
  - wired project/report/simulation managers to `sync/flush` through the store
- Closed the first incomplete migration regressions:
  - fixed undefined `manager` usages in `backend/app/api/simulation.py`
  - switched report lookup for a simulation to `ReportManager` instead of raw `reports/` traversal
  - flushed `state.json` after auto-promoting `preparing -> ready`
  - made `zep_tools` load simulation profiles through `SimulationManager` with `sync=True`
- Updated operator/runtime wiring:
  - refreshed `.env.example` for object-store env vars
  - enriched web/worker `/health` with `artifact_object_bucket`, `artifact_object_prefix`, and `artifact_scratch_dir`
  - regenerated `backend/uv.lock` after adding `boto3`
- Reworked the regression harness to follow the new artifact-store contract instead of the legacy `RUN_STATE_DIR` override and fixed the outdated object-store validation expectation.

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/services/artifact_store.py` | New store abstraction for local/shared/object-store artifact backends |
| `backend/app/models/project.py` | Project I/O routed through artifact store |
| `backend/app/services/simulation_manager.py` | Simulation state/files routed through artifact store |
| `backend/app/services/simulation_runner.py` | Runner state/paths use artifact store semantics |
| `backend/app/services/report_agent.py` | Report folder/progress/lookup flows use artifact store and return latest report deterministically |
| `backend/app/api/simulation.py` | Fixed store-backed simulation/report lookups and runtime `manager` scope bugs |
| `backend/app/services/zep_tools.py` | Profile loading now syncs simulation artifacts through manager/store |
| `backend/app/__init__.py` | Web `/health` exposes artifact backend metadata |
| `backend/worker.py` | Worker `/health` exposes artifact backend metadata |
| `backend/pyproject.toml` | Added `boto3` dependency for object-store backend |
| `backend/uv.lock` | Regenerated lockfile with object-store dependency graph |
| `scripts/verify_production_fixes.sh` | Updated regression harness for artifact-store contract and new health fields |
| `.env.example` | Added object-store env guidance |
| `docs/plan-comparison-log.md` | Added Item 34 |

**Verification:**
- `cd backend && uv lock` -> success
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`

**Current technical position:**
- `GO` for treating object-store groundwork as implemented and testable locally.
- `NO-GO` for flipping Railway to active worker mode today, because we still do not have a proven live object-store canary for separate `web + worker`.

**Residual risks:**
- No real object-store integration test has been run yet against MinIO/S3-compatible infra.
- Artifact flushes currently upload full resource directories, which is safe but potentially expensive under load.
- Legacy class-level `*_DIR` constants remain in a few services and should be treated as technical debt, not source of truth.

**Next steps:**
- provision or target a real S3-compatible canary backend
- prove web/worker env parity against that backend using the new `/health` metadata
- only then stage `ARTIFACT_STORAGE_MODE=object_store` and keep `TASK_EXECUTION_MODE=inline` on web until canary smoke is clean

## [2026-03-18 09:25] - Checkpoint: Low-severity review findings closed

**Agent/Tool:** Codex CLI + reviewer follow-up + regression harness

**Completed in this checkpoint:**
- Closed the public-health metadata concern by trimming the new object-store detail fields from web and worker `/health`.
- Expanded the regression harness to directly cover the codepaths that had only indirect coverage before:
  - latest report lookup by `simulation_id`
  - `/api/report/by-simulation/<simulation_id>`
  - realtime simulation profile/config reads
  - DB-backed post/comment reads
  - `ZepToolsService._load_agent_profiles`
- Confirmed the public `/health` payload still carries the operational basics we need now, without the extra object-store internals.

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/__init__.py` | Removed extra object-store fields from public web `/health` |
| `backend/worker.py` | Removed extra object-store fields from public worker `/health` |
| `scripts/verify_production_fixes.sh` | Added direct regression coverage for report lookup, realtime reads, DB-backed reads, and zep profile loading; updated health assertions |
| `docs/plan-comparison-log.md` | Added Item 35 |

**Verification:**
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; app=create_app(); print(app.test_client().get('/health').get_json())"` -> payload contains operational basics only, without object-store bucket/prefix/scratch metadata

**Current state:**
- The two low-severity review findings are closed.
- Local/runtime verification is now stronger and more direct than before.
- We still have not started live object-store canary work; active worker cutover remains intentionally blocked until that exists.

**Next steps:**
- set up a real S3-compatible canary backend
- validate web + worker parity against that backend
- only then move to Day 2 live cutover work

## [2026-03-18 10:01] - Checkpoint: Published clean private GitHub snapshot

**Agent/Tool:** Codex CLI + GitHub CLI

**Completed in this checkpoint:**
- Published the current project state into a brand new private GitHub repository without reusing the original dirty git history.
- Used a safe snapshot path instead of pushing the existing repo directly:
  - exported tracked + untracked non-ignored files from the current workspace
  - excluded `.git`, `.env`, ignored runtime artifacts, and local-only clutter
- Ran a basic secret/size sanity pass on the snapshot before publication.
- Initialized a fresh git repo in the snapshot, created one root commit, and pushed `main`.

**Important naming note:**
- The exact GitHub slug `codex-agenic-predict` was already occupied on the account.
- The new private repo was therefore created as `codex-agenic-predict-private`.

**Files/Artifacts involved:**
| File | Change |
|------|--------|
| `/Users/alexanderivenski/Projects/codex-agenic-predict-publish` | Clean publish snapshot created from current workspace |
| `docs/plan-comparison-log.md` | Added Item 36 |

**Verification:**
- `gh auth status` -> authenticated as `alexprime1889-prog`
- snapshot sanity -> `.ENV_PRESENT=no`, `GIT_PRESENT=no`, no files larger than `95MB`
- token scan -> no direct matches for common PAT/API/private-key signatures
- `git commit -m "Initial snapshot"` -> root commit `0ce505e`
- `git push -u origin main` -> success
- `git ls-remote --heads origin` -> `0ce505e5c30fa78233d5ce47f1922bb464bd3923 refs/heads/main`

**Current result:**
- New private repo published successfully.
- URL target: `https://github.com/alexprime1889-prog/codex-agenic-predict-private`

**Next steps:**
- if exact naming matters, inspect the already-occupied `codex-agenic-predict` slug and decide whether to reclaim/rename

## [2026-03-18 10:22] - Checkpoint: Production vs GitHub snapshot parity verified

**Agent/Tool:** Codex CLI + GitHub CLI + Railway CLI + explorer/system-context subagents

**Completed in this checkpoint:**
- Verified the private GitHub snapshot itself, including its published `main` commit and tree state.
- Compared the published snapshot against the current AgenikPredict workspace over every file included in the snapshot.
- Confirmed that only the two live planning/session logs differ; the deployable code and build inputs match.
- Rebuilt the frontend locally and compared the exact live production JS/CSS assets to the local build by SHA-256.
- Cross-checked the public `/health` contract on production against the current code shape.

**Result:**
- The live production frontend is byte-for-byte aligned with the published GitHub snapshot.
- The observable public backend/runtime contract is aligned with the current code shape and therefore with the published snapshot inputs.
- We did not prove exact deployment provenance at the image-digest level, so the strongest accurate wording is:
  - frontend: identical by asset hash
  - backend/public contract: behaviorally equivalent

**Files/Artifacts involved:**
| File | Change |
|------|--------|
| `docs/plan-comparison-log.md` | Added Item 37 |

**Verification:**
- `cd /Users/alexanderivenski/Projects/codex-agenic-predict-publish && git rev-parse HEAD` -> `0ce505e5c30fa78233d5ce47f1922bb464bd3923`
- `cd /Users/alexanderivenski/Projects/codex-agenic-predict-publish && git rev-parse HEAD^{tree}` -> `d8b6dc4894d14fa7d5f82cbb6b08757ef9027267`
- `cd /Users/alexanderivenski/Projects/codex-agenic-predict-publish && git ls-remote --heads origin` -> same `0ce505e...` on `refs/heads/main`
- snapshot-vs-workspace compare over `git ls-files` -> only `docs/AGENT_SESSION_LOG.md` and `docs/plan-comparison-log.md` differ
- `cd /Users/alexanderivenski/Projects/AgenikPredict && npm run build` -> success
- live `index.html` references `/assets/index-CkYmH1Ba.js` and `/assets/index-DyQi3PGL.css`
- live/local SHA-256 matches for both assets
- `curl https://app.agenikpredict.com/health` and local `create_app().test_client().get('/health')` -> same operational fields, with only expected path-prefix differences

**Next steps:**
- if needed, add deploy provenance by tying the Railway running image digest to a build from snapshot commit `0ce505e`
- otherwise treat production and GitHub as aligned for frontend and public runtime verification purposes

## [2026-03-18 10:48] - Checkpoint: Provenance proof attempted to the maximum defensible limit

**Agent/Tool:** Codex CLI + Railway CLI + BuildKit/buildx + system-context/explorer subagents

**Completed in this checkpoint:**
- Retrieved immutable Railway deployment metadata for the active production web service.
- Confirmed the live `AgenikPredict` deployment has a stable `deploymentId` and `imageDigest`, but no repo/commit source metadata because it was deployed via direct CLI upload.
- Enabled local `docker-buildx` to inspect BuildKit-level behavior.
- Created a temporary Railway control service, deployed the published GitHub snapshot into it, and inspected its Railway build logs.
- Verified that the control Railway build produces the same named frontend assets as the current live production build.

**Key finding:**
- We reached the proof ceiling of the current release process.
- The live deployment can be identified by immutable Railway metadata:
  - deployment `fc73be0b-cd74-4cc5-97cb-1f2d862a3ae8`
  - image digest `sha256:f6c6c9a22ff1c179da4c3bf8c83dd2b1f107b16266923d4365c27df6121fada8`
- But Railway reports `source = null` for this deployment, so there is no stored GitHub commit provenance for it.
- A control Railway build from the GitHub snapshot reproduced the same frontend asset outputs, but BuildKit step digests still differed, which means those digests are not a safe retroactive substitute for exact git commit identity in this pipeline.

**Why exact proof is blocked:**
- The production image was deployed from local workspace via `railway up`, not from a CI pipeline that stamped commit metadata.
- Without embedded OCI labels / signed provenance, `imageDigest` proves image immutability, not git commit ancestry.

**Files/Artifacts involved:**
| File | Change |
|------|--------|
| `docs/plan-comparison-log.md` | Added Item 38 |

**Verification:**
- `railway service status -s AgenikPredict --json` -> live deployment `fc73be0b-cd74-4cc5-97cb-1f2d862a3ae8`
- Railway metadata for live deployment -> `imageDigest=sha256:f6c6c9a22ff1c179da4c3bf8c83dd2b1f107b16266923d4365c27df6121fada8`, `source=null`
- `brew install docker-buildx` and `docker buildx version` -> local BuildKit tooling enabled
- `railway add -s AgenikPredictProvenance --json` -> temporary control service created
- `railway up ... -s AgenikPredictProvenance --path-as-root -m "provenance check snapshot"` -> control deployment `d024115d-76ae-479c-a42b-c18707829644`
- `railway logs --build d024115d-76ae-479c-a42b-c18707829644 --json` -> same frontend artifact names as live (`index-CkYmH1Ba.js`, `index-DyQi3PGL.css`, `AccountView-D3tfCVMU.js`, `AdminView-Bf5dw1XZ.js`)

**Current result:**
- The strongest accurate statement remains:
  - frontend: identical by asset hash
  - backend/public runtime: behaviorally equivalent
  - exact git-commit provenance for the already-running production image: not recoverable from current metadata alone

**Next steps:**
- add OCI labels like `org.opencontainers.image.revision` and `org.opencontainers.image.source`
- or move build provenance to GitHub Actions and deploy Railway by pinned digest
- use that on the next release so exact commit proof becomes automatic instead of inferential

## [2026-03-18 11:08] - Checkpoint: Switched Railway source of truth to the private GitHub repo

**Agent/Tool:** Codex CLI + Railway Public API (GraphQL) + Railway CLI

**Completed in this checkpoint:**
- Switched the existing production services to use the private GitHub repository as their deployment source of truth instead of future direct local `railway up` pushes.
- Used Railway’s official `serviceConnect` mutation against the Public API, targeting the existing services rather than recreating infrastructure.
- Connected both services to:
  - repo: `alexprime1889-prog/codex-agenic-predict-private`
  - branch: `main`
- Confirmed that Railway immediately created new GitHub-based deployments for both services.
- Deleted the temporary `AgenikPredictProvenance` service after the switch, so the Railway project remains clean.
- Confirmed that the new deployment metadata now includes Git commit provenance:
  - `commitHash = 0ce505e5c30fa78233d5ce47f1922bb464bd3923`
  - `commitMessage = "Initial snapshot"`

**Why this matters:**
- This changes the future source of truth from local manual deploys to the private GitHub repo.
- It preserves the current project/services, variables, domains, and volume mounts.
- It also solves the provenance gap going forward: Railway metadata now ties deployments to a specific GitHub repo/branch/commit.

**Files/Artifacts involved:**
| File | Change |
|------|--------|
| `docs/plan-comparison-log.md` | Added Item 39 |

**Verification:**
- Railway docs confirm `serviceConnect(id, input: { repo, branch })` for existing services.
- Public API auth check against `https://backboard.railway.com/graphql/v2` succeeded as `alexprime1889@gmail.com`.
- `serviceConnect` succeeded for:
  - `AgenikPredict` (`06f4d692-6bb9-4886-9115-e1fb944868a3`)
  - `AgenikPredictWorker` (`7440ce35-effe-4bc1-b3a4-53b3ef74262c`)
- GraphQL project query after the switch shows both services with `source.repo = "alexprime1889-prog/codex-agenic-predict-private"`.
- New GitHub-sourced deployments created:
  - `AgenikPredict` -> `1c9951cc-709b-4542-be75-1ec1613208c7`
  - `AgenikPredictWorker` -> `da68f909-28ea-45da-a8dc-322275591efb`
- Both new deployment metadata records include:
  - `repo`
  - `branch = main`
  - `commitHash = 0ce505e5c30fa78233d5ce47f1922bb464bd3923`
  - `commitMessage = "Initial snapshot"`
- `https://app.agenikpredict.com/health` remained `status=ok` during rollout.
- `serviceDelete("1edc75a8-ffb7-4968-a8ff-cc58aa3b72ea")` -> `true`

**Current state:**
- The source switch is complete.
- The first GitHub-based deployments finished successfully:
  - `AgenikPredict` -> `1c9951cc-709b-4542-be75-1ec1613208c7`
  - `AgenikPredictWorker` -> `da68f909-28ea-45da-a8dc-322275591efb`
- The currently serving public web instance remains healthy.
- Future Railway deployments for these services now come from the private GitHub repository rather than local manual upload state.

**Next steps:**
- treat GitHub as the canonical deployment source going forward

## 2026-03-18 11:26 - Checkpoint: GitHub-based Railway rollout reached final `SUCCESS`

**Context:** The user asked to continue monitoring the GitHub-source switch rollout and finish it to terminal state.

**Work completed:**
- Verified Railway terminal status for both production services:
  - `railway service status -s AgenikPredict --json` -> `deploymentId=1c9951cc-709b-4542-be75-1ec1613208c7`, `status=SUCCESS`
  - `railway service status -s AgenikPredictWorker --json` -> `deploymentId=da68f909-28ea-45da-a8dc-322275591efb`, `status=SUCCESS`
- Rechecked live prod health:
  - `curl -fsS https://app.agenikpredict.com/health`
  - Response stayed green with `status=ok`, `task_execution_mode=inline`, `worker_consumer_active=false`
- Updated plan-vs-execution logging so the source switch is recorded as fully completed rather than in-progress.

**Result:**
- Railway web and worker are now both GitHub-sourced and healthy.
- Future deployments now inherit Railway metadata for `repo`, `branch`, and `commitHash`, closing the earlier provenance gap for subsequent releases.

## 2026-03-18 11:31 - Checkpoint: Prepared object-store canary path for active worker cutover

**Context:** After making GitHub the Railway source of truth, the next execution block was the real active-worker cutover. The immediate blocker was shared artifact storage: prod still ran with `ARTIFACT_STORAGE_MODE=local`, `TASK_EXECUTION_MODE=inline`, and only the web service had the uploads volume.

**Work completed:**
- Added fail-fast artifact probing to both app startup and standby worker startup:
  - [backend/app/config.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/config.py)
  - [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py)
  - [backend/worker.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/worker.py)
- Revalidated locally:
  - `cd backend && uv run python -m py_compile app/__init__.py app/config.py worker.py`
  - `bash scripts/verify_production_fixes.sh` -> `PASS`
- Confirmed current production runtime values:
  - `AgenikPredict` -> `SERVICE_ROLE=web`, `TASK_EXECUTION_MODE=inline`, `TASK_STORE_MODE=dual`, `TASK_READ_SOURCE=fallback`, `ARTIFACT_STORAGE_MODE=local`
  - `AgenikPredictWorker` -> `SERVICE_ROLE=worker`, `TASK_EXECUTION_MODE=inline`, `TASK_STORE_MODE=dual`, `TASK_READ_SOURCE=fallback`, `ARTIFACT_STORAGE_MODE=local`, `WORKER_STANDBY=true`
- Upgraded Railway CLI from `4.30.5` to `4.32.0` so bucket management is available.
- Created and deployed a real Railway production bucket:
  - name: `compact-tupperware-DXP7`
  - id: `139bfcfd-0747-4556-bf02-1ca6f034de4f`
  - region: `iad`
- Retrieved S3-compatible credentials for the deployed bucket, which unblocks standby worker canary wiring.
- Synced the current project into the private publish repo so the next Railway deploy can actually carry the new probe logic.

**Result:**
- The storage blocker is now narrowed from "no shared artifact backend" to "wire the deployed Railway bucket into the worker service and verify standby canary health".
- The next step is operational, not architectural: push the synced repo, set `ARTIFACT_*` vars on `AgenikPredictWorker`, deploy, and verify object-store standby health before switching any service to active worker mode.

## 2026-03-18 11:37 - Checkpoint: Added object-store probe timeouts and pre-health diagnostics

**Context:** After wiring Railway bucket credentials into `AgenikPredictWorker`, the standby canary created GitHub-based deployments but left them in long `BUILDING/DEPLOYING` states without a decisive runtime outcome. The last known healthy worker deployment still reported `mode=local`, so the object-store path needed better diagnostics.

**Work completed:**
- Added explicit object-store startup timeout knobs:
  - `ARTIFACT_OBJECT_CONNECT_TIMEOUT_SECONDS`
  - `ARTIFACT_OBJECT_READ_TIMEOUT_SECONDS`
- Updated [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py) to build the S3 client with `botocore.config.Config(connect_timeout=..., read_timeout=..., retries=...)`.
- Updated [backend/worker.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/worker.py) so standby mode logs `Starting standby worker artifact probe...` before probing, then logs the exception path explicitly before re-raising.
- Updated [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py) to do the same for web/app startup probe logging.
- Updated [.env.example](/Users/alexanderivenski/Projects/AgenikPredict/.env.example) with the new timeout env vars.
- Revalidated locally:
  - `cd backend && uv run python -m py_compile app/__init__.py app/config.py app/services/artifact_store.py worker.py`
  - `bash scripts/verify_production_fixes.sh` -> `PASS`

**Result:**
- The object-store canary path is now fail-fast and observable instead of silently hanging before `/health`.
- Next step: sync the new commit into the private publish repo, push, and redeploy the worker canary again so Railway either reaches `mode=object_store` or exposes a concrete startup error.

## 2026-03-18 11:44 - Checkpoint: Worker object-store canary proven, web staged safely

**Context:** After pushing `48d5659` to the private GitHub release repo, Railway created a new worker deployment but kept the service pointer in `DEPLOYING`. The practical question was whether object-store wiring was actually functional or still hypothetical.

**Work completed:**
- Confirmed the effective worker runtime reached standby on object storage:
  - `railway logs -s AgenikPredictWorker --lines 120`
  - key line: `Standby worker artifact probe succeeded: mode=object_store`
- Confirmed the public web runtime stayed untouched:
  - `curl -fsS https://app.agenikpredict.com/health`
  - still shows `artifact_storage_mode=local`, `task_execution_mode=inline`
- Staged object-store env vars on the web service with `--skip-deploys`, so the next canary no longer requires secret copying or ad hoc setup.
- Verified the staged web config without printing secrets:
  - `ARTIFACT_STORAGE_MODE=local`
  - bucket/endpoint/timeout vars present
  - `TASK_EXECUTION_MODE=inline`, `TASK_STORE_MODE=dual`, `TASK_READ_SOURCE=fallback`

**Result:**
- The deployed Railway bucket is now proven to work for the worker service.
- The next controlled canary is clear: redeploy web with `ARTIFACT_STORAGE_MODE=object_store` while keeping execution inline, then re-run live smoke before enabling any active worker consumption.

## 2026-03-18 12:05 - Checkpoint: Web object-store canary succeeded through start and exposed a live monitoring gap

**Context:** With the worker artifact backend already proven, the next safe step was a web canary that switched only artifact storage from `local` to `object_store` while keeping `TASK_EXECUTION_MODE=inline`.

**Work completed:**
- Set `ARTIFACT_STORAGE_MODE=object_store` on `AgenikPredict` and monitored the GitHub-based deployment `1581597f-b19b-4ec1-9865-221445f79430` to `SUCCESS`.
- Verified live health:
  - `curl -fsS https://app.agenikpredict.com/health`
  - response now reports `artifact_storage_mode=object_store`, `task_execution_mode=inline`, `status=ok`
- Verified startup probe logs:
  - `railway logs -s AgenikPredict --lines 200`
  - key lines: `Starting artifact store probe: mode=object_store` and `Artifact store probe succeeded: mode=object_store`
- Ran a real production smoke that succeeded through:
  - ontology generation
  - graph build (`23` qualifying entities)
  - simulation create
  - prepare (`progress=100`, `status=completed`)
  - simulation start (`runner_status=running`, `reddit_running=true`)

**Result:**
- The web object-store canary itself is healthy.
- A new product/runtime bug surfaced instead: `run-status` and `run-status/detail` stayed at `current_round=0`, `total_actions_count=0` even while server logs showed the simulation actively executing.
- That changed the immediate priority from storage readiness to live monitoring correctness.

## 2026-03-18 12:24 - Checkpoint: Fixed inline object-store live monitoring locally and added regression coverage

**Context:** The live canary showed that `web inline + object_store` was reading stale status during execution. Code inspection confirmed that polling paths still forced `sync=True` object-store reads instead of trusting the active local runtime.

**Work completed:**
- Updated [backend/app/services/simulation_runner.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_runner.py):
  - added `_has_active_local_runtime()` to detect when this process owns the live inline run
  - changed `get_run_state()` to prefer the in-memory `SimulationRunState` for active inline runs under `object_store`
  - changed `_load_run_state()` to accept `sync=` so live paths can avoid destructive remote syncs
  - changed `get_all_actions()` to read local scratch files with `sync=False` while the inline runtime is active
- Expanded [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh):
  - active inline `object_store` polling must not call `_load_run_state()`
  - active inline `object_store` action reads must use `sync=False`
  - inactive object-store reads still use `sync=True`
- Revalidated locally:
  - `python3 -m py_compile backend/app/services/simulation_runner.py`
  - `bash -n scripts/verify_production_fixes.sh`
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`

**Result:**
- The minimal fix is in place for the stale live-monitoring bug without changing worker mode or broadening the cutover scope.
- Next step: sync this patch into the GitHub-backed release repo, redeploy Railway web from GitHub, and rerun the live smoke to verify that `run-status` now advances under the same `object_store + inline` canary.

## 2026-03-18 12:46 - Checkpoint: Closed object-store startup artifact gap locally and hardened start preflight

**Context:** A deeper live root-cause pass showed the canary still had a startup hole: a simulation could enter `runner_status=running` while the subprocess immediately logged `Profile file does not exist: .../reddit_profiles.json` and stayed alive in command-wait mode with no environment. That meant object-store artifact persistence and start-time validation were still too weak.

**Work completed:**
- Updated [backend/app/services/simulation_manager.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_manager.py):
  - added explicit artifact flushes immediately after saving profile files
  - added explicit artifact flush after writing `simulation_config.json`
- Updated [backend/app/api/simulation.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/simulation.py):
  - added unconditional `_check_simulation_prepared()` preflight before every `/start`, even when the simulation state already says `READY`
- Updated [backend/app/services/simulation_runner.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_runner.py):
  - added `_get_required_runtime_artifacts()` and `_validate_runtime_artifacts()`
  - `start_simulation()` now fails fast if synced runtime artifacts are incomplete for the requested platform
- Expanded [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh):
  - `READY` simulation without `reddit_profiles.json` must be rejected by `/api/simulation/start`
  - fake object-store prepare path must persist `reddit_profiles.json` and `simulation_config.json` across flush/sync
  - direct runner start in fake object-store mode must fail fast when required runtime artifacts are missing
- Revalidated locally:
  - `python3 -m py_compile backend/app/services/simulation_manager.py backend/app/services/simulation_runner.py backend/app/api/simulation.py`
  - `bash -n scripts/verify_production_fixes.sh`
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`

**Result:**
- The remaining known object-store startup gap is now closed locally.
- The next step is release plumbing only: sync to the GitHub-backed publish repo, let Railway deploy the new commit, then rerun the real production smoke on `object_store + inline`.

## 2026-03-18 12:54 - Checkpoint: Fixed object-store scratch race after live Railway logs exposed concurrent sync failure

**Context:** The next GitHub-based web deploy came up healthy, but the follow-up production smoke and Railway logs exposed a new blocker before the simulation stage: concurrent `sync=True` calls on the same project resource could corrupt the local object-store scratch cache and crash graph-task polling with a boto rename `FileNotFoundError`.

**Work completed:**
- Updated [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py):
  - added per-resource `RLock` management inside `ObjectArtifactStore`
  - wrapped `sync_resource()`, `flush_resource()`, and `delete_resource()` with the resource lock so concurrent requests against the same namespace/resource_id no longer mutate the same scratch tree at once
- Expanded [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh):
  - added a deterministic concurrent `sync_resource("projects", "race")` regression using a fake object-store client
  - validates that the same resource can be synced from two threads without losing the final file or raising an exception
- Revalidated locally:
  - `python3 -m py_compile backend/app/services/artifact_store.py backend/app/services/simulation_manager.py backend/app/services/simulation_runner.py backend/app/api/simulation.py`
  - `bash -n scripts/verify_production_fixes.sh`
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`

**Result:**
- The new live blocker is understood and fixed locally: object-store scratch sync is now serialized per resource.
- Next step: publish this second fix to the GitHub-backed repo, let Railway redeploy again, and rerun the full production canary from ontology through live `run-status`.

## 2026-03-18 13:07 - Checkpoint: Fixed object-store runtime upload failure after live canary reached start

**Context:** The next live web canary finally crossed the earlier blockers and reached `prepare -> start`, but the first real runtime on `object_store` still failed immediately after launch. Production `run-status` showed `runner_status=failed` for `sim_085275c7be5d`, and Railway logs reported `Need to rewind the stream <botocore.httpchecksum.AwsChunkedWrapper ...>, but stream is not seekable.` This narrowed the remaining issue to object-store flush behavior during run-state persistence, not graph generation, preparation, or simulation startup itself.

**Work completed:**
- Updated [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py):
  - configured the S3 client with `request_checksum_calculation="when_required"` and `response_checksum_validation="when_required"` to avoid aggressive checksum-wrapped streaming behavior on the S3-compatible backend
  - added `_upload_local_file()` and routed `flush_resource()` through it
  - small artifacts (`<= 8 MiB`) now upload via `put_object(Body=bytes)` instead of streaming `upload_file`, while larger files still use `upload_file`
- Expanded [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh):
  - added regression coverage for `_upload_local_file()`
  - validates that small files use `put_object` and large files still use `upload_file`
- Revalidated locally:
  - `cd backend && uv run python -m compileall app worker.py run.py`
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`

**Result:**
- The web object-store canary is now narrowed to one concrete runtime artifact-upload contract, and that contract has a targeted local fix plus regression coverage.
- Next step: sync this fix to the GitHub-backed repo, let Railway redeploy, and rerun the live `prepare -> start -> run-status` canary to confirm the run survives beyond round 0.

## 2026-03-18 13:12 - Checkpoint: Production web object-store canary reached green through run-status

**Context:** After pushing commit `ab0e67f` to the GitHub-backed private repo, Railway rolled a new production web deployment on the same commit. The key question was whether the earlier `AwsChunkedWrapper` runtime-upload crash was truly gone under `artifact_storage_mode=object_store`.

**Work completed:**
- Confirmed Railway production web deployment:
  - `AgenikPredict` -> `d27b29ea-de21-4efd-baa6-cc4e9cbc0c39` -> `SUCCESS`
  - commit `ab0e67fc34d0d9bb3bbd5d08b135c2fc79a98e63`
- Revalidated production `/health`:
  - `artifact_storage_mode=object_store`
  - `task_execution_mode=inline`
  - `status=ok`
- Ran a focused live runtime smoke against the already-prepared simulation `sim_085275c7be5d`:
  - restarted with `/api/simulation/start` and `force=true`
  - observed successful process start (`process_pid=236`, `runner_status=running`)
  - verified immediate action generation via `run-status/detail` (`all_actions` contained 12 live actions)
  - verified eventual counter convergence via `run-status` (`runner_status=completed`, `current_round=2`, `total_actions_count=12`, `reddit_actions_count=12`, `error=null`)

**Result:**
- The current production web canary is green end-to-end for `prepare -> start -> run-status` on `object_store`.
- The runtime-hardening focus now moves to the next block: controlled active worker cutover.
- Immediate next blocker: `AgenikPredictWorker` latest GitHub deployment `0873e188-1b44-4532-bf9e-2ba8dc31aaf3` is still shown by Railway as `BUILDING/stopped=true`, so worker rollout must be investigated before switching execution off the web process.

## 2026-03-18 13:18 - Checkpoint: User-reported graph-build interruption traced to restart recovery, not graph logic

**Context:** The user reported a graph build that kept refreshing node/edge counts and then failed at `12:58 PM EDT` with `Interrupted by server restart. Please retry.` The immediate question was whether this signaled a new graph-runtime defect after the green web canary.

**Work completed:**
- Checked current production state:
  - `AgenikPredict` is healthy on deployment `d27b29ea-de21-4efd-baa6-cc4e9cbc0c39`
  - `/health` returns `status=ok`, `artifact_storage_mode=object_store`, `task_execution_mode=inline`
- Checked current worker state:
  - `AgenikPredictWorker` latest GitHub deployment still shows `BUILDING/stopped=true`
  - worker runtime logs confirm it can boot in standby and pass the object-store probe
- Traced the exact interruption message to code:
  - [backend/app/models/task.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/task.py) in `recover_interrupted_tasks()`
  - stale in-flight `graph_build` tasks are explicitly marked `FAILED` with `Interrupted by server restart. Please retry.` after a process restart

**Result:**
- The user’s graph build was not failing because the graph engine became invalid.
- It was interrupted by a web service restart/deploy while `TASK_EXECUTION_MODE=inline` was still active.
- This is exactly the remaining operational risk we expected before active worker cutover: long-running tasks are still hosted by the web process, so restarts can kill them.

## 2026-03-18 13:31 - Checkpoint: Active worker cutover attempt aborted safely; blocker is Railway rollout sequencing

**Context:** After the green `web inline + object_store` canary and the restart-recovery diagnosis, I attempted the next planned block: moving background task execution off the web process and onto `AgenikPredictWorker`.

**Work completed:**
- Safely moved both services to the prerequisite task backend contract:
  - `TASK_STORE_MODE=db`
  - `TASK_READ_SOURCE=db`
  - verified web on deploy `ae70108e-b589-4522-90b5-0754433554ac`
  - verified `/health` returned `task_execution_mode=inline`, `task_store_mode=db`, `task_read_source=db`
- Attempted the real cutover:
  - staged `TASK_EXECUTION_MODE=worker` on both services
  - removed standby on worker
  - redeployed web and worker in a controlled sequence
- Observed real worker activation at one point:
  - worker logs showed `Task worker started: mode=worker poll_interval=2.0s batch_size=10`
  - worker deployment history showed `57ed8735-f525-4d74-a1c9-e873dfe4111e | SUCCESS`
- Observed Railway rollout sequencing undermine the cutover:
  - later worker logs showed a newer standby boot (`TASK_EXECUTION_MODE=inline`) while web had already flipped to `TASK_EXECUTION_MODE=worker`
  - this created an unsafe queue-only / asymmetric state
- Performed immediate safe rollback:
  - restored web to `TASK_EXECUTION_MODE=inline`
  - rolled web to deployment `11161a77-b90a-4f40-8fe7-f0eb3217b512`
  - rechecked `/health`: `status=ok`, `task_execution_mode=inline`, `task_store_mode=db`, `task_read_source=db`

**Result:**
- Production is safe again.
- The blocker is no longer the application code or object-store runtime.
- The blocker is Railway deployment sequencing/orchestration for two coupled services: worker and web cannot yet be switched with enough determinism using ad hoc redeploy nudges without creating an unsafe intermediate state.

## 2026-03-18 13:44 - Checkpoint: Added fail-fast worker readiness gating and a maintenance-window cutover runbook

**Context:** The last production attempt proved that code/runtime prerequisites were good enough for a worker cutover, but Railway sequencing could still leave the app in an unsafe queue-only state if web flipped before worker was truly active. The next task was to make the application itself refuse that unsafe state and to turn the cutover into an explicit runbook.

**Work completed:**
- Added worker-mode preflight in [backend/app/services/task_worker.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/task_worker.py):
  - `WorkerDispatchUnavailable`
  - `ensure_worker_dispatch_ready()`
  - worker-mode dispatch now validates worker `/health` before accepting enqueue-only execution
- Added startup guardrails:
  - [backend/app/config.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/config.py) now defines `WORKER_HEALTHCHECK_URL` and timeout config
  - [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py) now enforces `validate_standby()` on web startup, so web cannot boot in worker mode without a configured healthcheck target
- Moved fail-fast gating ahead of task creation in:
  - [backend/app/api/graph.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/graph.py)
  - [backend/app/api/simulation.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/simulation.py)
  - [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py)
- Added regression coverage in [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh):
  - missing `WORKER_HEALTHCHECK_URL` fails fast
  - standby worker payload is rejected
  - active worker payload is accepted
  - graph/simulation/report endpoints return `503` before creating tasks or billing reservations when the worker is not active
- Wrote [docs/maintenance_window_worker_cutover.md](/Users/alexanderivenski/Projects/AgenikPredict/docs/maintenance_window_worker_cutover.md) to codify the next live cutover sequence and rollback procedure
- Revalidated locally:
  - `cd backend && uv run python -m compileall app worker.py run.py`
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`

**Result:**
- The next worker cutover will no longer rely on “web flips and hopes the worker is alive.”
- Unsafe web worker-mode startup without a healthcheck target is now blocked.
- Unsafe enqueue-only API calls are now rejected before task creation.
- The remaining live blocker is operational sequencing in Railway, not missing application-side safeguards.

## 2026-03-18 13:58 - Checkpoint: Safeguard commit shipped to GitHub-backed prod; worker rollout still blocked in Railway

**Context:** After the local safeguards were proven, the next goal was to land them in the GitHub-backed production pipeline and resume the live cutover sequence from a safe baseline.

**Work completed:**
- Synced only the safeguard-related files into the private source-of-truth repo and pushed:
  - commit `cdac5cc2340f8f3d00c3d44e0ddb2682cdf28642`
  - message: `Add worker cutover safety guardrails`
- Railway picked up the new commit automatically for both services.
- Verified web rollout:
  - `AgenikPredict` deployment `021e23ae-5e36-4a5f-86e8-6d827324a251` -> `SUCCESS`
  - deployment logs show the expected backend path:
    - `Building agenikpredict-backend @ file:///app/backend`
    - gunicorn startup
    - artifact store probe success
  - public `/health` stays green and safe:
    - `artifact_storage_mode=object_store`
    - `task_execution_mode=inline`
    - `task_store_mode=db`
    - `task_read_source=db`
- Staged the web-side worker preflight target without forcing a deploy:
  - `WORKER_HEALTHCHECK_URL=http://agenikpredictworker.railway.internal/health`
- Investigated worker rollout:
  - `AgenikPredictWorker` deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb` picked up the same commit
  - build logs show a successful `Dockerfile.production` build
  - deployment-specific runtime logs are still blank
  - Railway still reports the deployment as `DEPLOYING`

**Result:**
- The safeguard code is now live on the web service and ready for the next cutover attempt.
- Production remains safe; nothing has been flipped to worker mode yet.
- The current blocker is a Railway-side worker rollout stall, not missing application logic.

## 2026-03-18 18:07 - Checkpoint: First worker-first maintenance-window cutover halted and rolled back before touching web

**Context:** With the safeguard commit live and `WORKER_HEALTHCHECK_URL` staged on web, the next attempt was the actual runbook sequence: activate worker first, prove it is healthy, and only then consider flipping web to enqueue-only.

**Work completed:**
- Revalidated the live web baseline:
  - `https://app.agenikpredict.com/health` stayed green
  - `task_execution_mode=inline`
  - `task_store_mode=db`
  - `task_read_source=db`
- Verified recent web logs did not show obvious active long-running work; they only showed startup and healthcheck requests.
- Attempted worker-first activation only:
  - changed `AgenikPredictWorker` env to `TASK_EXECUTION_MODE=worker`, `WORKER_STANDBY=false`
  - Railway created deployment `d0738ad0-3f65-475e-b3a1-3282c5dfc78d`
  - build logs completed successfully
- Investigated the resulting worker state:
  - `railway status --json` reported the new deployment as `status=DEPLOYING`
  - the same status payload showed `deploymentStopped=true`
  - deployment-specific runtime logs stayed empty
  - previous standby deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb` remained present in `activeDeployments`
- Because the runbook requires a proven active worker before any web change, I stopped there and rolled worker env back:
  - `TASK_EXECUTION_MODE=inline`
  - `WORKER_STANDBY=true`
  - rollback deployment `728668ae-b3d9-4fa5-96aa-a14c8c22536f` started

**Result:**
- Web was never flipped to worker mode during this attempt.
- Production remained safe the entire time.
- The blocker is now isolated to Railway worker-service rollout behavior:
  - worker deployments can build successfully and still end up `DEPLOYING` with `deploymentStopped=true` and no runtime logs.
- This is no longer an application-code blocker; it is an orchestration/platform blocker on the worker service itself.

## 2026-03-18 18:15 - Checkpoint: Second worker-only activation reproduced the same Railway deploymentStopped failure

**Context:** After the first worker-first cutover was halted safely, I needed to determine whether that was a transient rollout glitch or a reproducible worker-service platform fault. To isolate that, I retried only the worker activation from a clean standby baseline, with web left untouched and healthy.

**Work completed:**
- Verified rollback baseline:
  - `AgenikPredictWorker` standby rollback deployment `728668ae-b3d9-4fa5-96aa-a14c8c22536f` reached `SUCCESS`
  - worker vars were back to `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`
  - public web remained healthy and inline
- Re-ran worker-only activation:
  - set `TASK_EXECUTION_MODE=worker`, `WORKER_STANDBY=false`
  - Railway created deployment `67c5ebce-1a92-4b51-8bf1-090ad2959050`
  - build logs again completed successfully
- Observed the same failure signature:
  - deployment moved through `INITIALIZING -> BUILDING -> DEPLOYING`
  - `railway status --json` again reported the latest worker deployment as `status=DEPLOYING`
  - status also again showed `deploymentStopped=true`
  - deployment-specific runtime logs were still empty
- Re-applied rollback to safe standby:
  - restored worker vars to `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`
  - rollback deployment `98f8ce78-063b-479c-99df-d482f04e9d58` started

**Result:**
- The worker-service failure is now reproducible, not anecdotal.
- We have two independent active-worker attempts (`d0738ad0...` and `67c5ebce...`) with the same pattern:
  - successful build
  - no useful runtime logs
  - `DEPLOYING`
  - `deploymentStopped=true`
- Web stayed safe and was never flipped during either attempt.

## 2026-03-18 18:08 - Checkpoint: Fresh canary worker service created and proven in standby

**Context:** The original `AgenikPredictWorker` had now failed two independent active-rollout attempts with the same Railway-specific `deploymentStopped=true` pattern. I needed to determine whether that fault belonged to the existing service object/orchestration state or to the app/runtime itself.

**Work completed:**
- Created a fresh Railway service:
  - `AgenikPredictWorkerCanary`
  - service id `8bb77a24-7773-4531-af62-219c74624602`
- Copied the original worker environment into the canary service, excluding Railway-managed variables only
- Confirmed the canary safe baseline:
  - `SERVICE_ROLE=worker`
  - `TASK_EXECUTION_MODE=inline`
  - `WORKER_STANDBY=true`
  - `TASK_STORE_MODE=db`
  - `TASK_READ_SOURCE=db`
  - `ARTIFACT_STORAGE_MODE=object_store`
  - `DATABASE_URL` present
- Deployed the known-good safeguard snapshot `cdac5cc` to the canary as deployment `e455f254-1386-4978-9843-dd8f65555abf`
- Waited through the long first build and captured successful standby runtime logs:
  - object-store probe succeeded
  - worker health server started
  - standby message emitted

**Result:**
- The workaround path is valid.
- A fresh worker service can deploy the current codebase successfully.
- This already proved the blocker was not a general incompatibility between the app and Railway worker runtime.

## 2026-03-18 18:22 - Checkpoint: Canary worker reached active SUCCESS with a real worker loop

**Context:** After the fresh canary service proved itself in standby, the next goal was to see whether it could run in full active worker mode without reproducing the original service's orchestration failure.

**Work completed:**
- Switched only the canary worker to active mode:
  - `TASK_EXECUTION_MODE=worker`
  - `WORKER_STANDBY=false`
  - `TASK_WORKER_ID=worker-canary-1`
- This created canary deployment `9031b625-99c2-4224-8ee6-b21e55a1eca5`
- Observed the deployment complete successfully
- Captured active runtime logs showing:
  - full backend startup
  - database initialization
  - object-store probe success
  - worker health server startup
  - active worker loop startup: `Task worker started: mode=worker poll_interval=2.0s batch_size=10`

**Result:**
- A real dedicated active worker is now proven on Railway via the fresh canary service.
- The original `AgenikPredictWorker` issue is therefore service-specific/platform-state-specific, not a fundamental code/runtime blocker.
- Public web remains untouched and safe in inline mode.
- The next cutover target is now the canary worker, not the original worker service.

## 2026-03-18 18:47 - Checkpoint: Public web successfully cut over to worker mode via canary worker

**Context:** With `AgenikPredictWorkerCanary` already proven in active mode, the remaining step was to move public web off inline execution and onto a true queue-to-worker model without breaking production.

**Work completed:**
- First flipped web to worker mode with `WORKER_HEALTHCHECK_URL=http://agenikpredictworkercanary.railway.internal/health`
- Observed a precise live failure:
  - `/api/graph/build` returned `503`
  - web logs showed `Worker healthcheck request failed ... connection refused`
- Traced the issue to the internal port:
  - canary worker logs advertised health on `0.0.0.0:8080/health`
  - web had been probing the private domain without `:8080`
- Corrected web env to:
  - `WORKER_HEALTHCHECK_URL=http://agenikpredictworkercanary.railway.internal:8080/health`
- Railway created web deployment `93d42022-d8a1-4568-9df7-d2bb842e41c9`, which reached `SUCCESS`
- Confirmed public `/health` now reports:
  - `task_execution_mode=worker`
  - `artifact_storage_mode=object_store`
  - `task_store_mode=db`
  - `task_read_source=db`
- Ran a live smoke:
  - demo-authenticated upload and ontology generation succeeded
  - web created graph task `a7c717f1-ce8c-44e7-a397-9ef36b8a6e92`
  - web logs explicitly showed:
    - `Task enqueued without local dispatch because TASK_EXECUTION_MODE=worker`
  - canary worker logs explicitly showed:
    - `Worker claimed task: task_id=a7c717f1-ce8c-44e7-a397-9ef36b8a6e92 worker_id=worker:worker-canary-1`
    - `Starting graph build...`
  - task API showed the task actively processing with live heartbeat and progress

**Result:**
- The production runtime substrate is now genuinely different from the original inline model:
  - public web enqueues
  - dedicated canary worker executes
  - task state is persisted in DB
  - artifact access is through object store
- This closes the main reliability blocker that had been causing long-running work to die on web restarts.
- The original `AgenikPredictWorker` can remain in standby; `AgenikPredictWorkerCanary` is now the proven production execution target.

## 2026-03-18 15:33 - Checkpoint: ReportAgent live evidence v1 added on the backend

**Context:** With the runtime substrate finally stable, the roadmap moved to the first scientific-layer step: giving `ReportAgent` access to current-world evidence instead of relying only on the Zep graph built from uploaded materials.

**Work completed:**
- Added a new backend service:
  - [backend/app/services/live_evidence.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/live_evidence.py)
  - `live_news_brief()`:
    - fetches recent headlines from Google News RSS search
    - parses source names, publish dates, and links
    - uses short timeouts and in-memory caching
    - degrades to warning text instead of raising
  - `live_market_snapshot()`:
    - uses the existing Twelve Data integration
    - detects tickers from query/context
    - returns live quote summaries and warnings when unavailable
- Added config toggles/defaults:
  - `LIVE_EVIDENCE_ENABLED`
  - `LIVE_NEWS_TIMEOUT_SECONDS`
  - `LIVE_NEWS_MAX_ITEMS`
  - `LIVE_EVIDENCE_CACHE_TTL_SECONDS`
- Wired live tools into `ReportAgent`:
  - imported `LiveEvidenceService`
  - instantiated it in `ReportAgent.__init__`
  - extended `_define_tools()` with:
    - `live_news_brief`
    - `live_market_snapshot`
  - extended `_execute_tool()` with execution paths for both tools
  - expanded tool validation so parsed tool calls can legally reference the new tools
  - changed per-section `all_tools` tracking to derive from `self.tools`, keeping the loop compatible with feature-flagged tools
- Kept the integration backend-only:
  - no new routes
  - no UI changes
  - no changes to the worker/runtime cutover path

**Verification:**
- `cd backend && uv run python -m compileall app` -> success
- targeted Python verification with mocked RSS + mocked market data -> `live_evidence_ok`
- `ReportAgent` instance now exposes `live_news_brief` and `live_market_snapshot`

**Result:**
- `ReportAgent` now has a safe v1 path to bring current-world evidence into report generation.
- The live-evidence layer is narrow, read-only, timeout-bounded, and backward compatible.
- The next scientific-layer step is no longer “connect current data”; it is “structure the output” with explicit probabilities/scenarios.

## 2026-03-18 15:45 - Checkpoint: Structured scenario probabilities added to ReportAgent

**Context:** After live evidence v1, the next roadmap step was to move report output from pure narrative toward a measurable prediction format without breaking existing markdown reports or API payloads.

**Work completed:**
- Extended [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py):
  - `Report` now carries `prediction_summary`
  - added `PROBABILITY_SUMMARY_SYSTEM_PROMPT`
  - added `_generate_prediction_summary()` post-pass over the completed markdown report
  - added `_normalize_prediction_summary()` and `_normalize_probability_values()`
  - added `ReportManager.save_prediction_summary()`
  - added `ReportManager._format_prediction_summary_markdown()`
  - updated `assemble_full_report()` to embed a `## Scenario Outlook` block
  - updated `save_report()` / `get_report()` so structured summaries persist and round-trip cleanly
- Addressed two real issues found during verification:
  - probability normalization now distributes integer remainder deterministically so scenario probabilities always sum to `100`
  - `_post_process_report()` now preserves `## Scenario Outlook` instead of demoting it to bold text
- Fixed an underlying storage bug in [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py):
  - `get_resource_dir(..., ensure=True, sync=True)` had been dropping the `ensure` guarantee
  - this could break report assembly on a cold path
  - both local and object-store backends now honor `ensure` even when `sync=True`

**Verification:**
- `cd backend && uv run python -m compileall app` -> success
- targeted Python verification -> `probability_layer_ok`
  - generated normalized `Bull case / Base case / Bear case`
  - confirmed probabilities sum to `100`
  - confirmed markdown includes `## Scenario Outlook`
  - confirmed the heading survives post-processing
  - confirmed `save_report()` / `get_report()` round-trip preserves `prediction_summary`

**Result:**
- The probability/scenario layer is now implemented locally and verified.
- This block remains backend-only for now and has not been deployed to Railway yet.
- The next roadmap step is `Prediction Ledger`, so scenario probabilities can be stored and later scored against outcomes without parsing markdown.

## 2026-03-18 15:53 - Checkpoint: DB-backed Prediction Ledger added and verified

**Context:** After adding structured probabilities, the next requirement was to stop treating markdown as the only durable output and persist scenario predictions in a form that future backtesting and calibration can query directly.

**Work completed:**
- Added a new DB-backed ledger model:
  - [backend/app/models/prediction_ledger.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/prediction_ledger.py)
  - schema stores one row per scenario with:
    - report/simulation/graph/project/owner linkage
    - scenario name and order
    - probability, timeframe, forecast horizon
    - summary, drivers, risks, assumptions
    - confidence note and caveats
    - placeholder outcome fields for later backtesting
- Wired startup initialization in [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py):
  - `PredictionLedgerManager.init_db()`
- Wired report persistence in [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py):
  - `ReportManager.save_report()` now best-effort syncs ledger rows when `prediction_summary` exists
  - `ReportManager.get_report()` can rebuild `prediction_summary` from ledger rows if sidecar/meta copies are missing
- Added two read-only endpoints in [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py):
  - `GET /api/report/<report_id>/predictions`
  - `GET /api/report/by-simulation/<simulation_id>/predictions`
- Kept the new ledger path backward compatible:
  - no UI changes
  - no markdown parsing needed
  - ledger sync logs warnings instead of breaking report save if DB write fails

**Verification:**
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- targeted Flask/test-client verification -> `prediction_ledger_ok`
  - created synthetic owned project + simulation
  - saved synthetic completed report with `prediction_summary`
  - confirmed 3 ledger rows were written
  - confirmed probabilities sum to `100`
  - confirmed summary rebuild from ledger works
  - confirmed both new read-only ledger endpoints return `200`

**Result:**
- Prediction scenarios now have a real backend source of truth outside markdown.
- The system is ready for the next scientific-layer step: outcome tracking and first-pass backtest/calibration metrics on top of the new ledger.

## 2026-03-18 15:55 - Checkpoint: Outcome tracking and baseline metrics added on top of Prediction Ledger

**Context:** After introducing the DB-backed ledger, the next useful scientific-layer slice was to stop at “stored predictions” and add the first measurable feedback loop: record realized outcomes and compute baseline quality metrics.

**Work completed:**
- Extended [backend/app/models/prediction_ledger.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/prediction_ledger.py):
  - `get_prediction()`
  - `record_outcome()`
  - `compute_metrics()`
- Outcome model now supports initial statuses:
  - `observed`
  - `not_observed`
  - `partial`
  - `pending`
- Added baseline aggregate metrics:
  - total vs settled vs pending predictions
  - counts by realized status
  - average predicted probability by realized status
  - scenario-level Brier-style score
- Added two API routes in [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py):
  - `POST /api/report/predictions/<prediction_id>/outcome`
  - `GET /api/report/predictions/metrics`
- Reused existing ownership validation through the prediction’s parent simulation/project chain instead of inventing a separate auth model.

**Verification:**
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- targeted Flask/test-client verification -> `prediction_metrics_ok`
  - created synthetic owned project + simulation
  - saved synthetic completed report with `prediction_summary`
  - recorded two outcomes through the API
  - fetched aggregate metrics through the API
  - confirmed:
    - `total_predictions = 3`
    - `settled_predictions = 2`
    - `observed_count = 1`
    - `not_observed_count = 1`
    - `brier_score` returned
- Reviewer request was sent for the latest slice, but the reviewer agent timed out before returning findings.

**Result:**
- The backend now has the first real prediction-feedback loop:
  - generate structured scenarios
  - persist them separately from markdown
  - record outcomes
  - compute baseline metrics
- The next practical step is no longer storage design; it is controlled deployment of the new scientific-layer backend changes and then live verification on a real report run.

## 2026-03-18 16:35 - Checkpoint: Scientific layer deployed live, malformed summary bug fixed, and production report backfilled

**Context:** After completing the local scientific-layer backend work, I pushed it to the private GitHub source repo and verified it on a real production report run rather than stopping at synthetic tests.

**Work completed:**
- Deployed the scientific-layer backend through the private GitHub repo in three production commits:
  - `31aaca8` `feat: add report prediction ledger and live evidence`
  - `d2bfb66` `fix: repair malformed structured prediction summaries`
  - `2c5925d` `fix: backfill missing report prediction summaries`
- Ran a real production report generation on `simulation_id=sim_351ed9f941be`.
- Confirmed the worker path completed on `AgenikPredictWorkerCanary` for `report_id=report_3df60809f7cd`.
- Verified in production worker logs:
  - live evidence/tool execution ran inside the report path
  - all four report sections were saved
  - final assembly completed
  - the new `Generating structured scenario outlook...` stage executed
- Exposed a real production bug during that smoke:
  - structured prediction summary generation failed on malformed LLM JSON
  - result: report completed, but `prediction_summary` and ledger rows were missing
- Fixed the bug in [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py):
  - `_generate_prediction_summary()` now uses `chat_json_with_fallback()` so the existing JSON-repair path is actually exercised
- Added a safe recovery path in [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py):
  - `GET /api/report/<report_id>/predictions?backfill=true`
  - this regenerates structured predictions from the saved markdown of an already-completed report and persists them via `ReportManager.save_report()`, which syncs the ledger

**Verification:**
- Local:
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - targeted recovery verification -> `report_prediction_backfill_ok`
- Production:
  - report smoke:
    - `simulation_id=sim_351ed9f941be`
    - `task_id=48792a39-547f-4c9e-847a-3bccc40d8906`
    - `report_id=report_3df60809f7cd`
  - progress reached:
    - `95` `Assembling complete report...`
    - `97` `Generating structured scenario outlook...`
    - `100` `Report generation complete`
  - live recovery after `2c5925d`:
    - `GET /api/report/report_3df60809f7cd/predictions?backfill=true` returned `3` items
    - scenarios: `Bull case`, `Base case`, `Bear case`
    - probabilities: `25`, `50`, `25`
    - `GET /api/report/report_3df60809f7cd` then returned `has_prediction_summary = true`
    - `GET /api/report/predictions/metrics?report_id=report_3df60809f7cd` returned `total_predictions = 3`, `pending_predictions = 3`

**Result:**
- The backend scientific layer is now live in production and verified on a real report.
- The system can recover missing structured predictions from completed reports instead of leaving them permanently empty after a malformed LLM JSON response.
- The next meaningful step is no longer deployment plumbing; it is the first historical backtest/calibration loop on real completed reports.

## 2026-03-18 17:25 - Checkpoint: Historical/backtest pilot dataset and evaluation routes added

**Context:** After rechecking Railway, all core services were green and production scientific-layer code was healthy. That cleared the way to start the next roadmap block: the first historical/backtest loop.

**Work completed:**
- Rechecked current production state:
  - `AgenikPredict` -> `SUCCESS`
  - `AgenikPredictWorker` -> `SUCCESS`
  - `AgenikPredictWorkerCanary` -> `SUCCESS`
  - `https://app.agenikpredict.com/health` -> `status=ok`
- Added a curated pilot historical dataset in [backend/app/data/historical_backtest_cases.json](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/data/historical_backtest_cases.json)
  - 5 starter cases
  - domains include AI governance, banking, enterprise outage, crypto collapse, and consumer platforms
- Added [backend/app/models/historical_backtest.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/historical_backtest.py)
  - `HistoricalBacktestCase`
  - `HistoricalBacktestManager`
  - list and get access to the pilot dataset
- Extended [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py) with:
  - `GET /api/report/backtest/cases`
  - `GET /api/report/backtest/cases/<case_id>`
  - `POST /api/report/backtest/reports/<report_id>/evaluate`
- The evaluation route:
  - optionally backfills predictions for a completed report
  - batch-applies outcomes for `Bull/Base/Bear`
  - links the evaluation to a historical case via outcome payload
  - returns updated metrics immediately

**Fixes during implementation:**
- Removed a bad dependency on nonexistent `Report.project_id` / `Report.owner_id` fields in the prediction backfill helper
- Fixed a positional call to keyword-only `PredictionLedgerManager.record_outcome()`

**Verification:**
- Local:
  - `cd backend && uv run python -m compileall app/api/report.py app/models/historical_backtest.py` -> success
  - targeted Flask/test-client verification -> `historical_backtest_ok`
    - listed pilot cases
    - fetched a case by id
    - created synthetic completed report with prediction summary
    - batch-applied outcomes
    - confirmed `applied_count = 3`
    - confirmed `settled_predictions = 3`
- Production:
  - pushed to private GitHub repo as `2f4c354` `feat: add pilot historical backtest cases`
  - `AgenikPredict` production deploy `334d47c9-1e1e-4232-a102-6d25ca612b0b` -> `SUCCESS`
  - live call to `GET /api/report/backtest/cases` returned:
    - `version = pilot-v1`
    - `case_count = 5`
    - first case = `openai-board-crisis-2023`

**Result:**
- The first historical/backtest slice is now live on the backend.
- The system can now:
  - serve a curated pilot historical dataset
  - attach completed reports to those cases
  - batch-write scenario outcomes
  - compute updated metrics immediately
- The next step is to move from “pilot case registry + batch evaluation” to cohort-level calibration views across multiple completed reports.

## 2026-03-18 17:55 - Checkpoint: Language-consistent scientific layer and cohort metrics hardening

**Context:** After historical pilot routes were live, the next requirement was to make report generation and client-read simulation/report artifacts respect the currently selected system language, while also continuing the historical calibration roadmap.

**Work completed:**
- Added locale normalization/request-resolution in [backend/app/utils/locale.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/utils/locale.py)
- Persisted `language_used` through:
  - [backend/app/models/project.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/project.py)
  - [backend/app/services/simulation_manager.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_manager.py)
  - [backend/app/services/simulation_config_generator.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_config_generator.py)
  - [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py)
- Wired language through ontology/report/profile generation:
  - ontology generation now stores `project.language_used`
  - simulation prepare now regenerates instead of silently reusing wrong-language prepared state
  - `OasisProfileGenerator` now receives `language` and avoids English rule-based fallbacks when non-English is selected
  - report generation now uses resolved request language and exposes `language_used` in report/prediction responses
- Localized the structured scenario block in report markdown:
  - `Bull/Base/Bear` stay canonical in stored summary
  - display markdown headings and scenario labels localize according to `language_used`
- Wired frontend report-config propagation:
  - [frontend/src/components/GraphPanel.vue](/Users/alexanderivenski/Projects/AgenikPredict/frontend/src/components/GraphPanel.vue) syncs report language with app locale and emits updates
  - [frontend/src/views/SimulationRunView.vue](/Users/alexanderivenski/Projects/AgenikPredict/frontend/src/views/SimulationRunView.vue) passes report config down
  - [frontend/src/components/Step3Simulation.vue](/Users/alexanderivenski/Projects/AgenikPredict/frontend/src/components/Step3Simulation.vue) forwards `language`, `custom_persona`, and `report_variables` into report generation
- Extended historical calibration with cohort-level aggregation:
  - added `PredictionLedgerManager.compute_historical_case_metrics()`
  - added `GET /api/report/backtest/metrics`

**Reviewer-driven fixes applied before release:**
- Fixed `force_regenerate=true` so it can no longer reuse an active report task in a different language.
- Added missing `language_used` to report/simulation fast-path status responses.
- Fixed `/api/simulation/<id>/profiles?platform=twitter` to read the real CSV output instead of a nonexistent JSON file.
- Added localized scenario-key matching in historical evaluation (`Бычий сценарий`, etc.).
- Fixed the regression harness mock signature so `bash scripts/verify_production_fixes.sh` stays green after the new `language=` parameter.

**Verification:**
- Local:
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `npm run build` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - targeted manager-level aggregation verification -> `historical_metrics_ok`
  - targeted route-level verification -> `route_contract_ok`
- Reviewer:
  - independent review caught five real issues in the first pass
  - all blocking/high-medium backend issues were addressed
  - one low residual remains: some Graph/Simulation panel chrome labels are still hardcoded in English

**Result:**
- The scientific layer is now materially stronger in two directions at once:
  - language consistency through project/simulation/report artifacts and report generation
  - cohort-level historical calibration metrics across multiple evaluated reports
- Backend/API correctness for the selected language is verified locally and ready for the next GitHub/Railway rollout.

## 2026-03-18 18:20 - Checkpoint: GitHub push completed, Railway rollout blocked in prolonged build state

**Context:** After local verification passed for the language-consistency + cohort-metrics slice, the next step was to promote it through the Railway-linked private GitHub repo instead of direct CLI deployment.

**Work completed:**
- Created a clean temporary clone of the Railway-linked private repo:
  - `https://github.com/alexprime1889-prog/codex-agenic-predict-private.git`
- Overlaid only the verified files from the working tree:
  - language propagation/backend scientific-layer files
  - historical cohort metrics changes
  - verification script updates
  - execution logs
- Committed and pushed:
  - commit `b593078`
  - message: `feat: align language flow and add cohort backtest metrics`

**Verification before push:**
- `cd backend && uv run python -m compileall app worker.py run.py` -> success
- `npm run build` -> success
- `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- targeted route-level contract verification -> `route_contract_ok`

**Railway rollout status after push:**
- GitHub-based deployments started automatically for commit `b593078d5857731c8e8199f6ff97e313e4cb77d5`
  - `AgenikPredict` -> deployment `6a1f6b5f-a732-4707-b5ee-c3b434699869`
  - `AgenikPredictWorker` -> deployment `b9426516-97ed-42af-90cb-2691da765c9a`
- Both deployments remained in `BUILDING`
- Available build logs reached:
  - `[production 11/11] WORKDIR /app/backend`
  - `[auth] sharing credentials for production-us-east4-eqdc4a.railway-registry.com`
- No explicit build error was exposed in the fetched logs

**Current live production state while rollout is blocked:**
- `https://app.agenikpredict.com/health` still returns `status=ok`
- current live remains on the previous healthy release
- live health still reports:
  - `artifact_storage_mode=object_store`
  - `task_execution_mode=worker`
  - `task_store_mode=db`

**Result:**
- Code work for this slice is done and pushed to the correct private GitHub source repo.
- The current blocker is Railway deployment progression, not repository code or local verification.
- Production is not down; it remains healthy on the last successful release while the new GitHub-triggered builds are stuck in `BUILDING`.

## 2026-03-18 18:35 - Checkpoint: GitHub rollout completed live on production

**Context:** After a long `BUILDING` phase on Railway, the goal was to verify whether the pushed language + cohort-metrics slice actually reached production and whether the new endpoints were live.

**Railway outcome:**
- `AgenikPredict` deployment `6a1f6b5f-a732-4707-b5ee-c3b434699869` -> `SUCCESS`
- `AgenikPredictWorker` deployment `b9426516-97ed-42af-90cb-2691da765c9a` -> `SUCCESS`
- both deployments are on commit `b593078d5857731c8e8199f6ff97e313e4cb77d5`

**Live verification:**
- `GET https://app.agenikpredict.com/health` -> `status=ok`
- Authenticated smoke using `POST /api/auth/demo`:
  - `GET /api/report/backtest/cases` -> `200`
    - `version = pilot-v1`
    - `case_count = 5`
  - `GET /api/report/backtest/cases/openai-board-crisis-2023` -> `200`
  - `GET /api/report/backtest/metrics` -> `200`
    - demo-user payload correctly returned an empty cohort:
      - `evaluated_case_count = 0`

**Result:**
- The language-consistency + cohort-metrics slice is now live in production through the GitHub-based Railway path.
- The release pipeline is healthy again with GitHub as the source of truth.
- The next work should move back to product quality, not deployment plumbing.

## 2026-03-18 19:05 - Checkpoint: Frontend UI i18n cleanup completed locally for Graph/Simulation panels

**Context:** With backend language propagation and historical cohort metrics already live, the remaining language-consistency gap was the frontend chrome in the graph and simulation panels. The goal for this pass was to make those panels respect the selected locale without reopening backend or infra scope.

**Work completed:**
- Localized remaining UI chrome in:
  - `frontend/src/components/GraphPanel.vue`
  - `frontend/src/components/Step3Simulation.vue`
- Replaced hardcoded English labels in:
  - node/relationship detail panels
  - report settings/configuration controls
  - graph legend / edge-label toggle
  - simulation platform headers
  - timeline card metadata and action labels
  - simulation waiting/log monitor labels
- Made frontend time/date formatting locale-aware:
  - graph detail timestamps now use the active `locale`
  - simulation action timestamps now use the active `locale`
  - elapsed-time compact units now flow through locale keys
- Added locale-triggered rerender in `GraphPanel.vue` so graph fallback labels like self-relations/related labels stay aligned after a language switch.
- Extended locale packs for all supported languages:
  - `en`, `ru`, `he`, `es`, `de`, `fr`, `it`, `pt`, `pl`, `nl`, `tr`, `ar`

**Bug caught and fixed during verification:**
- `vue-i18n` rejected strings like `@{user}` in locale JSON because it treats `@` as linked-message syntax.
- Fixed by moving the `@` sign into the interpolation payload in `Step3Simulation.vue` and changing locale messages from `@{user}` to `{user}`.

**Verification:**
- `jq empty frontend/src/i18n/locales/*.json` -> success
- initial `npm run build` -> failed with `vue-i18n` parse error on `step3.repostedFrom`
- after fix, `npm run build` -> success
- targeted grep over `GraphPanel.vue` and `Step3Simulation.vue` confirmed the previously identified hardcoded English user-facing strings were removed or replaced by i18n calls

**Result:**
- The previously known low-risk residual on Graph/Simulation chrome labels is now closed in the local working tree.
- This slice is ready for independent review and then GitHub/Railway rollout if no blocking findings appear.

## 2026-03-18 19:45 - Checkpoint: UI i18n slice rolled out to live web via GitHub/Railway

**Context:** After the local UI i18n pass built successfully, the next step was to promote only that frontend slice through the Railway-linked private GitHub repo without dragging unrelated local repository state.

**Work completed:**
- Synced the verified frontend-only slice and execution logs into the clean private repo clone:
  - `frontend/src/components/GraphPanel.vue`
  - `frontend/src/components/Step3Simulation.vue`
  - `frontend/src/i18n/locales/*.json`
  - `docs/plan-comparison-log.md`
  - `docs/AGENT_SESSION_LOG.md`
- Committed and pushed:
  - commit `a2742b9`
  - message: `feat: localize graph and simulation chrome`

**Verification before push:**
- `jq empty frontend/src/i18n/locales/*.json` -> success
- `npm run build` -> success

**Railway/live outcome:**
- `AgenikPredict` deployment `9e5c77f4-94fc-4081-9791-85640fc05029` -> `SUCCESS`
- live health after rollout:
  - `GET https://app.agenikpredict.com/health` -> `200`
  - payload remains healthy:
    - `status = ok`
    - `task_execution_mode = worker`
    - `artifact_storage_mode = object_store`
    - `task_store_mode = db`
- web runtime log shows a clean startup path including:
  - prediction ledger init
  - object-store probe success
  - backend startup complete

**Worker note:**
- `AgenikPredictWorker` deployment `5585a3c1-ec2e-4c4e-b55b-97c1a2346629` is still formally in `DEPLOYING`
- no runtime log content was emitted for that passive service on this rollout
- the active worker path remains backed by the healthy canary worker service, which is still `SUCCESS`

**Result:**
- The UI language-consistency slice is live on the production web path through GitHub-backed Railway deployment.
- The only remaining rollout uncertainty is the passive non-canary worker service, which is non-blocking for this frontend-only change.

## 2026-03-18 20:05 - Checkpoint: Reviewer follow-up fixed before finalizing UI i18n slice

**Context:** Independent review of the Graph/Simulation i18n pass found one medium issue worth fixing before treating the UI slice as complete: a user-selected report language could be overwritten when the app locale changed. The reviewer also flagged two low issues: zero elapsed-time fallback still hardcoded in English, and frontend-generated simulation log strings still mostly English.

**Work completed:**
- Fixed the report-language override bug in `frontend/src/components/GraphPanel.vue`
  - manual report language selection is now preserved across UI-locale changes
  - automatic syncing only continues when the report language is still following the app locale
- Fixed the zero-state elapsed-time fallback in `frontend/src/components/Step3Simulation.vue`
  - removed hardcoded `0h 0m`
  - zero-state now uses the same localized duration formatting path as non-zero elapsed time

**Verification:**
- `npm run build` -> success

**Residual low items intentionally left out of this follow-up:**
- frontend-generated simulation log strings in `Step3Simulation.vue` are still mostly English
- there are still no dedicated frontend component tests for this i18n path

**Result:**
- The reviewer-identified medium issue is closed.
- The remaining gaps on this UI slice are low-risk and documented.

## 2026-03-18 20:20 - Checkpoint: Reviewer follow-up deployed live on web

**Context:** After closing the reviewer-found medium issue locally, the goal was to push only that small fix through the GitHub/Railway release path and verify the corrected web deployment.

**Work completed:**
- Synced the follow-up fix and updated logs into the Railway-linked private repo clone
- Committed and pushed:
  - commit `fc88b54`
  - message: `fix: preserve report language selection`

**Verification before push:**
- `npm run build` -> success

**Railway/live outcome:**
- `AgenikPredict` deployment `ce4f514c-4f80-4708-9798-51e68b08c51c` -> `SUCCESS`
- `GET https://app.agenikpredict.com/health` -> `200`
  - `status = ok`
  - `task_execution_mode = worker`
  - `artifact_storage_mode = object_store`
  - `task_store_mode = db`
- Web build log reached successful healthcheck.

**Worker rollout note:**
- `AgenikPredictWorker` deployment `e3eec8d9-9223-40b6-b01c-d3218be38fd0` is still displayed by Railway as `DEPLOYING`
- however its build log also reached a successful healthcheck
- this currently looks like Railway deployment-state lag on the passive worker service, not an application regression

**Result:**
- The corrected UI i18n slice, including preserved manual report language selection, is live on the production web path.
- Remaining work in this area is now truly low priority: localizing frontend-generated simulation log strings if desired.

## 2026-03-18 20:35 - Checkpoint: Final multilingual Step3 log cleanup completed locally

**Context:** The last visible multilingual imperfection in the Graph/Simulation flow was the frontend-generated simulation log stream in `Step3Simulation.vue`, which still emitted English strings even when the rest of the panel UI followed the selected locale.

**Work completed:**
- Replaced remaining hardcoded simulation log strings in:
  - `frontend/src/components/Step3Simulation.vue`
- Added i18n-backed log messages for:
  - missing simulation id
  - start/stop lifecycle
  - round-progress updates
  - dynamic graph-update mode
  - report-generation flow
  - initialization
- Added locale keys across all supported frontend locale packs:
  - `en`, `ru`, `he`, `es`, `de`, `fr`, `it`, `pt`, `pl`, `nl`, `tr`, `ar`
- Added a small helper so the report-language line in logs renders the chosen language label, not just the raw locale code.

**Verification:**
- `jq empty frontend/src/i18n/locales/*.json` -> success
- `npm run build` -> success

**Result:**
- The last known multilingual residual inside the Graph/Simulation frontend path is now closed in the working tree.
- This slice is ready to be synced into the private GitHub deployment repo.

## 2026-03-18 20:48 - Checkpoint: Brand identity document created and final i18n pass re-verified

**Context:** The user asked not only to finish the multilingual polish to the end, but also how a real AgenikPredict brand-identity document would be created.

**Work completed:**
- Created a working brand document:
  - `docs/brand_identity_agenikpredict.md`
- The document now contains:
  - brand core
  - positioning
  - audience framing
  - messaging pillars
  - tone of voice
  - visual identity direction
  - multilingual brand rules
  - brand manifesto
- Re-ran the frontend verification after the final Step3 i18n work:
  - `npm run build` -> success

**Result:**
- There is now a real brand-identity artifact inside the repo, suitable as a source document for site copy, deck writing, and creative direction.
- The final multilingual Step3 log-localization slice remains build-verified and ready to push to the private GitHub deployment repo.

## 2026-03-18 20:58 - Checkpoint: Final multilingual polish pushed to GitHub and rolled out on web

**Context:** The goal was to stop at neither local verification nor prompt-level planning. The final multilingual Step3 cleanup had to be pushed through the real GitHub -> Railway path, and the brand-identity artifact had to exist as a stored repo document.

**Work completed:**
- Synced the following into the Railway-linked private repo clone:
  - `frontend/src/components/Step3Simulation.vue`
  - `frontend/src/i18n/locales/*.json`
  - `docs/plan-comparison-log.md`
  - `docs/AGENT_SESSION_LOG.md`
  - `docs/brand_identity_agenikpredict.md`
- Committed and pushed:
  - commit `3135fa6961ee6ea0a34899563914d25585a34537`
  - message: `feat: finish multilingual simulation logs and add brand identity doc`
- Verified rollout state:
  - `AgenikPredict` deployment `6ae30d35-50d8-4f0a-b1a6-64f96bacc0d7` -> `SUCCESS`
  - public `/health` returned `200` with `status=ok`
  - `AgenikPredictWorker` and `AgenikPredictWorkerCanary` build logs both reached successful `/health` checks

**Important note:**
- Railway still shows the passive `AgenikPredictWorker` deployment as `DEPLOYING`, even though its build log reached successful healthcheck again. This matches the earlier pattern of Railway status lag on the passive worker service rather than a live web-path regression.

**Result:**
- The last known multilingual UI tail for Graph/Simulation is now shipped through the real GitHub-backed deployment path.
- The AgenikPredict brand-identity document now exists as a versioned repo artifact and can be used as the source for copy, decks, and creative.

## 2026-03-18 20:24 - Checkpoint: Historical quality loop upgraded beyond static metrics

**Context:** After multilingual polish and brand artifact work were complete, the next roadmap step was no longer infrastructure. The product needed a real historical evaluation loop with operator visibility: richer calibration metrics, a reusable evaluation helper, a batch path, and an internal screen where quality can actually be read.

**Work completed:**
- Extended `backend/app/models/prediction_ledger.py` with richer cohort metrics:
  - domain breakdowns
  - scenario-type breakdowns
  - forecast-horizon breakdowns
  - calibration buckets
  - recent evaluation groups
  - top-scenario hit-rate style metrics
- Refactored `backend/app/api/report.py`:
  - added shared helpers for historical outcome resolution/application
  - historical evaluation can now auto-use a case’s `suggested_outcomes`
  - added `POST /api/report/backtest/evaluate-batch`
- Extended frontend operator tooling:
  - `frontend/src/api/report.js`
  - `frontend/src/views/AdminView.vue`
  - new `Quality` tab shows aggregate backtest/case/domain/scenario/calibration slices

**Verification:**
- `cd backend && ARTIFACT_STORAGE_MODE=local TASK_EXECUTION_MODE=inline JWT_SECRET=test-secret uv run python -m compileall app worker.py run.py` -> success
- `cd frontend && npm run build` -> success
- targeted synthetic API smoke -> `historical_quality_ok`
  - created temporary project/simulation/report
  - evaluated it through `POST /api/report/backtest/evaluate-batch`
  - confirmed `GET /api/report/backtest/metrics` returns the new breakdown fields
  - cleaned up the temporary report/project/simulation artifacts afterward

**Result:**
- AgenikPredict now has a real quality-loop operator path rather than only static historical case metadata and raw single-report outcome recording.
- The next step is deployment and live smoke of this new historical-calibration slice.

## 2026-03-18 21:35 - Checkpoint: Historical quality loop push is blocked on Railway web activation

**Context:** The code for the quality-loop slice was already built, locally verified, committed, and pushed to the Railway-linked private GitHub repo. The remaining job was not implementation, but getting that release active on the live web service.

**Work completed:**
- Confirmed GitHub commit `6c2136f478973cd808dbbaa52017e141aa28b80b` exists in the private repo with message:
  - `feat: add historical quality loop dashboard`
- Checked Railway rollout state for both services:
  - `AgenikPredict` latest deployment `72e282da-6cb0-4a10-bd31-f52b9f053e7f`
  - `AgenikPredictWorker` latest deployment `59e9f39d-3bd1-484d-a843-7a6558573bc0`
- Verified public production remained healthy:
  - `GET https://app.agenikpredict.com/health` -> `200`
  - web still serves the previous healthy release
- Verified the new API shape is still not live:
  - `GET /api/report/backtest/metrics` still returns only `dataset`, `items`, and `overall`
- Triggered a manual web redeploy to separate code issues from platform rollout issues:
  - `railway redeploy -s AgenikPredict -y --json`
  - created deployment `9456bd04-74bf-47d7-a4d6-e569352a9ce7`

**Key finding:**
- The manual web redeploy reproduced the same failure mode as the GitHub auto-deploy:
  - latest deployment stays `BUILDING`
  - Railway state marks it with `deploymentStopped=true`
  - previous successful deployment `6ae30d35-50d8-4f0a-b1a6-64f96bacc0d7` continues serving live traffic

**Result:**
- The blocker is currently Railway web activation/orchestration, not the application code for the quality loop.
- Production remains safe, but the new historical-calibration slice is still not active on public web.

## 2026-03-18 21:49 - Checkpoint: Fresh web canary reproduced the same Railway activation stall

**Context:** After the main `AgenikPredict` service reproduced the same stuck `BUILDING` state on both GitHub auto-deploy and manual redeploy, the next question was whether the problem was tied to that service slot specifically or to Railway rollout inside this project more broadly.

**Work completed:**
- Created a fresh web service:
  - `AgenikPredictWebCanary`
- Linked it to the same private GitHub repo:
  - `alexprime1889-prog/codex-agenic-predict-private`
- Copied the non-Railway-managed environment variables from the main web service into the canary service
- Confirmed Railway assigned the canary its own generated domain and internal service identity
- Observed its first deployment:
  - `82d50caa-7107-4a04-8563-1b2c983336d4`
  - commit `6c2136f478973cd808dbbaa52017e141aa28b80b`

**Key finding:**
- The brand-new web canary entered the same stuck state:
  - `status = BUILDING`
  - repeated polling kept it in `BUILDING`
- This makes the blocker much less likely to be tied to the original `AgenikPredict` service slot itself.

**Result:**
- The rollout problem is now strongly evidenced as a Railway project-level web activation/orchestration issue rather than an application-code failure or a single-service corruption.
- Current public production remains safe on the previous healthy release, but the historical quality-loop release still is not live.

## 2026-03-18 22:04 - Checkpoint: Web runtime image split to remove simulation-only heavy deps

**Context:** The Railway evidence narrowed the stall to the build/activation path itself. The new builds on commit `6c2136f` showed the correct new frontend assets, but they never reached final `Build time` / `Healthcheck` lines and repeatedly stalled after the registry-auth phase. The biggest structural suspect left was the universal production image still carrying the full OASIS simulation stack into every web deployment.

**Work completed:**
- Moved simulation-only dependencies out of the base backend runtime:
  - `camel-oasis`
  - `camel-ai`
- Added a new optional dependency group:
  - `simulation`
- Updated `Dockerfile.production` so build-time `SERVICE_ROLE` decides dependency installation:
  - web services: `uv sync --frozen --no-dev`
  - worker services: `uv sync --frozen --no-dev --extra simulation`
- Regenerated `backend/uv.lock`

**Verification:**
- `cd backend && uv lock` -> success
- Base web environment:
  - `cd backend && uv sync --frozen --no-dev` -> success
  - `cd backend && env JWT_SECRET=test-secret TASK_EXECUTION_MODE=inline ARTIFACT_STORAGE_MODE=local uv run python -c "from app import create_app; create_app(); print('web_boot_ok')"` -> `web_boot_ok`
- Worker simulation environment:
  - `cd backend && uv sync --frozen --no-dev --extra simulation` -> success
  - `cd backend && env JWT_SECRET=test-secret TASK_EXECUTION_MODE=worker ARTIFACT_STORAGE_MODE=local uv run python - <<'PY' ...` -> `simulation_manager_ok True`
  - `cd backend && env JWT_SECRET=test-secret TASK_EXECUTION_MODE=worker ARTIFACT_STORAGE_MODE=local uv run python -m compileall app worker.py run.py` -> success

**Result:**
- The repository now supports a significantly lighter web runtime image while preserving the worker simulation stack.
- The next live step is to push this split-dependency fix and test it against `AgenikPredictWebCanary` before touching public traffic.

## 2026-03-18 22:18 - Checkpoint: Split-deps fix recovered Railway web rollout and made quality loop live

**Context:** The earlier quality-loop release was blocked at Railway web activation even after repeated redeploy attempts and a fresh canary service. The working hypothesis was that the universal production image was too heavy for reliable web rollout because it still dragged the full OASIS simulation stack into web services.

**Work completed:**
- Synced the split-dependency fix to the private GitHub repo
- Pushed:
  - commit `201e0459c6670b00dfb9d39e6f74f52f8e02a655`
  - message: `build: split web and simulation dependencies`
- Observed new Railway deployments:
  - `AgenikPredictWebCanary` -> `3298eb95-31ff-4218-b578-af57bf59f45c`
  - `AgenikPredict` -> `1958448b-1fa3-4151-9278-7b8407faaf83`
- Both web services moved beyond the previous stuck `BUILDING` behavior and reached `SUCCESS` with image digests.

**Verification:**
- Public production:
  - `GET https://app.agenikpredict.com/health` -> `200`
  - `GET /api/report/backtest/metrics` now returns the expanded quality-loop fields:
    - `by_domain`
    - `by_horizon`
    - `by_scenario`
    - `calibration_buckets`
    - `recent_evaluations`
- Canary production:
  - `GET https://agenikpredictwebcanary-production.up.railway.app/health` -> `200`
  - `GET /api/report/backtest/metrics` returns the same expanded shape

**Important note:**
- `AgenikPredictWorker` on the same commit was still in `BUILDING` at the moment of this checkpoint, but the active worker path was already healthy from the previous deployment.
- The user-facing and operator-facing blocker was the web rollout, and that blocker is now resolved.

**Result:**
- The historical quality loop is live on public production.
- The root cause was effectively mitigated by separating simulation-only heavy dependencies from the base web runtime image.

## 2026-03-18 21:41 - Checkpoint: Active multilingual UI tail cleaned and legacy CJK parser artifacts removed

**Context:** The remaining user-facing roughness was no longer in infrastructure. It was in the active process/report UI path: hardcoded English runtime logs, report tool-card labels, locale-insensitive time formatting, and a lingering legacy parser tail carrying old `【...】` / fullwidth punctuation markers.

**Work completed:**
- Localized active runtime logs in:
  - `frontend/src/views/MainView.vue`
  - `frontend/src/components/Step2EnvSetup.vue`
- Localized the visible report workflow/tool-card/timeline copy in:
  - `frontend/src/components/Step4Report.vue`
- Switched active timestamp formatting to locale-aware `Intl.DateTimeFormat`
- Added new i18n keysets to:
  - `frontend/src/i18n/locales/en.json`
  - `frontend/src/i18n/locales/ru.json`
- Normalized legacy report parser markers to keep backward compatibility while removing active-code CJK literals
- Replaced Chinese comments in:
  - `backend/requirements.txt`

**Verification:**
- Active-code CJK grep:
  - `rg -n --pcre2 "[\\p{Han}\\p{Hiragana}\\p{Katakana}]" frontend/src/views/MainView.vue frontend/src/components/Step2EnvSetup.vue frontend/src/components/Step4Report.vue backend/requirements.txt` -> no matches
- Locale key parity:
  - `node - <<'NODE' ... prefixes = ['theme.', 'mainView.logs.', 'step2.logs.', 'reportUi.'] ...` -> `missingInRu=0`, `missingInEn=0`
- Frontend:
  - `cd frontend && npm run build` -> success
- Backend:
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success

**Result:**
- The active process/report path is materially quieter and more language-consistent.
- The remaining multilingual work is now product/UI strategy, not active hardcoded UI noise.

## 2026-03-18 - Analysis Mode Strategy And API Prioritization

**Context:** The next user decision is not another infrastructure patch. It is product architecture: whether AgenikPredict should keep one monolithic analysis path or split into a fast operational mode and a deeper global mode, while expanding external evidence integrations without turning the system into a slow, noisy connector farm.

**Work completed:**
- Audited the current analysis/report architecture
- Verified that `ReportAgent` already supports a mixed evidence model:
  - graph-native tools: `quick_search`, `panorama_search`, `insight_forge`, `interview_agents`
  - lightweight live tools: `live_news_brief`, `live_market_snapshot`
- Verified that language propagation already exists end-to-end:
  - frontend sends `Accept-Language`
  - backend resolves/persists `language_used`
- Verified that the quality loop is already in place and can absorb richer evidence:
  - prediction ledger
  - historical backtest dataset
  - cohort metrics endpoint
- Checked official source options for next API priorities:
  - SEC EDGAR
  - OpenFIGI
  - Twelve Data
  - FDIC bank data / BankFind references

**Conclusion:**
- The platform is already structurally ready for two modes:
  - `Quick Analysis` for fast, decision-support output
  - `Global Analysis` for slower, more defensible, evidence-heavy output
- The correct API strategy is not “connect everything.”
- The correct API strategy is:
  1. define an evidence-provider abstraction
  2. attach providers by domain and mode
  3. start with finance/regulatory sources that materially improve report quality

**Recommended next implementation direction:**
- add `analysis_mode=quick|global`
- add provider registry / evidence bundle abstraction
- prioritize finance/regulatory connectors before broad connector sprawl

## 2026-03-18 - Social Evidence, Provenance, And Agent-Level Explainability

**Context:** The user clarified that X/Twitter and Reddit matter for market perception, that reports must visibly show the basis of their claims, and that the client should be able to ask each agent to explain its own opinion.

**Work completed:**
- Verified the current product already has building blocks for agent-level questioning:
  - simulation interview endpoints
  - batch agent interviews
  - report conversation flow
  - detailed agent logs
- Verified official platform constraints at a high level for:
  - X API search access
  - Reddit Developer / Data API terms and capabilities
- Mapped the next architecture layer:
  - `SocialEvidenceLayer`
  - `SourceManifest` / provenance model
  - `Ask this agent` UX and response schema

**Conclusion:**
- X and Reddit should not be treated as generic “extra news.”
- They should be a separate evidence class focused on sentiment, narrative spread, retail reaction, and discourse divergence.
- Every report needs an auditable basis trail.
- Every agent-facing view should support opinion explanation with evidence references and uncertainty, not just a generated answer.

**Recommended next implementation direction:**
- add `SocialEvidenceProvider` with provider-specific licensing/rate-limit guards
- add report-level provenance and claim-to-source linkage
- expose `Ask this agent` directly from node/card UI

## 2026-03-18 - Deep Research On Perplexity-As-Primary Provider

**Context:** The user asked for a chief-advisor recommendation on whether AgenikPredict could rely mainly on a single provider such as Perplexity Search, while also needing financial precision, news, historical context, social discourse, provenance, and agent-level explanation.

**Work completed:**
- Ran a system-level architecture review
- Ran a codebase review on current report/evidence/interview/language capabilities
- Ran an independent reviewer pass focused on practical risk and smallest viable next step
- Checked official documentation for:
  - Perplexity Search / Sonar
  - X Search Posts
  - Reddit Developer / Data API terms

**Decision:**
- Do not use Perplexity as the sole primary evidence layer.
- Use a minimal layered architecture:
  - Perplexity = discovery / synthesis
  - Market provider = canonical financial facts / history
  - Social layer = X / Reddit where licensing allows
  - Provenance = mandatory internal schema

**Why:**
- Single-provider concentration is too risky for institutional use.
- A general search provider is not the canonical source for structured market history or backtest-grade evidence.
- Provider-level citations are not enough for claim-level explainability.
- The current AgenikPredict codebase already structurally points toward a layered model.

**Recommended smallest viable next step:**
- ship `analysis_mode=quick|global`
- add `PerplexityProvider` + canonical market provider
- add thin `SourceManifest`
- then build `Why do we think this?` and `Ask this agent` on top

## 2026-03-18 - Review Of External Cloud Code Audit

**Context:** The user supplied a `Cloud Code` audit and asked for a non-biased evaluation of its adequacy and correctness.

**Assessment:**
- The architectural direction in the audit is often reasonable.
- The factual repository audit is partially stale and appears to target another snapshot/repo path.

**Verified outdated claims in the current repo:**
- `live_evidence.py` does already exist
- `ReportAgent` already has live evidence tools
- `custom_persona` and `report_variables` are already sent from the frontend
- task persistence is no longer memory-only; DB-backed task storage exists
- `/api/auth/billing-status` already exists
- `/api/billing/status` already exists
- `BillingBadge` no longer depends on the missing auth endpoint

**Verified still-valid concerns:**
- `analysis_mode` is still missing
- config limits for report-agent tool/reflection counts are still not wired into the agent
- no Perplexity/FRED provider integration yet
- no real provenance / claim-to-source model yet

**Decision:**
- Treat the `Cloud Code` memo as a useful directional input, not as the current source of truth.
- Keep its valid recommendations.
- Discard its already-obsolete remediation items.

## 2026-03-18 - Review Of Corrected Current-State Memo

**Context:** The user supplied a corrected memo aligned to the real `/Projects/AgenikPredict` repo and asked for an unbiased judgment of its adequacy.

**Assessment:**
- This corrected memo is materially better and mostly accurate.
- It is close to an execution-grade plan.
- It still needs several implementation corrections.

**What I agree with:**
- wire config limits into `ReportAgent`
- add `analysis_mode`
- add Perplexity as discovery layer
- add provenance/source manifest

**Important corrections:**
- `analysis_mode` must flow through task metadata / worker path too, not just direct API instantiation
- a fake `DEFAULT_SECTION_COUNT` field will not control the current outline planner; section count must be enforced in the outline prompt or post-parse
- `SourceManifest` should be persisted as data, not only appended as markdown footer
- the plan still needs an explicit explainability item: `Why do we think this?` and `Ask this agent`

**Decision:**
- Use this corrected memo as the basis for the final implementation plan.
- Add the missing explainability item and fix the section-count / worker-path details before execution.

## 2026-03-19 - Start: Overnight Evidence Upgrade

**Agent/Tool:** Codex

**Started:**
- implementing the bounded overnight evidence upgrade for report generation
- wiring config-driven report-agent limits into runtime
- adding `analysis_mode=quick|global` across frontend, API, task metadata, worker path, and report metadata
- adding `SourceManifest` persistence, optional Perplexity discovery, and explainability MVP

**Not finished:**
- backend report/runtime changes
- frontend mode selector and payload propagation
- targeted backend tests
- required compile/build verification
- docs close-out and handoff

**Known issues:**
- target files are already dirty in the worktree, so edits must preserve unrelated user changes
- no existing backend test scaffold for this report slice

**Files changed:**
| File | Change |
|------|--------|
| (pending) | (pending) |

**Next steps:**
- implement backend contract and runtime changes first
- add frontend propagation on top of the backend contract
- add targeted tests and run required verification commands

## 2026-03-19 - Complete: Overnight Evidence Upgrade

**Agent/Tool:** Codex

**Completed:**
- wired `Config.REPORT_AGENT_MAX_TOOL_CALLS` and `Config.REPORT_AGENT_MAX_REFLECTION_ROUNDS` into `ReportAgent` runtime behavior
- added `analysis_mode=quick|global` through report API, task metadata, worker path, report metadata, and frontend report settings flow
- added structured provenance via `SourceManifest` data model plus `source_manifest.json` persistence and `source_manifest_summary` in `meta.json`
- added optional `PerplexityProvider` as discovery-only `web_search` for global mode with graceful no-key / malformed-payload fallback
- added explainability MVP in report metadata/API: `why_this_conclusion`, `basis_summary`, `source_attribution`
- added targeted backend tests covering limits, routing, manifest persistence, Perplexity fallback, and generation without provider key

**Verification:**
- `cd backend && uv run python -m compileall app worker.py run.py tests/test_report_upgrade.py` ✅
- `cd backend && uv run python -m compileall app worker.py run.py` ✅
- `cd backend && uv run pytest -q tests/test_report_upgrade.py` ✅ `9 passed`
- `cd frontend && npm run build` ✅

**Files changed:**
| File | Change |
|------|--------|
| `backend/app/config.py` | added `PERPLEXITY_API_KEY` |
| `backend/app/api/report.py` | added `analysis_mode` parsing/validation, reuse/conflict handling, metadata/API propagation |
| `backend/app/services/report_agent.py` | wired config limits, quick/global tool policy, source manifest/explainability generation, persistence hooks |
| `backend/app/services/task_handlers.py` | propagated `analysis_mode` through worker path |
| `backend/app/services/perplexity_provider.py` | new discovery-only Perplexity search provider |
| `backend/app/services/source_manifest.py` | new provenance data model |
| `backend/tests/test_report_upgrade.py` | targeted backend test coverage |
| `frontend/src/components/GraphPanel.vue` | added compact quick/global selector in report settings |
| `frontend/src/views/SimulationRunView.vue` | preserved `analysis_mode` in shared report config state |
| `frontend/src/components/Step3Simulation.vue` | sent `analysis_mode` in report generation payload |
| `frontend/src/api/report.js` | documented expanded request payload |
| `frontend/src/i18n/locales/*.json` | added minimal labels for analysis mode selector |

**Blocked:**
- no blocking issues after local verification

**Next step:**
- if the next slice continues this work, expose `source_manifest_summary` and explainability blocks in the report UI and add follow-up tests around report retrieval for multiple completed variants per simulation

## 2026-03-19 - Deploy Hardening Follow-up

**Agent/Tool:** Codex

**Additional hardening completed:**
- added deploy runbooks:
  - `scripts/pre_deploy_evidence_slice.sh`
  - `scripts/post_deploy_evidence_smoke.sh`
- updated `.env.example` so the new deploy-audit keys exist:
  - `PERPLEXITY_API_KEY`
  - `REPORT_AGENT_MAX_TOOL_CALLS`
  - `REPORT_AGENT_MAX_REFLECTION_ROUNDS`
- normalized `POST /api/report/generate/status` task-path responses to include top-level:
  - `language_used`
  - `analysis_mode`
  - `report_id`
  - `simulation_id`
- re-ran backend verification after the status-shape change:
  - `compileall` ✅
  - `pytest tests/test_report_upgrade.py` ✅ `9 passed`
- exercised the pre-deploy script locally without push; it completed through Railway state inspection and confirmed the current audit path is executable

**Non-blocking observations:**
- the frontend production build still emits a large bundle-size warning; this is not a blocker for the evidence deploy slice
- some internal read paths still default to “latest report by simulation” without explicit `language_used` + `analysis_mode`; acceptable for tonight, but worth tightening before deeper UI surfacing of multiple variants

**Next step:**
- use the new pre/post deploy scripts during the real rollout window, then treat UI surfacing of provenance/explainability and multi-variant retrieval cleanup as the next follow-up slice

## 2026-03-19 - Verification: Evidence Slice Complete, Deploy Session Reframed

**Agent/Tool:** Codex

**Completed in this checkpoint:**
- independently verified that the overnight evidence slice is already implemented in the current working tree
- confirmed the presence of:
  - config-driven report-agent limits
  - `analysis_mode=quick|global`
  - `PerplexityProvider`
  - `SourceManifest` persistence
  - explainability fields in report metadata/API
- re-ran local verification:
  - `cd backend && uv run python -m compileall app worker.py run.py`
  - `cd backend && uv run pytest tests/test_report_upgrade.py`
  - `cd frontend && npm run build`
- compared these results against the proposed 6-hour continuation plan and determined that the remaining work is primarily deploy-oriented rather than implementation-oriented

**Verified Evidence**
```bash
$ cd backend && uv run python -m compileall app worker.py run.py
# success
```

```bash
$ cd backend && uv run pytest tests/test_report_upgrade.py
# 9 passed
```

```bash
$ cd frontend && npm run build
# success
```

```bash
$ rg -n "analysis_mode|PerplexityProvider|SourceManifest|why_this_conclusion|basis_summary|source_attribution|source_manifest_summary" ...
# matches found across report_agent.py, report.py, task_handlers.py, config.py, frontend report settings flow, and targeted backend tests
```

**Assessment:**
- The current implementation matches the approved overnight brief.
- The proposed next 6-hour session should not spend time rebuilding this slice.
- The correct continuation is:
  - env/config rollout
  - web/worker parity validation
  - artifact persistence checks on deployed storage
  - staging smoke
  - rollback preparation
  - production rollout or explicit no-go

**Remaining gap before deploy work starts:**
- `.env.example` does not yet document `PERPLEXITY_API_KEY`, `REPORT_AGENT_MAX_TOOL_CALLS`, or `REPORT_AGENT_MAX_REFLECTION_ROUNDS`

**Next step:**
- run a deploy-focused 6-hour continuation session for the already-implemented evidence slice, starting with env/default documentation and prod-like verification rather than new feature implementation

### Item 86

- Task: Harden the deploy path for the overnight evidence slice and close rollout-sensitive inconsistencies before production validation
- Work performed:
  - added deploy runbooks:
    - `scripts/pre_deploy_evidence_slice.sh`
    - `scripts/post_deploy_evidence_smoke.sh`
  - updated `.env.example` to document:
    - `PERPLEXITY_API_KEY`
    - `REPORT_AGENT_MAX_TOOL_CALLS`
    - `REPORT_AGENT_MAX_REFLECTION_ROUNDS`
  - fixed a status-shape inconsistency in `POST /api/report/generate/status` so the active-task branch returns top-level `language_used`, `analysis_mode`, `report_id`, and `simulation_id`
  - hardened frontend report generation so the main Step 3 path no longer forces regeneration by default, allowing the new `language_used + analysis_mode` reuse logic to actually work
  - tightened quick-mode runtime policy by blocking legacy heavy-tool aliases (`get_graph_statistics`, `get_entity_summary`, `get_entities_by_type`, `get_simulation_context`) in quick mode
  - hardened retrieval/filtering behavior:
    - `generate/status` now defaults simulation-only lookups to the resolved request language plus `global`
    - `/api/report/by-simulation/<simulation_id>`, `/api/report/by-simulation/<simulation_id>/predictions`, and `/api/report/check/<simulation_id>` now validate `analysis_mode` when provided and can filter by `language` / `analysis_mode`
  - strengthened the post-deploy smoke script:
    - fail-fast HTTP requests via `curl --fail-with-body`
    - strict JSON parsing instead of falling back to raw text
    - polling until report completion before metadata verification
    - explicit conflict-path handling with HTTP status capture
  - added an observability checklist to the pre-deploy script for post-rollout log inspection
  - extended backend tests to cover:
    - strict quick-mode legacy alias rejection
    - `generate/status` defaulting to request language + global mode when queried by simulation only
- Verification:
  - `cd backend && uv run python -m compileall app worker.py run.py`
  - `cd backend && uv run pytest -q tests/test_report_upgrade.py` -> `10 passed`
  - `cd frontend && npm run build`
  - `bash -n scripts/pre_deploy_evidence_slice.sh scripts/post_deploy_evidence_smoke.sh`
  - `./scripts/pre_deploy_evidence_slice.sh`
- Notes:
  - frontend build remains green but still emits the existing Vite warnings about large chunks and mixed dynamic/static import of `pendingUpload.js`
  - multi-variant report retrieval is now safer on the main status/check paths, but report chat is still simulation-scoped and would need a later variant-selection pass if chat must become mode-aware
- Next step:
  - use the pre/post deploy scripts for staging or canary rollout, then surface `source_manifest_summary` and `explainability` in the report UI

### Item 87

- Task: Build a clean deploy worktree for the evidence slice and verify that the isolated candidate, not the dirty main worktree, passes pre-deploy checks
- Work performed:
  - created a clean deploy worktree at `/Users/alexanderivenski/Projects/AgenikPredict-deploy` on branch `codex/deploy-evidence-slice`
  - discovered and fixed a runbook bug: both deploy scripts were defaulting to the original repo path instead of resolving the repo root from the script location, which meant they audited the wrong tree when run from a worktree
  - patched both scripts to derive `REPO` from `$(dirname "${BASH_SOURCE[0]}")/..`
  - used the clean worktree run to discover missing runtime dependencies that were not in the initial evidence-slice copy list:
    - backend support/runtime files required for isolated imports and worker path:
      - `backend/app/models/task.py`
      - `backend/app/models/user.py`
      - `backend/app/models/prediction_ledger.py`
      - `backend/app/models/historical_backtest.py`
      - `backend/app/services/artifact_store.py`
      - `backend/app/services/live_evidence.py`
      - `backend/app/services/task_worker.py`
      - `backend/app/utils/locale.py`
      - `backend/app/utils/llm_client.py`
      - `backend/app/services/zep_tools.py`
      - `backend/worker.py`
      - `backend/pyproject.toml`
      - `backend/requirements.txt`
      - `backend/uv.lock`
      - `backend/app/data/historical_backtest_cases.json`
    - frontend support files required for the current Step 3/report settings path to build cleanly:
      - `frontend/src/api/billing.js`
      - `frontend/src/api/index.js`
      - `frontend/src/store/auth.js`
      - locale files under `frontend/src/i18n/locales/`
  - hardened the backend test fixture so `tests/test_report_upgrade.py` initializes `PredictionLedgerManager` explicitly; this removed a hidden dependency on an already-existing local SQLite table and made the test reproducible in a fresh worktree
  - re-synced the expanded dependency set into the deploy worktree and reran pre-deploy successfully there
- Verification:
  - `cd /Users/alexanderivenski/Projects/AgenikPredict-deploy/frontend && npm ci`
  - `cd /Users/alexanderivenski/Projects/AgenikPredict-deploy && bash scripts/pre_deploy_evidence_slice.sh` -> success
  - pre-deploy in the clean worktree now passes:
    - backend compile
    - backend targeted tests (`10 passed`)
    - frontend build
- Notes:
  - the original minimal copy list was insufficient for an isolated deploy candidate; clean-worktree validation proved necessary
  - canary/prod deploy should now proceed from the clean worktree branch, not from the dirty main worktree
- Next step:
  - stage and commit the isolated deploy candidate in `/Users/alexanderivenski/Projects/AgenikPredict-deploy`, push `codex/deploy-evidence-slice`, then run canary smoke with `SIM_ID_QUICK` and `SIM_ID_GLOBAL`

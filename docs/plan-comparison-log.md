# Plan Comparison Log

Дата: 2026-03-17
Проект: `AgenikPredict`
Задача: production-readiness audit + implementation plan for higher-fidelity simulation

## Entries

### Item 1

- Plan item: Inspect persona prompts, agent generation logic, and simulation scale limits
- Work done: Проверены `oasis_profile_generator.py`, `simulation_config_generator.py`, `run_parallel_simulation.py`, `run_twitter_simulation.py`, `run_reddit_simulation.py`, UI claims в `en.json`, а также связка `simulation_manager.py`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/services/oasis_profile_generator.py:671-771`
  - `backend/app/services/oasis_profile_generator.py:850-883`
  - `backend/app/services/simulation_config_generator.py:542-650`
  - `backend/app/services/simulation_config_generator.py:818-993`
  - `backend/scripts/run_parallel_simulation.py:1040-1090`
  - `frontend/src/i18n/locales/en.json:8-18`
- Next action: Зафиксировать выводы в audit document.

### Item 2

- Plan item: Audit production readiness, external dependencies, and market-data integration
- Work done: Проверены auth, billing, README, package/runtime requirements, file ingestion deps и market data enrichment.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/api/auth.py:152-161`
  - `backend/app/api/auth.py:182-195`
  - `backend/app/models/user.py:202-217`
  - `backend/app/models/user.py:249-260`
  - `frontend/src/api/billing.js:1-10`
  - `backend/app/api/billing.py:17-100`
  - `backend/app/utils/file_parser.py:257-357`
  - `backend/app/services/market_data.py:19-170`
  - `backend/app/api/graph.py:265-273`
  - `README.md:29-42`
- Next action: Свести production blockers и runtime gaps в приоритетный список.

### Item 3

- Plan item: Design implementation plan to improve realism, reproducibility, and operational reliability
- Work done: Сформирована phased roadmap: stabilization, determinism, market-aware modeling, calibration/backtesting, report integrity.
- Comparison status: `AHEAD`
- Evidence:
  - выводы основаны на inspection evidence из items 1-2;
  - подтверждено отсутствие backtesting/calibration слоя и высокая доля uncontrolled randomness.
- Next action: Включить roadmap и exit criteria в итоговый документ.

### Item 4

- Plan item: Write audit document in the repository and summarize key conclusions
- Work done: Создан отдельный audit document с executive summary, risk matrix, prompt/persona audit, scale-limit analysis, market integration audit и phased implementation plan.
- Comparison status: `ON_TRACK`
- Evidence:
  - `docs/agenikpredict_production_and_fidelity_audit.md`
- Next action: Сообщить пользователю путь к документу и коротко вынести главные выводы.

### Item 5

- Plan item: Fix critical backend/frontend contract bugs blocking auth, billing, ontology submission, and report status handling
- Work done: Исправлены magic-link auth return-value bugs, добавлены совместимые billing status endpoints, восстановлены frontend billing helpers, добавлен `/account` route, исправлен `BillingBadge`, включен passthrough для `urls` и `enrich_with_market_data`, добавлен URL-only ontology path и placeholder report persistence.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/api/auth.py`
  - `backend/app/api/billing.py`
  - `backend/app/api/graph.py`
  - `backend/app/api/report.py`
  - `backend/app/models/user.py`
  - `frontend/src/api/billing.js`
  - `frontend/src/components/BillingBadge.vue`
  - `frontend/src/router/index.js`
  - `frontend/src/views/MainView.vue`
- Next action: Прогнать локальную и продовую верификацию после завершения Railway deployment.

### Item 6

- Plan item: Harden processing reliability for ontology/report generation and production runtime configuration
- Work done: В ontology path переключен JSON LLM call на fallback-aware client; в report generation сохранение статуса `generating` и placeholder metadata делается раньше, чтобы frontend не гонялся за еще не созданным report artifact.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/services/ontology_generator.py`
  - `backend/app/services/report_agent.py`
  - `backend/app/api/report.py`
  - локальная проверка `uv run python` через Flask test client (URL-only ontology = `200`, placeholder report status = `pending`)
- Next action: Подтвердить live behavior на Railway после завершения deploy.

### Item 7

- Plan item: Run local verification for build and backend runtime, then assess Railway deployment actions
- Work done: Подтверждены `npm run build`, backend `create_app()` import, demo auth flow, оба billing status endpoints, magic-link verify, idempotency helper, URL-only ontology contract и placeholder report creation. Запущен Railway deployment `1d930992-4c7d-405d-83c8-c76d6ef798f5`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `npm run build` -> success
  - `uv run python -c "from app import create_app; app=create_app(); print('routes', len(app.url_map._rules))"` -> success
  - `uv run python` verification snippets executed on `2026-03-17`
  - `railway deployment list -s AgenikPredict` -> latest deployment `1d930992-4c7d-405d-83c8-c76d6ef798f5 | BUILDING`
- Next action: Дождаться окончания билда, затем выполнить live smoke test against `app.agenikpredict.com`.

### Item 8

- Plan item: Harden processing reliability for ontology/report generation and production runtime configuration
- Work done: Устранен reviewer-found gap по atomic Stripe crediting; добавлен production fail-fast для нестабильного `JWT_SECRET`; backend подготовлен к gunicorn runtime (`run:app` + `Dockerfile.production` + `gunicorn` в lockfile). Отправлен второй Railway deployment `159eddb4-3341-4f6c-a242-65b9ebd6e98f`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/models/user.py`
  - `backend/app/api/billing.py`
  - `backend/app/config.py`
  - `backend/run.py`
  - `backend/pyproject.toml`
  - `backend/uv.lock`
  - `Dockerfile.production`
  - `uv run gunicorn --check-config run:app` -> success
  - `railway deployment list -s AgenikPredict` -> latest deployment `159eddb4-3341-4f6c-a242-65b9ebd6e98f | BUILDING`
- Next action: Дождаться завершения актуального deploy и зафиксировать live smoke result или build failure reason.

### Item 5

- Plan item: Re-audit current runtime state for end-to-end production processing on Railway
- Work done: Проверены текущие Railway-логи, runtime entrypoint, API-контракты фронта/бэка, статус билда и ключевые async-paths (ontology -> simulation -> report).
- Comparison status: `ON_TRACK`
- Evidence:
  - Railway logs (2026-03-17): `POST /api/graph/ontology/generate` returns `402` after `=== Starting ontology generation ===`
  - `backend/app/api/graph.py:181`
  - `backend/run.py:43`
  - `Dockerfile.production:60`
  - `frontend/src/views/MainView.vue:231`
  - `frontend/src/store/pendingUpload.js:16`
  - `frontend/src/api/report.js:15`
  - `backend/app/api/report.py:274`
  - `backend/app/api/report.py:251`
  - `backend/app/services/simulation_runner.py:437`
- Next action: Выдать пользователю приоритизированный stabilization-audit с production implications и порядком внедрения.

### Item 9

- Plan item: Harden live processing reliability and close release-blocking ownership/billing gaps before re-running production smoke
- Work done: Добавлен robust fallback chain в `LLMClient` для ontology JSON-path; report generation переведен на reservation-based billing вместо late deduct; убран неверный billing gate из report chat; закрыты ownership leaks в report/simulation endpoints; создан verification script и прогнан локальный regression pass. Также создан и примонтирован Railway volume `agenikpredict-volume` на `/app/backend/uploads`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/utils/llm_client.py`
  - `backend/app/api/report.py`
  - `backend/app/api/simulation.py`
  - `backend/app/models/user.py`
  - `scripts/verify_production_fixes.sh`
  - `railway volume list --json` -> volume `7daea671-804b-444a-8de1-76dea8ed83cc`, mount `/app/backend/uploads`
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `npm run build` -> success
  - `cd backend && uv run python -m compileall app && uv run gunicorn --check-config run:app` -> success
- Next action: Подтвердить, что новый Railway deployment активен и повторный live smoke проходит на production.

### Item 10

- Plan item: Re-run full live production smoke after deployment hardening and fix any regressions found in the hot path
- Work done: Выполнен live smoke после deploy `dbcd8206-e513-4483-a13c-153c48bfd105`; пойман регресс в `prepare_simulation` (`manager` reference lost), исправлен отдельным follow-up deploy `e4b0af76-98ee-4d2c-8655-59442922e687`. После этого на live production повторно пройден полный path: demo auth -> ontology generate -> graph build -> simulation create -> prepare -> start (`max_rounds=1`) -> run-status `completed` -> report generate -> report progress `planning`.
- Comparison status: `ON_TRACK`
- Evidence:
  - Railway logs at `2026-03-18 02:13-02:15 UTC` show:
    - ontology fallback from `glm-5-turbo` to `anthropic/claude-sonnet-4.6`
    - graph build complete for `proj_551ec0f0de4c`
    - simulation preparation complete for `sim_397537230812`
    - simulation completed for `sim_397537230812`
    - report started for `report_df6e603b6cf1`
  - `railway deployment list -s AgenikPredict --json` -> deployment `e4b0af76-98ee-4d2c-8655-59442922e687 | SUCCESS`
  - Live smoke identifiers:
    - `project_id=proj_551ec0f0de4c`
    - `graph_id=agenikpredict_b1267e60cb314326`
    - `simulation_id=sim_397537230812`
    - `report_id=report_df6e603b6cf1`
  - Live smoke terminal output:
  - `run_done {"runner_status": "completed", "current_round": 1, "total_actions_count": 10}`
  - `report_progress {"status": "planning", "progress": 5, ...}`
- Next action: Зафиксировать residual risks (process-local tasks, graph task ownership, long-running deploy drains) и выдать пользователю итоговый production status.

### Item 11

- Plan item: Build an exact UI source-of-truth map across production, current dirty main workspace, and the alternate `claude/funny-villani` worktree
- Work done: Проверены production frontend asset hashes, локальная сборка текущего `main`, наличие второго worktree, diff against `origin/main`, buildability of `claude/funny-villani`, и ключевые file-level overlaps/divergences (`Home.vue`, `Step3Simulation.vue`, `AdminView.vue`, `AccountView.vue`, `billing.js`, admin/billing APIs). Отдельный документ с картой создан.
- Comparison status: `ON_TRACK`
- Evidence:
  - `https://app.agenikpredict.com` -> `/assets/index-CkYmH1Ba.js`, `/assets/index-DyQi3PGL.css`
  - local current-main build -> same asset names and exact SHA-256 matches
  - `git worktree list` -> separate worktree `claude/funny-villani` at commit `7de8790`
  - `cd /Users/alexanderivenski/projects/AgenikPredict/.claude/worktrees/funny-villani && npm run build` -> fails because `getBillingPrices` is missing from branch `frontend/src/api/billing.js`
  - `docs/ui_source_of_truth_map_2026-03-18.md`
- Next action: Сообщить пользователю, что current production matches current local dirty workspace exactly, and that the perceived “old UI” is caused by multi-source local divergence rather than Railway failing to deploy the frontend.

### Item 12

- Plan item: Convert the strategic production/fidelity plan into a code-focused 7-day execution roadmap with regulatory work explicitly deferred
- Work done: На основе production/fidelity audit, current production status и repo instructions создан отдельный недельный roadmap по дням. Вынесены за скобки legal/regulatory и UI-redesign work; зафиксирована последовательность `durable runtime -> ownership -> observability -> determinism -> market grounding -> hardening`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `docs/7_day_execution_roadmap.md`
  - `docs/agenikpredict_production_and_fidelity_audit.md`
  - `docs/plan-comparison-log.md`
- Next action: Показать пользователю краткую версию roadmap и предложить сразу стартовать с Day 1 implementation block.

### Item 13

- Plan item: Independently review and tighten the 7-day roadmap so it does not miss critical production risks
- Work done: Проведен reviewer-pass по roadmap. По замечаниям пересобрана последовательность: owner-scoping и minimal CI/smoke guardrails перенесены на Day 1, добавлены live migration/cutover strategy для persistent tasks, exactly-once billing semantics для retryable jobs, distributed leases + DLQ/reaper для workers, а calibration day ужат до pilot scope.
- Comparison status: `AHEAD`
- Evidence:
  - `docs/7_day_execution_roadmap.md`
  - reviewer findings against missing billing idempotency / early guardrails / migration plan / worker leases
- Next action: Дать пользователю финальную версию недельного плана и предложить стартовать с Day 1 implementation set.

### Item 14

- Plan item: Execute Day 1 by closing highest-risk ownership leaks, adding minimal CI/smoke guardrails, and writing the task-store cutover plan
- Work done: Добавлены owner checks для `graph task/data/delete`, simulation graph-driven entity/profile endpoints, report task status и report debug tool endpoints. Новые graph/simulation/report tasks теперь создаются с owner-aware metadata. Добавлен CI workflow с `frontend build`, `backend boot sanity`, `security smoke`, а `verify_production_fixes.sh` расширен новыми access-control assertions. Отдельно зафиксирован cutover plan для перехода на persistent task store.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/api/graph.py`
  - `backend/app/api/simulation.py`
  - `backend/app/api/report.py`
  - `backend/app/models/task.py`
  - `backend/app/models/project.py`
  - `.github/workflows/ci.yml`
  - `scripts/verify_production_fixes.sh`
  - `docs/task_store_cutover_plan.md`
  - `cd backend && uv run python -m compileall app` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `npm run build` -> success
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
- Next action: Start Day 2 persistent task-store implementation with the cutover plan as the migration envelope.

### Item 15

- Plan item: Start Day 2 by implementing a safe initial persistent task store and closing the reviewer-found foreign-graph simulation creation bug
- Work done: Реализован DB-backed `TaskManager` с feature flags `TASK_STORE_MODE=dual` и `TASK_READ_SOURCE=fallback`, автоматической инициализацией таблицы задач на старте, dual-write/fallback-read логикой и persisted cleanup. Дополнительно закрыт P0 в `simulation/create`, где раньше можно было привязать чужой `graph_id` к своему `project_id`. Smoke script расширен проверками на task survival after manager reset и foreign-graph simulation create denial.
- Comparison status: `AHEAD`
- Evidence:
  - `backend/app/config.py`
  - `backend/app/models/task.py`
  - `backend/app/__init__.py`
  - `backend/app/api/simulation.py`
  - `scripts/verify_production_fixes.sh`
  - `docs/task_store_cutover_plan.md`
  - reviewer finding about cross-tenant `graph_id` injection in `simulation/create`
  - `cd backend && uv run python -m compileall app` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
- Next action: Expand restart/redeploy verification around the new persistent task layer and prepare the controlled rollout/deploy step.

### Item 16

- Plan item: Advance Day 3 with claim/lease execution guards, duplicate-trigger dedupe, and lightweight stuck-task reaping before the full worker split
- Work done: В `TaskManager` добавлены persistent execution metadata (`execution_key`, lease timestamps, attempt counters, started/finished timestamps), `claim_task()`/heartbeat semantics и background reaper для abandoned tasks. `graph_build`, `simulation_prepare` и `report_generate` теперь claim'ят задачу перед реальным выполнением и держат lease heartbeat во время работы. Повторные API-trigger'ы по `project_id`/`simulation_id` теперь возвращают активную задачу вместо запуска нового фонового path.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/models/task.py`
  - `backend/app/api/graph.py`
  - `backend/app/api/simulation.py`
  - `backend/app/api/report.py`
  - `backend/app/config.py`
  - `backend/app/__init__.py`
  - `scripts/verify_production_fixes.sh`

### Item 24

- Plan item: Validate a curated high-signal production smoke and close single-platform simulation regressions before moving deeper into scientific-layer work
- Work done: Сконструирован сильный live smoke fixture (`Helios` crisis), который дал реальный graph (`15 nodes / 31 edges`) и `12 qualifying entities`, тем самым отделив input-quality failures от runtime failures. На этом smoke найдены и исправлены два production-важных single-platform дефекта: `_check_simulation_prepared()` требовал `twitter_profiles.csv` даже при `enable_twitter=false`, а `SimulationRunner.start_simulation(platform='reddit'|'twitter')` запускал legacy scripts, несовместимые с монитором `actions.jsonl`. После этого readiness-check сделан platform-aware, а single-platform start переведен на `run_parallel_simulation.py` с `--reddit-only/--twitter-only`. Regression suite расширен readiness- и runner-behavior проверками. Railway deployment `ace15292-8a37-42bc-9638-6ef605c4e3e8` отправлен с финальным hotfix.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/api/simulation.py`
  - `backend/app/services/simulation_runner.py`
  - `scripts/verify_production_fixes.sh`
  - local diagnostic output: `filtered_count=12`, `entity_types=['MediaOutlet','Executive','OnlineCommunity','AdvocacyGroup','InvestmentFirm','GovernmentAgency','UtilityCompany','Person']`
  - `cd backend && uv run python -m py_compile app/api/simulation.py app/services/simulation_runner.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> assertion suite passes
  - `railway up -d -s AgenikPredict -m "fix: single-platform simulation runtime and readiness checks"` -> deployment `ace15292-8a37-42bc-9638-6ef605c4e3e8`
- Next action: Дождаться `SUCCESS` и прогнать live reddit-only smoke на Helios project, затем report generation smoke.
  - `cd backend && uv run python -m compileall app` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
- Next action: Complete independent reviewer pass, then move from web-thread execution to an explicit worker/queue loop with retry policy and exactly-once task boundary semantics.

### Item 17

- Plan item: Reconcile the provided expert scientific-analysis memo with the current production/fidelity roadmap and adjust priority sequencing
- Work done: Сравнен внешний экспертный анализ с уже существующими [production/fidelity audit](/Users/alexanderivenski/Projects/AgenikPredict/docs/agenikpredict_production_and_fidelity_audit.md) и [7-day roadmap](/Users/alexanderivenski/Projects/AgenikPredict/docs/7_day_execution_roadmap.md). Зафиксировано, что экспертный анализ сильнее в четырех продуктовых gaps: `live evidence tools`, `structured probabilities`, `Prediction Ledger`, `parallel scenario modeling`. Также отмечено, что часть его UX/API замечаний устарела для текущего local workspace, а наш runtime-first sequencing остается правильным. Создан отдельный comparison memo с merged priority order.
- Comparison status: `AHEAD`
- Evidence:
  - `docs/expert_analysis_comparison_2026-03-17.md`
  - `docs/7_day_execution_roadmap.md`
  - `docs/agenikpredict_production_and_fidelity_audit.md`
  - `frontend/src/router/index.js`
  - `frontend/src/api/billing.js`
  - `backend/app/api/billing.py`
  - `backend/app/api/auth.py`
- Next action: Keep the current runtime-hardening sequence, then elevate `ReportAgent live evidence + structured probabilities + Prediction Ledger` as the immediate post-runtime product-science phase.

### Item 18

- Plan item: Turn the merged plan into a concrete Day 3.5 / Day 4 execution slice and begin the worker split
- Work done: Создан execution-block документ для `Day 3.5 / Day 4`, добавлены `TASK_EXECUTION_MODE`, worker poll/batch flags, `claim_next_task()` в `TaskManager`, reusable handlers в `backend/app/services/task_handlers.py`, worker loop в `backend/app/services/task_worker.py` и отдельный entrypoint `backend/worker.py`. API task paths переведены на `enqueue + dispatch-by-mode`. Отдельно подтвержден `worker`-mode execution для `report_generate`, а `graph_build` и `simulation_prepare` прошли handler-level smoke после выноса логики из API closures.
- Comparison status: `ON_TRACK`
- Evidence:
  - `docs/day_3_5_day_4_execution_block.md`
  - `backend/app/config.py`
  - `backend/app/models/task.py`
  - `backend/app/services/task_handlers.py`
  - `backend/app/services/task_worker.py`
  - `backend/worker.py`
  - `backend/app/api/graph.py`
  - `backend/app/api/simulation.py`
  - `backend/app/api/report.py`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - worker-mode report smoke -> `worker_mode_report_ok`
  - graph handler smoke -> `graph_handler_ok`
  - simulation handler smoke -> `simulation_handler_ok`
- Next action: Add retry/backoff/DLQ semantics and full worker-mode smoke for graph/simulation, then start the first scientific layer (`ReportAgent live evidence + structured probabilities + Prediction Ledger`).

### Item 19

- Plan item: Add retry/backoff/DLQ semantics and full worker-mode smoke for graph/simulation, then close the main runtime correctness gaps before moving to the scientific layer
- Work done: В `TaskManager` добавлены persistent retry/DLQ поля (`max_attempts`, `next_retry_at`, `dead_letter_reason`), retry scheduling через `fail_or_retry_task()`, eligibility gating по `next_retry_at`, а recovery после рестарта теперь трогает только stale `PROCESSING` tasks, не queued `PENDING`. В `task_handlers` добавлена консервативная retry-классификация, безопасная обработка reservation lifecycle, billing finalization только после lease-validated `complete_task()`, и stale-worker guards для graph/simulation/report. В `/api/report/generate` закрыто окно утечки reservation на exception path до dispatch. Verify script расширен полным worker-mode smoke для `graph_build` и `simulation_prepare`, а также кейсами `report retry`, `DLQ`, `lease_rejected`, `route-exception refund` и `stale-success no-finalize`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/models/task.py`
  - `backend/app/services/task_handlers.py`
  - `backend/app/api/report.py`
  - `scripts/verify_production_fixes.sh`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
  - reviewer pass identified lease-loss and reservation lifecycle issues; follow-up fixes and explicit tests were added in the same slice
- Next action: Canary the worker-backed runtime on Railway, then start the first scientific-product layer (`ReportAgent live evidence`, `structured probabilities`, `Prediction Ledger`) on top of the hardened execution substrate.

### Item 20

- Plan item: Eliminate the last report-task admission race and make pre-dispatch failures deterministic before the Railway worker canary
- Work done: В `TaskManager` добавлены startup reconciliation для duplicate active execution keys, unique partial index на `(task_type, execution_key)` для активных задач и новый atomic admission helper `create_or_reuse_task(...)`. `/api/report/generate` переведен на этот helper, а failure path между reservation/task creation и dispatch теперь всегда освобождает billing reservation, помечает task `FAILED` и переводит placeholder report/progress в `failed`. Verify script расширен регрессиями на duplicate admission reuse, route exception before admission и dispatch failure cleanup. Независимый reviewer-pass по этой slice завершился без blocking findings.
- Comparison status: `AHEAD`
- Evidence:
  - `backend/app/models/task.py`
  - `backend/app/api/report.py`
  - `scripts/verify_production_fixes.sh`
  - reviewer findings resolved: active execution-key uniqueness + deterministic pre-dispatch cleanup
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
  - `npm run build` -> success
- Next action: Add `SERVICE_ROLE` runtime split + worker health support, verify locally, then prepare the Railway canary rollout for a dedicated worker service.

### Item 21

- Plan item: Prepare the Railway worker canary by adding role-aware runtime/health support and validating safe rollout assumptions
- Work done: Первоначальный role-switch через Docker `CMD` и `SERVICE_ROLE` реализован локально, затем прогнан reviewer-pass и частично пересобран. По reviewer findings исправлены три high-risk gaps: worker больше не импортирует `run.py` и не инициализирует app дважды; конфиг стал fail-fast для `TASK_EXECUTION_MODE`/`TASK_STORE_MODE`/`TASK_READ_SOURCE`, а standby worker теперь требует явного `WORKER_STANDBY=true`; Docker entrypoint возвращен к фиксированному web startup, чтобы shared/global `SERVICE_ROLE=worker` не мог уронить API при зеленом `/health`. Health payload enriched with role/consumer metadata, `dispatch_task()` теперь падает на unsupported mode, а verify script покрывает web health, invalid worker mode, standby guard, standby health и active worker health. На Railway создан отдельный service `AgenikPredictWorker` с service-scoped vars, но активация task consumption осознанно не выполнена.
- Comparison status: `DEVIATION`
- Evidence:
  - `backend/app/config.py`
  - `backend/app/__init__.py`
  - `backend/app/services/task_worker.py`
  - `backend/worker.py`
  - `Dockerfile.production`
  - `scripts/verify_production_fixes.sh`
  - reviewer findings on double init / false-green standby / env-scoped Docker role switch
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `npm run build` -> success
  - `railway variable list -s AgenikPredictWorker --json` -> service exists with `SERVICE_ROLE=worker`, `TASK_EXECUTION_MODE=inline`
- Root cause:
  - The original canary design assumed role selection through shared image `CMD`, but that created false-green outage risk for the web service and silent non-consuming worker states.
  - Current Railway topology still stores artifacts under `/app/backend/uploads` on a volume attached only to the web service, and the repo config does not yet encode a per-service worker start command.
- Recovery plan:
  - Deploy the safer web-runtime changes first.
  - Keep `AgenikPredictWorker` out of active consumption until service-specific start-command wiring and shared artifact-access strategy are solved.
  - Resume worker canary only after those infra constraints are closed, or pivot next to the scientific-product layer if this blocker stays open.
- Revised ETA:
  - Safe web-runtime rollout: immediate.
  - Active dedicated worker canary: blocked on Railway service-command + shared-storage strategy.
- Next action: Deploy the current safer web runtime to production, then reassess whether the dedicated worker can be activated or should remain dormant while work continues on prediction-quality features.

### Item 22

- Plan item: Deploy the safer web-runtime changes to production and validate Railway canary state
- Work done: Отправлен новый production deployment для `AgenikPredict` с current runtime-hardening changes (`884037d6-459d-48dd-a4fe-535546c97c79`). Отдельно создан и задеплоен dormant worker-service `AgenikPredictWorker` (`d06ed70a-a5e7-44ec-a864-442942f3db16`) как standby foundation только для дальнейшей canary wiring. По build logs оба deployment'а успешно прошли frontend build и Docker stages до тяжелого `uv sync` / image packaging; явного code-level build failure на момент записи не наблюдается.
- Comparison status: `BLOCKED`
- Evidence:
  - `railway up -d -s AgenikPredict -m "runtime-hardening: worker role validation and safe web entrypoint"`
  - `railway up -d -s AgenikPredictWorker -m "standby worker canary foundation"`
  - `railway variable list -s AgenikPredictWorker --json`
  - `railway deployment list -s AgenikPredict --json` -> latest `884037d6-459d-48dd-a4fe-535546c97c79 | BUILDING`
  - `railway deployment list -s AgenikPredictWorker --json` -> latest `d06ed70a-a5e7-44ec-a864-442942f3db16 | BUILDING`
  - `railway logs -s AgenikPredict --build --latest -n 80`
  - `railway logs -s AgenikPredictWorker --build --latest -n 80`
- Root cause:
  - Railway builds are still in progress because the production image pulls a very heavy backend dependency chain (`torch`, `camel-oasis`, multiple `nvidia-*` packages).
  - Dedicated worker activation remains blocked beyond build completion because current artifact storage lives on a web-attached volume and the repo config still lacks per-service worker start-command wiring.
- Recovery plan:
  - Wait for the current web deployment to reach `SUCCESS` or fail with a concrete build/runtime reason.
  - Keep `AgenikPredictWorker` dormant; do not switch task consumption to it until service-command + storage constraints are solved.
- Revised ETA:
  - Web deployment verdict: pending Railway build completion.
  - Active worker canary: still blocked after build by infrastructure constraints.
- Next action: Monitor deployment completion, then either run live web smoke on the new production revision or capture the exact Railway failure mode if the build fails.

### Item 23

- Plan item: Recover the failed production rollout by fixing the Postgres boot regression and re-validating the live web path
- Work done: Снята точная причина failed deploy `884037d6-459d-48dd-a4fe-535546c97c79`: `TaskManager.init_db()` выполнял SQLite-specific `PRAGMA table_info(tasks)` против Postgres и падал на boot. В `backend/app/models/task.py` schema probe заменен на DB-agnostic `SELECT * FROM tasks LIMIT 0`, а verify script получил отдельную regression-проверку на Postgres-like bootstrap без `PRAGMA`. После локальной верификации (`compileall`, `verify_production_fixes.sh`, `npm run build`) отправлен recovery deploy `c3f953fd-ec85-43fc-bf3b-901d230a71c6`, который вышел в `SUCCESS`. Live `/health` снова отвечает. Дополнительно пройден live API smoke до `auth -> ontology -> graph build`; попытки synthetic end-to-end smoke показали, что слабые smoke inputs дают `entities_count=0` / слишком бедный graph и ломаются уже на simulation-quality уровне, а не на runtime availability.
- Comparison status: `ON_TRACK`
- Evidence:
  - `railway logs -s AgenikPredict 884037d6-459d-48dd-a4fe-535546c97c79 -n 200`
  - `backend/app/models/task.py`
  - `scripts/verify_production_fixes.sh`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `npm run build` -> success
  - `railway up -d -s AgenikPredict -m "fix: postgres-compatible task schema bootstrap"`
  - `railway deployment list -s AgenikPredict --json` -> latest `c3f953fd-ec85-43fc-bf3b-901d230a71c6 | SUCCESS`
  - `curl https://app.agenikpredict.com/health` -> healthy JSON
  - live logs confirm fresh ontology + graph tasks executing after recovery
- Next action: Keep the dedicated worker rollout deferred, and move next to improving high-signal smoke inputs / entity grounding so live end-to-end validation reaches `prepare -> start -> report` reliably.

### Item 25

- Plan item: Validate scope and architecture fit for live verification after the single-platform simulation hotfix
- Work done: Подтверждено, что целевой deploy действительно активен в production (`ace15292-8a37-42bc-9638-6ef605c4e3e8 | SUCCESS`), `/health` отражает ожидаемую web-role topology (`task_execution_mode=inline`, `task_store_mode=dual`, `worker_consumer_active=false`), и hotfix-код стоит в правильных местах: platform-aware readiness check в `_check_simulation_prepared()` и unified runner path (`run_parallel_simulation.py` + `--reddit-only/--twitter-only`) в `SimulationRunner.start_simulation()`. На этой базе сформирован строгий scope для credible production-check: доказать не только availability, но и single-platform state-machine correctness (`prepare -> ready`, `start`, `run-status completed`, `report progress`), плюс выделены blind spots, которые легко дают false-green (in-memory run-state, dormant worker topology, отсутствие durable queue semantics в live path).
- Comparison status: `ON_TRACK`
- Evidence:
  - `railway deployment list -s AgenikPredict --json` -> `ace15292-8a37-42bc-9638-6ef605c4e3e8 | SUCCESS`
  - `curl https://app.agenikpredict.com/health` -> `{"role":"web","status":"ok","task_execution_mode":"inline","task_store_mode":"dual","worker_consumer_active":false}`
  - `backend/app/api/simulation.py` (`_check_simulation_prepared`, `/prepare/status`, `/start`, `/<simulation_id>/run-status`)
  - `backend/app/services/simulation_runner.py` (`start_simulation`, `script_args` with `--reddit-only/--twitter-only`)
  - `backend/scripts/run_parallel_simulation.py` (supports `--twitter-only` / `--reddit-only`)
- Next action: Run live reddit-only curated smoke on production and classify outcome by rule: `INPUT_INVALID` vs `RUNTIME_REGRESSION`.

### Item 26

- Plan item: Recover the failed Railway worker service and bring it to a healthy explicit-standby state without impacting the live web path
- Work done: Проведена multi-agent диагностика `AgenikPredictWorker`: подтверждено, что исторический fail шел из-за несогласованности entrypoint/env contract (`SERVICE_ROLE=worker`, `TASK_EXECUTION_MODE=inline`, без `WORKER_STANDBY=true`, плюс Docker `CMD` раньше был web-only). В коде внесены два минимальных изменения: `backend/worker.py` теперь допускает explicit standby без полного app bootstrap, а `Dockerfile.production` выбирает entrypoint по `SERVICE_ROLE` (`worker.py` для worker, `gunicorn run:app` для web). Локально проверены оба режима: worker standby health и web gunicorn health. На Railway для `AgenikPredictWorker` добавлен `WORKER_STANDBY=true`, затем выполнен отдельный deploy `213140f5-432e-4448-95e4-d54a1bdce78d`, который вышел в `SUCCESS`. Runtime logs подтверждают ожидаемый контракт: `Worker health server listening on 0.0.0.0:8080/health` и `Worker process is in standby because TASK_EXECUTION_MODE=inline`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/worker.py`
  - `Dockerfile.production`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `npm run build` -> success
  - local standby smoke -> `{"status":"standby","role":"worker","worker_standby":true,...}`
  - local web smoke -> `{"role":"web","status":"ok","task_execution_mode":"inline",...}`
  - `railway variable list -s AgenikPredictWorker --kv` -> includes `WORKER_STANDBY=true`
  - `railway deployment list -s AgenikPredictWorker` -> `213140f5-432e-4448-95e4-d54a1bdce78d | SUCCESS`
  - Railway runtime logs at `2026-03-18T12:06:50Z` -> `Worker health server listening on 0.0.0.0:8080/health`
  - Railway runtime logs at `2026-03-18T12:06:50Z` -> `Worker process is in standby because TASK_EXECUTION_MODE=inline`
- Next action: Keep the worker in explicit standby for now; when moving to active queue consumption, add full worker secrets/runtime env plus shared artifact storage (`/app/backend/uploads` volume or object storage) before switching `TASK_EXECUTION_MODE=worker`.

### Item 27

- Plan item: Compress the strategic roadmap into a 5-day battle plan that removes dangerous tech debt first and then accelerates the prediction-science layer
- Work done: На базе текущего runtime state, 7-day roadmap, expert gap analysis и multi-agent revalidation собран новый боевой план на 5 дней. Порядок зафиксирован жестко: `Day 1 worker cutover prep`, `Day 2 active worker activation`, `Day 3 live evidence layer for ReportAgent`, `Day 4 structured probabilities + Prediction Ledger`, `Day 5 backtest pilot + quality baseline`. План записан как отдельный операторский документ с целями, файлами и exit criteria по каждому дню.
- Comparison status: `ON_TRACK`
- Evidence:
  - `docs/5_day_battle_plan.md`
  - `docs/7_day_execution_roadmap.md`
  - `docs/expert_analysis_comparison_2026-03-17.md`
  - multi-agent revalidation:
  - `system_context`: runtime truth -> evidence truth -> probabilistic truth -> measurement truth
  - `explorer`: current repo already has DB-backed task substrate and worker loop, but lacks active worker cutover, live-evidence tools, structured probabilities, and prediction ledger
- Next action: Use `Day 1` as the next execution block: shared artifact strategy, env parity checklist, and safe switch plan for active worker mode.

### Item 28

- Plan item: Execute the first Day 1 slice by hardening cutover-safe storage/task-mode configuration before any active worker switch
- Work done: В `Config` введены explicit artifact storage semantics: `ARTIFACT_STORAGE_MODE=local|shared_fs|object_store` и `ARTIFACT_ROOT`, при этом активный worker теперь fail-fast запрещен на `local` artifacts и на transitional task-store flags (`TASK_STORE_MODE!=db`, `TASK_READ_SOURCE!=db`). Критичные simulation/report/profile paths переведены с разрозненных `../../uploads/...` на config-driven roots (`Config.UPLOAD_FOLDER`, `Config.OASIS_SIMULATION_DATA_DIR`). Отдельно создан operator checklist для Day 1 с тремя hard-gates: storage, env parity, task-store pinning.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/config.py`
  - `backend/app/services/simulation_manager.py`
  - `backend/app/services/simulation_runner.py`
  - `backend/app/api/simulation.py`
  - `backend/app/services/zep_tools.py`
  - `scripts/verify_production_fixes.sh`
  - `docs/day1_active_worker_cutover_checklist.md`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> success
  - `bash scripts/verify_production_fixes.sh` -> prints `verify_production_fixes: PASS` while retaining the pre-existing shell harness non-zero exit quirk
- Next action: Close the remaining Day 1 operator gates on Railway itself: confirm shared artifact mode for `web + worker`, derive exact env parity diff, and decide the production-safe path for switching away from `dual/fallback` to `db/db`.

### Item 29

- Plan item: Tighten the new 5-day battle plan after independent review so later execution does not build on weak assumptions
- Work done: После reviewer-pass battle plan скорректирован в трех местах: `Day 1` теперь требует runtime-validated shared artifact path, `Day 4` теперь включает outcome-resolution contract для `Prediction Ledger`, а `Day 5` теперь явно зависит от determinism gate перед backtest pilot.
- Comparison status: `AHEAD`
- Evidence:
  - `docs/5_day_battle_plan.md`
  - reviewer findings on determinism-before-backtest, outcome policy for ledger, and runtime-validated shared artifacts
- Next action: Continue executing `Day 1` on Railway itself, now against the tightened operator criteria.

### Item 30

- Plan item: Close the Day 1 env parity gate with an exact production diff between web and worker services
- Work done: Из Railway извлечен и зафиксирован machine-checked diff env names между `AgenikPredict` и `AgenikPredictWorker`. Подтверждено, что worker сейчас хватает только на standby: у него отсутствуют `DATABASE_URL`, `JWT_SECRET`, весь `LLM_*`, `ZEP_API_KEY`, `TWELVE_DATA_API_KEY`, а также `RESEND_*` / `STRIPE_*` для полного runtime profile.
- Comparison status: `ON_TRACK`
- Evidence:
  - `docs/day1_worker_env_parity_diff.md`
  - `railway variable list -s AgenikPredict --json`
  - `railway variable list -s AgenikPredictWorker --json`
  - `railway service status -s AgenikPredictWorker --json` -> `SUCCESS`, `stopped=false`
- Next action: Decide whether to populate the full worker runtime env on Railway now or only after the shared artifact gate is closed.

### Item 31

- Plan item: Independently review Day 1 cutover hardening for artifact storage validation, worker standby/cutover safety, and env parity readiness
- Work done: Проведен независимый line-level audit по `config.py`, `worker.py`, `task_worker.py`, `verify_production_fixes.sh`, Railway env parity и runtime probes. Найдены критичные блокеры для Day 2 switch: (1) split artifact roots (`UPLOAD_FOLDER` vs hardcoded `OASIS_SIMULATION_DATA_DIR`), (2) active worker boot без `DATABASE_URL` с SQLite fallback, (3) standby-bypass для invalid `TASK_EXECUTION_MODE` при `WORKER_STANDBY=true`, (4) `object_store` разрешен конфигом, но runtime остается файловым. Подтверждено, что `AgenikPredictWorker` в production все еще только standby и env parity не закрыт.
- Comparison status: `DEVIATION`
- Evidence:
  - `backend/app/config.py` (`ARTIFACT_ROOT` vs `OASIS_SIMULATION_DATA_DIR`)
  - `backend/worker.py` (standby path bypasses validation)
  - `backend/app/models/user.py` (`DATABASE_URL` optional with SQLite fallback)
  - `scripts/verify_production_fixes.sh` (active worker smoke uses `env -u DATABASE_URL`)
  - `railway variable list -s AgenikPredict --json`
  - `railway variable list -s AgenikPredictWorker --json`
  - runtime probe: `TASK_EXECUTION_MODE=bogus WORKER_STANDBY=true uv run python worker.py` still returns healthy standby `/health`
  - runtime probe: active worker boot succeeds with `TASK_EXECUTION_MODE=worker TASK_STORE_MODE=db TASK_READ_SOURCE=db` and no `DATABASE_URL`
  - runtime probe: `ARTIFACT_ROOT=/tmp/shared-artifacts` leaves `OASIS_SIMULATION_DATA_DIR` under `backend/uploads/simulations`
- Root cause:
  - Day 1 hardening added strong guardrails but did not yet fully unify artifact roots or enforce active-worker DB coupling.
  - Standby health behavior intentionally prioritized Railway health stability and currently masks an invalid execution mode when standby is explicitly enabled.
- Recovery plan:
  - Make `OASIS_SIMULATION_DATA_DIR` derive from `ARTIFACT_ROOT` (with optional explicit override), then add regression checks for root coherence.
  - Enforce `DATABASE_URL` as required when `SERVICE_ROLE=worker` and `TASK_EXECUTION_MODE=worker`.
  - In worker standby path, still fail fast on invalid mode values; standby should only bypass full app bootstrap, not config correctness.
  - Either remove `object_store` from allowed modes for now or gate it behind implemented adapter checks.
- Revised ETA:
  - These Day 1 corrections are small and can be closed in the next focused implementation block before Day 2 cutover.
- Next action: Implement the four fixes above, extend verification script with deterministic assertions, and re-run Day 1 go/no-go checklist.

### Item 32

- Plan item: Close the four Day 1 review blockers in code and verification before any active worker switch
- Work done: Исправлены все четыре выявленных code-level deviations. `OASIS_SIMULATION_DATA_DIR` теперь строго derives from `ARTIFACT_ROOT`, а report/project paths унифицированы через config constants. Для active worker добавлены честные runtime guards: `object_store` mode запрещен до реальной реализации backend-а, а в production active mode теперь обязателен `DATABASE_URL`. Standby worker больше не маскирует мусорный `TASK_EXECUTION_MODE`: structural validation выполняется даже без полного app bootstrap. `/health` для web и worker теперь отдает `artifact_storage_mode`, `artifact_root`, `simulation_data_dir`, `task_read_source`, а `verify_production_fixes.sh` усилен новыми проверками на root coherence, standby invalid-mode rejection, production active-worker DB requirement и устойчивые random ports. Дополнительно Docker runtime теперь создает artifact root/directories после mount, а `.env.example` и Day 1 operator docs обновлены под новые flags.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/config.py`
  - `backend/app/__init__.py`
  - `backend/worker.py`
  - `backend/app/models/project.py`
  - `backend/app/services/report_agent.py`
  - `backend/app/api/simulation.py`
  - `Dockerfile.production`
  - `.env.example`
  - `docs/day1_active_worker_cutover_checklist.md`
  - `docs/day1_worker_env_parity_diff.md`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `ARTIFACT_ROOT=/tmp/shared-artifacts uv run python - <<'PY' ...` -> `UPLOAD_FOLDER`, `REPORTS_DIR`, `PROJECTS_DIR`, `OASIS_SIMULATION_DATA_DIR` all pinned under the same root
- Next action: Stage the missing Railway env parity safely, deploy the new guardrails, and re-evaluate Day 1 go/no-go from live health plus worker service state.

### Item 33

- Plan item: Close the Day 1 env parity gate as far as safely possible on Railway and publish the guarded Day 1 state to production without activating active worker consumption
- Work done: На Railway staged safe env parity for `AgenikPredictWorker`: скопированы app-level runtime vars (`DATABASE_URL`, `JWT_SECRET`, весь `LLM_*`, `ZEP_API_KEY`, `TWELVE_DATA_API_KEY`, `RESEND_*`, `STRIPE_*`) и explicit flags (`ARTIFACT_STORAGE_MODE=local`, `ARTIFACT_ROOT=/app/backend/uploads`, `TASK_STORE_MODE=dual`, `TASK_READ_SOURCE=fallback`). На web тоже зафиксированы explicit `SERVICE_ROLE=web`, `TASK_EXECUTION_MODE=inline`, `ARTIFACT_*` и текущие task-store flags. После локального `npm run build` и backend boot sanity выполнен live deploy для `AgenikPredict`; production `/health` уже показывает новые artifact/task fields и подтверждает безопасный inline runtime. Для `AgenikPredictWorker` отправлен новый deploy, но service orchestration Railway оставила его в `BUILDING`/`stopped=true` без новых runtime logs, при том что последний healthy standby deploy до этого был `213140f5-432e-4448-95e4-d54a1bdce78d`.
- Comparison status: `BLOCKED`
- Evidence:
  - `railway variable list -s AgenikPredictWorker --json`
  - `railway variable list -s AgenikPredict --json`
  - `npm run build` -> success
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> success
  - `railway up -d -s AgenikPredict -m "chore: day1 cutover guardrails"` -> latest deploy `fc73be0b-cd74-4cc5-97cb-1f2d862a3ae8`
  - `railway service status -s AgenikPredict --json` -> `SUCCESS`
  - `curl https://app.agenikpredict.com/health` -> includes `artifact_root=/app/backend/uploads`, `artifact_storage_mode=local`, `simulation_data_dir=/app/backend/uploads/simulations`, `task_read_source=fallback`
  - `railway up -d -s AgenikPredictWorker -m "chore: day1 cutover guardrails"` -> deploy `6b2711f9-5a06-42ba-97c3-6febc2e652c0`
  - `railway service redeploy -s AgenikPredictWorker --yes` -> latest deploy `18a0a035-38ee-40c5-9e07-f27604925267`
  - `railway service status -s AgenikPredictWorker --json` -> still `BUILDING`, `stopped=true`
- Root cause:
  - Day 1 storage gate remains intentionally open: the current Railway topology still lacks a proven shared artifact contract for separate web+worker roles.
  - In parallel, Railway is not bringing the latest standby worker deploy to runtime, so worker live verification is temporarily platform-blocked even though local verification and the previous standby deploy were healthy.
- Recovery plan:
  - Do not switch `TASK_EXECUTION_MODE=worker`.
  - Treat Day 1 as complete for `code hardening + env parity staging + live web publication`.
  - Keep monitoring/retrying the standby worker deploy separately, but do not let that block the next implementation track: build the real shared artifact backend/object-store path needed for Day 2.
- Revised ETA:
  - Day 2 active worker cutover remains blocked until the storage gate is actually closed; the next engineering move should start the artifact backend work rather than forcing the worker switch.
- Next action: Begin the shared-artifact backend workstream required to turn the current `NO-GO` into a real Day 2 cutover candidate.

### Item 34

- Plan item: Implement the shared-artifact backend foundation and close the first object-store/runtime migration gaps before any active worker cutover
- Work done: Добавлен `artifact_store` abstraction layer с `LocalArtifactStore` и `ObjectArtifactStore` (S3-compatible bucket + local scratch cache), а критичные project/report/simulation paths переведены на store-backed `sync/flush` семантику. Добиты незавершенные refactor points, которые ломали runtime: `simulation.py` больше не падает на undefined `manager`, lookup report-by-simulation теперь идет через `ReportManager`, auto-promotion `preparing -> ready` flush'ит `state.json`, а `zep_tools` загружает persona profiles через `SimulationManager` с `sync=True`. Дополнительно обновлены operator surfaces: `.env.example` описывает object-store env contract, `/health` для web/worker теперь отдает bucket/prefix/scratch metadata, `uv.lock` пересобран с `boto3`, а `verify_production_fixes.sh` переведен на новый artifact-store contract и усилен новыми assertions.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/services/artifact_store.py`
  - `backend/app/models/project.py`
  - `backend/app/services/simulation_manager.py`
  - `backend/app/services/simulation_runner.py`
  - `backend/app/services/report_agent.py`
  - `backend/app/api/simulation.py`
  - `backend/app/services/zep_tools.py`
  - `backend/app/__init__.py`
  - `backend/worker.py`
  - `.env.example`
  - `backend/pyproject.toml`
  - `backend/uv.lock`
  - `scripts/verify_production_fixes.sh`
  - `cd backend && uv lock` -> success
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; create_app(); print('backend_boot_ok')"` -> `backend_boot_ok`
- Next action: Add an actual object-store integration environment for canary validation, then use the new `/health` metadata to prove web/worker env parity before switching any Railway service to `ARTIFACT_STORAGE_MODE=object_store`.

### Item 35

- Plan item: Resolve the low-severity post-review findings before any canary rollout by trimming public health metadata and adding direct regression coverage for the new artifact-store codepaths
- Work done: Убраны лишние object-store metadata поля из публичного `/health` на web и worker (`artifact_object_bucket`, `artifact_object_prefix`, `artifact_scratch_dir`), чтобы не светить инфраструктурные детали на unauthenticated endpoint. Параллельно усилен `scripts/verify_production_fixes.sh`: теперь он напрямую проверяет deterministic latest-report lookup (`ReportManager.get_report_by_simulation`, `_get_report_id_for_simulation`, `/api/report/by-simulation/<simulation_id>`, `simulation history -> report_id`), realtime reads (`profiles/realtime` для reddit и twitter, `config/realtime` при наличии и отсутствии config файла), DB-backed reads (`posts`/`comments` для reddit/twitter и graceful empty-path без DB), а также `ZepToolsService._load_agent_profiles` для reddit JSON, twitter CSV и отсутствующих profile files.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/__init__.py`
  - `backend/worker.py`
  - `scripts/verify_production_fixes.sh`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `cd backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; app=create_app(); print(app.test_client().get('/health').get_json())"` -> health payload no longer contains object-store bucket/prefix/scratch fields
- Next action: Keep the public `/health` slim, and move the next observability details to an internal/admin-only surface if needed. The next engineering block should focus on real object-store canary setup and Day 2 cutover criteria, not more local-only hardening.

### Item 36

- Plan item: Publish the current project state into a new private GitHub repository as a clean snapshot without reusing the dirty local git history
- Work done: Вместо перепушивания существующей истории текущего dirty repo собран отдельный sanitized snapshot из текущего workspace через `git ls-files --cached --others --exclude-standard`, что исключило `.git`, `.env`, ignored runtime artifacts и локальные служебные файлы. По snapshot выполнены базовые проверки: явные токены/ключи по сигнатурам не найдены, файлов `>95MB` нет. Затем в snapshot инициализирован новый git repo, создан один root commit `0ce505e`, и содержимое запушено в новый private GitHub repository. Запрошенный slug `codex-agenic-predict` оказался уже занят на аккаунте, поэтому был создан ближайший свободный private slug `codex-agenic-predict-private`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `gh auth status` -> authenticated as `alexprime1889-prog`
  - `git -C /Users/alexanderivenski/Projects/AgenikPredict ls-files '.env' '.env.*' ...` -> `.env` not tracked in source repo
  - snapshot path: `/Users/alexanderivenski/Projects/codex-agenic-predict-publish`
  - snapshot sanity: `.ENV_PRESENT=no`, `GIT_PRESENT=no`, `FILES=141`
  - secret scan: `rg ... '(github_pat_|ghp_|sk-|AKIA|AIza|xox...|PRIVATE KEY)'` -> no matches
- repo create API: `gh api user/repos --method POST -f name='codex-agenic-predict-private' -F private=true` -> success
- push: `git push -u origin main` -> success
- remote verification: `git ls-remote --heads origin` -> `0ce505e5c30fa78233d5ce47f1922bb464bd3923 refs/heads/main`
- Next action: If the user wants the exact slug `codex-agenic-predict`, inspect or reclaim the already-occupied account-level name and then rename/replace the newly published private repo.

### Item 37

- Plan item: Verify whether the live production deployment matches the published private GitHub snapshot using source, asset, and observable-runtime evidence
- Work done: Проведена трехступенчатая сверка. Сначала подтверждено состояние private GitHub snapshot: commit `0ce505e5c30fa78233d5ce47f1922bb464bd3923`, tree `d8b6dc4894d14fa7d5f82cbb6b08757ef9027267`, и `origin/main` у snapshot совпадает с этим commit. Затем snapshot сравнен с текущим workspace по всем файлам, входящим в snapshot: различаются только `docs/AGENT_SESSION_LOG.md` и `docs/plan-comparison-log.md`, то есть deployable code и build inputs совпадают. После этого выполнена byte-level сверка прод-фронтенда: live `https://app.agenikpredict.com/` отдает `index-CkYmH1Ba.js` и `index-DyQi3PGL.css`, их SHA-256 полностью совпадают с локальной сборкой из текущего workspace. Дополнительно сверен публичный `/health`: live operational contract совпадает с локальным current code shape, кроме ожидаемого различия локального абсолютного пути и Railway path. Вывод: production frontend и наблюдаемый публичный runtime contract совпадают с опубликованным GitHub snapshot; exact deploy provenance на уровне image digest/commit не доказывался, поэтому backend корректно описывать как behaviorally equivalent, а не cryptographically proven identical.
- Comparison status: `ON_TRACK`
- Evidence:
  - `cd /Users/alexanderivenski/Projects/codex-agenic-predict-publish && git rev-parse HEAD` -> `0ce505e5c30fa78233d5ce47f1922bb464bd3923`
  - `cd /Users/alexanderivenski/Projects/codex-agenic-predict-publish && git rev-parse HEAD^{tree}` -> `d8b6dc4894d14fa7d5f82cbb6b08757ef9027267`
  - `cd /Users/alexanderivenski/Projects/codex-agenic-predict-publish && git ls-remote --heads origin` -> `0ce505e5c30fa78233d5ce47f1922bb464bd3923 refs/heads/main`
  - snapshot-vs-workspace compare over `git ls-files` -> only `docs/AGENT_SESSION_LOG.md` and `docs/plan-comparison-log.md` differ
  - `cd /Users/alexanderivenski/Projects/AgenikPredict && npm run build` -> success
  - `curl -sS https://app.agenikpredict.com/` -> references `/assets/index-CkYmH1Ba.js` and `/assets/index-DyQi3PGL.css`
  - local/live asset SHA-256 matches for both JS and CSS
  - `curl -sS https://app.agenikpredict.com/health` -> public health contract matches current code shape (`role=web`, `artifact_storage_mode=local`, `task_execution_mode=inline`, `task_store_mode=dual`, `worker_consumer_active=false`)
- `cd /Users/alexanderivenski/Projects/AgenikPredict/backend && env JWT_SECRET=test-secret uv run python -c "from app import create_app; app=create_app(); print(app.test_client().get('/health').get_json())"` -> same operational fields locally, with expected local-path prefix
- Next action: If a stronger claim is required than functional parity, tie the running Railway image digest to a build from the GitHub snapshot commit or run an authenticated live contract suite against the changed backend endpoints.

### Item 38

- Plan item: Attempt the strongest post hoc provenance proof available for production by tying Railway deployment metadata and a Railway-built control image back to the published snapshot commit
- Work done: Выполнена более строгая provenance-проверка. Для live web сервиса `AgenikPredict` подтвержден active deployment `fc73be0b-cd74-4cc5-97cb-1f2d862a3ae8` и immutable `imageDigest=sha256:f6c6c9a22ff1c179da4c3bf8c83dd2b1f107b16266923d4365c27df6121fada8` из Railway metadata. Критичное ограничение тоже подтверждено: у live deployment `source=null`, то есть Railway не хранит repo/commit provenance для этого web deploy, потому что он был загружен напрямую через CLI. Для усиления доказательства создан временный control service `AgenikPredictProvenance` и в Railway отправлен deploy published snapshot (`d024115d-76ae-479c-a42b-c18707829644`) без изменения live production. Контрольная Railway build-трасса показала тот же итоговый frontend artifact set (`index-CkYmH1Ba.js`, `index-DyQi3PGL.css`, `AccountView-D3tfCVMU.js`, `AdminView-Bf5dw1XZ.js`), но ранние BuildKit step digests между live deploy и control build расходятся. Это означает, что post hoc digest-chain на уровне BuildKit steps не дает надежного exact-commit proof: в текущем pipeline отсутствует встроенная commit provenance, а image/build digests зависят не только от содержимого приложения, но и от build-context metadata / упаковки архива. На момент фиксации контрольный service все еще в `BUILDING`, поэтому финальный control `imageDigest` не был получен в пределах этого шага.
- Comparison status: `BLOCKED`
- Evidence:
  - `railway service status -s AgenikPredict --json` -> deployment `fc73be0b-cd74-4cc5-97cb-1f2d862a3ae8`, status `SUCCESS`
  - `python3 ... railway status --json ...` -> `AgenikPredict.latestDeployment.meta.imageDigest = sha256:f6c6c9a22ff1c179da4c3bf8c83dd2b1f107b16266923d4365c27df6121fada8`, `source = null`
  - `railway deployment list -s AgenikPredict --json` -> live web deployment metadata includes immutable `imageDigest`
  - `brew install docker-buildx` + `docker buildx version` -> local BuildKit client enabled for comparison work
  - `railway add -s AgenikPredictProvenance --json` -> temporary control service `1edc75a8-ffb7-4968-a8ff-cc58aa3b72ea`
  - `railway up /Users/alexanderivenski/Projects/codex-agenic-predict-publish -s AgenikPredictProvenance --path-as-root -d -m "provenance check snapshot"` -> control deployment `d024115d-76ae-479c-a42b-c18707829644`
  - `railway logs --build d024115d-76ae-479c-a42b-c18707829644 --lines ... --json` -> control build produces the same named frontend assets as live (`index-CkYmH1Ba.js`, `index-DyQi3PGL.css`, `AccountView-D3tfCVMU.js`, `AdminView-Bf5dw1XZ.js`)
  - Railway live build logs for `fc73...` and control build logs for `d024...` show differing BuildKit step digests despite equivalent frontend output
- Root cause:
  - The current deploy process is direct `railway up` from local workspace, not GitHub/CI-driven, so Railway metadata does not embed a source repo or commit SHA for the live deployment.
  - Build/image digests are not a reliable retroactive proxy for git commit identity unless commit metadata or signed provenance is embedded at build time.
- Recovery plan:
  - Treat current proof ceiling as: frontend identical by asset hash; backend/public contract behaviorally equivalent; live image digest known but not attributable to a GitHub commit with exact certainty.
  - For future releases, embed OCI labels such as `org.opencontainers.image.revision` and `org.opencontainers.image.source`, or move builds into GitHub Actions and deploy Railway strictly by pinned digest.
  - Optionally let the control build finish and capture its final `imageDigest`, but do not oversell that as exact commit proof without embedded source metadata.
- Revised ETA:
  - Immediate exact-commit provenance for the already-running production image is not recoverable from current metadata alone.
  - One release cycle is enough to add strong provenance to all future deployments.
- Next action: Update the user with the strongest honest conclusion now, and then decide whether to implement OCI/git provenance in the build pipeline for subsequent releases.

### Item 39

- Plan item: Switch existing Railway services from direct local CLI deployments to the private GitHub repository as the source of truth, while preserving the current production infrastructure
- Work done: Через официальный Railway Public API выполнен `serviceConnect` для существующих services `AgenikPredict` (`06f4d692-6bb9-4886-9115-e1fb944868a3`) и `AgenikPredictWorker` (`7440ce35-effe-4bc1-b3a4-53b3ef74262c`) с source repo `alexprime1889-prog/codex-agenic-predict-private` и branch `main`. Это не пересоздало проект/сервисы, не трогало переменные, volume mounts или домены; Railway просто переключил source и автоматически запустил новые GitHub-based deployments. В metadata этих deployments появился `commitHash=0ce505e5c30fa78233d5ce47f1922bb464bd3923`, `commitMessage="Initial snapshot"`, `repo="alexprime1889-prog/codex-agenic-predict-private"`, `branch="main"`, то есть provenance теперь встроена и больше не зависит от локального `railway up`. Затем rollout был доведен до финального terminal state: `AgenikPredict` deployment `1c9951cc-709b-4542-be75-1ec1613208c7` и `AgenikPredictWorker` deployment `da68f909-28ea-45da-a8dc-322275591efb` оба вышли в `SUCCESS`, а публичный `https://app.agenikpredict.com/health` остался зеленым. Временный сервис `AgenikPredictProvenance`, использованный для предыдущей provenance-проверки, после этого удален через `serviceDelete`, чтобы не оставлять лишний мусор в проекте.
- Comparison status: `ON_TRACK`
- Evidence:
  - Railway docs: `serviceConnect(id, input: { repo, branch })` on https://docs.railway.com/integrations/api/manage-services
  - GraphQL test query against `https://backboard.railway.com/graphql/v2` with Railway account token -> authenticated as `alexprime1889@gmail.com`
  - `serviceConnect` mutation success for `AgenikPredict` -> `{"data":{"serviceConnect":{"id":"06f4d692-6bb9-4886-9115-e1fb944868a3"}}}`
  - `serviceConnect` mutation success for `AgenikPredictWorker` -> `{"data":{"serviceConnect":{"id":"7440ce35-effe-4bc1-b3a4-53b3ef74262c"}}}`
  - GraphQL project query after the switch -> both services now show `source.repo = "alexprime1889-prog/codex-agenic-predict-private"`
  - New GitHub-based deployments:
    - `AgenikPredict` -> `1c9951cc-709b-4542-be75-1ec1613208c7`
    - `AgenikPredictWorker` -> `da68f909-28ea-45da-a8dc-322275591efb`
  - New deployment metadata already includes:
    - `commitHash = 0ce505e5c30fa78233d5ce47f1922bb464bd3923`
    - `commitMessage = "Initial snapshot"`
    - `branch = "main"`
    - `repo = "alexprime1889-prog/codex-agenic-predict-private"`
  - `curl -sS https://app.agenikpredict.com/health` -> `status:"ok"` while rollout is in progress
  - `serviceDelete("1edc75a8-ffb7-4968-a8ff-cc58aa3b72ea")` -> `true`
  - `railway service status -s AgenikPredict --json` -> `deploymentId=1c9951cc-709b-4542-be75-1ec1613208c7`, `status="SUCCESS"`, `stopped=false`
  - `railway service status -s AgenikPredictWorker --json` -> `deploymentId=da68f909-28ea-45da-a8dc-322275591efb`, `status="SUCCESS"`, `stopped=false`
  - Final `curl -fsS https://app.agenikpredict.com/health` -> `{"status":"ok","task_execution_mode":"inline","worker_consumer_active":false,...}`
- Next action: Treat the private GitHub repository as the canonical release source for both Railway services; future deploy verification can rely on Railway deployment metadata `repo/branch/commitHash`.

### Item 40

- Plan item: Advance Day 1 / Day 2 active-worker cutover by replacing local-only artifact assumptions with a real object-store canary path
- Work done: Добавлен fail-fast artifact probe на старте приложения и standby worker, чтобы `ARTIFACT_STORAGE_MODE=object_store` валидировался при boot, а не только по наличию env vars. Для этого введен флаг `ARTIFACT_PROBE_ON_STARTUP` в конфиге, `create_app()` теперь вызывает `get_artifact_store().probe()`, и `backend/worker.py` делает тот же probe даже в standby-режиме. После локальной проверки (`py_compile` и `verify_production_fixes.sh`) выяснилось, что активный worker все еще упирается не в код, а в storage topology: в проде `AgenikPredict`/`AgenikPredictWorker` оба были на `ARTIFACT_STORAGE_MODE=local`, а volume смонтирован только на web. Затем обновлен Railway CLI (`4.30.5 -> 4.32.0`), потому что старый бинарь не умел `railway bucket`. Через новый CLI создан и задеплоен production bucket `compact-tupperware-DXP7` (`id=139bfcfd-0747-4556-bf02-1ca6f034de4f`, region `iad`), и получены S3-compatible credentials для будущего object-store canary. Параллельно рабочий проект синхронизирован в private publish-repo, потому что Railway теперь тянет релизы из GitHub, а не из локального `railway up`.
- Comparison status: `ON_TRACK`
- Evidence:
  - [backend/app/config.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/config.py)
  - [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py)
  - [backend/worker.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/worker.py)
  - [.env.example](/Users/alexanderivenski/Projects/AgenikPredict/.env.example)
  - `cd backend && uv run python -m py_compile app/__init__.py app/config.py worker.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - `railway --version` -> `4.32.0`
  - `railway bucket create agenikpredict-artifacts -e production -r iad --json` -> bucket deployed as `compact-tupperware-DXP7` / `139bfcfd-0747-4556-bf02-1ca6f034de4f`
  - `railway bucket info -b 139bfcfd-0747-4556-bf02-1ca6f034de4f -e production --json` -> environment `production`, `objects=0`, `region=iad`
  - `railway bucket credentials -b 139bfcfd-0747-4556-bf02-1ca6f034de4f -e production --json` -> S3-compatible endpoint/keys returned successfully
  - `railway variable list` confirms current prod still uses `TASK_EXECUTION_MODE=inline`, `TASK_STORE_MODE=dual`, `TASK_READ_SOURCE=fallback`, `ARTIFACT_STORAGE_MODE=local`
  - `rsync ... /Users/alexanderivenski/Projects/AgenikPredict/ -> /Users/alexanderivenski/Projects/codex-agenic-predict-publish/` -> GitHub publish repo picked up the new worker/object-store probe changes
- Next action: Commit and push the synchronized publish repo to GitHub, set object-store env vars on `AgenikPredictWorker` for a standby canary deploy, and verify that the worker boots green with `ARTIFACT_STORAGE_MODE=object_store` before any active cutover.

### Item 41

- Plan item: Make the standby object-store canary observable and fail fast instead of hanging in opaque `DEPLOYING`
- Work done: После настройки `ARTIFACT_STORAGE_MODE=object_store` на `AgenikPredictWorker` Railway дважды оставлял canary deployment в долгом `BUILDING/DEPLOYING` без финального runtime-лога, при этом предыдущий GitHub-based worker deploy на том же коммите успешно работал в `mode=local`. Это подтвердило, что безопаснее усилить наблюдаемость и ограничить object-store startup probe по времени, чем ждать бесконечный rollout. В локальном коде добавлены явные `ARTIFACT_OBJECT_CONNECT_TIMEOUT_SECONDS` и `ARTIFACT_OBJECT_READ_TIMEOUT_SECONDS`, `boto3` переведен на `botocore.config.Config` с `connect_timeout`, `read_timeout` и `retries`, а startup paths теперь логируют `Starting ... artifact probe` и `... probe failed` до проброса исключения. Это не меняет успешный путь, но превращает зависающий canary в диагностируемый fail-fast. Локальная проверка прошла: `py_compile` зеленый, `verify_production_fixes.sh` зеленый.
- Comparison status: `ON_TRACK`
- Evidence:
  - [backend/app/config.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/config.py)
  - [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py)
  - [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py)
  - [backend/worker.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/worker.py)
  - [.env.example](/Users/alexanderivenski/Projects/AgenikPredict/.env.example)
  - `railway deployment list -s AgenikPredictWorker --json` -> object-store deployments `c8c4b25d-6732-4c05-9e96-215c6224abd6` and `2469c4e0-d050-4ca5-bdbd-c4f501834983` remained in `DEPLOYING` while prior deployment `c3b00309-2c9c-42a5-9d20-18989c1a45bb` was `SUCCESS`
  - `railway logs -s AgenikPredictWorker --lines 80` -> last healthy runtime still showed `Standby worker artifact probe succeeded: mode=local`
  - `cd backend && uv run python -m py_compile app/__init__.py app/config.py app/services/artifact_store.py worker.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- Next action: Sync these probe-timeout/logging changes into the private GitHub publish repo, push, and redeploy `AgenikPredictWorker` again so Railway either reaches `mode=object_store` success or emits a concrete startup failure.

### Item 42

- Plan item: Prove Railway object-store canary end-to-end on worker and stage the same backend on web without touching live traffic
- Work done: После публикации коммита `48d5659` в private GitHub repo Railway автоматически создал новый worker deployment `030f6a7f-7c75-4835-be00-d7282e83d8f4`, но service pointer продолжил висеть в `DEPLOYING`. При этом runtime-логи уже подтвердили, что предыдущий GitHub-based deployment `2469c4e0-d050-4ca5-bdbd-c4f501834983` успешно поднял worker в standby на `ARTIFACT_STORAGE_MODE=object_store`: `Standby worker artifact probe succeeded: mode=object_store`. Это сняло главный Day 2 blocker: deployed Railway bucket реально доступен процессу worker. Пока свежий auto-deploy еще не догнал активный service pointer, на web были безопасно staged те же object-store env vars через `railway variable set --skip-deploys`, но без переключения live web с `ARTIFACT_STORAGE_MODE=local`. Таким образом, текущий production web не изменился, а вся конфигурация для следующего controlled canary уже подготовлена.
- Comparison status: `ON_TRACK`
- Evidence:
  - `git push origin main` in `/Users/alexanderivenski/Projects/codex-agenic-predict-publish` -> `48d5659` pushed to `alexprime1889-prog/codex-agenic-predict-private`
  - `railway deployment list -s AgenikPredictWorker --json` -> new deployment `030f6a7f-7c75-4835-be00-d7282e83d8f4` on commit `48d565909411aec718efb0b1fbf0de8d606cf20f`
  - `railway logs -s AgenikPredictWorker --lines 120` -> `Standby worker artifact probe succeeded: mode=object_store`
  - `curl -fsS https://app.agenikpredict.com/health` -> web still `artifact_storage_mode=local`, `task_execution_mode=inline`
  - `railway variable set -s AgenikPredict -e production --skip-deploys ...` -> staged object-store vars on web without triggering a deploy
  - Filtered `railway variable list -s AgenikPredict --json` confirms:
    - `ARTIFACT_STORAGE_MODE=local`
    - object-store bucket/endpoint/timeout vars present
    - `TASK_EXECUTION_MODE=inline`, `TASK_STORE_MODE=dual`, `TASK_READ_SOURCE=fallback`
- Next action: Stop waiting on Railway’s slow service-pointer update for `030f6a7f...`; treat worker object-store canary as proven and move to the next controlled step: a web object-store canary deploy that keeps `TASK_EXECUTION_MODE=inline` while switching `ARTIFACT_STORAGE_MODE` from `local` to `object_store`.

### Item 43

- Plan item: Run a controlled web object-store canary without changing inline execution semantics
- Work done: Переключил production web `AgenikPredict` на `ARTIFACT_STORAGE_MODE=object_store`, сохранив `TASK_EXECUTION_MODE=inline`, и прогнал live smoke. Web deployment `1581597f-b19b-4ec1-9865-221445f79430` вышел в `SUCCESS`, `/health` подтвердил `artifact_storage_mode=object_store`, а Railway runtime-логи показали `Artifact store probe succeeded: mode=object_store`. Live smoke дошел через `ontology -> graph build -> simulation create -> prepare -> start`: ontology с fallback ушла с GLM на Claude, graph build дал `23` qualifying entities, prepare завершился на `100%`, start поднял `reddit` run с живым `pid`. При этом обнаружился новый runtime gap: `GET /api/simulation/<simulation_id>/run-status` и `/run-status/detail` под `web inline + object_store` оставались на `current_round=0`, `total_actions_count=0`, хотя server logs уже показывали выполнение симуляции. Это перевело Day 2 из storage-risk в monitoring-consistency bug.
- Comparison status: `ON_TRACK`
- Evidence:
  - `railway service status -s AgenikPredict --json` -> deployment `1581597f-b19b-4ec1-9865-221445f79430`, `SUCCESS`
  - `curl -fsS https://app.agenikpredict.com/health` -> `artifact_storage_mode=object_store`, `task_execution_mode=inline`, `status=ok`
  - `railway logs -s AgenikPredict --lines 200` -> `Starting artifact store probe: mode=object_store` then `Artifact store probe succeeded: mode=object_store`
  - Live smoke IDs:
    - `project_id=proj_54d2ec65834b`
    - `graph_id=agenikpredict_bf48f767b07c44b5`
    - `simulation_id=sim_42e823de3ecb`
    - `prepare_task_id=300c6aa3-cae4-4c63-945b-8f55b21c60ec`
  - Live smoke observations:
    - graph entities endpoint returned `filtered_count=23`
    - prepare task reached `status=completed`, `progress=100`
    - start returned `runner_status=running`, `reddit_running=true`, `process_pid=1416`
    - repeated `run-status` polling stayed at `current_round=0`, `total_actions_count=0`
- Next action: Fix live monitoring so inline object-store polling prefers the active local runtime state and local action logs instead of syncing stale object-store snapshots back into the same working directory during execution.

### Item 44

- Plan item: Repair inline object-store live monitoring before any active worker cutover
- Work done: В [backend/app/services/simulation_runner.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_runner.py) добавил `_has_active_local_runtime()` и изменил live read-path так, чтобы `web inline + object_store` сначала использовал in-memory `SimulationRunState` и локальные action-логи для активного процесса, а не вызывал `sync=True` against object-store на каждом polling-запросе. `get_run_state()` теперь в этом режиме не тянет stale `run_state.json` из object-store поверх живого subprocess workspace, а `get_all_actions()` читает local scratch для активного inline run. В [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh) добавлены targeted regressions: `object_store + inline` не должен синкать stale run state для живого runtime и должен читать local actions с `sync=False`, при этом inactive object-store path по-прежнему идет через `sync=True`. Локальная верификация зеленая.
- Comparison status: `ON_TRACK`
- Evidence:
  - [backend/app/services/simulation_runner.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_runner.py)
  - [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh)
  - `python3 -m py_compile backend/app/services/simulation_runner.py` -> success
  - `bash -n scripts/verify_production_fixes.sh` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - Independent explorer review identified the root cause in `get_run_state(sync=True)` / `get_all_actions(sync=True)` under object-store polling and recommended the same minimal fix
- Next action: Sync this fix into the GitHub-backed publish repo, let Railway redeploy the web service from GitHub, and rerun the live smoke to confirm `run-status` and `run-status/detail` advance during a real inline object-store simulation.

### Item 45

- Plan item: Close the remaining object-store simulation startup gap before active worker cutover
- Work done: Повторный live/root-cause analysis показал, что stale `run-status` был не последней проблемой: при новом canary `start` мог уходить в `runner_status=running`, но subprocess логировал `Profile file does not exist: .../reddit_profiles.json` и оставался в command-wait mode без поднятой среды. Это вскрыло два контракта, которые раньше были слишком мягкими. Во-первых, в [backend/app/services/simulation_manager.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_manager.py) добавил явный flush simulation artifacts сразу после сохранения profile files и после `simulation_config.json`, а не только на финальном `state.json` save. Во-вторых, в [backend/app/api/simulation.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/simulation.py) добавил unconditional `_check_simulation_prepared()` preflight перед любым `start`, даже если state уже `READY`, чтобы битый READY-state не проходил дальше. В-третьих, в [backend/app/services/simulation_runner.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_runner.py) добавил fail-fast runtime artifact validation: после `sync=True` runner теперь проверяет platform-required files и поднимает `ValueError`, если, например, нет `reddit_profiles.json`. В [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh) добавлены regressions на оба слоя: start endpoint должен отказывать на READY simulation без profiles, а object-store prepare должен переживать flush/sync cycle так, чтобы `reddit_profiles.json` и `simulation_config.json` реально существовали в синкнутом scratch после подготовки.
- Comparison status: `ON_TRACK`
- Evidence:
  - [backend/app/services/simulation_manager.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_manager.py)
  - [backend/app/services/simulation_runner.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/simulation_runner.py)
  - [backend/app/api/simulation.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/simulation.py)
  - [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh)
  - `python3 -m py_compile backend/app/services/simulation_manager.py backend/app/services/simulation_runner.py backend/app/api/simulation.py` -> success
  - `bash -n scripts/verify_production_fixes.sh` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- Next action: Sync Item 45 into the GitHub-backed publish repo, monitor the Railway GitHub deployment, and rerun the full live inline `object_store` smoke to confirm `prepare -> start -> run-status` now advances with real actions instead of entering a dead `running 0/0` state.

### Item 46

- Plan item: Remove the live `object_store` scratch-cache race that blocks graph-task polling and can break inline canary smoke
- Work done: После GitHub deployment `f07dd40` live web поднялся, но новый smoke и Railway logs выявили следующий blocker: concurrent `sync=True` against one project resource мог ломать local object-store scratch cache в [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py). Конкретный symptom в проде: `FileNotFoundError` на rename temp file inside boto download path during `/api/graph/task/<task_id>`, когда два запроса синхронизировали один и тот же project directory. Это объясняет, почему новый smoke не дошел стабильно до симуляции уже после починки simulation artifacts. Локально добавил resource-level `RLock` внутри `ObjectArtifactStore` и обернул им `sync_resource()`, `flush_resource()` и `delete_resource()`, чтобы concurrent requests к одному namespace/resource_id больше не могли удалять temp files друг друга. В [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh) добавлена deterministic regression: два concurrent `sync_resource("projects", "race")` against the same fake object-store resource должны завершаться без ошибок и оставлять final file на месте. Полная локальная верификация после lock-layer снова зеленая.
- Comparison status: `ON_TRACK`
- Evidence:
  - [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py)
  - [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh)
  - Railway live evidence from deploy `2bd3f8c3-2873-471f-8671-569ffd7e0b0a`:
    - `/api/graph/task/...` stack trace ended in `artifact_store.sync_resource()` -> boto rename `FileNotFoundError`
    - this occurred while `artifact_storage_mode=object_store`, `task_execution_mode=inline`
  - `python3 -m py_compile backend/app/services/artifact_store.py backend/app/services/simulation_manager.py backend/app/services/simulation_runner.py backend/app/api/simulation.py` -> success
  - `bash -n scripts/verify_production_fixes.sh` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- Next action: Publish Item 46 into the GitHub-backed repo, let Railway roll forward one more GitHub deployment, and rerun the full live inline `object_store` smoke from ontology through `run-status` to verify the canary is finally stable enough for the next cutover decision.

### Item 47

- Plan item: Remove the live `object_store` runtime upload failure that aborts simulation runs immediately after `start`
- Work done: После GitHub deployment `d79f7e80-e50b-4947-b273-fc8b02c948e8` web object-store canary наконец дошел live до `prepare -> start`, и это сузило проблему до точного runtime blocker. Полный smoke для `sim_085275c7be5d` подтвердил: `prepare` завершился (`status=ready`, `existing_files=["state.json","simulation_config.json","reddit_profiles.json"]`), `start` успешно поднял процесс (`process_pid=4875`, `runner_status=running`), но затем `run-status` почти сразу перешел в `failed` с ошибкой `Need to rewind the stream <botocore.httpchecksum.AwsChunkedWrapper ...>, but stream is not seekable.` Railway logs одновременно показали `Monitor thread exception`, что указывает не на simulation logic, а на artifact flush during run-state persistence. Локально в [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py) я сделал два целевых смягчения: `botocore.config.Config` теперь использует `request_checksum_calculation=\"when_required\"` и `response_checksum_validation=\"when_required\"`, а мелкие runtime artifacts (`<= 8 MiB`) загружаются через `put_object(Body=bytes)` вместо streaming `upload_file`, чтобы S3-compatible backend не требовал rewind не-seekable checksum-wrapped stream на retry. В [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh) добавлен regression на `_upload_local_file()`: small file must go through `put_object`, large file must still fall back to `upload_file`. Полная локальная верификация снова зеленая.
- Comparison status: `ON_TRACK`
- Evidence:
  - [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py)
  - [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh)
  - Live smoke for `sim_085275c7be5d`:
    - `/api/simulation/prepare/status` -> `ready`
    - `/api/simulation/start` -> `runner_status=running`, `process_pid=4875`
    - `/api/simulation/<id>/run-status` -> `failed`, `error=\"Need to rewind the stream <botocore.httpchecksum.AwsChunkedWrapper ...>, but stream is not seekable.\"`
  - Railway logs:
    - `[17:04:38] ERROR: Monitor thread exception: sim_085275c7be5d, error=Need to rewind the stream <botocore.httpchecksum.AwsChunkedWrapper object ...>, but stream is not seekable.`
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
- Next action: Sync Item 47 to the GitHub-backed repo, wait for the next Railway deployment to turn green, and rerun the live `object_store` canary through `run-status` to verify that inline runtime persistence now survives past round 0.

### Item 48

- Plan item: Prove that the production web `object_store` canary is now green end-to-end through live `run-status`
- Work done: Коммит `ab0e67f` (`Harden object-store runtime uploads`) был запушен в private GitHub repo и поднял новый Railway web deployment `d27b29ea-de21-4efd-baa6-cc4e9cbc0c39` в `SUCCESS` с `artifact_storage_mode=object_store`, `task_execution_mode=inline`. После этого я не ограничился healthcheck: повторно запустил live canary на уже подготовленной simulation `sim_085275c7be5d` через `/api/simulation/start` с `force=true`, чтобы проверить именно runtime upload path, который до фикса падал на `AwsChunkedWrapper`. Новый рант только стартовал успешно (`runner_status=running`, `force_restarted=true`, `process_pid=236`), но и прошел дальше: сначала `run-status/detail` показал `12` реальных действий в `all_actions`, затем follow-up poll подтвердил финальную консистентность counters — `runner_status=completed`, `current_round=2`, `total_actions_count=12`, `reddit_actions_count=12`, `error=null`. Это закрывает текущий Day 2 gate: `web inline + object_store` теперь переживает `prepare -> start -> run-status` на production.
- Comparison status: `ON_TRACK`
- Evidence:
  - Railway deploy provenance:
    - `AgenikPredict` -> deployment `d27b29ea-de21-4efd-baa6-cc4e9cbc0c39` -> `SUCCESS`
    - commit `ab0e67fc34d0d9bb3bbd5d08b135c2fc79a98e63`
  - Production `/health`:
    - `artifact_storage_mode=object_store`
    - `task_execution_mode=inline`
    - `status=ok`
  - Live restart smoke for `sim_085275c7be5d`:
    - `/api/simulation/start` returned `runner_status=running`, `force_restarted=true`, `process_pid=236`
    - immediate poll showed `detail_all_actions_len=12` with `error=null`
    - final poll showed `runner_status=completed`, `current_round=2`, `total_actions_count=12`, `reddit_actions_count=12`, `error=null`
- Next action: Move from proved web canary to the next production block: controlled active worker cutover. The first blocker to resolve is the lagging `AgenikPredictWorker` GitHub deployment (`0873e188-1b44-4532-bf9e-2ba8dc31aaf3`, still `BUILDING/stopped=true`) before switching `TASK_EXECUTION_MODE=worker`.

### Item 49

- Plan item: Explain the user-reported graph-build interruption and identify the next production move after the green web canary
- Work done: Reviewed current Railway status, web health, recent web runtime logs, and the exact code path for the message `Interrupted by server restart. Please retry.`. Production web is currently healthy on deployment `d27b29ea-de21-4efd-baa6-cc4e9cbc0c39` (`SUCCESS`) with `artifact_storage_mode=object_store` and `task_execution_mode=inline`; `AgenikPredictWorker` still shows latest GitHub deployment `0873e188-1b44-4532-bf9e-2ba8dc31aaf3` as `BUILDING/stopped=true`, though its runtime logs confirm standby boot and successful object-store probe. The interruption string in the user’s graph-build failure is not emitted by graph generation itself; it comes from [backend/app/models/task.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/task.py) inside `recover_interrupted_tasks()`, where stale in-flight `graph_build` tasks are reconciled to `FAILED` with `Interrupted by server restart. Please retry.` after a process restart. That means the observed `12:55-12:58 PM EDT` graph build was progressing normally and then got cut by a service restart/deploy while still running on the web process.
- Comparison status: `ON_TRACK`
- Evidence:
  - Current prod web:
    - deployment `d27b29ea-de21-4efd-baa6-cc4e9cbc0c39` -> `SUCCESS`
    - `/health` -> `status=ok`, `artifact_storage_mode=object_store`, `task_execution_mode=inline`
  - Current worker:
    - latest GitHub deployment `0873e188-1b44-4532-bf9e-2ba8dc31aaf3` -> `BUILDING/stopped=true`
    - runtime logs still show standby boot success and object-store probe success
  - Web logs prove the app is healthy now and completed recent simulation work on the current deployment
  - Code provenance for the interruption message:
    - [backend/app/models/task.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/task.py) -> `recover_interrupted_tasks()` sets `graph_build` tasks to failed with `Interrupted by server restart. Please retry.`
- Next action: Proceed with controlled active worker cutover. Until `TASK_EXECUTION_MODE` moves from `inline` to `worker`, long-running graph/prepare/report tasks remain vulnerable to any web restart or deployment. Operationally, avoid deploying during active long jobs; strategically, finish the worker cutover so this class of interruption disappears.

### Item 50

- Plan item: Attempt the first real active worker cutover now that `web inline + object_store` canary is green
- Work done: I staged and deployed the safe prerequisite layer first: both `AgenikPredict` and `AgenikPredictWorker` were switched to `TASK_STORE_MODE=db` and `TASK_READ_SOURCE=db` while keeping execution `inline/standby`. Web deployment `ae70108e-b589-4522-90b5-0754433554ac` completed successfully, and `/health` confirmed `task_store_mode=db`, `task_read_source=db`, `task_execution_mode=inline`. Then I attempted the real cutover by staging `TASK_EXECUTION_MODE=worker` on web and worker, removing standby on the worker, and redeploying in the safer order `web enqueue-only -> worker active`. What Railway actually did was non-deterministic: worker deployment `57ed8735-f525-4d74-a1c9-e873dfe4111e` eventually became `SUCCESS` and its logs showed `Task worker started: mode=worker poll_interval=2.0s batch_size=10`, but subsequent Railway redeploy ordering later replaced it with a standby worker boot at `17:27:39`, while web had already flipped to `TASK_EXECUTION_MODE=worker`. That created an unsafe queue-only window, so I immediately rolled production back to safe web inline mode via deployment `11161a77-b90a-4f40-8fe7-f0eb3217b512`.
- Comparison status: `BLOCKED_BY_PLATFORM_ORCHESTRATION`
- Evidence:
  - Safe prerequisite step:
    - `AgenikPredict` deploy `ae70108e-b589-4522-90b5-0754433554ac` -> `SUCCESS`
    - `/health` -> `task_execution_mode=inline`, `task_store_mode=db`, `task_read_source=db`
  - Worker active signal during attempt:
    - worker logs: `Task worker started: mode=worker poll_interval=2.0s batch_size=10`
    - worker deployment history showed `57ed8735-f525-4d74-a1c9-e873dfe4111e | SUCCESS`
  - Unsafe asymmetry detected immediately after:
    - web `/health` showed `task_execution_mode=worker`
    - worker logs later showed a newer standby boot: `Worker process is in standby because TASK_EXECUTION_MODE=inline`
  - Safe rollback completed:
    - `AgenikPredict` deploy `11161a77-b90a-4f40-8fe7-f0eb3217b512` -> `/health` back to `task_execution_mode=inline`, `task_store_mode=db`, `task_read_source=db`
- Next action: Treat active worker cutover as blocked by Railway deployment sequencing/orchestration rather than code. The next safe path is a controlled maintenance-window cutover with strict sequencing or service-level deployment isolation: activate worker and verify its live runtime first, then flip web to enqueue-only only after the worker is provably active on the same env snapshot.

### Item 51

- Plan item: Add deterministic worker-cutover safeguards before the next production switch
- Work done: Implemented a fail-fast worker readiness gate in the backend so web no longer accepts worker-mode task creation unless a live worker consumer is provably active. In [backend/app/services/task_worker.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/task_worker.py) I added `WorkerDispatchUnavailable` and `ensure_worker_dispatch_ready()`, which validates `WORKER_HEALTHCHECK_URL` and requires the worker `/health` payload to report `role=worker`, `task_execution_mode=worker`, `worker_consumer_active=true`, `task_store_mode=db`, and `task_read_source=db`. In [backend/app/api/graph.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/graph.py), [backend/app/api/simulation.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/simulation.py), and [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py) I moved this gate ahead of task creation so `graph_build`, `simulation_prepare`, and `report_generate` now return `503` before mutating state if web is in worker mode but the consumer is standby/unreachable. In [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py) and [backend/app/config.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/config.py) I added standby-time config validation so web cannot boot in worker mode without `WORKER_HEALTHCHECK_URL`. In [scripts/verify_production_fixes.sh](/Users/alexanderivenski/Projects/AgenikPredict/scripts/verify_production_fixes.sh) I added regression coverage for: missing `WORKER_HEALTHCHECK_URL`, standby worker payload rejection, active worker payload acceptance, and endpoint-level fail-fast for graph/simulation/report before any task or billing reservation is created. I also wrote the operational runbook [docs/maintenance_window_worker_cutover.md](/Users/alexanderivenski/Projects/AgenikPredict/docs/maintenance_window_worker_cutover.md) so the next Railway cutover happens under a deterministic maintenance sequence instead of ad hoc deploy nudges.
- Comparison status: `AHEAD`
- Evidence:
  - `cd backend && uv run python -m compileall app worker.py run.py` -> success
  - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
  - New runtime assertions from the regression harness:
    - graph build under standby worker -> `503`, no task created
    - simulation prepare under standby worker -> `503`, no task created
    - report generate under standby worker -> `503`, no task created, no pending billing reservation
    - web boot with `TASK_EXECUTION_MODE=worker` and no `WORKER_HEALTHCHECK_URL` -> validation failure
- Next action: Use the new runbook for the next maintenance-window cutover attempt. Operationally, the worker must be activated and proven healthy first; only after that should web flip to `TASK_EXECUTION_MODE=worker`. Once that is green, the roadmap resumes with the scientific layer (`live evidence`, `structured probabilities`, `Prediction Ledger`).

### Item 52

- Plan item: Ship the new worker-cutover safeguards to the GitHub-backed production pipeline and validate the rollout baseline before the next live flip
- Work done: Synced only the safeguard-related files into the private GitHub source-of-truth repo and pushed commit `cdac5cc` (`Add worker cutover safety guardrails`). Railway picked the commit up automatically for both services. `AgenikPredict` deployment `021e23ae-5e36-4a5f-86e8-6d827324a251` reached `SUCCESS`; deployment logs confirm the expected backend startup path (`Building agenikpredict-backend @ file:///app/backend`, `gunicorn`, artifact probe success), and public `/health` remains green with `artifact_storage_mode=object_store`, `task_execution_mode=inline`, `task_store_mode=db`, and `task_read_source=db`. I also staged `WORKER_HEALTHCHECK_URL=http://agenikpredictworker.railway.internal/health` on the web service without forcing a deployment, so the next worker-mode flip has the correct preflight target. `AgenikPredictWorker` picked up the same commit as deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb`, but as of this checkpoint Railway still reports it as `DEPLOYING`, and the latest deployment-specific runtime logs are still blank even though build logs show `Using Detected Dockerfile` and a successful `Dockerfile.production` build. Because the worker rollout has not reached a healthy terminal state yet, I did not start the live maintenance-window cutover.
- Comparison status: `BLOCKED_BY_PLATFORM_ORCHESTRATION`
- Evidence:
  - Private GitHub repo advanced to commit `cdac5cc2340f8f3d00c3d44e0ddb2682cdf28642`
  - Railway web:
    - deployment `021e23ae-5e36-4a5f-86e8-6d827324a251` -> `SUCCESS`
    - deployment logs show gunicorn startup and artifact probe success on the new commit
    - `curl https://app.agenikpredict.com/health` -> `status=ok`, `task_execution_mode=inline`, `task_store_mode=db`, `task_read_source=db`, `artifact_storage_mode=object_store`
  - Railway worker:
    - deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb` -> still `DEPLOYING`
    - build logs show successful `Dockerfile.production` build, but deployment logs for this specific rollout are still empty
  - Web env staged for next cutover:
    - `WORKER_HEALTHCHECK_URL=http://agenikpredictworker.railway.internal/health`
- Next action: Do not flip `TASK_EXECUTION_MODE=worker` yet. First resolve the worker rollout blocker until deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb` reaches a healthy terminal state. Only then execute the maintenance-window runbook: activate worker, verify worker `/health` and logs, and only after that flip web to enqueue-only.

### Item 53

- Plan item: Execute the first maintenance-window worker-first cutover using the new safeguards
- Work done: After confirming both services were on safeguard commit `cdac5cc` and public web was healthy, I started the runbook exactly in the safe order: `worker first, web second`. I did not touch web. I changed only `AgenikPredictWorker` to `TASK_EXECUTION_MODE=worker` and `WORKER_STANDBY=false`, which triggered deployment `d0738ad0-3f65-475e-b3a1-3282c5dfc78d`. Railway built the image successfully, but the deployment never reached a healthy terminal state. `railway status --json` shows the latest deployment as `status=DEPLOYING` with `deploymentStopped=true`, and deployment-specific runtime logs stay empty. The previously healthy standby deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb` remains listed in `activeDeployments`, which means Railway did not actually give us a proven active worker consumer. Because the runbook requires proven active worker health before any web flip, I treated this as a hard blocker and rolled the worker env back to the safe baseline (`TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`). That spawned rollback deployment `728668ae-b3d9-4fa5-96aa-a14c8c22536f`; while Railway is again slow to settle the worker deployment, public web remains green and worker env is back on the standby-safe values.
- Comparison status: `BLOCKED_BY_PLATFORM_ORCHESTRATION`
- Evidence:
  - Pre-cutover baseline:
    - `curl https://app.agenikpredict.com/health` -> `status=ok`, `task_execution_mode=inline`, `task_store_mode=db`, `task_read_source=db`
    - recent web logs showed only startup and healthchecks, no visible active long-running work
  - Worker-first cutover attempt:
    - set `TASK_EXECUTION_MODE=worker`, `WORKER_STANDBY=false`
    - Railway deployment `d0738ad0-3f65-475e-b3a1-3282c5dfc78d`
    - build logs completed successfully
    - `railway status --json` for `AgenikPredictWorker` shows:
      - latest deployment `d0738ad0-3f65-475e-b3a1-3282c5dfc78d`
      - `status=DEPLOYING`
      - `deploymentStopped=true`
      - previous standby deployment `40a63f29-83d7-4fa8-9103-1fec65d13cfb` still present in `activeDeployments`
  - Safe rollback:
    - worker env restored to `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`
    - public web still returns `task_execution_mode=inline`
- Next action: Stop the live cutover attempt here. The blocker is now crisply isolated to Railway worker-service rollout/orchestration, not to app code, artifact sharing, or queue safety. The next step is not another blind flip; it is diagnosing why worker deployments are being left in `DEPLOYING` with `deploymentStopped=true` and empty runtime logs, then retrying `worker first` only after that platform-level behavior is resolved.

### Item 54

- Plan item: Re-run a worker-only activation from a clean standby baseline to distinguish transient rollout lag from a reproducible worker-service platform fault
- Work done: After rollback deployment `728668ae-b3d9-4fa5-96aa-a14c8c22536f` reached `SUCCESS`, I confirmed worker env was back to `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true` and public web was still healthy and inline. From that clean baseline, I repeated the worker-only activation without touching web. This created deployment `67c5ebce-1a92-4b51-8bf1-090ad2959050`. The second attempt again failed to reach a usable active state: Railway moved it through `INITIALIZING -> BUILDING -> DEPLOYING`, build logs completed successfully, but `railway status --json` again reported the latest deployment as `status=DEPLOYING` with `deploymentStopped=true`, and deployment-specific runtime logs remained empty. That reproduces the same worker-service orchestration failure independently of the first attempt. I therefore rolled the worker env back again to `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`, which triggered rollback deployment `98f8ce78-063b-479c-99df-d482f04e9d58`. Public web remains on deployment `021e23ae-5e36-4a5f-86e8-6d827324a251` and stays healthy in inline mode.
- Comparison status: `BLOCKED_BY_PLATFORM_ORCHESTRATION`
- Evidence:
  - Clean baseline before retry:
    - `AgenikPredictWorker` deployment `728668ae-b3d9-4fa5-96aa-a14c8c22536f` -> `SUCCESS`
    - worker vars: `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`
    - public web `/health` -> `task_execution_mode=inline`, `status=ok`
  - Reproduced failure on second worker-only activation:
    - active attempt deployment `67c5ebce-1a92-4b51-8bf1-090ad2959050`
    - build logs completed successfully
    - `railway status --json` -> latest deployment `67c5ebce...`, `status=DEPLOYING`, `deploymentStopped=true`
    - deployment-specific runtime logs stayed empty again
  - Safe rollback re-applied:
    - worker vars restored to `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`
    - rollback deployment `98f8ce78-063b-479c-99df-d482f04e9d58` started
    - public web still healthy and untouched
- Next action: Treat this as a reproducible Railway worker-service rollout fault. Do not attempt any web flip until the worker service can complete an active deployment without `deploymentStopped=true`. The next productive step is a focused worker-service diagnosis or Railway support escalation with the exact failing deployment IDs (`d0738ad0...`, `67c5ebce...`) and the fact that both were built successfully but left in `DEPLOYING` with empty runtime logs.

### Item 55

- Plan item: Create a fresh parallel worker service to distinguish service-specific Railway rollout faults from app/runtime faults
- Work done: I created a new Railway service, `AgenikPredictWorkerCanary` (`8bb77a24-7773-4531-af62-219c74624602`), instead of continuing to fight the existing `AgenikPredictWorker`. I copied the existing worker environment onto the canary service, excluding only `RAILWAY_*` variables and `RAILWAY_SERVICE_AGENIKPREDICT_URL`, and confirmed the new service had the expected safe baseline: `SERVICE_ROLE=worker`, `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`, `TASK_STORE_MODE=db`, `TASK_READ_SOURCE=db`, `ARTIFACT_STORAGE_MODE=object_store`, with `DATABASE_URL` and object-store credentials present. I then deployed the known-good safeguard snapshot `cdac5cc` directly to the canary service as deployment `e455f254-1386-4978-9843-dd8f65555abf`.
- Comparison status: `WORKAROUND_PATH_VALIDATED`
- Evidence:
  - New worker canary service:
    - name: `AgenikPredictWorkerCanary`
    - service id: `8bb77a24-7773-4531-af62-219c74624602`
  - Canary baseline env:
    - `SERVICE_ROLE=worker`
    - `TASK_EXECUTION_MODE=inline`
    - `WORKER_STANDBY=true`
    - `TASK_STORE_MODE=db`
    - `TASK_READ_SOURCE=db`
    - `ARTIFACT_STORAGE_MODE=object_store`
    - `DATABASE_URL` present
  - Canary standby deployment:
    - deployment `e455f254-1386-4978-9843-dd8f65555abf`
    - build time `509.13s`
    - final status `SUCCESS`
    - runtime logs showed:
      - `Starting standby worker artifact probe: mode=object_store`
      - `Standby worker artifact probe succeeded: mode=object_store`
      - `Worker process is in standby because TASK_EXECUTION_MODE=inline`
- Next action: Promote only the canary service to active worker mode while keeping public web untouched. If the canary can reach `SUCCESS` with a real worker loop, then the blocker is isolated to the original worker service and the cutover path can proceed through the canary instead.

### Item 56

- Plan item: Prove a real active worker loop on the new canary service before any web cutover
- Work done: I switched only `AgenikPredictWorkerCanary` from standby to active mode by setting `TASK_EXECUTION_MODE=worker`, `WORKER_STANDBY=false`, and `TASK_WORKER_ID=worker-canary-1`. This created canary deployment `9031b625-99c2-4224-8ee6-b21e55a1eca5`. Unlike the original worker service, the canary deployment completed successfully and emitted normal runtime logs. The logs show full backend startup, successful object-store probe, the worker health server listening, and the task worker loop starting in active mode. This is the first live proof that the current codebase, environment shape, task DB mode, and object-store artifact backend can run a dedicated active worker on Railway.
- Comparison status: `ACTIVE_WORKER_PROVEN_VIA_CANARY`
- Evidence:
  - Canary active deployment:
    - `9031b625-99c2-4224-8ee6-b21e55a1eca5` -> `SUCCESS`
  - Canary runtime logs:
    - `Artifact store probe succeeded: mode=object_store`
    - `Worker health server listening on 0.0.0.0:8080/health`
    - `Task worker started: mode=worker poll_interval=2.0s batch_size=10`
  - Original worker remains safely rolled back:
    - `AgenikPredictWorker` latest deployment `98f8ce78-063b-479c-99df-d482f04e9d58` -> `SUCCESS`
    - still on `TASK_EXECUTION_MODE=inline`, `WORKER_STANDBY=true`
  - Public web remains untouched and safe:
    - `https://app.agenikpredict.com/health` still reports inline web execution
- Next action: Use the canary worker as the new cutover target. Update web to point `WORKER_HEALTHCHECK_URL` at `http://agenikpredictworkercanary.railway.internal/health`, then flip web to `TASK_EXECUTION_MODE=worker` and run a live smoke to prove that long-running tasks survive web restarts because they are now executed by the dedicated canary worker.

### Item 57

- Plan item: Cut public web over to the proven canary worker and validate the real worker-only dispatch path
- Work done: I first flipped `AgenikPredict` web to `TASK_EXECUTION_MODE=worker` with `WORKER_HEALTHCHECK_URL=http://agenikpredictworkercanary.railway.internal/health`, which produced web deployment `5b2792c7-fa8f-4d1e-96ee-fb73e8c6021d` and moved public `/health` to `task_execution_mode=worker`. A live smoke then showed the worker-health gate rejecting `/api/graph/build` with `503` and `connection refused` to that URL. I traced the problem to the private-network port: the canary runtime logs clearly show the worker health server listening on `0.0.0.0:8080`, so web had been probing port `80`. I corrected web to `WORKER_HEALTHCHECK_URL=http://agenikpredictworkercanary.railway.internal:8080/health`, which created deployment `93d42022-d8a1-4568-9df7-d2bb842e41c9`. That deployment reached `SUCCESS`. I then ran a live smoke again through the public app using demo auth and a small uploaded text document. Web logs confirmed that ontology generation completed and graph build was enqueued without local dispatch. Canary worker logs confirmed it claimed the graph-build task, and the task API showed an active processing task with fresh heartbeats and progressing Zep work.
- Comparison status: `WORKER_CUTOVER_SUCCEEDED`
- Evidence:
  - First cutover attempt surfaced the port issue:
    - web deployment `5b2792c7-fa8f-4d1e-96ee-fb73e8c6021d`
    - `/api/graph/build` returned `503`
    - error: `Worker healthcheck request failed for http://agenikpredictworkercanary.railway.internal/health: [Errno 111] Connection refused`
  - Corrected worker health URL:
    - `WORKER_HEALTHCHECK_URL=http://agenikpredictworkercanary.railway.internal:8080/health`
    - web deployment `93d42022-d8a1-4568-9df7-d2bb842e41c9` -> `SUCCESS`
  - Public health after successful cutover:
    - `https://app.agenikpredict.com/health` -> `task_execution_mode=worker`, `artifact_storage_mode=object_store`, `task_store_mode=db`, `task_read_source=db`
  - Live smoke proof:
    - web runtime logs:
      - `Created graph build task: task_id=a7c717f1-ce8c-44e7-a397-9ef36b8a6e92`
      - `Task enqueued without local dispatch because TASK_EXECUTION_MODE=worker`
    - canary worker runtime logs:
      - `Worker claimed task: task_id=a7c717f1-ce8c-44e7-a397-9ef36b8a6e92 worker_id=worker:worker-canary-1`
      - `[a7c717f1-ce8c-44e7-a397-9ef36b8a6e92] Starting graph build...`
    - task API state:
      - `status=processing`
      - `attempt_count=1`
      - `last_heartbeat_at=2026-03-18T18:46:57.660305`
      - `message='Zep processing... 7/37 done, 30 pending (67s)'`
- Next action: Treat the runtime-substrate cutover as complete enough to move the roadmap forward. The next product block is the scientific layer: add live evidence tools to `ReportAgent`, then structured probability outputs, then the first `Prediction Ledger`/backtest pilot. The original `AgenikPredictWorker` can remain in standby while the canary worker carries production task execution.

### Item 58

- Plan item: Day 3 scientific layer v1 — add live-current-world evidence tools to `ReportAgent` without changing UI or widening the API surface
- Work done: I implemented a new backend-only service, [live_evidence.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/live_evidence.py), with graceful degradation, short timeouts, and simple in-memory caching. It provides two read-only tools for the report layer: `live_news_brief` (recent headlines via Google News RSS search) and `live_market_snapshot` (live quotes via the existing Twelve Data integration). I added corresponding config flags and defaults in [config.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/config.py) and [.env.example](/Users/alexanderivenski/Projects/AgenikPredict/.env.example). I then wired these tools into [report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py) by extending `_define_tools()`, `_execute_tool()`, tool validation, and the per-section tool inventory so the ReACT loop can call live tools alongside graph retrieval and agent interviews. The integration is backward compatible: if live evidence is disabled or market data is unavailable, the tools return structured warning text instead of raising and the report path still works.
- Comparison status: `ON_TRACK`
- Evidence:
  - New backend live evidence layer:
    - `backend/app/services/live_evidence.py`
    - read-only, cached, timeout-bounded
    - providers:
      - Google News RSS for recent headlines
      - Twelve Data for live market snapshots
  - ReportAgent integration:
    - new tools: `live_news_brief`, `live_market_snapshot`
    - dynamic tool registration via `self.tools`
    - execution paths added in `_execute_tool()`
    - tool validation accepts the new live tool names
    - section loop now derives `all_tools` from `self.tools`
  - Local verification:
    - `cd backend && uv run python -m compileall app` -> success
    - targeted Python check with mocked RSS and market data -> `live_evidence_ok`
    - `ReportAgent` instance exposes both new live tools
- Next action: Move to the next scientific-layer block: structured probability outputs. That means teaching `ReportAgent` to emit a stable `bull/base/bear` or equivalent scenario block with timeframe, drivers, risks, and explicit probability fields, while preserving the current markdown report format.

### Item 59

- Plan item: Day 4 scientific layer v1 — add structured scenario probabilities to `ReportAgent` while preserving backward-compatible report loading and markdown output
- Work done: I extended [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py) so completed reports can generate and persist a structured `prediction_summary` with `Bull case`, `Base case`, and `Bear case` scenarios. The new flow runs as a non-blocking post-pass after the core markdown report is assembled: `_generate_prediction_summary()` calls `chat_json()` with a constrained JSON schema prompt, `_normalize_prediction_summary()` coerces the output into a stable contract, `ReportManager._format_prediction_summary_markdown()` renders a human-readable `## Scenario Outlook` block, and `ReportManager.save_report()` persists the structured payload alongside existing report metadata. During verification I fixed two real regressions: first, probability normalization now uses deterministic remainder distribution so the three scenario percentages always sum to 100 without drifting on rounding edges; second, `_post_process_report()` now preserves the scenario heading instead of demoting it to bold text. The verification also exposed a storage-contract bug in [backend/app/services/artifact_store.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/artifact_store.py): `ensure=True` was being ignored whenever `sync=True`, which meant report assembly could still fail on a missing directory. I fixed that in both local and object-store backends and made `assemble_full_report()` explicitly create/sync the report folder before writing `full_report.md`.
- Comparison status: `AHEAD`
- Evidence:
  - Structured probability/report changes:
    - `Report.prediction_summary`
    - `_generate_prediction_summary()`
    - `_normalize_prediction_summary()`
    - `_normalize_probability_values()`
    - `ReportManager._format_prediction_summary_markdown()`
    - `ReportManager.save_prediction_summary()`
    - `ReportManager.get_report()` fallback loading for `prediction_summary`
  - Markdown/rendering safeguard:
    - `_post_process_report()` now preserves `## Scenario Outlook`
  - Artifact store fix discovered during verification:
    - `artifact_store.get_resource_dir(..., ensure=True, sync=True)` now honors both flags
  - Local verification:
    - `cd backend && uv run python -m compileall app` -> success
    - targeted Python check covering:
      - probability generation/normalization
      - scenario markdown rendering
      - preservation of `## Scenario Outlook`
      - `save_report()` / `get_report()` round-trip for `prediction_summary`
      - result: `probability_layer_ok`
- Next action: Move to the next scientific-layer block: `Prediction Ledger`. That means introducing a structured store for emitted scenarios/probabilities so future backtesting and calibration can measure outcomes without parsing markdown.

### Item 60

- Plan item: Day 4.5 scientific layer v1 — introduce a DB-backed `Prediction Ledger` so structured scenario outputs are queryable without parsing markdown
- Work done: I added [backend/app/models/prediction_ledger.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/prediction_ledger.py) as a new DB-backed store for scenario-level predictions. Each completed report can now write one row per scenario with `report_id`, `simulation_id`, `graph_id`, `project_id`, `owner_id`, scenario name/order, probability, timeframe, forecast horizon, summary, drivers, risks, assumptions, confidence note, caveats, and placeholder outcome fields for future backtesting. I initialized the schema from startup in [backend/app/__init__.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/__init__.py), wired [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py) so `ReportManager.save_report()` best-effort syncs the ledger whenever `prediction_summary` exists, and added a ledger fallback in `get_report()` so a report can reconstruct `prediction_summary` from DB if needed. I also added two read-only endpoints in [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py): `GET /api/report/<report_id>/predictions` and `GET /api/report/by-simulation/<simulation_id>/predictions`. During verification I confirmed the full round-trip on a synthetic owned project/simulation/report path.
- Comparison status: `AHEAD`
- Evidence:
  - New DB-backed ledger:
    - `backend/app/models/prediction_ledger.py`
    - `PredictionLedgerManager.init_db()`
    - `PredictionLedgerManager.sync_report_prediction_summary()`
    - `PredictionLedgerManager.list_predictions()`
    - `PredictionLedgerManager.get_prediction_summary()`
  - Startup wiring:
    - `PredictionLedgerManager.init_db()` added in `backend/app/__init__.py`
  - Report integration:
    - `ReportManager.save_report()` best-effort sync
    - `ReportManager.get_report()` fallback to ledger summary
  - Read-only API:
    - `GET /api/report/<report_id>/predictions`
    - `GET /api/report/by-simulation/<simulation_id>/predictions`
  - Local verification:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - targeted Flask/test-client verification:
      - synthetic owned project + simulation created
      - synthetic completed report saved with `prediction_summary`
      - ledger row count = 3
      - probabilities sum to `100`
      - `PredictionLedgerManager.get_prediction_summary()` reconstructs the structured block
      - both new API endpoints return `200`
      - result: `prediction_ledger_ok`
- Next action: Move to the next scientific-layer block: outcome/backtest groundwork on top of the ledger. The immediate target is the smallest slice that can record realized outcomes and compute first-pass quality metrics without touching the UI.

### Item 61

- Plan item: Day 5 backtest groundwork — add minimal outcome tracking and baseline prediction metrics on top of the new ledger
- Work done: I extended [backend/app/models/prediction_ledger.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/prediction_ledger.py) with `get_prediction()`, `record_outcome()`, and `compute_metrics()`. This gives the ledger an initial scoring loop: prediction rows can now be marked as `observed`, `not_observed`, `partial`, or `pending`, and the backend can compute first-pass metrics including settled vs pending counts, average probability by realized status, and a scenario-level Brier-style score. I then added two thin API surfaces in [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py): `POST /api/report/predictions/<prediction_id>/outcome` and `GET /api/report/predictions/metrics`. Both routes use existing ownership checks through the prediction’s simulation/project chain, so they remain aligned with the app’s current access model. I verified the full loop with a synthetic owned project/simulation/report path: write report -> ledger rows created -> record outcomes through the API -> read aggregate metrics through the API.
- Comparison status: `ON_TRACK`
- Evidence:
  - New ledger capabilities:
    - `PredictionLedgerManager.get_prediction()`
    - `PredictionLedgerManager.record_outcome()`
    - `PredictionLedgerManager.compute_metrics()`
  - New API:
    - `POST /api/report/predictions/<prediction_id>/outcome`
    - `GET /api/report/predictions/metrics`
  - Local verification:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - targeted Flask/test-client verification:
      - synthetic completed report saved with `prediction_summary`
      - two outcome writes returned `200`
      - metrics endpoint returned `200`
      - verified:
        - `total_predictions = 3`
        - `settled_predictions = 2`
        - `observed_count = 1`
        - `not_observed_count = 1`
        - `brier_score` present
      - result: `prediction_metrics_ok`
  - Independent reviewer:
    - reviewer request was issued but timed out before returning findings
- Next action: Deploy the scientific-layer changes together in one controlled backend rollout, then run a live smoke on report generation to confirm the new `live evidence`, `Scenario Outlook`, `Prediction Ledger`, and metrics paths behave correctly in production. After that, the next substantial product step is a true historical backtest dataset rather than more storage scaffolding.

### Item 62

- Plan item: Deploy the scientific-layer backend changes to production and verify them on a real completed report
- Work done: I deployed the backend scientific layer to production in three steps through the private GitHub source repo: `31aaca8` (`feat: add report prediction ledger and live evidence`), `d2bfb66` (`fix: repair malformed structured prediction summaries`), and `2c5925d` (`fix: backfill missing report prediction summaries`). I then ran a real production report generation on `simulation_id=sim_351ed9f941be`. The worker path completed end-to-end on `AgenikPredictWorkerCanary` for `report_id=report_3df60809f7cd`, and worker logs confirmed live execution of the new scientific layer, including `live_market_snapshot`, all four report sections, final assembly, and the new `Generating structured scenario outlook...` stage. That smoke exposed a real production bug: the structured scenario JSON sometimes came back malformed from the LLM, which caused `_generate_prediction_summary()` to fail, leaving the completed report without `prediction_summary` or ledger rows. I fixed that by switching the prediction path in [backend/app/services/report_agent.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/services/report_agent.py) to `chat_json_with_fallback()` so the existing JSON-repair flow is actually used. I also added a recovery path in [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py): `GET /api/report/<report_id>/predictions?backfill=true` now regenerates missing structured predictions from the saved markdown of a completed report and persists them through `ReportManager.save_report()`, which also syncs the ledger.
- Comparison status: `AHEAD`
- Evidence:
  - Production commits:
    - `31aaca8`
    - `d2bfb66`
    - `2c5925d`
  - Live report smoke:
    - simulation: `sim_351ed9f941be`
    - task: `48792a39-547f-4c9e-847a-3bccc40d8906`
    - report: `report_3df60809f7cd`
    - progress reached:
      - `95` `Assembling complete report...`
      - `97` `Generating structured scenario outlook...`
      - `100` `Report generation complete`
  - Production worker logs confirmed:
    - live scientific-tool execution
    - all section saves through `section_04.md`
    - original failure signature:
      - `Structured prediction summary generation failed: Invalid JSON format from LLM`
  - Local verification:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
    - targeted backfill verification -> `report_prediction_backfill_ok`
  - Live recovery verification after `2c5925d`:
    - `GET /api/report/report_3df60809f7cd/predictions?backfill=true` -> `count = 3`
    - names = `Bull case`, `Base case`, `Bear case`
    - probabilities = `25`, `50`, `25`
    - `GET /api/report/report_3df60809f7cd` -> `has_prediction_summary = true`
    - `GET /api/report/predictions/metrics?report_id=report_3df60809f7cd` -> `total_predictions = 3`, `pending_predictions = 3`
- Next action: The backend scientific layer is now live and verified on a real production report. The next roadmap step is the first historical backtest loop: curate a pilot dataset, mark outcomes, and start calibration measurements on actual completed reports.

### Item 63

- Plan item: Start the `historical/backtest` workstream now that production scientific-layer builds are green
- Work done: I rechecked current Railway state before starting the next block. All core services were healthy: `AgenikPredict`, `AgenikPredictWorker`, and `AgenikPredictWorkerCanary` all reported `SUCCESS`, and live `/health` returned `status=ok`, `task_execution_mode=worker`, `task_store_mode=db`, `task_read_source=db`, `artifact_storage_mode=object_store`. I also reviewed fresh production logs and confirmed the recent scientific-layer code was already live and executing. With runtime stable, I implemented the first historical/backtest slice. I added [backend/app/models/historical_backtest.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/models/historical_backtest.py) and a curated pilot dataset in [backend/app/data/historical_backtest_cases.json](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/data/historical_backtest_cases.json). The dataset contains five starter cases spanning AI governance, banking, enterprise outage, crypto collapse, and social-platform launch dynamics. I then extended [backend/app/api/report.py](/Users/alexanderivenski/Projects/AgenikPredict/backend/app/api/report.py) with three historical/backtest routes:
  - `GET /api/report/backtest/cases`
  - `GET /api/report/backtest/cases/<case_id>`
  - `POST /api/report/backtest/reports/<report_id>/evaluate`
  The evaluate route batch-applies outcomes to a completed report’s `Bull/Base/Bear` predictions, optionally links the run to a curated historical case, and immediately returns updated metrics. During verification I found and fixed two defects in the first pass: an invalid `Report` attribute dependency inside the backfill helper and a positional call into the keyword-only `PredictionLedgerManager.record_outcome()` API. After that, local evaluation verification passed. I then pushed the historical slice to the private GitHub source repo as `2f4c354` (`feat: add pilot historical backtest cases`), waited for the production web deploy to reach `SUCCESS`, and confirmed the new historical dataset endpoint is live.
- Comparison status: `ON_TRACK`
- Evidence:
  - Railway recheck before starting:
    - `AgenikPredict` -> `SUCCESS`
    - `AgenikPredictWorker` -> `SUCCESS`
    - `AgenikPredictWorkerCanary` -> `SUCCESS`
    - live `/health` returned `status=ok`
  - New historical files:
    - `backend/app/models/historical_backtest.py`
    - `backend/app/data/historical_backtest_cases.json`
  - New historical routes:
    - `GET /api/report/backtest/cases`
    - `GET /api/report/backtest/cases/<case_id>`
    - `POST /api/report/backtest/reports/<report_id>/evaluate`
  - Local verification:
    - `cd backend && uv run python -m compileall app/api/report.py app/models/historical_backtest.py` -> success
    - targeted Flask/test-client verification -> `historical_backtest_ok`
      - listed historical cases
      - fetched one case by id
      - created synthetic completed report with prediction summary
      - batch-applied outcomes for `Bull/Base/Bear`
      - confirmed `applied_count = 3`
      - confirmed `settled_predictions = 3`
  - Production deploy:
    - private repo commit: `2f4c354`
    - `AgenikPredict` deployment `334d47c9-1e1e-4232-a102-6d25ca612b0b` -> `SUCCESS`
  - Live verification:
    - `GET /api/report/backtest/cases`
    - response:
      - `version = pilot-v1`
      - `case_count = 5`
      - first case = `openai-board-crisis-2023`
- Next action: The first historical slice is live. The next step is to connect real completed reports to this pilot dataset and start producing calibration views per historical cohort instead of only per-report metrics.

### Item 64

- Plan item: Extend the scientific layer with language-consistent outputs and cohort-level historical calibration
- Work done: The backend and frontend now carry `language_used` through project ontology generation, simulation preparation, profile/config reads, and report generation, with conflict detection when an in-flight task already owns a different language. I added locale normalization helpers in `backend/app/utils/locale.py`, persisted `language_used` in project/simulation/report/config state, passed the selected language into profile generation and report generation, and localized the structured scenario block inside report markdown. On the frontend, `GraphPanel` now syncs report language with the selected app locale and emits report-config changes, while `SimulationRunView` wires that config into `Step3Simulation`, which forwards `language`, `custom_persona`, and `report_variables` into report generation. I also extended the historical slice with cohort-level calibration metrics via `GET /api/report/backtest/metrics`, so completed historical evaluations can now be aggregated across reports instead of only report-by-report. During review, I fixed four concrete regressions before deployment: `force_regenerate=true` could silently reuse an active report task in the wrong language, simulation/report fast-path status responses dropped `language_used`, Twitter `/profiles` still read JSON instead of the generated CSV, and localized historical outcome keys (`Бычий сценарий`, etc.) were not matched during evaluation. Finally, I repaired the CI regression harness by updating the mocked profile generator signature to accept `language=...`.
- Comparison status: `ON_TRACK`
- Evidence:
  - Language propagation files:
    - `backend/app/utils/locale.py`
    - `backend/app/models/project.py`
    - `backend/app/api/graph.py`
    - `backend/app/api/simulation.py`
    - `backend/app/api/report.py`
    - `backend/app/services/oasis_profile_generator.py`
    - `backend/app/services/simulation_config_generator.py`
    - `backend/app/services/simulation_manager.py`
    - `backend/app/services/report_agent.py`
    - `frontend/src/components/GraphPanel.vue`
    - `frontend/src/components/Step3Simulation.vue`
    - `frontend/src/views/SimulationRunView.vue`
  - Historical cohort aggregation:
    - `backend/app/models/prediction_ledger.py`
    - `backend/app/api/report.py`
  - Verification:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - `npm run build` -> success
    - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
    - targeted route-level contract verification -> `route_contract_ok`
    - targeted manager-level historical aggregation verification -> `historical_metrics_ok`
  - Reviewer findings addressed:
    - `force_regenerate` language conflict reuse
    - missing `language_used` in status fast-paths
    - Twitter CSV profile reads
    - localized historical outcome matching
    - CI mock signature mismatch
- Next action: Commit and deploy the language + cohort-metrics slice to the private GitHub source repo, monitor Railway, and run a production smoke focused on `worker report generation -> predictions/backtest metrics` plus language-consistent response metadata.

### Item 65

- Plan item: Roll out the language + cohort-metrics slice through the private GitHub source repo and confirm Railway adoption
- Work done: I created a clean clone of the Railway-linked private repo (`codex-agenic-predict-private`), overlaid only the verified language/historical files from the working tree, committed them as `b593078` (`feat: align language flow and add cohort backtest metrics`), and pushed to `main`. Railway immediately started GitHub-based deployments for `AgenikPredict` and `AgenikPredictWorker` on commit `b593078d5857731c8e8199f6ff97e313e4cb77d5`. I rechecked current production health during rollout and confirmed that the live app stayed healthy on the previous release while the new GitHub-based builds were still pending.
- Comparison status: `BLOCKED`
- Evidence:
  - Private repo push:
    - `git ls-remote https://github.com/alexprime1889-prog/codex-agenic-predict-private.git` -> new `main` head `b593078`
    - commit message: `feat: align language flow and add cohort backtest metrics`
  - Local verification before push:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - `npm run build` -> success
    - `bash scripts/verify_production_fixes.sh` -> `verify_production_fixes: PASS`
    - route-level contract smoke -> `route_contract_ok`
  - Railway deployments triggered from GitHub:
    - `AgenikPredict` deployment `6a1f6b5f-a732-4707-b5ee-c3b434699869` -> `BUILDING`
    - `AgenikPredictWorker` deployment `b9426516-97ed-42af-90cb-2691da765c9a` -> `BUILDING`
    - both show `commitHash = b593078d5857731c8e8199f6ff97e313e4cb77d5`
  - Build logs:
    - both services reached the final Dockerfile stages through `[production 11/11] WORKDIR /app/backend`
    - both logs then showed registry auth (`[auth] sharing credentials for production-us-east4-eqdc4a.railway-registry.com`)
    - no explicit build error appeared in available logs
  - Live production remained healthy during the blocked rollout:
    - `GET https://app.agenikpredict.com/health` -> `status=ok`
    - current live still reports `task_execution_mode=worker`, `artifact_storage_mode=object_store`, `task_store_mode=db`
- Root cause: The current blocker is no longer in repository code or local verification. Railway is keeping the GitHub-triggered `AgenikPredict` and `AgenikPredictWorker` deployments in an unusually long `BUILDING` state after image assembly/registry-auth stages, without exposing a concrete failure line in the fetched build logs.
- Recovery plan: Continue monitoring these two deployments for terminal state. If they do not resolve, inspect Railway build/deploy logs again and either retry the GitHub deployment or treat it as a Railway platform-side stuck build while keeping production on the last healthy commit.
- Revised ETA: Deployment confirmation is pending Railway completing or failing the two active GitHub-based builds.

### Item 66

- Plan item: Confirm the GitHub-based rollout of the language + cohort-metrics slice on live production and validate the new prod routes
- Work done: Railway eventually completed both GitHub-triggered deployments for commit `b593078d5857731c8e8199f6ff97e313e4cb77d5`. I verified that `AgenikPredict` and `AgenikPredictWorker` both reached `SUCCESS` with image digests, and then ran a live authenticated smoke against `app.agenikpredict.com`. Using `POST /api/auth/demo` for a demo JWT, I confirmed the new historical/calibration endpoints are active in production:
  - `GET /api/report/backtest/cases`
  - `GET /api/report/backtest/cases/openai-board-crisis-2023`
  - `GET /api/report/backtest/metrics`
  The metrics route returned the expected empty-cohort payload for the demo user (`evaluated_case_count = 0`), which is the correct behavior when no historical outcomes have been recorded yet.
- Comparison status: `ON_TRACK`
- Evidence:
  - Railway deployment terminal states:
    - `AgenikPredict` -> `6a1f6b5f-a732-4707-b5ee-c3b434699869 | SUCCESS | sha256:2f80c5b21215f211ad7a708f0cf127f8853528114bc4082584e065b75f9ba3e8`
    - `AgenikPredictWorker` -> `b9426516-97ed-42af-90cb-2691da765c9a | SUCCESS | sha256:f5050dd384715ac0b05cc40e47a5cdd55c62b2c0b5f6ee8c9b48177a6740fe59`
    - both on `commitHash = b593078d5857731c8e8199f6ff97e313e4cb77d5`
  - Live health:
    - `GET https://app.agenikpredict.com/health` -> `status=ok`
    - current live reports `artifact_storage_mode=object_store`, `task_execution_mode=worker`, `task_store_mode=db`
  - Live authenticated smoke:
    - `POST /api/auth/demo` -> `200`
    - `GET /api/report/backtest/cases` -> `200`, `dataset.version = pilot-v1`, `case_count = 5`
    - `GET /api/report/backtest/cases/openai-board-crisis-2023` -> `200`
    - `GET /api/report/backtest/metrics` -> `200`, `overall.evaluated_case_count = 0`
- Next action: The rollout is complete. The next roadmap step is product-facing: either (a) finish the remaining low-risk frontend i18n pass for Graph/Simulation chrome labels, or (b) move directly into the next scientific block: real evaluated reports against historical cases and calibration dashboards using the newly live cohort metrics route.

### Item 67

- Plan item: Close the remaining frontend language-consistency gap in Graph/Simulation UI chrome so panel labels, card metadata, and agent-configuration controls follow the selected locale
- Work done: I finished the targeted frontend i18n pass in the two residual components called out earlier:
  - `frontend/src/components/GraphPanel.vue`
  - `frontend/src/components/Step3Simulation.vue`
  The changes replaced hardcoded English UI strings with locale keys, made date/time formatting locale-aware, and added a locale-triggered graph rerender so graph fallback labels stay aligned with language changes. I also extended the locale packs for all supported languages (`en`, `ru`, `he`, `es`, `de`, `fr`, `it`, `pt`, `pl`, `nl`, `tr`, `ar`) with the new Graph/Simulation chrome keys. During verification, Vite caught a real `vue-i18n` parser issue: messages like `@{user}` were interpreted as linked-message syntax. I corrected that by moving `@` into the runtime interpolation payload and reran the build successfully.
- Comparison status: `ON_TRACK`
- Evidence:
  - Components updated:
    - `frontend/src/components/GraphPanel.vue`
    - `frontend/src/components/Step3Simulation.vue`
  - Locale packs updated:
    - `frontend/src/i18n/locales/en.json`
    - `frontend/src/i18n/locales/ru.json`
    - `frontend/src/i18n/locales/he.json`
    - `frontend/src/i18n/locales/es.json`
    - `frontend/src/i18n/locales/de.json`
    - `frontend/src/i18n/locales/fr.json`
    - `frontend/src/i18n/locales/it.json`
    - `frontend/src/i18n/locales/pt.json`
    - `frontend/src/i18n/locales/pl.json`
    - `frontend/src/i18n/locales/nl.json`
    - `frontend/src/i18n/locales/tr.json`
    - `frontend/src/i18n/locales/ar.json`
  - Verification:
    - `jq empty frontend/src/i18n/locales/*.json` -> success
    - first `npm run build` -> failed with `vue-i18n` message-compiler error on `@{user}`
    - post-fix `npm run build` -> success
    - regression grep over `GraphPanel.vue` and `Step3Simulation.vue` shows the targeted hardcoded English strings are no longer present as user-facing literals
- Residual risk:
  - This pass covered the two known residual components and their locale packs; it did not attempt a repo-wide audit for every possible hardcoded string outside these files.
  - Deployment has not been triggered yet for this UI-only slice.
- Next action: Wait for independent reviewer findings on the UI i18n pass. If no blocking issues surface, sync this frontend-only change set to the Railway-linked private GitHub repo and confirm the new locale-consistent UI build on production.

### Item 68

- Plan item: Roll out the UI-only Graph/Simulation i18n cleanup through the private GitHub Railway source and confirm the new web build on production
- Work done: I synced only the UI i18n slice plus execution logs into the clean Railway-linked private repo clone, committed it as `a2742b9` (`feat: localize graph and simulation chrome`), and pushed it to `main`. Railway picked up the new commit automatically for `AgenikPredict` and `AgenikPredictWorker`. The web service completed successfully and production health remained green with the expected worker-backed runtime flags. The non-active `AgenikPredictWorker` service is still formally in `DEPLOYING`, while the actually active `AgenikPredictWorkerCanary` service remains healthy on its prior successful deployment.
- Comparison status: `ON_TRACK`
- Evidence:
  - Private repo push:
    - `main` advanced from `b593078` to `a2742b9`
    - commit message: `feat: localize graph and simulation chrome`
  - Pre-push verification in the working tree:
    - `jq empty frontend/src/i18n/locales/*.json` -> success
    - `npm run build` -> success
  - Railway adoption:
    - `AgenikPredict` deployment `9e5c77f4-94fc-4081-9791-85640fc05029` -> `SUCCESS`
      - `commitHash = a2742b905aa8be46fc489eff05609e4ea71e8594`
      - `imageDigest = sha256:457ac237f3b5b93f74d31c76b45e6f03e45b679006dbdd692d39601c7d68551d`
    - `AgenikPredictWorker` deployment `5585a3c1-ec2e-4c4e-b55b-97c1a2346629` -> still `DEPLOYING`
      - same `commitHash = a2742b905aa8be46fc489eff05609e4ea71e8594`
      - no `imageDigest` yet
    - `AgenikPredictWorkerCanary` remains healthy:
      - `76dcbddb-0bae-4277-9838-7edcbc6fb9fc | SUCCESS | sha256:0497d3e25eb6298bcb29335c856e11b7673803ea386a9ac3aa9196caa3dba687`
  - Live web verification:
    - `GET https://app.agenikpredict.com/health` -> `200`
    - payload:
      - `status = ok`
      - `task_execution_mode = worker`
      - `task_store_mode = db`
      - `artifact_storage_mode = object_store`
      - `worker_consumer_active = false`
    - runtime logs for `AgenikPredict` show clean startup:
      - `Prediction ledger database initialized`
      - `Artifact store probe succeeded: mode=object_store`
      - `AgenikPredict Backend startup complete`
- Residual risk:
  - The passive `AgenikPredictWorker` service did not yet reach terminal state on this UI-only rollout, so Railway still shows one non-critical deployment in progress.
  - The live active worker path currently remains the healthy canary worker, not this passive service.
- Next action: Continue monitoring the passive worker deployment for terminal state, but treat the UI rollout as successful on the live web path. The next product move after this is either a browser-level locale smoke on the updated graph/simulation UI or a return to the historical-calibration block.

### Item 69

- Plan item: Address reviewer findings on the UI i18n pass before treating the slice as final
- Work done: Independent review found one medium issue and two low issues. I fixed the medium issue in `GraphPanel.vue`: changing the app locale no longer overwrites a manually chosen report language. I also fixed the low zero-state elapsed-time fallback in `Step3Simulation.vue`, so `0h 0m` now flows through the same i18n duration formatting as non-zero states. I intentionally did not expand this follow-up into a full localization of every frontend-generated simulation log line; that remains the only user-facing low residual in this slice. After the fixes, `npm run build` passed again.
- Comparison status: `ON_TRACK`
- Evidence:
  - Reviewer findings:
    - `Medium`: manual report-language choice could be overwritten by `watch(locale, ...)` in `frontend/src/components/GraphPanel.vue`
    - `Low`: zero-state elapsed time remained hardcoded as `0h 0m` in `frontend/src/components/Step3Simulation.vue`
    - `Low`: frontend-generated simulation log lines still contain English phrases
  - Fixes applied:
    - `frontend/src/components/GraphPanel.vue`
      - added manual-report-language preservation via `reportLanguageManuallySelected`
      - switched language select to explicit `handleReportLanguageChange`
    - `frontend/src/components/Step3Simulation.vue`
      - removed hardcoded `0h 0m` fallback and normalized zero-state through localized duration formatting
  - Verification:
    - `npm run build` -> success
- Residual risk:
  - Frontend-generated simulation log strings are still largely English; this is now the remaining low-priority localization gap inside `Step3Simulation.vue`.
  - Frontend i18n paths are still verified by build/regression scan rather than automated component tests.
- Next action: Sync this small follow-up fix to the private GitHub repo and let Railway roll the corrected UI slice.

### Item 70

- Plan item: Roll out the reviewer follow-up fix (`preserve report language selection`) and confirm the corrected web deployment
- Work done: I synced the follow-up fix into the clean private repo clone, committed it as `fc88b54` (`fix: preserve report language selection`), and pushed it to `main`. Railway started new deployments for `AgenikPredict` and `AgenikPredictWorker` on that commit. The web deployment reached `SUCCESS`, and live production health remained green with the expected worker-backed runtime flags. Railway still shows the passive `AgenikPredictWorker` deployment in `DEPLOYING`, but both web and worker build logs already show successful healthchecks, so this is now an orchestration/status-lag issue rather than an application failure.
- Comparison status: `ON_TRACK`
- Evidence:
  - Private repo push:
    - `main` advanced from `a2742b9` to `fc88b54`
    - commit message: `fix: preserve report language selection`
  - Pre-push verification:
    - `npm run build` -> success
  - Railway adoption:
    - `AgenikPredict` deployment `ce4f514c-4f80-4708-9798-51e68b08c51c` -> `SUCCESS`
      - `commitHash = fc88b54e411d1522af60412fee3d6910c38dfe60`
      - `imageDigest = sha256:463728cbad9336c9461b5722b96b3c39fb5ef254ef51556c64a21c4d2942678e`
    - `AgenikPredictWorker` deployment `e3eec8d9-9223-40b6-b01c-d3218be38fd0` -> still `DEPLOYING`
      - same `commitHash = fc88b54e411d1522af60412fee3d6910c38dfe60`
      - no `imageDigest` yet in deployment list
  - Build/runtime evidence:
    - `railway logs --service AgenikPredict --build --lines 80` -> build complete, healthcheck succeeded
    - `railway logs --service AgenikPredictWorker --build --lines 80` -> build complete, healthcheck succeeded
  - Live web verification:
    - `GET https://app.agenikpredict.com/health` -> `200`
    - payload still reports:
      - `status = ok`
      - `task_execution_mode = worker`
      - `task_store_mode = db`
      - `artifact_storage_mode = object_store`
      - `worker_consumer_active = false`
- Residual risk:
  - The remaining deployment lag is with the passive `AgenikPredictWorker` service record in Railway, not with the live web path or the active canary worker path.
- Next action: Treat the corrected UI slice as live on the web path and move the roadmap forward. The remaining follow-up on this area is optional low-priority cleanup of frontend-generated simulation log strings in `Step3Simulation.vue`.

### Item 71

- Plan item: Finish the last multilingual UI residual by localizing frontend-generated simulation log messages in `Step3Simulation.vue`
- Work done: I replaced the remaining hardcoded client-side simulation log messages in `frontend/src/components/Step3Simulation.vue` with i18n-backed messages and added the required keys across all supported locale files. This covers initialization, start/stop flow, dynamic graph-update mode, report-generation status, and per-platform round-progress logs. I also added a helper to render the selected report language in a localized label inside the log stream. The full locale set was updated: `en`, `ru`, `he`, `es`, `de`, `fr`, `it`, `pt`, `pl`, `nl`, `tr`, `ar`.
- Comparison status: `ON_TRACK`
- Evidence:
  - Code updates:
    - `frontend/src/components/Step3Simulation.vue`
    - `frontend/src/i18n/locales/en.json`
    - `frontend/src/i18n/locales/ru.json`
    - `frontend/src/i18n/locales/he.json`
    - `frontend/src/i18n/locales/es.json`
    - `frontend/src/i18n/locales/de.json`
    - `frontend/src/i18n/locales/fr.json`
    - `frontend/src/i18n/locales/it.json`
    - `frontend/src/i18n/locales/pt.json`
    - `frontend/src/i18n/locales/pl.json`
    - `frontend/src/i18n/locales/nl.json`
    - `frontend/src/i18n/locales/tr.json`
    - `frontend/src/i18n/locales/ar.json`
  - Verification:
    - `jq empty frontend/src/i18n/locales/*.json` -> success
    - `npm run build` -> success
- Result:
  - The last known multilingual gap in the Graph/Simulation UI path is now closed in the working tree.
- Next action: Sync this last frontend-only i18n pass to the Railway-linked private GitHub repo so the fully polished multilingual Step3 log experience reaches production.

### Item 72

- Plan item: Turn the AgenikPredict brand-identity request into a real working document artifact instead of leaving it as a prompt-only idea
- Work done: I created a first working brand identity document at `docs/brand_identity_agenikpredict.md`. The document covers brand core, positioning, audience framing, emotional promise, tone of voice, visual direction, multilingual brand rules, messaging pillars, do/don't guidance, and a brand manifesto so it can be used immediately for the website, pitch deck, investor materials, and video scripts.
- Comparison status: `AHEAD`
- Evidence:
  - New artifact:
    - `docs/brand_identity_agenikpredict.md`
  - Structure included:
    - brand core
    - positioning
    - messaging pillars
    - tone of voice
    - visual identity direction
    - multilingual rules
    - audience-specific framing
    - manifesto
- Result:
  - The user now has a concrete brand-identity source document inside the repo, not just a meta-prompt about how one could be created.
- Next action: Sync the new brand-identity document and the final multilingual `Step3Simulation` i18n polish to the Railway-linked private GitHub repo, then verify the resulting deployment state.

### Item 73

- Plan item: Finish the multilingual polish all the way through the GitHub/Railway path and confirm the working brand-identity artifact is stored in the repo
- Work done: I synced the final `Step3Simulation` multilingual log-localization slice, the updated execution logs, and the new `docs/brand_identity_agenikpredict.md` artifact into the Railway-linked private repo clone, committed them as `3135fa6`, and pushed to `alexprime1889-prog/codex-agenic-predict-private`. Railway picked up the commit for both `AgenikPredict` and `AgenikPredictWorker`. The web deployment reached `SUCCESS`, public `/health` stayed green, and the worker/canary build logs both reached successful healthchecks.
- Comparison status: `ON_TRACK`
- Evidence:
  - GitHub push:
    - private repo commit: `3135fa6961ee6ea0a34899563914d25585a34537`
    - commit message: `feat: finish multilingual simulation logs and add brand identity doc`
  - Local verification:
    - `jq empty frontend/src/i18n/locales/*.json` -> success
    - `npm run build` -> success
  - Railway:
    - `AgenikPredict` latest deployment `6ae30d35-50d8-4f0a-b1a6-64f96bacc0d7` -> `SUCCESS`
    - `AgenikPredictWorker` latest deployment `c33f1263-b6bd-4dd6-8e5b-b9e0efb32391` -> build log healthcheck succeeded, Railway status still displays `DEPLOYING`
    - `AgenikPredictWorkerCanary` build log healthcheck succeeded
  - Live health:
    - `GET https://app.agenikpredict.com/health` -> `200`
    - payload remained:
      - `status = ok`
      - `task_execution_mode = worker`
      - `task_store_mode = db`
      - `artifact_storage_mode = object_store`
- Result:
  - The last known multilingual UI tail in the Graph/Simulation flow is now deployed through the GitHub-backed Railway path.
  - AgenikPredict now also has a first-class brand-identity source document inside `docs/`.
- Next action: Use `docs/brand_identity_agenikpredict.md` as the source for website copy, deck messaging, and video creative while optionally monitoring the passive worker service until Railway stops showing stale `DEPLOYING`.

### Item 74

- Plan item: Advance the historical/calibration loop from static case listing into a real evaluation and operator-visibility workflow
- Work done: I extended the backtest/calibration layer in three connected ways. First, I upgraded `PredictionLedgerManager` so historical metrics now return richer cohort slices: domain breakdowns, scenario-type breakdowns, forecast-horizon breakdowns, calibration buckets, and recent evaluation groups, plus top-scenario hit-rate style metrics. Second, I refactored `backend/app/api/report.py` so historical evaluation can reuse one helper path, can auto-apply a case’s `suggested_outcomes`, and now supports batch evaluation via `POST /api/report/backtest/evaluate-batch`. Third, I added a new internal `Quality` tab to `frontend/src/views/AdminView.vue`, wired through `frontend/src/api/report.js`, so admins can see the quality loop instead of reading raw JSON only.
- Comparison status: `ON_TRACK`
- Evidence:
  - Backend:
    - `backend/app/models/prediction_ledger.py`
    - `backend/app/api/report.py`
  - Frontend:
    - `frontend/src/api/report.js`
    - `frontend/src/views/AdminView.vue`
  - Verification:
    - `cd backend && ARTIFACT_STORAGE_MODE=local TASK_EXECUTION_MODE=inline JWT_SECRET=test-secret uv run python -m compileall app worker.py run.py` -> success
    - `cd frontend && npm run build` -> success
    - targeted synthetic API smoke -> `historical_quality_ok`
      - created a temporary owned project/simulation/report
      - evaluated it through `POST /api/report/backtest/evaluate-batch` using a historical case’s `suggested_outcomes`
      - confirmed `GET /api/report/backtest/metrics` now returns populated:
        - `by_domain`
        - `by_scenario`
        - `by_horizon`
        - `calibration_buckets`
        - `recent_evaluations`
- Result:
  - The product now has a real operator path for historical evaluation and calibration review, not just a static pilot dataset and a single-report outcome endpoint.
- Next action: Sync this quality-loop slice to the Railway-linked private GitHub repo, deploy it, and then run a live smoke on the new `Quality` tab plus the batch historical evaluation route.

### Item 75

- Plan item: Push the historical quality loop into the live Railway web path and verify the new backtest metrics contract on production
- Work done: I synced the quality-loop slice into the clean private repo, committed and pushed it as `6c2136f`, and then monitored Railway rollout for both `AgenikPredict` and `AgenikPredictWorker`. Public health stayed green, but the live `/api/report/backtest/metrics` contract remained on the previous release shape. To separate code issues from platform issues, I triggered a manual `railway redeploy` for the web service, creating deployment `9456bd04-74bf-47d7-a4d6-e569352a9ce7`. That redeploy reproduced the same pattern as the auto-deploy: the new deployment remained `BUILDING`, showed `deploymentStopped=true` in Railway state, and never became the live web release, while the previous successful deployment continued serving traffic.
- Comparison status: `BLOCKED_ON_PLATFORM`
- Evidence:
  - GitHub push:
    - private repo commit: `6c2136f478973cd808dbbaa52017e141aa28b80b`
    - commit message: `feat: add historical quality loop dashboard`
  - Railway auto-deploys:
    - `AgenikPredict` latest deployment `72e282da-6cb0-4a10-bd31-f52b9f053e7f` -> `BUILDING`
    - `AgenikPredictWorker` latest deployment `59e9f39d-3bd1-484d-a843-7a6558573bc0` -> `BUILDING`
    - both carried commit `6c2136f478973cd808dbbaa52017e141aa28b80b`
- Railway manual redeploy:
    - `railway redeploy -s AgenikPredict -y --json` -> created `9456bd04-74bf-47d7-a4d6-e569352a9ce7`
    - latest web deployments `9456bd04...` and `72e282da...` both remained `BUILDING`
  - Railway canary isolation test:
    - created `AgenikPredictWebCanary` linked to the same private repo
    - its first deployment `82d50caa-7107-4a04-8563-1b2c983336d4` also entered `BUILDING` on commit `6c2136f478973cd808dbbaa52017e141aa28b80b`
    - repeated polling kept it in `BUILDING`, which means the stall is reproducible outside the original `AgenikPredict` service slot
  - Railway state:
    - `railway status --json` showed for `AgenikPredict` latest deployment:
      - `status = BUILDING`
      - `deploymentStopped = true`
      - `commitHash = 6c2136f478973cd808dbbaa52017e141aa28b80b`
    - the previous successful live deployment remained:
      - `6ae30d35-50d8-4f0a-b1a6-64f96bacc0d7` on commit `3135fa6961ee6ea0a34899563914d25585a34537`
  - Live prod checks:
    - `GET https://app.agenikpredict.com/health` -> `200`
    - payload stayed healthy:
      - `status = ok`
      - `task_execution_mode = worker`
      - `task_store_mode = db`
      - `artifact_storage_mode = object_store`
    - `GET /api/report/backtest/metrics` still returned only:
      - `dataset`
      - `items`
      - `overall`
    - which proves the new quality-loop release is not yet active on public web
- Result:
  - The historical quality loop is implemented, locally verified, and pushed to GitHub, but it is not yet live on production because Railway is repeatedly stalling between build and activation for web services in this project, including a fresh canary service.
- Next action: Treat the issue as a Railway project-level rollout blocker. Keep current live prod untouched, and use either Railway support/platform remediation or a different deployment slot/path before attempting to switch public traffic to the quality-loop release.

### Item 76

- Plan item: Remove the most likely deployment bottleneck by slimming the web runtime image while keeping the worker simulation stack intact
- Work done: I separated the OASIS simulation dependencies from the base backend runtime. `camel-oasis` and `camel-ai` were moved out of core dependencies into a new optional `simulation` extra in `backend/pyproject.toml`. Then I updated `Dockerfile.production` to use `ARG SERVICE_ROLE` at build time so Railway web services install only the base backend dependencies, while worker services still install `--extra simulation`. This directly targets the most suspicious part of the stuck rollout path: huge web images pulling `torch`, `transformers`, and related simulation-only transitive packages even though the web runtime does not import them.
- Comparison status: `ON_TRACK`
- Evidence:
  - Files changed:
    - `backend/pyproject.toml`
    - `backend/uv.lock`
    - `Dockerfile.production`
  - Local dependency verification:
    - `cd backend && uv lock` -> success
    - `cd backend && uv sync --frozen --no-dev` -> removed the simulation stack from the base web env
    - `cd backend && env JWT_SECRET=test-secret TASK_EXECUTION_MODE=inline ARTIFACT_STORAGE_MODE=local uv run python -c "from app import create_app; create_app(); print('web_boot_ok')"` -> `web_boot_ok`
    - `cd backend && uv sync --frozen --no-dev --extra simulation` -> success
    - `cd backend && env JWT_SECRET=test-secret TASK_EXECUTION_MODE=worker ARTIFACT_STORAGE_MODE=local uv run python - <<'PY' ...` -> `simulation_manager_ok True`
    - `cd backend && env JWT_SECRET=test-secret TASK_EXECUTION_MODE=worker ARTIFACT_STORAGE_MODE=local uv run python -m compileall app worker.py run.py` -> success
- Result:
  - The repo now supports a materially lighter web image without sacrificing the worker simulation path.
  - The next live test should be a GitHub/Railway deploy of this split-dependency build to the existing `AgenikPredictWebCanary` slot first.
- Next action: Sync the dependency-split fix to the private GitHub repo, redeploy `AgenikPredictWebCanary`, and verify whether the lighter web image finally reaches terminal activation and exposes the new backtest quality contract.

### Item 77

- Plan item: Prove the dependency-split fix removes the Railway web rollout blocker and gets the historical quality loop live
- Work done: I synced the split-dependency fix to the Railway-linked private repo, committed it as `201e045`, and let Railway roll it out. This time the web path behavior materially changed: both `AgenikPredictWebCanary` and the public `AgenikPredict` service moved past the old stuck `BUILDING` phase and reached `SUCCESS` with image digests. I then verified both the public domain and the canary domain live over HTTP, confirming that the historical quality metrics contract is now active in both places.
- Comparison status: `RECOVERED_AND_LIVE`
- Evidence:
  - GitHub push:
    - private repo commit: `201e0459c6670b00dfb9d39e6f74f52f8e02a655`
    - commit message: `build: split web and simulation dependencies`
  - Railway deployments:
    - `AgenikPredictWebCanary` deployment `3298eb95-31ff-4218-b578-af57bf59f45c` -> `SUCCESS`
      - image digest: `sha256:7d8c9a54837bd505a566c768e3d38e86c8d0ba45cebbabfc84ded39ef21a04c4`
    - `AgenikPredict` deployment `1958448b-1fa3-4151-9278-7b8407faaf83` -> `SUCCESS`
      - image digest: `sha256:a9212543b84771b4305b31afa69b3ecfe007abfadd5943a37eeaabd6b8b2c370`
  - Live prod:
    - `GET https://app.agenikpredict.com/health` -> `200`
    - `GET /api/report/backtest/metrics` now returns:
      - `dataset`
      - `items`
      - `overall`
      - `by_domain`
      - `by_horizon`
      - `by_scenario`
      - `calibration_buckets`
      - `recent_evaluations`
  - Live canary:
    - `GET https://agenikpredictwebcanary-production.up.railway.app/health` -> `200`
    - `GET /api/report/backtest/metrics` returns the same new expanded quality-loop shape
- Result:
  - The historical quality loop is now genuinely live on the public production web service.
  - The key blocker was the oversized universal web image; separating simulation-only dependencies from the base web runtime removed the rollout stall.
- Next action: Optionally wait for the new `AgenikPredictWorker` deployment on `201e045` to reach terminal state, but the critical user-facing and operator-facing quality-loop rollout is already live and verified.

### Item 78

- Plan item: Finish the remaining active multilingual UI tail and remove legacy CJK/parser artifacts from the live process/report flow
- Work done: I localized the remaining active user-facing runtime logs in `MainView` and `Step2EnvSetup`, moved the visible `Step4Report` timeline/tool-card copy onto i18n keys, switched active log timestamps to locale-aware `Intl.DateTimeFormat`, and normalized legacy report parser markers so old `【...】` / fullwidth punctuation inputs still parse while the code no longer carries those literals in active UI logic. I also converted the lingering Chinese comments in `backend/requirements.txt` to English and added the new i18n keyset to `en.json` and `ru.json`.
- Comparison status: `ON_TRACK`
- Evidence:
  - Active-code CJK grep:
    - `rg -n --pcre2 "[\\p{Han}\\p{Hiragana}\\p{Katakana}]" frontend/src/views/MainView.vue frontend/src/components/Step2EnvSetup.vue frontend/src/components/Step4Report.vue backend/requirements.txt` -> no matches
  - Locale key parity:
    - `node - <<'NODE' ... prefixes = ['theme.', 'mainView.logs.', 'step2.logs.', 'reportUi.'] ...` -> `missingInRu=0`, `missingInEn=0` for all four prefixes
  - Frontend build:
    - `cd frontend && npm run build` -> success
  - Backend syntax check:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
- Result:
  - The active process/report UI path is now materially quieter and structurally language-aware for the new frontend-generated logs/cards.
  - The legacy CJK tail is removed from the active code paths without breaking backward parsing of older report artifacts.
- Next action: Productize the next UX layer by adding node-scoped editing affordances (persona override, analyst note, include/exclude in report, open questions) instead of adding more global control panels.

### Item 79

- Plan item: Define a fast-vs-global analysis strategy and prioritize external evidence APIs for practical accuracy
- Work done: I audited the current analysis stack and verified that AgenikPredict already has the technical foundation for tiered analysis rather than a single heavy mode. In code, `ReportAgent` already composes graph-native tools (`quick_search`, `panorama_search`, `insight_forge`, `interview_agents`) with lightweight live evidence tools (`live_news_brief`, `live_market_snapshot`). The frontend already passes `Accept-Language`, and the backend already preserves `language_used` through graph, simulation, and report flows. I then checked current official API options to define a realistic expansion order for finance/legal/macroeconomic evidence instead of trying to connect to “everything” at once.
- Comparison status: `AHEAD`
- Evidence:
  - Current tier-ready agent/tool architecture:
    - `backend/app/services/report_agent.py` -> report tool registry includes graph search, interviews, live news, and live market snapshot
    - `backend/app/services/live_evidence.py` -> lightweight live evidence currently uses Google News RSS + Twelve Data with cache/timeout/degradation
    - `backend/app/services/market_data.py` -> existing Twelve Data integration is already reusable for quote/summary enrichment
  - Language propagation already in place:
    - `frontend/src/api/index.js` -> sends `Accept-Language`
    - `backend/app/utils/locale.py` -> resolves request language
    - `backend/app/api/report.py` and related graph/simulation APIs -> preserve `language_used`
  - Quality loop already exists and can consume richer evidence:
    - `backend/app/api/report.py` -> `/backtest/metrics`
    - `backend/app/models/prediction_ledger.py`
    - `backend/app/models/historical_backtest.py`
  - Official source checks used to prioritize next API integrations:
    - SEC EDGAR API overview: `https://www.sec.gov/files/edgar/filer-information/specifications/en-api-specs073123.pdf`
    - OpenFIGI API documentation: `https://www.openfigi.com/api/documentation`
    - Twelve Data official support/docs: `https://support.twelvedata.com`
    - FDIC BankFind / bank data guide references from FDIC docs and `banks.data.fdic.gov`
- Result:
  - The analysis does not need to remain slow. The right model is:
    - `Quick Analysis`: graph retrieval + lightweight live signals + no deep interview fan-out
    - `Global Analysis`: graph retrieval + deep interviews + broader external evidence provider set + richer calibration context
  - The most practical next API rollout is domain-prioritized, not “all connectors at once”:
    - finance core: Twelve Data, SEC EDGAR, OpenFIGI, FRED/ALFRED, FDIC
    - legal core: docket/opinion sources such as CourtListener/RECAP plus regulator/public filing feeds
    - strategy/news core: current live news, later broader source attribution and provider routing
- Next action: Turn this into a concrete implementation plan with `analysis_mode=quick|global`, an evidence-provider registry, and a phased integration order starting with finance/regulatory sources that improve report defensibility the most.

### Item 80

- Plan item: Extend the analysis strategy to social-market evidence, provenance monitoring, and agent-level explainability
- Work done: I verified the current product already has the kernel of an “ask the agents” capability through simulation interview endpoints and report conversation tooling, then mapped how to turn that into a clean user-facing capability. I also checked current official platform constraints for X and Reddit so the social evidence plan stays legally/operationally grounded instead of assuming unrestricted scraping or generic API access.
- Comparison status: `AHEAD`
- Evidence:
  - Existing agent opinion infrastructure:
    - `backend/app/api/simulation.py` -> `/interview/batch` and `/interview/all`
    - `backend/app/services/simulation_runner.py` -> `interview_agents_batch(...)`
    - `backend/app/services/report_agent.py` -> autonomous tool invocation and detailed `agent_log.jsonl`
    - `backend/app/api/report.py` -> conversation endpoints + report/agent-log retrieval
  - Official X API search docs:
    - `https://docs.x.com/x-api/posts/search/introduction`
    - recent search: last 7 days for all developers
    - full archive search: pay-per-use / enterprise
  - Official Reddit docs/terms:
    - `https://developers.reddit.com/docs/capabilities/server/reddit-api`
    - `https://redditinc.com/policies/developer-terms`
    - `https://redditinc.com/policies/data-api-terms`
    - Important constraints include monitoring/audit rights, app review discretion, rate-limit enforcement, attribution requirements, and additional requirements for commercial / non-express use cases
- Result:
  - X and Reddit should be modeled as a dedicated `SocialEvidenceLayer`, not mixed blindly into core market/news retrieval.
  - Every report should carry a first-class provenance object:
    - source provider
    - source URL / permalink
    - query used
    - fetched_at
    - claim/evidence linkage
    - transformation chain
    - confidence and freshness
  - The product should expose two user-facing explanation features:
    - `Why do we think this?` at claim/report level
    - `Ask this agent` at node/agent/card level, returning the agent’s stance, reasons, evidence refs, and uncertainty
- Next action: Design the concrete data model for `EvidenceBundle`, `SourceManifest`, and `AgentOpinionResponse`, then wire `Ask this agent` into the node/card UI as a premium low-noise drawer rather than a separate debug screen.

### Item 81

- Plan item: Decide whether a single provider like Perplexity Search can serve as the primary evidence layer, and produce a chief-advisor recommendation for the next architecture step
- Work done: I ran a deep research pass across the current codebase, official provider documentation, and independent sub-agent reviews. The conclusion is consistent: Perplexity is strong as a discovery/synthesis layer, but it should not be the sole or primary evidence layer for AgenikPredict. The current codebase already points toward a layered model via graph-native tools, interviews, and live evidence. Official docs confirm Perplexity is excellent at web-grounded search with domain/language/date filters and source-returning search results, but X and Reddit have access/licensing constraints, and a general search provider is not sufficient as the canonical source for structured market history, social provenance, or audit-grade claim lineage.
- Comparison status: `AHEAD`
- Evidence:
  - Official Perplexity docs:
    - `https://docs.perplexity.ai/api-reference/search-post` -> search API returns `results` with `title`, `url`, `snippet`, `date`, `last_updated`, plus filters for domain, language, country, and date windows
    - `https://docs.perplexity.ai/docs/sonar/quickstart` -> Sonar API is positioned for web-grounded AI responses
    - `https://docs.perplexity.ai/docs/resources/changelog` -> `search_results` field added for transparency/source tracking and structured outputs broadly available
  - Official X docs:
    - `https://docs.x.com/x-api/posts/search/introduction` -> recent search is last 7 days for all developers; full-archive search back to 2006 is limited to pay-per-use / enterprise
  - Official Reddit policy/docs:
    - `https://developers.reddit.com/docs/capabilities/server/reddit-api`
    - `https://redditinc.com/policies/developer-terms`
    - `https://redditinc.com/policies/data-api-terms`
    - `https://redditinc.com/news/reddit-and-google-expand-partnership` -> Reddit explicitly states content accessed through the Data API cannot be used for commercial purposes without approval
  - Independent agent outcomes:
    - `system_context` agent: recommended layered architecture with Perplexity as discovery/synthesis provider, not sole foundation
    - `explorer` agent: confirmed current codebase already has report tools, interviews, logs, and language propagation, but lacks a strict provenance/evidence schema and mode split
    - `reviewer` agent: flagged high risk in single-provider trust concentration, provenance weakness, historical/market mismatch, and cost/latency unpredictability
- Result:
  - Chief-advisor recommendation:
    - Use a **minimal layered architecture**
    - Keep **Perplexity as discovery/synthesis**
    - Use the user’s **high-coverage market provider as canonical financial facts/history**
    - Add a thin **provenance schema** immediately
    - Route through exactly **two modes**:
      - `quick`: graph + Perplexity + market snapshot
      - `global`: quick + deep retrieval/interviews + social/regulatory/historical expansion
  - This is the best tradeoff between speed, report quality, institutional defensibility, and implementation complexity.
- Next action: Implement the smallest viable slice: `analysis_mode`, `EvidenceProvider/EvidenceBundle`, `PerplexityProvider`, `MarketProvider`, and `SourceManifest`, then expose `Why do we think this?` and `Ask this agent` on top of that evidence model.

### Item 82

- Plan item: Evaluate the external `Cloud Code` audit against the current real repository state and form an unbiased final judgment
- Work done: I checked the `Cloud Code` claims against the actual current repository under `/Users/alexanderivenski/Projects/AgenikPredict`. The result is mixed: the architectural direction is often reasonable, but the repository-state audit is materially outdated and appears to be based on another snapshot/repo (`/Users/alexanderivenski/Projects/codex-agenic-predict-publish/...`). In the current repo, `live_evidence.py` already exists, `ReportAgent` already has `live_news_brief` and `live_market_snapshot`, `custom_persona`/`report_variables` are already sent from the frontend, task persistence already supports DB-backed modes, `/api/auth/billing-status` and `/api/billing/status` already exist, and `BillingBadge` already uses `/api/billing/status`.
- Comparison status: `ON_TRACK`
- Evidence:
  - `backend/app/services/live_evidence.py` exists and implements live news + live market snapshot
  - `backend/app/services/report_agent.py` includes `live_news_brief` and `live_market_snapshot`
  - `frontend/src/components/Step3Simulation.vue` sends `custom_persona` and `report_variables`
  - `backend/app/models/task.py` supports `memory` / `dual` / `db` task store modes with DB persistence
  - `backend/app/api/auth.py` already exposes `/billing-status`
  - `backend/app/api/billing.py` already exposes `/status`
  - `frontend/src/components/BillingBadge.vue` reads `/api/billing/status` via `frontend/src/api/billing.js`
  - Still-correct `Cloud Code` findings:
    - `analysis_mode` is not implemented yet
    - `REPORT_AGENT_MAX_TOOL_CALLS` / `REPORT_AGENT_MAX_REFLECTION_ROUNDS` exist in config but are not wired into `ReportAgent`
    - no Perplexity/FRED provider integration exists yet
    - there is no proper provenance/evidence schema yet
- Result:
  - Unbiased judgment:
    - As a **design recommendation**, `Cloud Code` is directionally useful.
    - As a **current-state audit of this repo**, it is not reliable enough to use blindly.
  - The correct move is to salvage the still-valid recommendations (analysis mode, provenance, provider abstraction) and discard the already-obsolete “fixes” (creating `live_evidence.py`, adding billing status endpoints, rebuilding DB task persistence from scratch).
- Next action: Use the corrected plan for implementation: wire config into `ReportAgent`, add `analysis_mode`, add a real evidence/provenance model, and integrate Perplexity + canonical market provider without redoing features that already exist.

### Item 83

- Plan item: Evaluate the user’s corrected implementation memo and refine it into an execution-grade plan
- Work done: I checked the updated memo against the current code and found it substantially more accurate than the earlier external audit. The four proposed changes are mostly the right next slice, but they need several corrections: `analysis_mode` must propagate not only through the direct API path but also task metadata and `task_handlers.py`; forcing `3 sections` cannot be done by inventing a `DEFAULT_SECTION_COUNT` field because the current outline is LLM-planned in `plan_outline()` and must be constrained either in the outline prompt or by post-parse clamping; a `SourceManifest` should be persisted both as a standalone artifact and in report metadata, not only rendered as a footer; and the plan still omits the user-requested explanation surface (`Why do we think this?` / `Ask this agent`) as an explicit implementation item.
- Comparison status: `ON_TRACK`
- Evidence:
  - `report_agent.py` currently plans the outline through `plan_outline()` with a prompt-constrained `2..5` section range and no `DEFAULT_SECTION_COUNT` mechanism
  - `task_handlers.py` already propagates `custom_persona` and `report_variables`, so `analysis_mode` must be added there too for worker-path correctness
  - `report_agent.py` / `ReportManager.save_report()` already persist `meta.json` and `prediction_summary.json`, making a separate `source_manifest.json` a natural fit
- Result:
  - The updated memo is the first external plan that is close to execution-grade for the current repo.
  - Final refinement:
    - keep Changes 1, 3, 4
    - keep Change 2 but implement section-count control correctly
    - add Change 5 explicitly: report/agent explainability surface
- Next action: Convert this corrected 5-part plan into the final night-mode task list with precise file ownership, acceptance tests, and stop conditions.

### Item 84

- Plan item: Implement the approved overnight evidence upgrade as the smallest viable bounded slice in the current AgenikPredict repo
- Work done: I implemented the approved slice directly in the current repository: config-driven report-agent limits are now effective at runtime; `analysis_mode=quick|global` propagates through frontend, API, task metadata, worker execution, and persisted report metadata; `SourceManifest` now exists as a real data model with `source_manifest.json` persistence and `source_manifest_summary` in report metadata; Perplexity was added as an optional discovery-only provider and only registers `web_search` in global mode when `PERPLEXITY_API_KEY` is present; and report metadata/API now carry an explainability MVP with `why_this_conclusion`, `basis_summary`, and `source_attribution`.
- Comparison status: `DONE`
- Evidence:
  - Runtime/config wiring:
    - `backend/app/services/report_agent.py` now uses config-driven per-instance limits instead of effective hardcodes for section tool calls and reflection rounds
  - `analysis_mode` propagation:
    - `backend/app/api/report.py`
    - `backend/app/services/task_handlers.py`
    - `backend/app/services/report_agent.py`
    - `frontend/src/components/GraphPanel.vue`
    - `frontend/src/views/SimulationRunView.vue`
    - `frontend/src/components/Step3Simulation.vue`
    - `frontend/src/api/report.js`
  - Provenance/data persistence:
    - `backend/app/services/source_manifest.py`
    - `backend/app/services/report_agent.py` (`source_manifest.json` + metadata summary)
  - Optional Perplexity discovery:
    - `backend/app/config.py`
    - `backend/app/services/perplexity_provider.py`
    - `backend/app/services/report_agent.py`
  - Verification:
    - `cd backend && uv run python -m compileall app worker.py run.py tests/test_report_upgrade.py`
    - `cd backend && uv run pytest -q tests/test_report_upgrade.py`
    - `cd frontend && npm run build`
- Result:
  - The approved overnight brief is implemented as a bounded, locally verified slice.
  - Existing worker/web topology was preserved.
  - The multilingual path remained intact.
  - The report path does not depend on Perplexity being configured.
- Next action: Surface the new provenance/explainability metadata in the report UI and add retrieval/API tests for multi-variant completed reports (`language_used` + `analysis_mode`) on the same simulation.

### Item 85

- Plan item: Verify the completed overnight evidence slice against the repository and turn the next 6-hour continuation plan into a deploy-focused session
- Work done: I independently verified that the evidence slice is already present in the current working tree and passes the required local checks. I confirmed `analysis_mode` propagation across frontend, API, task metadata, worker execution, and report persistence; verified config-driven tool/reflection limits, `PerplexityProvider`, `SourceManifest`, and explainability fields in code; ran backend compile checks, the targeted backend test file, and the frontend production build; and compared these results against the proposed 6-hour continuation plan. The conclusion is that the implementation phase is largely complete, so the next 6-hour session should focus on deploy-sensitive work: env rollout, artifact persistence on deployed storage, staging/prod smoke, and rollback readiness. I also confirmed one remaining deploy-prep gap: the new env knobs are not yet documented in `.env.example`.
- Comparison status: `AHEAD`
- Evidence:
  - Implementation present in code:
    - `backend/app/services/report_agent.py`
    - `backend/app/api/report.py`
    - `backend/app/services/task_handlers.py`
    - `backend/app/services/perplexity_provider.py`
    - `backend/app/services/source_manifest.py`
    - `frontend/src/components/GraphPanel.vue`
    - `frontend/src/views/SimulationRunView.vue`
    - `frontend/src/components/Step3Simulation.vue`
    - `frontend/src/api/report.js`
  - Verification commands:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - `cd backend && uv run pytest tests/test_report_upgrade.py` -> `9 passed`
    - `cd frontend && npm run build` -> success
  - Diff / deploy audit:
    - `git diff --stat -- backend/app/api/report.py backend/app/config.py backend/app/services/report_agent.py backend/app/services/perplexity_provider.py backend/app/services/source_manifest.py backend/app/services/task_handlers.py frontend/src/api/report.js frontend/src/components/GraphPanel.vue frontend/src/components/Step3Simulation.vue frontend/src/views/SimulationRunView.vue`
    - `.env.example` currently has no `PERPLEXITY_API_KEY`, `REPORT_AGENT_MAX_TOOL_CALLS`, or `REPORT_AGENT_MAX_REFLECTION_ROUNDS` entries
- Result:
  - The proposed 6-hour continuation should no longer spend time re-implementing the slice.
  - The correct continuation is deploy-oriented:
    - env/config rollout
    - web/worker parity in prod-like mode
    - artifact persistence checks on the real artifact backend
    - staging deploy and smoke
    - production go/no-go and rollback prep
- Next action: Execute a deploy-validation session for the already-built slice, starting with env/default documentation and prod-like web/worker verification before staging rollout.

### Item 86

- Plan item: Convert the verified overnight evidence slice into a production-safe deploy path without adding new product scope
- Work done:
  - documented the new deploy env keys in `.env.example`
  - added two copy-paste runbooks under `scripts/` for pre-deploy audit and post-deploy smoke
  - hardened the shipped slice in three deploy-sensitive areas:
    - frontend no longer forces report regeneration on the main Step 3 path, so completed-report reuse by `language_used + analysis_mode` can work
    - quick mode now blocks the remaining heavy legacy alias path instead of allowing graph-stat/entity-summary fallbacks
    - status and retrieval paths now behave more deterministically for variant-aware lookups (`language` + `analysis_mode`) and validate `analysis_mode` inputs
  - upgraded the post-deploy smoke flow so it fails on HTTP errors, insists on valid JSON, waits for report completion, and treats conflict-path responses explicitly
  - re-ran local verification and the new pre-deploy script after the hardening changes
- Comparison status: `AHEAD`
- Evidence:
  - changed files:
    - `.env.example`
    - `backend/app/api/report.py`
    - `backend/app/services/report_agent.py`
    - `backend/tests/test_report_upgrade.py`
    - `frontend/src/components/Step3Simulation.vue`
    - `scripts/pre_deploy_evidence_slice.sh`
    - `scripts/post_deploy_evidence_smoke.sh`
  - verification:
    - `cd backend && uv run python -m compileall app worker.py run.py` -> success
    - `cd backend && uv run pytest -q tests/test_report_upgrade.py` -> `10 passed`
    - `cd frontend && npm run build` -> success
    - `bash -n scripts/pre_deploy_evidence_slice.sh scripts/post_deploy_evidence_smoke.sh` -> success
    - `./scripts/pre_deploy_evidence_slice.sh` -> success
- Result:
  - the slice is now better aligned with the intended deploy contract than the earlier overnight brief:
    - reuse semantics are no longer accidentally bypassed by the main UI path
    - quick mode is materially stricter
    - deploy smoke is closer to a real gate than a visual checklist
  - remaining work is operational, not architectural:
    - push/deploy
    - staging/canary smoke
    - production go/no-go
- Next action:
  - run the staging/canary rollout using the scripts, then expose provenance/explainability metadata in the report UI

### Item 87

- Plan item: Turn the deploy guidance into a truly isolated candidate branch and verify the branch itself, not the source worktree
- Work done:
  - created a clean deploy worktree and validated the candidate there
  - fixed a deploy-script path bug so `pre_deploy` / `post_deploy` resolve the repo from their own location instead of a hardcoded source tree path
  - expanded the isolated dependency set after real clean-worktree runs exposed missing backend/frontend support files and a hidden test dependency on an already-existing `prediction_ledger` table
  - updated the backend test fixture so the targeted report-upgrade suite is reproducible in a fresh worktree
- Comparison status: `AHEAD`
- Evidence:
  - clean worktree path: `/Users/alexanderivenski/Projects/AgenikPredict-deploy`
  - branch: `codex/deploy-evidence-slice`
  - verification in clean worktree:
    - `bash scripts/pre_deploy_evidence_slice.sh` -> success
    - backend tests -> `10 passed`
    - frontend build -> success
- Result:
  - the deploy candidate is now isolated enough for a canary rollout
  - the remaining work is release execution:
    - git add / commit / push from clean worktree
    - canary deploy
    - `post_deploy_evidence_smoke.sh`
    - prod go/no-go
- Next action:
  - commit and push the clean worktree candidate, then run the canary smoke matrix on two distinct simulations

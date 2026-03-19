"""
Report API routes
Provides simulation report generation, retrieval, and conversation endpoints
"""

import os
import traceback
from datetime import datetime
from flask import request, jsonify, send_file, g

from . import report_bp
from ..config import Config
from ..services.report_agent import (
    ReportAgent,
    ReportManager,
    ReportStatus,
    Report,
    normalize_analysis_mode,
)
from ..utils.llm_client import LLMClient
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..services.task_worker import dispatch_task, ensure_worker_dispatch_ready, WorkerDispatchUnavailable
from ..models.user import (
    log_usage, get_user_report_count,
    reserve_report_generation, finalize_report_generation_reservation,
    release_report_generation_reservation,
)
from ..models.prediction_ledger import PredictionLedgerManager
from ..models.historical_backtest import HistoricalBacktestManager
from .auth import require_auth, optional_auth
from ..utils.logger import get_logger
from ..utils.locale import resolve_request_language

logger = get_logger('agenikpredict.api.report')


def _language_mode_conflict_message(existing_language: str, existing_mode: str) -> str:
    return (
        "Report generation is already running with a different language or analysis mode. "
        f"Existing language: {existing_language}, existing analysis_mode: {existing_mode}. "
        "Please wait for it to finish or retry later."
    )


def _verify_simulation_access(simulation_id):
    """
    Verify current user has access to a simulation (through its parent project).

    Returns (simulation_state, project, error_response).
    """
    manager = SimulationManager()
    state = manager.get_simulation(simulation_id)
    if not state:
        return None, None, (jsonify({"success": False, "error": f"Simulation not found: {simulation_id}"}), 404)

    project = ProjectManager.get_project(state.project_id)
    if not project:
        return None, None, (jsonify({"success": False, "error": f"Project not found: {state.project_id}"}), 404)

    if project.owner_id and project.owner_id != g.user_id and getattr(g, 'user_role', '') != 'admin':
        return None, None, (jsonify({"success": False, "error": "Access denied"}), 403)

    return state, project, None


def _verify_graph_access(graph_id):
    """Verify current user has access to a graph through its owning project."""
    project = ProjectManager.find_project_by_graph_id(graph_id)
    if not project:
        return None, (jsonify({"success": False, "error": f"Graph not found: {graph_id}"}), 404)

    if project.owner_id and project.owner_id != g.user_id and getattr(g, 'user_role', '') != 'admin':
        return None, (jsonify({"success": False, "error": "Access denied"}), 403)

    return project, None


def _verify_report_access(report_id):
    """
    Verify current user has access to a report (through simulation -> project chain).

    Returns (report, error_response).
    """
    report = ReportManager.get_report(report_id)
    if not report:
        return None, (jsonify({"success": False, "error": f"Report not found: {report_id}"}), 404)

    # Check ownership through the simulation's parent project
    _, _, error = _verify_simulation_access(report.simulation_id)
    if error:
        return None, error

    return report, None


def _verify_prediction_access(prediction_id):
    """Verify current user has access to a prediction ledger row."""
    entry = PredictionLedgerManager.get_prediction(prediction_id)
    if not entry:
        return None, (jsonify({"success": False, "error": f"Prediction not found: {prediction_id}"}), 404)

    _, _, error = _verify_simulation_access(entry.simulation_id)
    if error:
        return None, error

    return entry, None


def _backfill_report_predictions(report: Report) -> Report:
    """Regenerate structured predictions from an already-completed report when missing."""
    if report.prediction_summary:
        try:
            PredictionLedgerManager.sync_report_prediction_summary(
                report_id=report.report_id,
                simulation_id=report.simulation_id,
                graph_id=report.graph_id,
                prediction_summary=report.prediction_summary,
            )
        except Exception:
            logger.warning("Prediction ledger sync failed during report backfill", exc_info=True)
        return report

    if report.status != ReportStatus.COMPLETED or not (report.markdown_content or "").strip():
        return report

    sim_manager = SimulationManager()
    state = sim_manager.get_simulation(report.simulation_id)
    if not state:
        return report

    project = ProjectManager.get_project(state.project_id)
    if not project:
        return report

    graph_id = state.graph_id or project.graph_id or report.graph_id
    simulation_requirement = project.simulation_requirement
    if not graph_id or not simulation_requirement:
        return report

    try:
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=report.simulation_id,
            simulation_requirement=simulation_requirement,
            language=getattr(report, "language_used", None),
            analysis_mode=getattr(report, "analysis_mode", "global"),
        )
        prediction_summary = agent._generate_prediction_summary(report.markdown_content)
        if not prediction_summary:
            return report

        report.prediction_summary = prediction_summary
        report.graph_id = graph_id
        ReportManager.save_report(report)
        refreshed = ReportManager.get_report(report.report_id)
        return refreshed or report
    except Exception:
        logger.warning("Prediction summary backfill failed for report %s", report.report_id, exc_info=True)
        return report


def _normalize_scenario_key(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _scenario_key_aliases(scenario_name: str, language_used: str | None = None) -> set[str]:
    aliases = {_normalize_scenario_key(scenario_name)}
    localized_name = ReportManager._localize_scenario_name(scenario_name, getattr(language_used, "strip", lambda: language_used)() if language_used else "en")
    aliases.add(_normalize_scenario_key(localized_name))
    return {alias for alias in aliases if alias}


def _resolve_historical_outcomes_payload(
    *,
    case,
    outcomes_payload,
    use_suggested_outcomes: bool,
):
    if isinstance(outcomes_payload, dict) and outcomes_payload:
        return outcomes_payload
    if use_suggested_outcomes and case and case.suggested_outcomes:
        return dict(case.suggested_outcomes)
    return {}


def _apply_historical_case_evaluation(
    *,
    report: Report,
    case,
    outcomes_payload,
    notes: str,
    should_backfill: bool,
):
    if should_backfill:
        report = _backfill_report_predictions(report)

    entries = PredictionLedgerManager.list_predictions(
        report_id=report.report_id,
        limit=16,
    )
    if not entries:
        raise ValueError("No structured predictions available for this report")

    report_language = getattr(report, "language_used", "en")
    normalized_outcomes = {
        _normalize_scenario_key(key): value
        for key, value in (outcomes_payload or {}).items()
        if _normalize_scenario_key(key)
    }
    if not normalized_outcomes:
        raise ValueError("Please provide an outcomes object keyed by scenario name")

    updated_entries = []
    for entry in entries:
        outcome_spec = None
        for alias in _scenario_key_aliases(entry.scenario_name, report_language):
            outcome_spec = normalized_outcomes.get(alias)
            if outcome_spec is not None:
                break
        if outcome_spec is None:
            continue

        if isinstance(outcome_spec, dict):
            outcome_status = str(outcome_spec.get('status') or '').strip()
            outcome_notes = str(outcome_spec.get('notes') or notes).strip()
            outcome_payload = dict(outcome_spec.get('payload') or {})
        else:
            outcome_status = str(outcome_spec).strip()
            outcome_notes = notes
            outcome_payload = {}

        if not outcome_status:
            continue

        if case:
            outcome_payload.setdefault('historical_case_id', case.case_id)
            outcome_payload.setdefault('historical_case_title', case.title)
            outcome_payload.setdefault('historical_case_reference_date', case.reference_date)
            outcome_payload.setdefault('historical_case_domain', case.domain)

        updated = PredictionLedgerManager.record_outcome(
            prediction_id=entry.prediction_id,
            outcome_status=outcome_status,
            outcome_notes=outcome_notes,
            outcome_payload=outcome_payload,
        )
        if updated:
            updated_entries.append(updated)

    if not updated_entries:
        raise LookupError("No matching scenario outcomes were applied")

    return {
        "report_id": report.report_id,
        "simulation_id": report.simulation_id,
        "language_used": getattr(report, "language_used", "en"),
        "historical_case": case.to_dict() if case else None,
        "applied_count": len(updated_entries),
        "items": [entry.to_dict() for entry in updated_entries],
        "metrics": PredictionLedgerManager.compute_metrics(report_id=report.report_id),
    }


def _verify_task_access(task_id, task):
    """Verify current user can access a task through its linked resources."""
    if getattr(g, 'user_role', '') == 'admin':
        return None

    metadata = getattr(task, 'metadata', None) or {}

    simulation_id = metadata.get('simulation_id')
    if simulation_id:
        _, _, error = _verify_simulation_access(simulation_id)
        return error

    project_id = metadata.get('project_id')
    if project_id:
        project = ProjectManager.get_project(project_id)
        if not project:
            return jsonify({"success": False, "error": f"Project not found: {project_id}"}), 404
        if project.owner_id and project.owner_id != g.user_id:
            return jsonify({"success": False, "error": "Access denied"}), 403
        return None

    owner_id = metadata.get('owner_id')
    if owner_id and owner_id == g.user_id:
        return None

    return jsonify({"success": False, "error": "Access denied"}), 403


# ============== Report Generation API ==============

@report_bp.route('/generate', methods=['POST'])
@require_auth
def generate_report():
    """
    Generate simulation analysis report (async task)

    This is a time-consuming operation. The endpoint returns task_id immediately,
    use GET /api/report/generate/status to query progress

    Request (JSON):
        {
            "simulation_id": "sim_xxxx",    // required, simulation ID
            "force_regenerate": false        // optional, force regeneration
        }

    Returns:
        {
            "success": true,
            "data": {
                "simulation_id": "sim_xxxx",
                "task_id": "task_xxxx",
                "status": "generating",
                "message": "Report generation task started"
            }
        }
    """
    reservation_id = None
    task_dispatched = False
    user_id = getattr(g, 'user_id', None)
    task_id = None
    report_id = None
    task_created = False

    try:
        data = request.get_json() or {}

        simulation_id = data.get('simulation_id')
        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400
        
        force_regenerate = data.get('force_regenerate', False)
        custom_persona = data.get('custom_persona', '')
        report_variables = data.get('report_variables', {})
        raw_analysis_mode = data.get('analysis_mode')
        analysis_mode = normalize_analysis_mode(raw_analysis_mode)
        if raw_analysis_mode is not None and str(raw_analysis_mode).strip() and analysis_mode != str(raw_analysis_mode).strip().lower():
            return jsonify({
                "success": False,
                "error": "analysis_mode must be one of: quick, global"
            }), 400
        language = resolve_request_language(
            request.headers.get('Accept-Language'),
            data,
        )

        # Get simulation info (with ownership check)
        state, project, error = _verify_simulation_access(simulation_id)
        if error:
            return error

        # Check for existing report
        matching_report = ReportManager.get_report_by_simulation(
            simulation_id,
            language_used=language,
            analysis_mode=analysis_mode,
            statuses=[ReportStatus.COMPLETED],
        )
        active_report = ReportManager.get_report_by_simulation(
            simulation_id,
            statuses=[ReportStatus.PENDING, ReportStatus.GENERATING],
        )
        if not force_regenerate and matching_report:
            existing_language = getattr(matching_report, "language_used", "en")
            existing_mode = normalize_analysis_mode(getattr(matching_report, "analysis_mode", "global"))
            if matching_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": matching_report.report_id,
                        "status": "completed",
                        "message": "Report already exists",
                        "already_generated": True,
                        "language_used": existing_language,
                        "analysis_mode": existing_mode,
                    }
                })
        if not force_regenerate and active_report:
            existing_language = getattr(active_report, "language_used", "en")
            existing_mode = normalize_analysis_mode(getattr(active_report, "analysis_mode", "global"))
            if active_report.status in (ReportStatus.PENDING, ReportStatus.GENERATING):
                if existing_language != language or existing_mode != analysis_mode:
                    return jsonify({
                        "success": False,
                        "error": _language_mode_conflict_message(existing_language, existing_mode),
                        "report_id": active_report.report_id,
                        "language_used": existing_language,
                        "analysis_mode": existing_mode,
                    }), 409
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": active_report.report_id,
                        "status": active_report.status.value,
                        "message": "Report generation already in progress",
                        "already_generated": False,
                        "already_in_progress": True,
                        "language_used": existing_language,
                        "analysis_mode": existing_mode,
                    }
                })

        task_manager = TaskManager()
        existing_task = task_manager.find_active_task(
            "report_generate",
            execution_key=f"report_generate:{simulation_id}",
            metadata={"simulation_id": simulation_id},
        )
        if existing_task:
            task_language = ((existing_task.metadata or {}).get("language") or "en")
            task_analysis_mode = normalize_analysis_mode((existing_task.metadata or {}).get("analysis_mode"))
            if task_language != language or task_analysis_mode != analysis_mode:
                return jsonify({
                    "success": False,
                    "error": _language_mode_conflict_message(task_language, task_analysis_mode),
                    "task_id": existing_task.task_id,
                    "language_used": task_language,
                    "analysis_mode": task_analysis_mode,
                }), 409
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "report_id": (existing_task.metadata or {}).get("report_id"),
                    "task_id": existing_task.task_id,
                    "status": existing_task.status.value,
                    "message": existing_task.message or "Report generation already in progress",
                    "already_generated": False,
                    "already_in_progress": True,
                    "language_used": task_language,
                    "analysis_mode": task_analysis_mode,
                }
            })
        
        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Missing graph ID, please ensure graph is built"
            }), 400
        
        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            return jsonify({
                "success": False,
                "error": "Missing simulation requirement description"
            }), 400
        
        ensure_worker_dispatch_ready()

        # Pre-generate report_id for immediate frontend return
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"

        # Atomically reserve billing before the background thread starts.
        reservation_id = None
        if user_id:
            can_gen, cost_cents, reason, reservation_id = reserve_report_generation(
                user_id,
                report_id=report_id,
                simulation_id=simulation_id,
            )
            if not can_gen:
                return jsonify({
                    "success": False,
                    "error": "payment_required",
                    "message": "Insufficient credits. Please purchase credits to continue.",
                    "next_report_cost": cost_cents,
                    "report_count": get_user_report_count(user_id),
                    "reason": reason
                }), 402

        # Atomically create or reuse the active task for this simulation.
        task, created_new = task_manager.create_or_reuse_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id,
                "project_id": project.project_id,
                "owner_id": user_id,
                "language": language,
                "analysis_mode": analysis_mode,
                "custom_persona": custom_persona,
                "report_variables": report_variables,
                "reservation_id": reservation_id,
            },
            execution_key=f"report_generate:{simulation_id}",
            max_attempts=3,
        )
        task_id = task.task_id

        if not created_new:
            if reservation_id and user_id:
                release_report_generation_reservation(reservation_id, user_id)
            task_language = ((task.metadata or {}).get("language") or "en")
            task_analysis_mode = normalize_analysis_mode((task.metadata or {}).get("analysis_mode"))
            if task_language != language or task_analysis_mode != analysis_mode:
                return jsonify({
                    "success": False,
                    "error": _language_mode_conflict_message(task_language, task_analysis_mode),
                    "task_id": task.task_id,
                    "language_used": task_language,
                    "analysis_mode": task_analysis_mode,
                }), 409
            return jsonify({
                "success": True,
                "data": {
                    "simulation_id": simulation_id,
                    "report_id": (task.metadata or {}).get("report_id"),
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "message": task.message or "Report generation already in progress",
                    "already_generated": False,
                    "already_in_progress": True,
                    "language_used": task_language,
                    "analysis_mode": task_analysis_mode,
                }
            })
        task_created = True

        placeholder_report = Report(
            report_id=report_id,
            simulation_id=simulation_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat(),
            language_used=language,
            analysis_mode=analysis_mode,
            source_manifest_summary={},
            explainability={},
        )
        ReportManager.save_report(placeholder_report)
        ReportManager.update_progress(
            report_id,
            "pending",
            0,
            "Queued for report generation",
            completed_sections=[],
        )
        dispatch_task(task_id)
        task_dispatched = True
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "language_used": language,
                "analysis_mode": analysis_mode,
                "message": "Report generation task started, query progress via /api/report/generate/status",
                "already_generated": False
            }
        })
        
    except WorkerDispatchUnavailable as e:
        logger.warning("Report generation rejected before task creation: %s", e)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 503

    except Exception as e:
        logger.error(f"Failed to start report generation task: {traceback.format_exc()}")
        if reservation_id and user_id and not task_dispatched:
            release_report_generation_reservation(reservation_id, user_id)
        if task_id and task_created and not task_dispatched:
            task_manager = TaskManager()
            task_manager.fail_task(
                task_id,
                str(e),
                message="Report task startup failed before execution",
            )
            if report_id:
                try:
                    existing_report = ReportManager.get_report(report_id)
                    if existing_report:
                        existing_report.status = ReportStatus.FAILED
                        existing_report.error = str(e)
                        ReportManager.save_report(existing_report)
                        ReportManager.update_progress(
                            report_id,
                            "failed",
                            -1,
                            f"Report task startup failed before execution: {e}",
                            completed_sections=[],
                        )
                except Exception:
                    logger.warning("Failed to persist startup failure state for report_id=%s", report_id)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/generate/status', methods=['POST'])
@require_auth
def get_generate_status():
    """
    Query report generation task progress
    
    Request (JSON):
        {
            "task_id": "task_xxxx",         // optional, task_id returned by generate
            "simulation_id": "sim_xxxx"     // optional, simulation ID
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "task_id": "task_xxxx",
                "status": "processing|completed|failed",
                "progress": 45,
                "message": "..."
            }
        }
    """
    try:
        data = request.get_json() or {}
        
        task_id = data.get('task_id')
        simulation_id = data.get('simulation_id')
        requested_language = data.get('language')
        raw_analysis_mode = data.get('analysis_mode')
        requested_analysis_mode = normalize_analysis_mode(raw_analysis_mode)
        if raw_analysis_mode is not None:
            if str(raw_analysis_mode).strip() and requested_analysis_mode != str(raw_analysis_mode).strip().lower():
                return jsonify({
                    "success": False,
                    "error": "analysis_mode must be one of: quick, global"
                }), 400

        task_manager = TaskManager()
        task = task_manager.get_task(task_id) if task_id else None
        if task:
            error = _verify_task_access(task_id, task)
            if error:
                return error
            task_metadata = getattr(task, 'metadata', None) or {}
            requested_language = requested_language or task_metadata.get("language")
            if raw_analysis_mode is None and "analysis_mode" in task_metadata:
                requested_analysis_mode = normalize_analysis_mode(task_metadata.get("analysis_mode"))
        if requested_language is None:
            requested_language = resolve_request_language(
                request.headers.get('Accept-Language'),
                data,
            )
        
        # If simulation_id provided, first check for completed report
        if simulation_id:
            _, _, error = _verify_simulation_access(simulation_id)
            if error:
                return error
            existing_report = ReportManager.get_report_by_simulation(
                simulation_id,
                language_used=requested_language or None,
                analysis_mode=requested_analysis_mode if requested_analysis_mode is not None else None,
                statuses=[ReportStatus.COMPLETED],
            )
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": "Report already generated",
                        "already_completed": True,
                        "language_used": getattr(existing_report, "language_used", "en"),
                        "analysis_mode": getattr(existing_report, "analysis_mode", "global"),
                    }
                })
        
        if not task_id:
            return jsonify({
                "success": False,
                "error": "Please provide task_id or simulation_id"
            }), 400

        if not task:
            return jsonify({
                "success": False,
                "error": f"Task not found: {task_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": {
                **task.to_dict(),
                "language_used": requested_language or ((task.metadata or {}).get("language") or "en"),
                "analysis_mode": requested_analysis_mode or normalize_analysis_mode((task.metadata or {}).get("analysis_mode")),
                "report_id": (task.metadata or {}).get("report_id"),
                "simulation_id": (task.metadata or {}).get("simulation_id"),
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Retrieval API ==============

@report_bp.route('/predictions/metrics', methods=['GET'])
@require_auth
def get_prediction_metrics():
    """Get baseline outcome metrics for prediction ledger rows."""
    try:
        report_id = request.args.get('report_id')
        simulation_id = request.args.get('simulation_id')

        if report_id:
            _, error = _verify_report_access(report_id)
            if error:
                return error
        if simulation_id:
            _, _, error = _verify_simulation_access(simulation_id)
            if error:
                return error

        owner_id = None
        if getattr(g, 'user_role', '') != 'admin' and not report_id and not simulation_id:
            owner_id = g.user_id

        metrics = PredictionLedgerManager.compute_metrics(
            report_id=report_id,
            simulation_id=simulation_id,
            owner_id=owner_id,
        )
        return jsonify({
            "success": True,
            "data": metrics,
        })
    except Exception as e:
        logger.error(f"Failed to compute prediction metrics: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/backtest/cases', methods=['GET'])
@require_auth
def list_historical_backtest_cases():
    """List curated historical pilot cases for report backtesting."""
    try:
        domain = request.args.get('domain', '').strip() or None
        tag = request.args.get('tag', '').strip() or None
        limit = request.args.get('limit', 50, type=int)
        cases = HistoricalBacktestManager.list_cases(
            domain=domain,
            tag=tag,
            limit=limit,
        )
        return jsonify({
            "success": True,
            "data": {
                "dataset": HistoricalBacktestManager.get_dataset_metadata(),
                "items": [case.to_dict() for case in cases],
            }
        })
    except Exception as e:
        logger.error(f"Failed to list historical backtest cases: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/backtest/cases/<case_id>', methods=['GET'])
@require_auth
def get_historical_backtest_case(case_id: str):
    """Get one curated historical backtest case."""
    try:
        case = HistoricalBacktestManager.get_case(case_id)
        if not case:
            return jsonify({
                "success": False,
                "error": f"Historical case not found: {case_id}"
            }), 404
        return jsonify({
            "success": True,
            "data": case.to_dict(),
        })
    except Exception as e:
        logger.error(f"Failed to get historical backtest case: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/backtest/metrics', methods=['GET'])
@require_auth
def get_historical_backtest_metrics():
    """Aggregate calibration metrics across historical backtest evaluations."""
    try:
        historical_case_id = request.args.get('historical_case_id', '').strip() or None
        case_lookup = {
            case.case_id: case
            for case in HistoricalBacktestManager.list_cases(limit=500)
        }
        if historical_case_id and historical_case_id not in case_lookup:
            return jsonify({
                "success": False,
                "error": f"Historical case not found: {historical_case_id}"
            }), 404

        owner_id = None
        if getattr(g, 'user_role', '') != 'admin':
            owner_id = g.user_id

        metrics = PredictionLedgerManager.compute_historical_case_metrics(
            owner_id=owner_id,
            historical_case_id=historical_case_id,
        )

        items = []
        for item in metrics.get("items", []):
            case = case_lookup.get(item.get("historical_case_id"))
            case_payload = case.to_dict() if case else None
            items.append({
                **item,
                "historical_case": case_payload,
            })

        return jsonify({
            "success": True,
            "data": {
                "dataset": HistoricalBacktestManager.get_dataset_metadata(),
                "overall": metrics.get("overall", {}),
                "items": items,
                "by_domain": metrics.get("by_domain", []),
                "by_scenario": metrics.get("by_scenario", []),
                "by_horizon": metrics.get("by_horizon", []),
                "calibration_buckets": metrics.get("calibration_buckets", []),
                "recent_evaluations": metrics.get("recent_evaluations", []),
            }
        })
    except Exception as e:
        logger.error(f"Failed to compute historical backtest metrics: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/backtest/reports/<report_id>/evaluate', methods=['POST'])
@require_auth
def evaluate_report_against_historical_case(report_id: str):
    """Batch-apply scenario outcomes to a completed report for backtesting."""
    try:
        report, error = _verify_report_access(report_id)
        if error:
            return error

        payload = request.get_json() or {}
        case_id = str(payload.get('historical_case_id') or '').strip()
        should_backfill = bool(payload.get('backfill_predictions', True))
        use_suggested_outcomes = bool(payload.get('use_suggested_outcomes', True))
        outcomes_payload = payload.get('outcomes') or {}
        notes = str(payload.get('notes') or '').strip()

        case = HistoricalBacktestManager.get_case(case_id) if case_id else None
        if case_id and not case:
            return jsonify({
                "success": False,
                "error": f"Historical case not found: {case_id}"
            }), 404

        resolved_outcomes = _resolve_historical_outcomes_payload(
            case=case,
            outcomes_payload=outcomes_payload,
            use_suggested_outcomes=use_suggested_outcomes,
        )
        if not resolved_outcomes:
            return jsonify({
                "success": False,
                "error": "Please provide an outcomes object keyed by scenario name or use a historical case with suggested outcomes"
            }), 400

        evaluation = _apply_historical_case_evaluation(
            report=report,
            case=case,
            outcomes_payload=resolved_outcomes,
            notes=notes,
            should_backfill=should_backfill,
        )
        return jsonify({
            "success": True,
            "data": evaluation
        })
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except LookupError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except Exception as e:
        logger.error(f"Failed to evaluate report against historical case: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/backtest/evaluate-batch', methods=['POST'])
@require_auth
def evaluate_reports_against_historical_case_batch():
    """Batch-apply historical outcomes to multiple completed reports."""
    try:
        payload = request.get_json() or {}
        case_id = str(payload.get('historical_case_id') or '').strip()
        report_ids = payload.get('report_ids') or []
        should_backfill = bool(payload.get('backfill_predictions', True))
        use_suggested_outcomes = bool(payload.get('use_suggested_outcomes', True))
        notes = str(payload.get('notes') or '').strip()
        base_outcomes = payload.get('outcomes') or {}

        if not isinstance(report_ids, list) or not report_ids:
            return jsonify({
                "success": False,
                "error": "Please provide report_ids"
            }), 400

        case = HistoricalBacktestManager.get_case(case_id) if case_id else None
        if case_id and not case:
            return jsonify({
                "success": False,
                "error": f"Historical case not found: {case_id}"
            }), 404

        resolved_outcomes = _resolve_historical_outcomes_payload(
            case=case,
            outcomes_payload=base_outcomes,
            use_suggested_outcomes=use_suggested_outcomes,
        )
        if not resolved_outcomes:
            return jsonify({
                "success": False,
                "error": "Please provide an outcomes object keyed by scenario name or use a historical case with suggested outcomes"
            }), 400

        results = []
        failed = []
        for report_id in [str(item).strip() for item in report_ids if str(item).strip()]:
            report, error = _verify_report_access(report_id)
            if error:
                failed.append({
                    "report_id": report_id,
                    "error": error[0].get_json().get("error") if isinstance(error, tuple) else "Access denied",
                })
                continue
            try:
                results.append(
                    _apply_historical_case_evaluation(
                        report=report,
                        case=case,
                        outcomes_payload=resolved_outcomes,
                        notes=notes,
                        should_backfill=should_backfill,
                    )
                )
            except (ValueError, LookupError) as e:
                failed.append({
                    "report_id": report_id,
                    "error": str(e),
                })

        aggregate_metrics = PredictionLedgerManager.compute_historical_case_metrics(
            owner_id=None if getattr(g, 'user_role', '') == 'admin' else g.user_id,
            historical_case_id=case_id or None,
        )
        return jsonify({
            "success": True,
            "data": {
                "historical_case": case.to_dict() if case else None,
                "requested_count": len(report_ids),
                "succeeded_count": len(results),
                "failed_count": len(failed),
                "items": results,
                "failed": failed,
                "metrics": aggregate_metrics,
            }
        })
    except Exception as e:
        logger.error(f"Failed to batch evaluate reports against historical case: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/predictions/<prediction_id>/outcome', methods=['POST'])
@require_auth
def record_prediction_outcome(prediction_id: str):
    """Record an outcome for a prediction ledger row."""
    try:
        _, error = _verify_prediction_access(prediction_id)
        if error:
            return error

        data = request.get_json() or {}
        outcome_status = data.get('outcome_status')
        if not outcome_status:
            return jsonify({
                "success": False,
                "error": "Please provide outcome_status"
            }), 400

        updated = PredictionLedgerManager.record_outcome(
            prediction_id=prediction_id,
            outcome_status=outcome_status,
            outcome_notes=data.get('outcome_notes', ''),
            outcome_payload=data.get('outcome_payload') or {},
        )
        if not updated:
            return jsonify({
                "success": False,
                "error": f"Prediction not found: {prediction_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": updated.to_dict(),
        })
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
    except Exception as e:
        logger.error(f"Failed to record prediction outcome: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@report_bp.route('/<report_id>', methods=['GET'])
@require_auth
def get_report(report_id: str):
    """
    Get report details (ownership verified)
    """
    try:
        report, error = _verify_report_access(report_id)
        if error:
            return error

        return jsonify({
            "success": True,
            "data": report.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to get report: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/by-simulation/<simulation_id>', methods=['GET'])
@require_auth
def get_report_by_simulation(simulation_id: str):
    """
    Get report by simulation ID (ownership verified)
    """
    try:
        # Verify access to the simulation
        _, _, error = _verify_simulation_access(simulation_id)
        if error:
            return error

        language = request.args.get('language')
        raw_analysis_mode = request.args.get('analysis_mode')
        analysis_mode = normalize_analysis_mode(raw_analysis_mode) if raw_analysis_mode is not None else None
        if raw_analysis_mode is not None and str(raw_analysis_mode).strip() and analysis_mode != str(raw_analysis_mode).strip().lower():
            return jsonify({
                "success": False,
                "error": "analysis_mode must be one of: quick, global"
            }), 400
        report = ReportManager.get_report_by_simulation(
            simulation_id,
            language_used=language or None,
            analysis_mode=analysis_mode,
        )

        if not report:
            return jsonify({
                "success": False,
                "error": f"No report available for this simulation: {simulation_id}",
                "has_report": False
            }), 404

        return jsonify({
            "success": True,
            "data": report.to_dict(),
            "has_report": True
        })
        
    except Exception as e:
        logger.error(f"Failed to get report: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/predictions', methods=['GET'])
@require_auth
def get_report_predictions(report_id: str):
    """Get structured prediction ledger entries for a report."""
    try:
        report, error = _verify_report_access(report_id)
        if error:
            return error

        should_backfill = request.args.get('backfill', '').lower() in {'1', 'true', 'yes'}
        entries = PredictionLedgerManager.list_predictions(
            report_id=report_id,
            limit=16,
        )
        if should_backfill and not entries:
            report = _backfill_report_predictions(report)
            entries = PredictionLedgerManager.list_predictions(
                report_id=report_id,
                limit=16,
            )
        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "simulation_id": report.simulation_id,
                "language_used": getattr(report, "language_used", "en"),
                "items": [entry.to_dict() for entry in entries],
            }
        })
    except Exception as e:
        logger.error(f"Failed to get report predictions: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/by-simulation/<simulation_id>/predictions', methods=['GET'])
@require_auth
def get_predictions_by_simulation(simulation_id: str):
    """Get prediction ledger entries across reports for a simulation."""
    try:
        _, _, error = _verify_simulation_access(simulation_id)
        if error:
            return error

        language = request.args.get('language')
        raw_analysis_mode = request.args.get('analysis_mode')
        analysis_mode = normalize_analysis_mode(raw_analysis_mode) if raw_analysis_mode is not None else None
        if raw_analysis_mode is not None and str(raw_analysis_mode).strip() and analysis_mode != str(raw_analysis_mode).strip().lower():
            return jsonify({
                "success": False,
                "error": "analysis_mode must be one of: quick, global"
            }), 400

        limit = request.args.get('limit', 50, type=int)
        entries = PredictionLedgerManager.list_predictions(
            simulation_id=simulation_id,
            limit=limit,
        )
        report = ReportManager.get_report_by_simulation(
            simulation_id,
            language_used=language or None,
            analysis_mode=analysis_mode,
        )
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "language_used": getattr(report, "language_used", "en") if report else None,
                "analysis_mode": getattr(report, "analysis_mode", "global") if report else None,
                "items": [entry.to_dict() for entry in entries],
            }
        })
    except Exception as e:
        logger.error(f"Failed to get simulation predictions: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/list', methods=['GET'])
@require_auth
def list_reports():
    """
    List reports accessible by the current user.

    Filters reports by checking ownership of the parent simulation/project chain.
    Admins see all reports.
    """
    try:
        simulation_id = request.args.get('simulation_id')
        limit = request.args.get('limit', 50, type=int)

        all_reports = ReportManager.list_reports(
            simulation_id=simulation_id,
            limit=limit
        )

        # Filter by ownership (admins bypass)
        if getattr(g, 'user_role', '') == 'admin':
            filtered_reports = all_reports
        else:
            filtered_reports = []
            for report in all_reports:
                # Check ownership through simulation -> project chain
                manager = SimulationManager()
                state = manager.get_simulation(report.simulation_id)
                if not state:
                    continue
                project = ProjectManager.get_project(state.project_id)
                if not project:
                    continue
                # Allow if: no owner (legacy), or owner matches
                if project.owner_id is None or project.owner_id == g.user_id:
                    filtered_reports.append(report)

        return jsonify({
            "success": True,
            "data": [r.to_dict() for r in filtered_reports],
            "count": len(filtered_reports)
        })
        
    except Exception as e:
        logger.error(f"Failed to list reports: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/download', methods=['GET'])
@require_auth
def download_report(report_id: str):
    """
    Download report (Markdown format, ownership verified)
    """
    try:
        report, error = _verify_report_access(report_id)
        if error:
            return error
        
        md_path = ReportManager._get_report_markdown_path(report_id)
        
        if not os.path.exists(md_path):
            # If MD file does not exist, generate a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
                f.write(report.markdown_content)
                temp_path = f.name
            
            return send_file(
                temp_path,
                as_attachment=True,
                download_name=f"{report_id}.md"
            )
        
        return send_file(
            md_path,
            as_attachment=True,
            download_name=f"{report_id}.md"
        )
        
    except Exception as e:
        logger.error(f"Failed to download report: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>', methods=['DELETE'])
@require_auth
def delete_report(report_id: str):
    """Delete report (ownership verified)"""
    try:
        report, error = _verify_report_access(report_id)
        if error:
            return error

        success = ReportManager.delete_report(report_id)

        if not success:
            return jsonify({
                "success": False,
                "error": f"Report not found: {report_id}"
            }), 404

        return jsonify({
            "success": True,
            "message": f"Report deleted: {report_id}"
        })
        
    except Exception as e:
        logger.error(f"Failed to delete report: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Agent Chat API ==============

@report_bp.route('/chat', methods=['POST'])
@require_auth
def chat_with_report_agent():
    """
    Chat with Report Agent
    
    Report Agent can autonomously invoke retrieval tools to answer questions during conversation
    
    Request (JSON):
        {
            "simulation_id": "sim_xxxx",        // required, simulation ID
            "message": "Please explain the public opinion trend",    // required, user message
            "chat_history": [                   // optional, conversation history
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
    
    Returns:
        {
            "success": true,
            "data": {
                "response": "Agent response...",
                "tool_calls": [list of tool calls],
                "sources": [information sources]
            }
        }
    """
    try:
        data = request.get_json() or {}
        user_id = getattr(g, 'user_id', None)

        simulation_id = data.get('simulation_id')
        message = data.get('message')
        chat_history = data.get('chat_history', [])

        if not simulation_id:
            return jsonify({
                "success": False,
                "error": "Please provide simulation_id"
            }), 400

        if not message:
            return jsonify({
                "success": False,
                "error": "Please provide message"
            }), 400

        # Get simulation and project info (with ownership check)
        state, project, error = _verify_simulation_access(simulation_id)
        if error:
            return error

        existing_report = ReportManager.get_report_by_simulation(simulation_id)
        if not existing_report or existing_report.status != ReportStatus.COMPLETED:
            return jsonify({
                "success": False,
                "error": "Report must be completed before chat is available"
            }), 400

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Missing graph ID"
            }), 400

        simulation_requirement = project.simulation_requirement or ""

        language = resolve_request_language(
            request.headers.get('Accept-Language'),
            data,
        )

        # Create Agent with secondary (cheap) LLM for chat
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            language=language,
            analysis_mode=getattr(existing_report, "analysis_mode", "global"),
            llm_client=LLMClient.secondary()
        )

        result = agent.chat(message=message, chat_history=chat_history)

        # Log chat usage (always log, but don't deduct — included in report cost)
        if user_id and agent.usage.total_tokens > 0:
            usage_data = agent.usage.to_dict()
            log_usage(
                user_id=user_id,
                action_type='report_chat',
                input_tokens=usage_data.get('prompt_tokens', 0),
                output_tokens=usage_data.get('completion_tokens', 0),
                model=agent.llm.model,
                simulation_id=simulation_id
            )

        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Chat failed: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Progress and Section API ==============

@report_bp.route('/<report_id>/progress', methods=['GET'])
@require_auth
def get_report_progress(report_id: str):
    """
    Get report generation progress (real-time)
    
    Returns:
        {
            "success": true,
            "data": {
                "status": "generating",
                "progress": 45,
                "message": "Generating section: Key Findings",
                "current_section": "Key Findings",
                "completed_sections": ["Executive Summary", "Simulation Background"],
                "updated_at": "2025-12-09T..."
            }
        }
    """
    try:
        # Verify ownership
        _, error = _verify_report_access(report_id)
        if error:
            return error

        progress = ReportManager.get_progress(report_id)

        if not progress:
            return jsonify({
                "success": False,
                "error": f"Report not found or progress info unavailable: {report_id}"
            }), 404

        return jsonify({
            "success": True,
            "data": progress
        })

    except Exception as e:
        logger.error(f"Failed to get report progress: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/sections', methods=['GET'])
@require_auth
def get_report_sections(report_id: str):
    """
    Get list of generated sections (section-by-section output)
    
    Frontend can poll this endpoint to get generated section content without waiting for the entire report
    
    Returns:
        {
            "success": true,
            "data": {
                "report_id": "report_xxxx",
                "sections": [
                    {
                        "filename": "section_01.md",
                        "section_index": 1,
                        "content": "## Executive Summary\\n\\n..."
                    },
                    ...
                ],
                "total_sections": 3,
                "is_complete": false
            }
        }
    """
    try:
        _, error = _verify_report_access(report_id)
        if error:
            return error

        sections = ReportManager.get_generated_sections(report_id)
        
        # Get report status
        report = ReportManager.get_report(report_id)
        is_complete = report is not None and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "report_id": report_id,
                "sections": sections,
                "total_sections": len(sections),
                "is_complete": is_complete
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get section list: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/section/<int:section_index>', methods=['GET'])
@require_auth
def get_single_section(report_id: str, section_index: int):
    """
    Get single section content
    
    Returns:
        {
            "success": true,
            "data": {
                "filename": "section_01.md",
                "content": "## Executive Summary\\n\\n..."
            }
        }
    """
    try:
        _, error = _verify_report_access(report_id)
        if error:
            return error

        section_path = ReportManager._get_section_path(report_id, section_index)
        
        if not os.path.exists(section_path):
            return jsonify({
                "success": False,
                "error": f"Section not found: section_{section_index:02d}.md"
            }), 404
        
        with open(section_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "success": True,
            "data": {
                "filename": f"section_{section_index:02d}.md",
                "section_index": section_index,
                "content": content
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get section content: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Status Check API ==============

@report_bp.route('/check/<simulation_id>', methods=['GET'])
@require_auth
def check_report_status(simulation_id: str):
    """
    Check if simulation has a report and its status (ownership verified)
    """
    try:
        # Verify access to the simulation
        _, _, error = _verify_simulation_access(simulation_id)
        if error:
            return error

        language = request.args.get('language')
        raw_analysis_mode = request.args.get('analysis_mode')
        analysis_mode = normalize_analysis_mode(raw_analysis_mode) if raw_analysis_mode is not None else None
        if raw_analysis_mode is not None and str(raw_analysis_mode).strip() and analysis_mode != str(raw_analysis_mode).strip().lower():
            return jsonify({
                "success": False,
                "error": "analysis_mode must be one of: quick, global"
            }), 400

        report = ReportManager.get_report_by_simulation(
            simulation_id,
            language_used=language or None,
            analysis_mode=analysis_mode,
        )
        
        has_report = report is not None
        report_status = report.status.value if report else None
        report_id = report.report_id if report else None
        
        # Only unlock interview after report is completed
        interview_unlocked = has_report and report.status == ReportStatus.COMPLETED
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "has_report": has_report,
                "report_status": report_status,
                "report_id": report_id,
                "analysis_mode": getattr(report, "analysis_mode", "global") if report else None,
                "interview_unlocked": interview_unlocked
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to check report status: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Agent Log API ==============

@report_bp.route('/<report_id>/agent-log', methods=['GET'])
@require_auth
def get_agent_log(report_id: str):
    """
    Get detailed execution log of Report Agent
    
    Real-time retrieval of each step during report generation, including:
    - Report start, planning start/complete
    - Each section start, tool calls, LLM responses, completion
    - Report completion or failure
    
    Query parameters:
        from_line: Start reading from which line (optional, default 0, for incremental retrieval)
    
    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    {
                        "timestamp": "2025-12-13T...",
                        "elapsed_seconds": 12.5,
                        "report_id": "report_xxxx",
                        "action": "tool_call",
                        "stage": "generating",
                        "section_title": "Executive Summary",
                        "section_index": 1,
                        "details": {
                            "tool_name": "insight_forge",
                            "parameters": {...},
                            ...
                        }
                    },
                    ...
                ],
                "total_lines": 25,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        _, error = _verify_report_access(report_id)
        if error:
            return error

        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_agent_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get Agent log: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/agent-log/stream', methods=['GET'])
@require_auth
def stream_agent_log(report_id: str):
    """
    Get complete Agent log (all at once)
    
    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 25
            }
        }
    """
    try:
        _, error = _verify_report_access(report_id)
        if error:
            return error

        logs = ReportManager.get_agent_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get Agent log: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Console Log API ==============

@report_bp.route('/<report_id>/console-log', methods=['GET'])
@require_auth
def get_console_log(report_id: str):
    """
    Get Report Agent console output log
    
    Real-time retrieval of console output during report generation (INFO, WARNING, etc.),
    Unlike the structured JSON logs returned by the agent-log endpoint,
    these are plain text console-style logs.
    
    Query parameters:
        from_line: Start reading from which line (optional, default 0, for incremental retrieval)
    
    Returns:
        {
            "success": true,
            "data": {
                "logs": [
                    "[19:46:14] INFO: Search complete: found 15 related facts",
                    "[19:46:14] INFO: Graph search: graph_id=xxx, query=...",
                    ...
                ],
                "total_lines": 100,
                "from_line": 0,
                "has_more": false
            }
        }
    """
    try:
        _, error = _verify_report_access(report_id)
        if error:
            return error

        from_line = request.args.get('from_line', 0, type=int)
        
        log_data = ReportManager.get_console_log(report_id, from_line=from_line)
        
        return jsonify({
            "success": True,
            "data": log_data
        })
        
    except Exception as e:
        logger.error(f"Failed to get console log: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/<report_id>/console-log/stream', methods=['GET'])
@require_auth
def stream_console_log(report_id: str):
    """
    Get complete console log (all at once)
    
    Returns:
        {
            "success": true,
            "data": {
                "logs": [...],
                "count": 100
            }
        }
    """
    try:
        _, error = _verify_report_access(report_id)
        if error:
            return error

        logs = ReportManager.get_console_log_stream(report_id)
        
        return jsonify({
            "success": True,
            "data": {
                "logs": logs,
                "count": len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to get console log: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Tool Call API (for debugging) ==============

@report_bp.route('/tools/search', methods=['POST'])
@require_auth
def search_graph_tool():
    """
    Graph search tool endpoint (for debugging)
    
    Request (JSON):
        {
            "graph_id": "agenikpredict_xxxx",
            "query": "search query",
            "limit": 10
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        query = data.get('query')
        limit = data.get('limit', 10)
        
        if not graph_id or not query:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id and query"
            }), 400

        _, error = _verify_graph_access(graph_id)
        if error:
            return error
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Graph search failed: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@report_bp.route('/tools/statistics', methods=['POST'])
@require_auth
def get_graph_statistics_tool():
    """
    Graph statistics tool endpoint (for debugging)
    
    Request (JSON):
        {
            "graph_id": "agenikpredict_xxxx"
        }
    """
    try:
        data = request.get_json() or {}
        
        graph_id = data.get('graph_id')
        
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Please provide graph_id"
            }), 400

        _, error = _verify_graph_access(graph_id)
        if error:
            return error
        
        from ..services.zep_tools import ZepToolsService
        
        tools = ZepToolsService()
        result = tools.get_graph_statistics(graph_id)
        
        return jsonify({
            "success": True,
            "data": result
        })
        
    except Exception as e:
        logger.error(f"Failed to get graph statistics: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

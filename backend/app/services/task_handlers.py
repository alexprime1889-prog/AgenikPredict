"""
Reusable task execution handlers for long-running background jobs.
"""

from __future__ import annotations

import traceback
from typing import Any, Dict

from ..config import Config
from ..models.project import ProjectManager, ProjectStatus
from ..models.task import TaskManager, TaskStatus
from ..models.user import (
    finalize_report_generation_reservation,
    release_report_generation_reservation,
)
from ..utils.logger import get_logger
from .graph_builder import GraphBuilderService
from .report_agent import (
    Report,
    ReportAgent,
    ReportManager,
    ReportStatus,
    normalize_analysis_mode,
)
from .simulation_manager import SimulationManager, SimulationStatus
from .text_processor import TextProcessor
from .zep_entity_reader import ZepEntityReader


logger = get_logger("agenikpredict.task_handlers")


def _get_task_metadata(task_id: str) -> Dict[str, Any]:
    task = TaskManager().get_task(task_id)
    return (task.metadata or {}) if task else {}


_RETRYABLE_ERROR_KEYWORDS = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "temporary failure",
    "rate limit",
    "too many requests",
    "service unavailable",
    "connection reset",
    "connection aborted",
    "connection refused",
    "gateway timeout",
    "bad gateway",
    "upstream",
    "503",
    "504",
)

_TERMINAL_ERROR_KEYWORDS = (
    "not found",
    "missing ",
    "invalid ",
    "access denied",
    "insufficient balance",
    "no resource package",
    "payment_required",
)


def _is_retryable_failure(error: Any) -> bool:
    """Best-effort classification for transient upstream failures."""
    if isinstance(error, (TimeoutError, ConnectionError)):
        return True

    class_name = error.__class__.__name__.lower() if isinstance(error, BaseException) else ""
    if "timeout" in class_name:
        return True

    message = str(error or "").lower()
    if any(keyword in message for keyword in _TERMINAL_ERROR_KEYWORDS):
        return False
    return any(keyword in message for keyword in _RETRYABLE_ERROR_KEYWORDS)


def _set_report_retrying(report_id: str, error_message: str):
    report = ReportManager.get_report(report_id) if report_id else None
    if not report:
        return

    report.status = ReportStatus.PENDING
    report.error = error_message
    report.completed_at = ""
    ReportManager.save_report(report)

    progress = ReportManager.get_progress(report_id) or {}
    ReportManager.update_progress(
        report_id,
        "pending",
        progress.get("progress", 0),
        f"Retry scheduled after transient failure: {error_message}",
        current_section=progress.get("current_section"),
        completed_sections=progress.get("completed_sections", []),
    )


def _set_report_failed(report_id: str, error_message: str):
    report = ReportManager.get_report(report_id) if report_id else None
    if not report:
        return

    report.status = ReportStatus.FAILED
    report.error = error_message
    ReportManager.save_report(report)

    progress = ReportManager.get_progress(report_id) or {}
    ReportManager.update_progress(
        report_id,
        "failed",
        -1,
        error_message,
        current_section=progress.get("current_section"),
        completed_sections=progress.get("completed_sections", []),
    )


def _release_reservation_if_needed(user_id: str | None, reservation_id: str | None):
    if user_id and reservation_id:
        release_report_generation_reservation(reservation_id, user_id)


def execute_graph_build_task(task_id: str, lease=None) -> bool:
    task_manager = TaskManager()
    metadata = _get_task_metadata(task_id)
    lease = lease or task_manager.claim_task(task_id)
    if not lease:
        return False

    build_logger = get_logger("agenikpredict.build")
    try:
        lease.start_heartbeat(task_manager)

        project_id = metadata.get("project_id")
        project = ProjectManager.get_project(project_id) if project_id else None
        if not project:
            task_manager.fail_task(
                task_id,
                f"Project not found: {project_id}",
                lease_token=lease.lease_token,
            )
            return True

        graph_name = metadata.get("graph_name") or project.name or "AgenikPredict Graph"
        chunk_size = metadata.get("chunk_size") or project.chunk_size or Config.DEFAULT_CHUNK_SIZE
        chunk_overlap = metadata.get("chunk_overlap") or project.chunk_overlap or Config.DEFAULT_CHUNK_OVERLAP

        text = ProjectManager.get_extracted_text(project.project_id)
        if not text:
            task_manager.fail_task(
                task_id,
                "Extracted text content not found",
                lease_token=lease.lease_token,
            )
            return True

        ontology = project.ontology
        if not ontology:
            task_manager.fail_task(
                task_id,
                "Ontology definition not found",
                lease_token=lease.lease_token,
            )
            return True

        project.status = ProjectStatus.GRAPH_BUILDING
        project.graph_build_task_id = task_id
        ProjectManager.save_project(project)

        build_logger.info("[%s] Starting graph build...", task_id)
        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            message="Initializing graph build service...",
            lease_token=lease.lease_token,
            refresh_lease=True,
        )

        builder = GraphBuilderService(api_key=Config.ZEP_API_KEY)

        task_manager.update_task(
            task_id,
            message="Chunking text...",
            progress=5,
            lease_token=lease.lease_token,
            refresh_lease=True,
        )
        chunks = TextProcessor.split_text(text, chunk_size=chunk_size, overlap=chunk_overlap)
        total_chunks = len(chunks)

        task_manager.update_task(
            task_id,
            message="Creating Zep graph...",
            progress=10,
            lease_token=lease.lease_token,
            refresh_lease=True,
        )
        graph_id = builder.create_graph(name=graph_name)

        project.graph_id = graph_id
        ProjectManager.save_project(project)

        task_manager.update_task(
            task_id,
            message="Setting ontology definition...",
            progress=15,
            lease_token=lease.lease_token,
            refresh_lease=True,
        )
        builder.set_ontology(graph_id, ontology)

        def add_progress_callback(msg, progress_ratio):
            progress = 15 + int(progress_ratio * 40)
            task_manager.update_task(
                task_id,
                message=msg,
                progress=progress,
                lease_token=lease.lease_token,
                refresh_lease=True,
            )

        task_manager.update_task(
            task_id,
            message=f"Starting to add {total_chunks} text chunks...",
            progress=15,
            lease_token=lease.lease_token,
            refresh_lease=True,
        )

        episode_uuids = builder.add_text_batches(
            graph_id,
            chunks,
            batch_size=3,
            progress_callback=add_progress_callback,
        )

        task_manager.update_task(
            task_id,
            message="Waiting for Zep to process data...",
            progress=55,
            lease_token=lease.lease_token,
            refresh_lease=True,
        )

        def wait_progress_callback(msg, progress_ratio):
            progress = 55 + int(progress_ratio * 35)
            task_manager.update_task(
                task_id,
                message=msg,
                progress=progress,
                lease_token=lease.lease_token,
                refresh_lease=True,
            )

        builder._wait_for_episodes(episode_uuids, wait_progress_callback)

        task_manager.update_task(
            task_id,
            message="Fetching graph data...",
            progress=95,
            lease_token=lease.lease_token,
            refresh_lease=True,
        )
        graph_data = builder.get_graph_data(graph_id)

        project.status = ProjectStatus.GRAPH_COMPLETED
        ProjectManager.save_project(project)

        node_count = graph_data.get("node_count", 0)
        edge_count = graph_data.get("edge_count", 0)
        build_logger.info(
            "[%s] Graph build complete: graph_id=%s, nodes=%s, edges=%s",
            task_id,
            graph_id,
            node_count,
            edge_count,
        )
        task_manager.complete_task(
            task_id,
            result={
                "project_id": project.project_id,
                "graph_id": graph_id,
                "node_count": node_count,
                "edge_count": edge_count,
                "chunk_count": total_chunks,
            },
            lease_token=lease.lease_token,
            message="Graph build complete",
        )
        return True

    except Exception as exc:
        build_logger.error("[%s] Graph build failed: %s", task_id, exc)
        build_logger.debug(traceback.format_exc())
        retryable_failure = _is_retryable_failure(exc)
        task_outcome = task_manager.fail_or_retry_task(
            task_id,
            traceback.format_exc(),
            lease_token=lease.lease_token,
            message=f"Build failed: {exc}",
            retryable=retryable_failure,
            dead_letter_reason="graph_build_failed",
        )
        project_id = metadata.get("project_id")
        project = ProjectManager.get_project(project_id) if project_id else None
        if project and task_outcome == "failed":
            project.status = ProjectStatus.FAILED
            project.error = str(exc)
            ProjectManager.save_project(project)
        return True
    finally:
        lease.stop()


def execute_simulation_prepare_task(task_id: str, lease=None) -> bool:
    task_manager = TaskManager()
    metadata = _get_task_metadata(task_id)
    lease = lease or task_manager.claim_task(task_id)
    if not lease:
        return False

    manager = SimulationManager()
    try:
        lease.start_heartbeat(task_manager)

        simulation_id = metadata.get("simulation_id")
        state = manager.get_simulation(simulation_id) if simulation_id else None
        if not state:
            task_manager.fail_task(
                task_id,
                f"Simulation not found: {simulation_id}",
                lease_token=lease.lease_token,
            )
            return True

        project = ProjectManager.get_project(state.project_id)
        if not project:
            task_manager.fail_task(
                task_id,
                f"Project not found: {state.project_id}",
                lease_token=lease.lease_token,
            )
            return True

        simulation_requirement = project.simulation_requirement or ""
        if not simulation_requirement:
            task_manager.fail_task(
                task_id,
                "Project is missing simulation requirement description (simulation_requirement)",
                lease_token=lease.lease_token,
            )
            return True

        document_text = ProjectManager.get_extracted_text(state.project_id) or ""
        language = metadata.get("language", "en")
        entity_types_list = metadata.get("entity_types")
        use_llm_for_profiles = metadata.get("use_llm_for_profiles", True)
        parallel_profile_count = metadata.get("parallel_profile_count", 5)

        state.status = SimulationStatus.PREPARING
        manager._save_simulation_state(state)

        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=0,
            message="Starting simulation environment preparation...",
            lease_token=lease.lease_token,
            refresh_lease=True,
        )

        stage_details = {}

        def progress_callback(stage, progress, message, **kwargs):
            stage_weights = {
                "reading": (0, 20),
                "generating_profiles": (20, 70),
                "generating_config": (70, 90),
                "copying_scripts": (90, 100),
            }
            start, end = stage_weights.get(stage, (0, 100))
            current_progress = int(start + (end - start) * progress / 100)
            stage_names = {
                "reading": "Reading graph entities",
                "generating_profiles": "Generating Agent profiles",
                "generating_config": "Generating simulation config",
                "copying_scripts": "Preparing simulation scripts",
            }
            stage_index = list(stage_weights.keys()).index(stage) + 1 if stage in stage_weights else 1
            total_stages = len(stage_weights)
            stage_details[stage] = {
                "stage_name": stage_names.get(stage, stage),
                "stage_progress": progress,
                "current": kwargs.get("current", 0),
                "total": kwargs.get("total", 0),
                "item_name": kwargs.get("item_name", ""),
            }
            detail = stage_details[stage]
            progress_detail_data = {
                "current_stage": stage,
                "current_stage_name": stage_names.get(stage, stage),
                "stage_index": stage_index,
                "total_stages": total_stages,
                "stage_progress": progress,
                "current_item": detail["current"],
                "total_items": detail["total"],
                "item_description": message,
            }
            if detail["total"] > 0:
                detailed_message = (
                    f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: "
                    f"{detail['current']}/{detail['total']} - {message}"
                )
            else:
                detailed_message = f"[{stage_index}/{total_stages}] {stage_names.get(stage, stage)}: {message}"
            task_manager.update_task(
                task_id,
                progress=current_progress,
                message=detailed_message,
                progress_detail=progress_detail_data,
                lease_token=lease.lease_token,
                refresh_lease=True,
            )

        result_state = manager.prepare_simulation(
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            defined_entity_types=entity_types_list,
            use_llm_for_profiles=use_llm_for_profiles,
            progress_callback=progress_callback,
            parallel_profile_count=parallel_profile_count,
            language=language,
        )

        task_manager.complete_task(
            task_id,
            result=result_state.to_simple_dict(),
            lease_token=lease.lease_token,
        )
        return True

    except Exception as exc:
        logger.error("Simulation preparation failed: %s", traceback.format_exc())
        retryable_failure = _is_retryable_failure(exc)
        task_outcome = task_manager.fail_or_retry_task(
            task_id,
            str(exc),
            lease_token=lease.lease_token,
            message=f"Simulation preparation failed: {exc}",
            retryable=retryable_failure,
            dead_letter_reason="simulation_prepare_failed",
        )
        simulation_id = metadata.get("simulation_id")
        state = manager.get_simulation(simulation_id) if simulation_id else None
        if state and task_outcome == "failed":
            state.status = SimulationStatus.FAILED
            state.error = str(exc)
            manager._save_simulation_state(state)
        return True
    finally:
        lease.stop()


def execute_report_generate_task(task_id: str, lease=None) -> bool:
    task_manager = TaskManager()
    metadata = _get_task_metadata(task_id)
    lease = lease or task_manager.claim_task(task_id)
    if not lease:
        return False

    try:
        lease.start_heartbeat(task_manager)

        simulation_id = metadata.get("simulation_id")
        graph_id = metadata.get("graph_id")
        report_id = metadata.get("report_id")
        project_id = metadata.get("project_id")
        user_id = metadata.get("owner_id")
        language = metadata.get("language", "en")
        analysis_mode = normalize_analysis_mode(metadata.get("analysis_mode"))
        custom_persona = metadata.get("custom_persona", "")
        report_variables = metadata.get("report_variables", {})
        reservation_id = metadata.get("reservation_id")

        manager = SimulationManager()
        state = manager.get_simulation(simulation_id) if simulation_id else None
        project = ProjectManager.get_project(project_id) if project_id else None
        if not state or not project:
            _release_reservation_if_needed(user_id, reservation_id)
            task_manager.fail_task(
                task_id,
                "Simulation or project not found for report generation",
                lease_token=lease.lease_token,
            )
            return True

        simulation_requirement = project.simulation_requirement
        if not simulation_requirement:
            _release_reservation_if_needed(user_id, reservation_id)
            task_manager.fail_task(
                task_id,
                "Missing simulation requirement description",
                lease_token=lease.lease_token,
            )
            return True

        placeholder_report = ReportManager.get_report(report_id) if report_id else None
        if not placeholder_report:
            placeholder_report = Report(
                report_id=report_id,
                simulation_id=simulation_id,
                graph_id=graph_id,
                simulation_requirement=simulation_requirement,
                status=ReportStatus.PENDING,
                language_used=language,
                analysis_mode=analysis_mode,
                source_manifest_summary={},
                explainability={},
            )
            ReportManager.save_report(placeholder_report)

        task_manager.update_task(
            task_id,
            status=TaskStatus.PROCESSING,
            progress=0,
            message="Initializing Report Agent...",
            lease_token=lease.lease_token,
            refresh_lease=True,
        )

        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            language=language,
            analysis_mode=analysis_mode,
            custom_persona=custom_persona,
            report_variables=report_variables,
        )

        def progress_callback(stage, progress, message):
            task_manager.update_task(
                task_id,
                progress=progress,
                message=f"[{stage}] {message}",
                lease_token=lease.lease_token,
                refresh_lease=True,
            )

        report = agent.generate_report(progress_callback=progress_callback, report_id=report_id)

        if report.status == ReportStatus.COMPLETED:
            completed = task_manager.complete_task(
                task_id,
                result={
                    "report_id": report.report_id,
                    "simulation_id": simulation_id,
                    "status": "completed",
                    "analysis_mode": analysis_mode,
                },
                lease_token=lease.lease_token,
            )
            if completed and user_id and reservation_id:
                finalize_report_generation_reservation(
                    reservation_id,
                    user_id,
                    usage=report.usage,
                    report_id=report.report_id,
                    simulation_id=simulation_id,
                    model=Config.LLM_MODEL_NAME,
                )
            elif not completed:
                logger.warning(
                    "Skipped report finalization because task completion lost lease ownership: task_id=%s report_id=%s",
                    task_id,
                    report.report_id,
                )
        else:
            error_message = report.error or "Report generation failed"
            task_outcome = task_manager.fail_or_retry_task(
                task_id,
                error_message,
                lease_token=lease.lease_token,
                message=f"Report generation failed: {error_message}",
                retryable=_is_retryable_failure(error_message),
                dead_letter_reason="report_generation_failed",
            )
            if task_outcome == "retry_scheduled":
                _set_report_retrying(report.report_id, error_message)
            elif task_outcome == "failed":
                _release_reservation_if_needed(user_id, reservation_id)
                _set_report_failed(report.report_id, error_message)

        return True

    except Exception as exc:
        logger.error("Report generation failed: %s", exc)
        user_id = metadata.get("owner_id")
        reservation_id = metadata.get("reservation_id")
        report_id = metadata.get("report_id")
        task_outcome = task_manager.fail_or_retry_task(
            task_id,
            str(exc),
            lease_token=lease.lease_token,
            message=f"Report generation failed: {exc}",
            retryable=_is_retryable_failure(exc),
            dead_letter_reason="report_generation_exception",
        )
        if task_outcome == "retry_scheduled":
            _set_report_retrying(report_id, str(exc))
        elif task_outcome == "failed":
            _release_reservation_if_needed(user_id, reservation_id)
            _set_report_failed(report_id, str(exc))
        return True
    finally:
        lease.stop()


TASK_HANDLERS = {
    "graph_build": execute_graph_build_task,
    "simulation_prepare": execute_simulation_prepare_task,
    "report_generate": execute_report_generate_task,
}

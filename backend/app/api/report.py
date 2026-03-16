"""
Report API routes
Provides simulation report generation, retrieval, and conversation endpoints
"""

import os
import traceback
import threading
from flask import request, jsonify, send_file, g

from . import report_bp
from ..config import Config
from ..services.report_agent import ReportAgent, ReportManager, ReportStatus
from ..services.simulation_manager import SimulationManager
from ..models.project import ProjectManager
from ..models.task import TaskManager, TaskStatus
from ..models.user import get_user_billing_status
from .auth import require_auth, optional_auth
from ..utils.logger import get_logger

logger = get_logger('agenikpredict.api.report')


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
    try:
        # Check billing status if user is authenticated
        user_id = getattr(g, 'user_id', None)
        if user_id:
            status = get_user_billing_status(user_id)
            if not status['can_generate']:
                return jsonify({
                    "success": False,
                    "error": "trial_expired",
                    "message": "Your free trial has ended. Please add credits to continue generating reports.",
                    "billing_status": status
                }), 402

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

        # Get simulation info (with ownership check)
        state, project, error = _verify_simulation_access(simulation_id)
        if error:
            return error

        # Check for existing report
        if not force_regenerate:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "message": "Report already exists",
                        "already_generated": True
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
        
        # Read user's language preference
        language = request.headers.get('Accept-Language', 'en')

        # Pre-generate report_id for immediate frontend return
        import uuid
        report_id = f"report_{uuid.uuid4().hex[:12]}"
        
        # Create async task
        task_manager = TaskManager()
        task_id = task_manager.create_task(
            task_type="report_generate",
            metadata={
                "simulation_id": simulation_id,
                "graph_id": graph_id,
                "report_id": report_id
            }
        )
        
        # Define background task
        def run_generate():
            try:
                task_manager.update_task(
                    task_id,
                    status=TaskStatus.PROCESSING,
                    progress=0,
                    message="Initializing Report Agent..."
                )
                
                # Create Report Agent
                agent = ReportAgent(
                    graph_id=graph_id,
                    simulation_id=simulation_id,
                    simulation_requirement=simulation_requirement,
                    language=language,
                    custom_persona=custom_persona,
                    report_variables=report_variables
                )
                
                # Progress callback
                def progress_callback(stage, progress, message):
                    task_manager.update_task(
                        task_id,
                        progress=progress,
                        message=f"[{stage}] {message}"
                    )
                
                # Generate report (pass pre-generated report_id)
                report = agent.generate_report(
                    progress_callback=progress_callback,
                    report_id=report_id
                )
                
                # Save report
                ReportManager.save_report(report)
                
                if report.status == ReportStatus.COMPLETED:
                    task_manager.complete_task(
                        task_id,
                        result={
                            "report_id": report.report_id,
                            "simulation_id": simulation_id,
                            "status": "completed"
                        }
                    )
                else:
                    task_manager.fail_task(task_id, report.error or "Report generation failed")
                
            except Exception as e:
                logger.error(f"Report generation failed: {str(e)}")
                task_manager.fail_task(task_id, str(e))
        
        # Start background thread
        thread = threading.Thread(target=run_generate, daemon=True)
        thread.start()
        
        return jsonify({
            "success": True,
            "data": {
                "simulation_id": simulation_id,
                "report_id": report_id,
                "task_id": task_id,
                "status": "generating",
                "message": "Report generation task started, query progress via /api/report/generate/status",
                "already_generated": False
            }
        })
        
    except Exception as e:
        logger.error(f"Failed to start report generation task: {traceback.format_exc()}")
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
        
        # If simulation_id provided, first check for completed report
        if simulation_id:
            existing_report = ReportManager.get_report_by_simulation(simulation_id)
            if existing_report and existing_report.status == ReportStatus.COMPLETED:
                return jsonify({
                    "success": True,
                    "data": {
                        "simulation_id": simulation_id,
                        "report_id": existing_report.report_id,
                        "status": "completed",
                        "progress": 100,
                        "message": "Report already generated",
                        "already_completed": True
                    }
                })
        
        if not task_id:
            return jsonify({
                "success": False,
                "error": "Please provide task_id or simulation_id"
            }), 400
        
        task_manager = TaskManager()
        task = task_manager.get_task(task_id)
        
        if not task:
            return jsonify({
                "success": False,
                "error": f"Task not found: {task_id}"
            }), 404
        
        return jsonify({
            "success": True,
            "data": task.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Failed to query task status: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============== Report Retrieval API ==============

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

        report = ReportManager.get_report_by_simulation(simulation_id)

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

        graph_id = state.graph_id or project.graph_id
        if not graph_id:
            return jsonify({
                "success": False,
                "error": "Missing graph ID"
            }), 400
        
        simulation_requirement = project.simulation_requirement or ""

        # Read user's language preference
        language = request.headers.get('Accept-Language', 'en')

        # Create Agent and start conversation
        agent = ReportAgent(
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
            language=language
        )

        result = agent.chat(message=message, chat_history=chat_history)
        
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

        report = ReportManager.get_report_by_simulation(simulation_id)
        
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

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, g

from app.api import report as report_api
from app.models.task import TaskStatus
from app.models.prediction_ledger import PredictionLedgerManager
from app.services import task_handlers
from app.services.artifact_store import reset_artifact_store
from app.services.live_evidence import LiveMarketSnapshotResult, LiveNewsResult
from app.services.perplexity_provider import PerplexityProvider
from app.services.report_agent import (
    Report,
    ReportAgent,
    ReportManager,
    ReportOutline,
    ReportSection,
    ReportStatus,
    normalize_analysis_mode,
)
from app.services.source_manifest import SourceEntry, SourceManifest
from app.services.zep_tools import InsightForgeResult, InterviewResult, PanoramaResult, SearchResult
from app.config import Config


@pytest.fixture()
def flask_app():
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test")
    return app


@pytest.fixture()
def artifact_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "ARTIFACT_ROOT", str(tmp_path))
    reset_artifact_store()
    PredictionLedgerManager.init_db()
    yield tmp_path
    reset_artifact_store()


class FakeZepTools:
    def get_simulation_context(self, graph_id, simulation_requirement):
        return {
            "graph_statistics": {
                "total_nodes": 12,
                "total_edges": 7,
                "entity_types": {"Company": 4, "Person": 8},
            },
            "total_entities": 6,
            "related_facts": ["Demand accelerated after the new launch."],
        }

    def quick_search(self, graph_id, query, limit=10):
        return SearchResult(
            facts=[f"Quick fact for {query}"],
            edges=[],
            nodes=[],
            query=query,
            total_count=1,
        )

    def panorama_search(self, graph_id, query, include_expired=True):
        return PanoramaResult(
            query=query,
            all_nodes=[],
            all_edges=[],
            active_facts=[f"Active fact for {query}"],
            historical_facts=[f"Historical fact for {query}"] if include_expired else [],
            total_nodes=2,
            total_edges=1,
            active_count=1,
            historical_count=1 if include_expired else 0,
        )

    def insight_forge(self, graph_id, query, simulation_requirement, report_context=""):
        return InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[query],
            semantic_facts=[f"Deep fact for {query}"],
            entity_insights=[],
            relationship_chains=[],
            total_facts=1,
            total_entities=1,
            total_relationships=0,
        )

    def interview_agents(self, simulation_id, interview_requirement, simulation_requirement, max_agents=5):
        return InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=["What changed?"],
            selected_agents=[],
            interviews=[],
            selection_reasoning="Selected the most relevant agents.",
            summary="Agents converged on the base scenario.",
            total_agents=max_agents,
            interviewed_count=0,
        )

    def get_graph_statistics(self, graph_id):
        return {"total_nodes": 12, "total_edges": 7}

    def get_entity_summary(self, graph_id, entity_name):
        return {"entity": entity_name, "summary": "Entity summary"}

    def get_entities_by_type(self, graph_id, entity_type):
        return []


class FakeLiveEvidenceDisabled:
    def __init__(self):
        self.enabled = False

    def live_news_brief(self, query, max_items=5):
        return LiveNewsResult(query=query, provider="fake_news", fetched_at="2026-03-19T00:00:00+00:00")

    def live_market_snapshot(self, query, max_symbols=5, context=""):
        return LiveMarketSnapshotResult(query=query, fetched_at="2026-03-19T00:00:00+00:00")


class FakeLLM:
    def __init__(self, *, outline_sections=4):
        self.outline_sections = outline_sections

    def chat(self, messages, temperature=0.5, max_tokens=4096, response_format=None):
        last_user = messages[-1]["content"]
        if "Observation (retrieval results)" in last_user or "Please immediately output section content" in last_user:
            return "Final Answer: Evidence-backed section content.", {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
        return (
            '<tool_call>{"name":"quick_search","parameters":{"query":"core signal","limit":3}}</tool_call>',
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    def chat_json(self, messages, temperature=0.3, max_tokens=4096):
        system_prompt = messages[0]["content"]
        if "compact explainability block" in system_prompt:
            return {
                "why_this_conclusion": "Итог опирается на согласованный набор сигналов.",
                "basis_summary": [
                    "Сигналы спроса усилились.",
                    "Структурные риски остались контролируемыми.",
                    "Базовый сценарий получил наибольшую поддержку.",
                ],
                "source_ids": ["src_manifest_1"],
            }, {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}

        sections = [
            {"title": f"Section {index}", "description": f"Description {index}"}
            for index in range(1, self.outline_sections + 1)
        ]
        return {
            "title": "Simulation Analysis Report",
            "summary": "Concise summary",
            "sections": sections,
        }, {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}

    def chat_json_with_fallback(self, messages, temperature=0.2, max_tokens=1600):
        return {
            "forecast_horizon": "12 months",
            "confidence_note": "Moderate confidence",
            "scenarios": [
                {"name": "Bull case", "probability": 25, "timeframe": "12 months", "summary": "Bull", "key_drivers": ["Driver"], "key_risks": ["Risk"], "assumptions": ["Assumption"]},
                {"name": "Base case", "probability": 50, "timeframe": "12 months", "summary": "Base", "key_drivers": ["Driver"], "key_risks": ["Risk"], "assumptions": ["Assumption"]},
                {"name": "Bear case", "probability": 25, "timeframe": "12 months", "summary": "Bear", "key_drivers": ["Driver"], "key_risks": ["Risk"], "assumptions": ["Assumption"]},
            ],
            "caveats": ["Caveat"],
        }, {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}


def _response_payload(result):
    if isinstance(result, tuple):
        response, status_code = result
        return response.get_json(), status_code
    return result.get_json(), result.status_code


def test_report_agent_limits_and_tool_gating(monkeypatch):
    monkeypatch.setattr(Config, "REPORT_AGENT_MAX_TOOL_CALLS", 4)
    monkeypatch.setattr(Config, "REPORT_AGENT_MAX_REFLECTION_ROUNDS", 5)
    monkeypatch.setattr(Config, "PERPLEXITY_API_KEY", "perplexity-test-key")

    quick_agent = ReportAgent(
        graph_id="graph_1",
        simulation_id="sim_1",
        simulation_requirement="Analyze the next quarter",
        llm_client=FakeLLM(),
        zep_tools=FakeZepTools(),
        analysis_mode="quick",
    )
    global_agent = ReportAgent(
        graph_id="graph_1",
        simulation_id="sim_1",
        simulation_requirement="Analyze the next quarter",
        llm_client=FakeLLM(),
        zep_tools=FakeZepTools(),
        analysis_mode="global",
    )

    assert quick_agent.max_tool_calls_per_section == 2
    assert quick_agent.max_reflection_rounds == 2
    assert quick_agent.min_tool_calls_per_section == 1
    assert "insight_forge" not in quick_agent.tools
    assert "interview_agents" not in quick_agent.tools
    assert "web_search" not in quick_agent.tools

    assert global_agent.max_tool_calls_per_section == 4
    assert global_agent.max_reflection_rounds == 5
    assert "insight_forge" in global_agent.tools
    assert "interview_agents" in global_agent.tools
    assert "web_search" in global_agent.tools


def test_quick_outline_clamps_to_three_sections(monkeypatch):
    monkeypatch.setattr(Config, "PERPLEXITY_API_KEY", None)

    agent = ReportAgent(
        graph_id="graph_1",
        simulation_id="sim_1",
        simulation_requirement="Compact analysis",
        llm_client=FakeLLM(outline_sections=5),
        zep_tools=FakeZepTools(),
        analysis_mode="quick",
    )

    outline = agent.plan_outline()

    assert len(outline.sections) == 3
    assert [section.title for section in outline.sections] == ["Section 1", "Section 2", "Section 3"]


def test_quick_mode_rejects_heavy_legacy_aliases(monkeypatch):
    monkeypatch.setattr(Config, "PERPLEXITY_API_KEY", None)

    agent = ReportAgent(
        graph_id="graph_1",
        simulation_id="sim_1",
        simulation_requirement="Compact analysis",
        llm_client=FakeLLM(),
        zep_tools=FakeZepTools(),
        analysis_mode="quick",
    )

    assert agent._is_valid_tool_call({"name": "search_graph", "parameters": {"query": "x"}}) is True
    assert agent._is_valid_tool_call({"name": "get_graph_statistics", "parameters": {}}) is False
    assert agent._is_valid_tool_call({"name": "get_entity_summary", "parameters": {"entity_name": "x"}}) is False
    assert agent._is_valid_tool_call({"name": "get_entities_by_type", "parameters": {"entity_type": "Company"}}) is False
    assert agent._is_valid_tool_call({"name": "get_simulation_context", "parameters": {"query": "x"}}) is False
    blocked = agent._execute_tool("get_simulation_context", {"query": "x"})
    assert "unavailable in quick mode" in blocked.text
    blocked_stats = agent._execute_tool("get_graph_statistics", {})
    assert "unavailable in quick mode" in blocked_stats.text


def test_source_manifest_persistence_and_legacy_defaults(artifact_root):
    manifest = SourceManifest(
        report_id="report_manifest",
        simulation_id="sim_manifest",
        graph_id="graph_manifest",
        analysis_mode="quick",
        language="ru",
    )
    manifest.add_source(
        SourceEntry.create(
            source_id="src_manifest_1",
            provider="zep_graph",
            source_type="graph_fact",
            query="demand",
            title="Demand fact",
            snippet="Demand accelerated.",
            language="ru",
        )
    )
    report = Report(
        report_id="report_manifest",
        simulation_id="sim_manifest",
        graph_id="graph_manifest",
        simulation_requirement="Forecast demand",
        status=ReportStatus.COMPLETED,
        outline=ReportOutline(title="Report", summary="Summary", sections=[ReportSection(title="Section 1", content="Content")]),
        markdown_content="# Report\n\nContent",
        created_at="2026-03-19T00:00:00",
        completed_at="2026-03-19T00:10:00",
        language_used="ru",
        analysis_mode="quick",
        source_manifest_summary=manifest.summary(),
        explainability={"why_this_conclusion": "Потому что сигналы согласованы.", "basis_summary": ["Основание"], "source_attribution": []},
    )

    ReportManager.save_source_manifest(report.report_id, manifest)
    ReportManager.save_report(report)

    meta_path = Path(ReportManager._get_report_path(report.report_id))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["analysis_mode"] == "quick"
    assert meta["source_manifest_summary"]["source_count"] == 1

    restored = ReportManager.get_report(report.report_id)
    assert restored is not None
    assert restored.analysis_mode == "quick"
    assert restored.source_manifest_summary["source_count"] == 1
    assert restored.explainability["why_this_conclusion"] == "Потому что сигналы согласованы."
    assert restored.language_used == "ru"

    legacy_folder = Path(ReportManager._get_report_folder("legacy_report", ensure=True))
    legacy_meta = {
        "report_id": "legacy_report",
        "simulation_id": "sim_manifest",
        "graph_id": "graph_manifest",
        "simulation_requirement": "Legacy report",
        "status": "completed",
        "language_used": "he",
    }
    (legacy_folder / "meta.json").write_text(json.dumps(legacy_meta), encoding="utf-8")

    legacy_report = ReportManager.get_report("legacy_report")
    assert legacy_report.analysis_mode == "global"
    assert legacy_report.source_manifest_summary == {}
    assert legacy_report.explainability == {}
    assert legacy_report.language_used == "he"


def test_perplexity_provider_fallbacks(monkeypatch):
    no_key_provider = PerplexityProvider(api_key=None)
    no_key_result = no_key_provider.search("latest earnings")
    assert no_key_result.entries == []
    assert no_key_result.warnings

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"unexpected": []}).encode("utf-8")

    monkeypatch.setattr("app.services.perplexity_provider.urlopen", lambda request, timeout=10: FakeResponse())
    malformed_provider = PerplexityProvider(api_key="configured")
    malformed_result = malformed_provider.search("latest earnings")
    assert malformed_result.entries == []
    assert malformed_result.warnings


def test_api_and_worker_propagate_analysis_mode(monkeypatch, flask_app):
    captured = {"saved_reports": []}

    class FakeTaskManagerRoute:
        def find_active_task(self, *args, **kwargs):
            return None

        def create_or_reuse_task(self, task_type, metadata, execution_key, max_attempts):
            captured["task_metadata"] = metadata
            return SimpleNamespace(
                task_id="task_route_1",
                metadata=metadata,
                status=TaskStatus.PENDING,
                message="Queued",
            ), True

    monkeypatch.setattr(report_api, "_verify_simulation_access", lambda simulation_id: (
        SimpleNamespace(simulation_id=simulation_id, graph_id="graph_route", project_id="project_route"),
        SimpleNamespace(project_id="project_route", graph_id="graph_route", simulation_requirement="Need a quick view"),
        None,
    ))
    monkeypatch.setattr(report_api, "ensure_worker_dispatch_ready", lambda: None)
    monkeypatch.setattr(report_api, "dispatch_task", lambda task_id: captured.setdefault("dispatched", []).append(task_id))
    monkeypatch.setattr(report_api, "reserve_report_generation", lambda *args, **kwargs: (True, 0, "", "reservation_1"))
    monkeypatch.setattr(report_api, "TaskManager", FakeTaskManagerRoute)
    monkeypatch.setattr(report_api.ReportManager, "get_report_by_simulation", classmethod(lambda cls, *args, **kwargs: None))
    monkeypatch.setattr(report_api.ReportManager, "save_report", classmethod(lambda cls, report: captured["saved_reports"].append(report)))
    monkeypatch.setattr(report_api.ReportManager, "update_progress", classmethod(lambda cls, *args, **kwargs: None))

    with flask_app.test_request_context(
        "/api/report/generate",
        method="POST",
        json={"simulation_id": "sim_route", "analysis_mode": "quick", "language": "ru"},
    ):
        g.user_id = "user_1"
        g.user_role = "user"
        payload, status_code = _response_payload(report_api.generate_report.__wrapped__())

    assert status_code == 200
    assert payload["data"]["analysis_mode"] == "quick"
    assert captured["task_metadata"]["analysis_mode"] == "quick"
    assert captured["saved_reports"][0].analysis_mode == "quick"

    worker_capture = {}
    worker_metadata = {
        "simulation_id": "sim_worker",
        "graph_id": "graph_worker",
        "report_id": "report_worker",
        "project_id": "project_worker",
        "owner_id": None,
        "language": "he",
        "analysis_mode": "quick",
        "custom_persona": "",
        "report_variables": {},
        "reservation_id": None,
    }

    class FakeLease:
        lease_token = "lease_1"

        def start_heartbeat(self, task_manager):
            return None

        def stop(self):
            return None

    class FakeTaskManagerWorker:
        def claim_task(self, task_id):
            return FakeLease()

        def update_task(self, *args, **kwargs):
            return None

        def complete_task(self, task_id, result, lease_token=None):
            worker_capture["result"] = result
            return True

        def fail_or_retry_task(self, *args, **kwargs):
            raise AssertionError("fail_or_retry_task should not be called in the success path")

    class FakeReportAgentWorker:
        def __init__(self, *args, **kwargs):
            worker_capture["analysis_mode"] = kwargs.get("analysis_mode")

        def generate_report(self, progress_callback=None, report_id=None):
            return Report(
                report_id=report_id,
                simulation_id="sim_worker",
                graph_id="graph_worker",
                simulation_requirement="Need a quick view",
                status=ReportStatus.COMPLETED,
                created_at="2026-03-19T00:00:00",
                completed_at="2026-03-19T00:05:00",
                language_used="he",
                analysis_mode="quick",
                source_manifest_summary={},
                explainability={},
            )

        @property
        def usage(self):
            return {}

    monkeypatch.setattr(task_handlers, "_get_task_metadata", lambda task_id: worker_metadata)
    monkeypatch.setattr(task_handlers, "TaskManager", FakeTaskManagerWorker)
    monkeypatch.setattr(task_handlers, "SimulationManager", lambda: SimpleNamespace(get_simulation=lambda simulation_id: SimpleNamespace(simulation_id=simulation_id)))
    monkeypatch.setattr(task_handlers.ProjectManager, "get_project", staticmethod(lambda project_id: SimpleNamespace(project_id=project_id, simulation_requirement="Need a quick view")))
    monkeypatch.setattr(task_handlers.ReportManager, "get_report", classmethod(lambda cls, report_id: None))
    monkeypatch.setattr(task_handlers.ReportManager, "save_report", classmethod(lambda cls, report: None))
    monkeypatch.setattr(task_handlers, "ReportAgent", FakeReportAgentWorker)

    assert task_handlers.execute_report_generate_task("task_worker") is True
    assert worker_capture["analysis_mode"] == "quick"
    assert worker_capture["result"]["analysis_mode"] == "quick"


def test_generate_status_uses_task_language_and_mode_filters(monkeypatch, flask_app):
    captured = {}
    task = SimpleNamespace(
        task_id="task_status",
        metadata={"language": "ru", "analysis_mode": "quick", "report_id": "report_status", "simulation_id": "sim_status"},
        status=TaskStatus.PENDING,
        to_dict=lambda: {"task_id": "task_status", "status": "pending", "metadata": task.metadata},
    )

    class FakeTaskManager:
        def get_task(self, task_id):
            return task

    def fake_get_report_by_simulation(cls, simulation_id, **kwargs):
        captured["kwargs"] = kwargs
        return Report(
            report_id="report_status",
            simulation_id=simulation_id,
            graph_id="graph_status",
            simulation_requirement="Status lookup",
            status=ReportStatus.COMPLETED,
            created_at="2026-03-19T00:00:00",
            completed_at="2026-03-19T00:02:00",
            language_used="ru",
            analysis_mode="quick",
        )

    monkeypatch.setattr(report_api, "TaskManager", FakeTaskManager)
    monkeypatch.setattr(report_api, "_verify_task_access", lambda task_id, task: None)
    monkeypatch.setattr(report_api, "_verify_simulation_access", lambda simulation_id: (
        SimpleNamespace(simulation_id=simulation_id, graph_id="graph_status", project_id="project_status"),
        SimpleNamespace(project_id="project_status", graph_id="graph_status", simulation_requirement="Status lookup"),
        None,
    ))
    monkeypatch.setattr(report_api.ReportManager, "get_report_by_simulation", classmethod(fake_get_report_by_simulation))

    with flask_app.test_request_context(
        "/api/report/generate/status",
        method="POST",
        json={"task_id": "task_status", "simulation_id": "sim_status"},
    ):
        g.user_id = "user_1"
        g.user_role = "user"
        payload, status_code = _response_payload(report_api.get_generate_status.__wrapped__())

    assert status_code == 200
    assert payload["data"]["analysis_mode"] == "quick"
    assert payload["data"]["language_used"] == "ru"
    assert payload["data"]["report_id"] == "report_status"
    assert payload["data"]["simulation_id"] == "sim_status"
    assert captured["kwargs"]["language_used"] == "ru"
    assert captured["kwargs"]["analysis_mode"] == "quick"


def test_generate_status_defaults_to_request_language_and_global_mode(monkeypatch, flask_app):
    captured = {}

    def fake_get_report_by_simulation(cls, simulation_id, **kwargs):
        captured["kwargs"] = kwargs
        return Report(
            report_id="report_status_default",
            simulation_id=simulation_id,
            graph_id="graph_status",
            simulation_requirement="Status lookup",
            status=ReportStatus.COMPLETED,
            created_at="2026-03-19T00:00:00",
            completed_at="2026-03-19T00:02:00",
            language_used="he",
            analysis_mode="global",
        )

    monkeypatch.setattr(report_api, "_verify_simulation_access", lambda simulation_id: (
        SimpleNamespace(simulation_id=simulation_id, graph_id="graph_status", project_id="project_status"),
        SimpleNamespace(project_id="project_status", graph_id="graph_status", simulation_requirement="Status lookup"),
        None,
    ))
    monkeypatch.setattr(report_api.ReportManager, "get_report_by_simulation", classmethod(fake_get_report_by_simulation))

    with flask_app.test_request_context(
        "/api/report/generate/status",
        method="POST",
        headers={"Accept-Language": "he-IL,he;q=0.9,en;q=0.8"},
        json={"simulation_id": "sim_status_default"},
    ):
        g.user_id = "user_1"
        g.user_role = "user"
        payload, status_code = _response_payload(report_api.get_generate_status.__wrapped__())

    assert status_code == 200
    assert payload["data"]["analysis_mode"] == "global"
    assert payload["data"]["language_used"] == "he"
    assert captured["kwargs"]["language_used"] == "he"
    assert captured["kwargs"]["analysis_mode"] == "global"


def test_generate_report_completes_without_perplexity_key(monkeypatch, artifact_root):
    monkeypatch.setattr(Config, "REPORT_AGENT_MAX_TOOL_CALLS", 1)
    monkeypatch.setattr(Config, "REPORT_AGENT_MAX_REFLECTION_ROUNDS", 2)
    monkeypatch.setattr(Config, "PERPLEXITY_API_KEY", None)
    monkeypatch.setattr("app.services.report_agent.LiveEvidenceService", FakeLiveEvidenceDisabled)

    agent = ReportAgent(
        graph_id="graph_full",
        simulation_id="sim_full",
        simulation_requirement="Forecast product demand",
        llm_client=FakeLLM(outline_sections=2),
        zep_tools=FakeZepTools(),
        language="ru",
        analysis_mode="global",
    )

    report = agent.generate_report(report_id="report_full")
    manifest = ReportManager.get_source_manifest("report_full")

    assert "web_search" not in agent.tools
    assert report.status == ReportStatus.COMPLETED
    assert report.analysis_mode == "global"
    assert manifest is not None
    assert manifest.analysis_mode == "global"
    assert Path(ReportManager._get_source_manifest_path("report_full")).exists()
    assert report.source_manifest_summary["source_count"] >= 1
    assert report.explainability["basis_summary"]
    assert normalize_analysis_mode(report.analysis_mode) == "global"


def test_get_report_ignores_malformed_source_manifest(artifact_root):
    report_folder = Path(ReportManager._get_report_folder("report_broken", ensure=True))
    meta = {
        "report_id": "report_broken",
        "simulation_id": "sim_broken",
        "graph_id": "graph_broken",
        "simulation_requirement": "Broken manifest",
        "status": "completed",
        "language_used": "en",
        "analysis_mode": "global",
    }
    (report_folder / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (report_folder / "source_manifest.json").write_text("{not valid json", encoding="utf-8")

    report = ReportManager.get_report("report_broken")

    assert report is not None
    assert report.analysis_mode == "global"
    assert report.source_manifest_summary == {}

"""
Prediction ledger model.

Stores structured scenario probabilities separately from markdown reports so
future backtesting and calibration can query a stable source of truth.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .user import PH, get_db
from ..models.project import ProjectManager
from ..services.simulation_manager import SimulationManager
from ..utils.logger import get_logger


logger = get_logger("agenikpredict.prediction_ledger")


@dataclass
class PredictionLedgerEntry:
    prediction_id: str
    report_id: str
    simulation_id: str
    graph_id: str
    project_id: Optional[str]
    owner_id: Optional[str]
    scenario_name: str
    scenario_order: int
    probability: int
    timeframe: str
    forecast_horizon: str
    summary: str
    key_drivers: List[str]
    key_risks: List[str]
    assumptions: List[str]
    confidence_note: str
    caveats: List[str]
    source: str
    outcome_status: Optional[str]
    outcome_recorded_at: Optional[str]
    outcome_notes: Optional[str]
    outcome_payload: Dict[str, Any]
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "project_id": self.project_id,
            "owner_id": self.owner_id,
            "scenario_name": self.scenario_name,
            "scenario_order": self.scenario_order,
            "probability": self.probability,
            "timeframe": self.timeframe,
            "forecast_horizon": self.forecast_horizon,
            "summary": self.summary,
            "key_drivers": self.key_drivers,
            "key_risks": self.key_risks,
            "assumptions": self.assumptions,
            "confidence_note": self.confidence_note,
            "caveats": self.caveats,
            "source": self.source,
            "outcome_status": self.outcome_status,
            "outcome_recorded_at": self.outcome_recorded_at,
            "outcome_notes": self.outcome_notes,
            "outcome_payload": self.outcome_payload,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PredictionLedgerManager:
    """DB-backed prediction ledger for structured report scenarios."""

    @staticmethod
    def _actual_score_for_status(status: Optional[str]) -> Optional[float]:
        outcome_value_map = {
            "observed": 1.0,
            "not_observed": 0.0,
            "partial": 0.5,
        }
        return outcome_value_map.get((status or "").strip().lower())

    @classmethod
    def _build_calibration_buckets(cls, entries: List[PredictionLedgerEntry]) -> List[Dict[str, Any]]:
        bucket_specs = [
            (0, 20),
            (20, 40),
            (40, 60),
            (60, 80),
            (80, 101),
        ]
        bucket_entries: Dict[str, List[PredictionLedgerEntry]] = {
            f"{start:02d}-{end - 1:02d}%": []
            for start, end in bucket_specs
        }

        for entry in entries:
            probability = max(0, min(100, int(entry.probability or 0)))
            for start, end in bucket_specs:
                if start <= probability < end:
                    bucket_entries[f"{start:02d}-{end - 1:02d}%"].append(entry)
                    break

        buckets: List[Dict[str, Any]] = []
        for label, bucket in bucket_entries.items():
            settled_scores = [
                cls._actual_score_for_status(entry.outcome_status)
                for entry in bucket
                if cls._actual_score_for_status(entry.outcome_status) is not None
            ]
            avg_probability = round(sum(entry.probability for entry in bucket) / len(bucket), 2) if bucket else None
            actual_rate = round(sum(settled_scores) / len(settled_scores), 4) if settled_scores else None
            buckets.append(
                {
                    "range": label,
                    "prediction_count": len(bucket),
                    "settled_count": len(settled_scores),
                    "average_probability": avg_probability,
                    "actual_rate": actual_rate,
                    "calibration_gap": round((avg_probability / 100.0) - actual_rate, 4)
                    if avg_probability is not None and actual_rate is not None
                    else None,
                }
            )
        return buckets

    @classmethod
    def _compute_top_scenario_stats(cls, entries: List[PredictionLedgerEntry]) -> Dict[str, Any]:
        grouped: Dict[str, List[PredictionLedgerEntry]] = {}
        for entry in entries:
            if cls._actual_score_for_status(entry.outcome_status) is None:
                continue
            case_id = str((entry.outcome_payload or {}).get("historical_case_id") or "").strip()
            group_key = f"{entry.report_id}:{case_id or entry.simulation_id}"
            grouped.setdefault(group_key, []).append(entry)

        if not grouped:
            return {
                "evaluated_report_groups": 0,
                "top_scenario_hit_rate": None,
                "average_probability_on_observed_path": None,
            }

        top_scores: List[float] = []
        observed_mass_values: List[float] = []
        for group_entries in grouped.values():
            max_probability = max(entry.probability for entry in group_entries)
            top_entries = [entry for entry in group_entries if entry.probability == max_probability]
            top_entry_scores = [
                cls._actual_score_for_status(entry.outcome_status)
                for entry in top_entries
                if cls._actual_score_for_status(entry.outcome_status) is not None
            ]
            if top_entry_scores:
                top_scores.append(max(top_entry_scores))

            observed_mass = 0.0
            for entry in group_entries:
                actual_score = cls._actual_score_for_status(entry.outcome_status)
                if actual_score is not None and actual_score > 0:
                    observed_mass += (entry.probability / 100.0) * actual_score
            observed_mass_values.append(observed_mass)

        return {
            "evaluated_report_groups": len(grouped),
            "top_scenario_hit_rate": round(sum(top_scores) / len(top_scores), 6) if top_scores else None,
            "average_probability_on_observed_path": round(sum(observed_mass_values) / len(observed_mass_values), 6)
            if observed_mass_values else None,
        }

    @classmethod
    def _summarize_groups(
        cls,
        groups: Dict[str, List[PredictionLedgerEntry]],
        *,
        metadata_factory: Optional[Callable[[str, List[PredictionLedgerEntry]], Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for group_key, group_entries in groups.items():
            latest_timestamp = max((entry.updated_at or entry.created_at or "") for entry in group_entries)
            payload = {
                "key": group_key,
                "prediction_count": len(group_entries),
                "report_count": len({entry.report_id for entry in group_entries}),
                "latest_outcome_at": latest_timestamp or None,
                "metrics": cls._compute_metrics_from_entries(group_entries),
            }
            if metadata_factory:
                payload.update(metadata_factory(group_key, group_entries))
            items.append(payload)

        items.sort(
            key=lambda item: (
                item.get("latest_outcome_at") or "",
                item.get("prediction_count") or 0,
            ),
            reverse=True,
        )
        return items

    @staticmethod
    def _compute_metrics_from_entries(entries: List[PredictionLedgerEntry]) -> Dict[str, Any]:
        settled_entries = [
            entry for entry in entries
            if PredictionLedgerManager._actual_score_for_status(entry.outcome_status) is not None
        ]

        def _avg_probability(target_status: str) -> Optional[float]:
            matched = [entry.probability for entry in settled_entries if entry.outcome_status == target_status]
            if not matched:
                return None
            return round(sum(matched) / len(matched), 2)

        brier_terms = [
            ((entry.probability / 100.0) - PredictionLedgerManager._actual_score_for_status(entry.outcome_status)) ** 2
            for entry in settled_entries
        ]
        top_scenario_stats = PredictionLedgerManager._compute_top_scenario_stats(entries)
        metrics = {
            "total_predictions": len(entries),
            "settled_predictions": len(settled_entries),
            "pending_predictions": len([entry for entry in entries if entry.outcome_status in (None, "", "pending")]),
            "observed_count": len([entry for entry in settled_entries if entry.outcome_status == "observed"]),
            "not_observed_count": len([entry for entry in settled_entries if entry.outcome_status == "not_observed"]),
            "partial_count": len([entry for entry in settled_entries if entry.outcome_status == "partial"]),
            "average_probability_observed": _avg_probability("observed"),
            "average_probability_not_observed": _avg_probability("not_observed"),
            "average_probability_partial": _avg_probability("partial"),
            "brier_score": round(sum(brier_terms) / len(brier_terms), 6) if brier_terms else None,
            "settled_rate": round(len(settled_entries) / len(entries), 6) if entries else None,
        }
        metrics.update(top_scenario_stats)
        return metrics

    @staticmethod
    def init_db():
        with get_db() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS prediction_ledger (
                    prediction_id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    simulation_id TEXT NOT NULL,
                    graph_id TEXT DEFAULT '',
                    project_id TEXT,
                    owner_id TEXT,
                    scenario_name TEXT NOT NULL,
                    scenario_order INTEGER DEFAULT 0,
                    probability INTEGER DEFAULT 0,
                    timeframe TEXT DEFAULT '',
                    forecast_horizon TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    key_drivers_json TEXT DEFAULT '[]',
                    key_risks_json TEXT DEFAULT '[]',
                    assumptions_json TEXT DEFAULT '[]',
                    confidence_note TEXT DEFAULT '',
                    caveats_json TEXT DEFAULT '[]',
                    source TEXT DEFAULT 'report_prediction_summary',
                    outcome_status TEXT,
                    outcome_recorded_at TEXT,
                    outcome_notes TEXT,
                    outcome_payload_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            schema_probe = conn.execute("SELECT * FROM prediction_ledger LIMIT 0")
            existing_columns = {column[0] for column in (schema_probe.description or [])}
            additive_columns = {
                "project_id": "TEXT",
                "owner_id": "TEXT",
                "confidence_note": "TEXT DEFAULT ''",
                "caveats_json": "TEXT DEFAULT '[]'",
                "source": "TEXT DEFAULT 'report_prediction_summary'",
                "outcome_status": "TEXT",
                "outcome_recorded_at": "TEXT",
                "outcome_notes": "TEXT",
                "outcome_payload_json": "TEXT DEFAULT '{}'",
            }
            for column_name, column_def in additive_columns.items():
                if column_name not in existing_columns:
                    conn.execute(f"ALTER TABLE prediction_ledger ADD COLUMN {column_name} {column_def}")

            index_stmts = [
                "CREATE INDEX IF NOT EXISTS idx_prediction_ledger_report_id ON prediction_ledger(report_id)",
                "CREATE INDEX IF NOT EXISTS idx_prediction_ledger_simulation_id ON prediction_ledger(simulation_id)",
                "CREATE INDEX IF NOT EXISTS idx_prediction_ledger_owner_id ON prediction_ledger(owner_id)",
                "CREATE INDEX IF NOT EXISTS idx_prediction_ledger_created_at ON prediction_ledger(created_at)",
            ]
            for stmt in index_stmts:
                conn.execute(stmt)

        logger.info("Prediction ledger database initialized")

    @classmethod
    def sync_report_prediction_summary(
        cls,
        *,
        report_id: str,
        simulation_id: str,
        graph_id: str,
        prediction_summary: Dict[str, Any],
        created_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> int:
        """Replace all ledger rows for a report with the current scenario summary."""
        if not prediction_summary:
            return 0

        scenarios = prediction_summary.get("scenarios") or []
        if not scenarios:
            return 0

        project_id = None
        owner_id = None
        simulation_state = SimulationManager().get_simulation(simulation_id)
        if simulation_state:
            project_id = simulation_state.project_id
            owner_id = simulation_state.owner_id
        if project_id:
            project = ProjectManager.get_project(project_id)
            if project and not owner_id:
                owner_id = project.owner_id
        elif graph_id:
            project = ProjectManager.find_project_by_graph_id(graph_id)
            if project:
                project_id = project.project_id
                owner_id = project.owner_id

        timestamp = completed_at or created_at or datetime.now().isoformat()
        forecast_horizon = str(prediction_summary.get("forecast_horizon") or "").strip()
        confidence_note = str(prediction_summary.get("confidence_note") or "").strip()
        caveats_json = json.dumps(prediction_summary.get("caveats") or [], ensure_ascii=False)

        with get_db() as conn:
            conn.execute(
                f"DELETE FROM prediction_ledger WHERE report_id = {PH}",
                (report_id,),
            )
            for index, scenario in enumerate(scenarios):
                conn.execute(
                    f"""INSERT INTO prediction_ledger (
                        prediction_id, report_id, simulation_id, graph_id,
                        project_id, owner_id, scenario_name, scenario_order, probability,
                        timeframe, forecast_horizon, summary,
                        key_drivers_json, key_risks_json, assumptions_json,
                        confidence_note, caveats_json, source,
                        outcome_status, outcome_recorded_at, outcome_notes, outcome_payload_json,
                        created_at, updated_at
                    ) VALUES (
                        {PH}, {PH}, {PH}, {PH},
                        {PH}, {PH}, {PH}, {PH}, {PH},
                        {PH}, {PH}, {PH},
                        {PH}, {PH}, {PH},
                        {PH}, {PH}, {PH},
                        NULL, NULL, NULL, {PH},
                        {PH}, {PH}
                    )""",
                    (
                        f"pred_{uuid.uuid4().hex[:16]}",
                        report_id,
                        simulation_id,
                        graph_id or "",
                        project_id,
                        owner_id,
                        str(scenario.get("name") or f"Scenario {index + 1}").strip(),
                        index,
                        int(scenario.get("probability") or 0),
                        str(scenario.get("timeframe") or "").strip(),
                        forecast_horizon,
                        str(scenario.get("summary") or "").strip(),
                        json.dumps(scenario.get("key_drivers") or [], ensure_ascii=False),
                        json.dumps(scenario.get("key_risks") or [], ensure_ascii=False),
                        json.dumps(scenario.get("assumptions") or [], ensure_ascii=False),
                        confidence_note,
                        caveats_json,
                        "report_prediction_summary",
                        "{}",
                        timestamp,
                        timestamp,
                    ),
                )
        return len(scenarios)

    @classmethod
    def list_predictions(
        cls,
        *,
        prediction_id: Optional[str] = None,
        report_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[PredictionLedgerEntry]:
        where_clauses = []
        params: List[Any] = []
        if prediction_id:
            where_clauses.append(f"prediction_id = {PH}")
            params.append(prediction_id)
        if report_id:
            where_clauses.append(f"report_id = {PH}")
            params.append(report_id)
        if simulation_id:
            where_clauses.append(f"simulation_id = {PH}")
            params.append(simulation_id)
        if owner_id:
            where_clauses.append(f"owner_id = {PH}")
            params.append(owner_id)

        query = "SELECT * FROM prediction_ledger"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY created_at DESC, report_id DESC, scenario_order ASC"
        if limit and limit > 0:
            query += f" LIMIT {int(limit)}"

        with get_db() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [cls._row_to_entry(row) for row in rows]

    @classmethod
    def get_prediction(cls, prediction_id: str) -> Optional[PredictionLedgerEntry]:
        entries = cls.list_predictions(prediction_id=prediction_id, limit=1)
        return entries[0] if entries else None

    @classmethod
    def get_prediction_summary(cls, report_id: str) -> Optional[Dict[str, Any]]:
        entries = cls.list_predictions(report_id=report_id, limit=16)
        if not entries:
            return None
        ordered = sorted(entries, key=lambda item: item.scenario_order)
        first = ordered[0]
        return {
            "forecast_horizon": first.forecast_horizon,
            "confidence_note": first.confidence_note,
            "scenarios": [
                {
                    "name": entry.scenario_name,
                    "probability": entry.probability,
                    "timeframe": entry.timeframe,
                    "summary": entry.summary,
                    "key_drivers": entry.key_drivers,
                    "key_risks": entry.key_risks,
                    "assumptions": entry.assumptions,
                }
                for entry in ordered
            ],
            "caveats": first.caveats,
        }

    @classmethod
    def record_outcome(
        cls,
        *,
        prediction_id: str,
        outcome_status: str,
        outcome_notes: str = "",
        outcome_payload: Optional[Dict[str, Any]] = None,
    ) -> Optional[PredictionLedgerEntry]:
        normalized_status = str(outcome_status or "").strip().lower()
        valid_statuses = {"observed", "not_observed", "partial", "pending"}
        if normalized_status not in valid_statuses:
            raise ValueError(f"Unsupported outcome_status: {outcome_status}")

        now = datetime.now().isoformat()
        payload_json = json.dumps(outcome_payload or {}, ensure_ascii=False)
        with get_db() as conn:
            row = conn.execute(
                f"SELECT prediction_id FROM prediction_ledger WHERE prediction_id = {PH}",
                (prediction_id,),
            ).fetchone()
            if not row:
                return None
            conn.execute(
                f"""UPDATE prediction_ledger SET
                    outcome_status = {PH},
                    outcome_recorded_at = {PH},
                    outcome_notes = {PH},
                    outcome_payload_json = {PH},
                    updated_at = {PH}
                WHERE prediction_id = {PH}""",
                (
                    normalized_status,
                    now,
                    outcome_notes.strip(),
                    payload_json,
                    now,
                    prediction_id,
                ),
            )
        return cls.get_prediction(prediction_id)

    @classmethod
    def compute_metrics(
        cls,
        *,
        report_id: Optional[str] = None,
        simulation_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        entries = cls.list_predictions(
            report_id=report_id,
            simulation_id=simulation_id,
            owner_id=owner_id,
            limit=1000,
        )
        return cls._compute_metrics_from_entries(entries)

    @classmethod
    def compute_historical_case_metrics(
        cls,
        *,
        owner_id: Optional[str] = None,
        historical_case_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        entries = cls.list_predictions(owner_id=owner_id, limit=5000)
        grouped: Dict[str, List[PredictionLedgerEntry]] = {}

        for entry in entries:
            case_id = str((entry.outcome_payload or {}).get("historical_case_id") or "").strip()
            if not case_id:
                continue
            if historical_case_id and case_id != historical_case_id:
                continue
            grouped.setdefault(case_id, []).append(entry)

        from .historical_backtest import HistoricalBacktestManager

        case_lookup = {
            case.case_id: case
            for case in HistoricalBacktestManager.list_cases(limit=500)
        }

        ordered_case_ids = sorted(
            grouped.keys(),
            key=lambda case_id: max((item.updated_at or item.created_at or "") for item in grouped[case_id]),
            reverse=True,
        )

        items = []
        aggregate_entries: List[PredictionLedgerEntry] = []
        domain_groups: Dict[str, List[PredictionLedgerEntry]] = defaultdict(list)
        scenario_groups: Dict[str, List[PredictionLedgerEntry]] = defaultdict(list)
        horizon_groups: Dict[str, List[PredictionLedgerEntry]] = defaultdict(list)
        evaluation_groups: Dict[str, List[PredictionLedgerEntry]] = defaultdict(list)

        for case_id in ordered_case_ids:
            case_entries = grouped[case_id]
            aggregate_entries.extend(case_entries)
            latest_timestamp = max((item.updated_at or item.created_at or "") for item in case_entries)
            case = case_lookup.get(case_id)
            domain = case.domain if case else str((case_entries[0].outcome_payload or {}).get("historical_case_domain") or "").strip()
            for entry in case_entries:
                scenario_groups[entry.scenario_name or "Unknown"].append(entry)
                horizon_groups[entry.forecast_horizon or "Unspecified"].append(entry)
                if domain:
                    domain_groups[domain].append(entry)
                evaluation_groups[f"{entry.report_id}:{case_id}"].append(entry)
            items.append(
                {
                    "historical_case_id": case_id,
                    "historical_case_title": str((case_entries[0].outcome_payload or {}).get("historical_case_title") or "").strip(),
                    "historical_case_reference_date": str((case_entries[0].outcome_payload or {}).get("historical_case_reference_date") or "").strip(),
                    "domain": domain or None,
                    "report_count": len({item.report_id for item in case_entries}),
                    "simulation_count": len({item.simulation_id for item in case_entries}),
                    "latest_outcome_at": latest_timestamp or None,
                    "metrics": cls._compute_metrics_from_entries(case_entries),
                }
            )

        overall = cls._compute_metrics_from_entries(aggregate_entries)
        overall["evaluated_case_count"] = len(items)
        calibration_buckets = cls._build_calibration_buckets(aggregate_entries)

        by_domain = cls._summarize_groups(
            domain_groups,
            metadata_factory=lambda domain, _entries: {"domain": domain},
        )
        by_scenario = cls._summarize_groups(
            scenario_groups,
            metadata_factory=lambda scenario_name, _entries: {"scenario_name": scenario_name},
        )
        by_horizon = cls._summarize_groups(
            horizon_groups,
            metadata_factory=lambda horizon, _entries: {"forecast_horizon": horizon},
        )
        recent_evaluations = cls._summarize_groups(
            evaluation_groups,
            metadata_factory=lambda evaluation_key, evaluation_entries: {
                "report_id": evaluation_entries[0].report_id,
                "simulation_id": evaluation_entries[0].simulation_id,
                "historical_case_id": str((evaluation_entries[0].outcome_payload or {}).get("historical_case_id") or "").strip(),
                "historical_case_title": str((evaluation_entries[0].outcome_payload or {}).get("historical_case_title") or "").strip(),
                "historical_case_reference_date": str((evaluation_entries[0].outcome_payload or {}).get("historical_case_reference_date") or "").strip(),
                "domain": (
                    case_lookup.get(str((evaluation_entries[0].outcome_payload or {}).get("historical_case_id") or "").strip()).domain
                    if case_lookup.get(str((evaluation_entries[0].outcome_payload or {}).get("historical_case_id") or "").strip())
                    else None
                ),
            },
        )[:20]

        return {
            "overall": overall,
            "items": items,
            "by_domain": by_domain,
            "by_scenario": by_scenario,
            "by_horizon": by_horizon,
            "calibration_buckets": calibration_buckets,
            "recent_evaluations": recent_evaluations,
        }

    @staticmethod
    def _row_to_entry(row) -> PredictionLedgerEntry:
        row_dict = dict(row)
        return PredictionLedgerEntry(
            prediction_id=row_dict["prediction_id"],
            report_id=row_dict["report_id"],
            simulation_id=row_dict["simulation_id"],
            graph_id=row_dict.get("graph_id") or "",
            project_id=row_dict.get("project_id"),
            owner_id=row_dict.get("owner_id"),
            scenario_name=row_dict.get("scenario_name") or "",
            scenario_order=int(row_dict.get("scenario_order") or 0),
            probability=int(row_dict.get("probability") or 0),
            timeframe=row_dict.get("timeframe") or "",
            forecast_horizon=row_dict.get("forecast_horizon") or "",
            summary=row_dict.get("summary") or "",
            key_drivers=json.loads(row_dict.get("key_drivers_json") or "[]"),
            key_risks=json.loads(row_dict.get("key_risks_json") or "[]"),
            assumptions=json.loads(row_dict.get("assumptions_json") or "[]"),
            confidence_note=row_dict.get("confidence_note") or "",
            caveats=json.loads(row_dict.get("caveats_json") or "[]"),
            source=row_dict.get("source") or "report_prediction_summary",
            outcome_status=row_dict.get("outcome_status"),
            outcome_recorded_at=row_dict.get("outcome_recorded_at"),
            outcome_notes=row_dict.get("outcome_notes"),
            outcome_payload=json.loads(row_dict.get("outcome_payload_json") or "{}"),
            created_at=row_dict.get("created_at") or "",
            updated_at=row_dict.get("updated_at") or "",
        )

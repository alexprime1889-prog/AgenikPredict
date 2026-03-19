"""
Historical backtest case registry.

Provides a small curated pilot dataset of historical evaluation cases so
prediction reports can be benchmarked against a stable set of known events.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "historical_backtest_cases.json"


@dataclass
class HistoricalBacktestCase:
    case_id: str
    title: str
    reference_date: str
    domain: str
    summary: str
    ground_truth_summary: str
    evaluation_focus: List[str]
    tags: List[str]
    suggested_simulation_requirement: str
    suggested_outcomes: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "reference_date": self.reference_date,
            "domain": self.domain,
            "summary": self.summary,
            "ground_truth_summary": self.ground_truth_summary,
            "evaluation_focus": self.evaluation_focus,
            "tags": self.tags,
            "suggested_simulation_requirement": self.suggested_simulation_requirement,
            "suggested_outcomes": self.suggested_outcomes,
        }


class HistoricalBacktestManager:
    """Load and serve the curated pilot backtest dataset."""

    @classmethod
    def _load_payload(cls) -> Dict[str, Any]:
        with open(DATA_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)

    @classmethod
    def get_dataset_metadata(cls) -> Dict[str, Any]:
        payload = cls._load_payload()
        return {
            "version": payload.get("version"),
            "updated_at": payload.get("updated_at"),
            "case_count": len(payload.get("cases") or []),
        }

    @classmethod
    def list_cases(
        cls,
        *,
        domain: Optional[str] = None,
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> List[HistoricalBacktestCase]:
        payload = cls._load_payload()
        cases = payload.get("cases") or []
        normalized_domain = (domain or "").strip().lower()
        normalized_tag = (tag or "").strip().lower()

        filtered: List[HistoricalBacktestCase] = []
        for item in cases:
            if normalized_domain and str(item.get("domain", "")).strip().lower() != normalized_domain:
                continue
            tags = [str(value).strip().lower() for value in (item.get("tags") or [])]
            if normalized_tag and normalized_tag not in tags:
                continue
            filtered.append(
                HistoricalBacktestCase(
                    case_id=str(item.get("case_id") or "").strip(),
                    title=str(item.get("title") or "").strip(),
                    reference_date=str(item.get("reference_date") or "").strip(),
                    domain=str(item.get("domain") or "").strip(),
                    summary=str(item.get("summary") or "").strip(),
                    ground_truth_summary=str(item.get("ground_truth_summary") or "").strip(),
                    evaluation_focus=[str(value).strip() for value in (item.get("evaluation_focus") or []) if str(value).strip()],
                    tags=[str(value).strip() for value in (item.get("tags") or []) if str(value).strip()],
                    suggested_simulation_requirement=str(item.get("suggested_simulation_requirement") or "").strip(),
                    suggested_outcomes={
                        str(key).strip(): str(value).strip()
                        for key, value in (item.get("suggested_outcomes") or {}).items()
                        if str(key).strip() and str(value).strip()
                    },
                )
            )

        return filtered[: max(1, min(limit, 200))]

    @classmethod
    def get_case(cls, case_id: str) -> Optional[HistoricalBacktestCase]:
        normalized_case_id = (case_id or "").strip()
        if not normalized_case_id:
            return None
        for case in cls.list_cases(limit=500):
            if case.case_id == normalized_case_id:
                return case
        return None

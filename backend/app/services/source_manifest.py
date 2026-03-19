"""
Source manifest persistence for report provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SourceEntry:
    source_id: str
    provider: str
    source_type: str
    query: str = ""
    title: str = ""
    url: str = ""
    snippet: str = ""
    published_at: Optional[str] = None
    last_updated: Optional[str] = None
    fetched_at: str = field(default_factory=_utcnow_iso)
    language: str = "en"
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        source_type: str,
        query: str = "",
        title: str = "",
        url: str = "",
        snippet: str = "",
        published_at: Optional[str] = None,
        last_updated: Optional[str] = None,
        fetched_at: Optional[str] = None,
        language: str = "en",
        extra: Optional[Dict[str, Any]] = None,
        source_id: Optional[str] = None,
    ) -> "SourceEntry":
        return cls(
            source_id=source_id or f"src_{uuid.uuid4().hex[:12]}",
            provider=(provider or "").strip() or "unknown",
            source_type=(source_type or "").strip() or "unknown",
            query=(query or "").strip(),
            title=(title or "").strip(),
            url=(url or "").strip(),
            snippet=(snippet or "").strip(),
            published_at=published_at,
            last_updated=last_updated,
            fetched_at=fetched_at or _utcnow_iso(),
            language=(language or "en").strip() or "en",
            extra=dict(extra or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "provider": self.provider,
            "source_type": self.source_type,
            "query": self.query,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "published_at": self.published_at,
            "last_updated": self.last_updated,
            "fetched_at": self.fetched_at,
            "language": self.language,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceEntry":
        return cls.create(
            source_id=data.get("source_id"),
            provider=data.get("provider", ""),
            source_type=data.get("source_type", ""),
            query=data.get("query", ""),
            title=data.get("title", ""),
            url=data.get("url", ""),
            snippet=data.get("snippet", ""),
            published_at=data.get("published_at"),
            last_updated=data.get("last_updated"),
            fetched_at=data.get("fetched_at"),
            language=data.get("language", "en"),
            extra=data.get("extra") or {},
        )


@dataclass
class SourceManifest:
    report_id: str
    simulation_id: str
    graph_id: str
    analysis_mode: str = "global"
    language: str = "en"
    generated_at: str = field(default_factory=_utcnow_iso)
    warnings: List[str] = field(default_factory=list)
    sources: List[SourceEntry] = field(default_factory=list)

    ARTIFACT_NAME = "source_manifest.json"

    def add_warning(self, warning: str) -> None:
        normalized = str(warning or "").strip()
        if normalized and normalized not in self.warnings:
            self.warnings.append(normalized)

    def add_source(self, source: SourceEntry) -> None:
        self.sources.append(source)

    def add_sources(self, sources: List[SourceEntry]) -> None:
        for source in sources or []:
            if isinstance(source, SourceEntry):
                self.add_source(source)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "simulation_id": self.simulation_id,
            "graph_id": self.graph_id,
            "analysis_mode": self.analysis_mode or "global",
            "language": self.language or "en",
            "generated_at": self.generated_at,
            "warnings": list(self.warnings),
            "sources": [source.to_dict() for source in self.sources],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceManifest":
        manifest = cls(
            report_id=data.get("report_id", ""),
            simulation_id=data.get("simulation_id", ""),
            graph_id=data.get("graph_id", ""),
            analysis_mode=data.get("analysis_mode", "global"),
            language=data.get("language", "en"),
            generated_at=data.get("generated_at") or _utcnow_iso(),
            warnings=list(data.get("warnings") or []),
        )
        manifest.sources = [
            SourceEntry.from_dict(item)
            for item in (data.get("sources") or [])
            if isinstance(item, dict)
        ]
        return manifest

    def summary(self) -> Dict[str, Any]:
        provider_counts: Dict[str, int] = {}
        for source in self.sources:
            provider_counts[source.provider] = provider_counts.get(source.provider, 0) + 1
        return {
            "artifact": self.ARTIFACT_NAME,
            "source_count": len(self.sources),
            "provider_counts": provider_counts,
            "warnings": list(self.warnings),
        }

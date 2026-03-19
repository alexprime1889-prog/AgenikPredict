"""
Perplexity Search API provider for deterministic discovery-only web search.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import Config
from ..utils.logger import get_logger


logger = get_logger("agenikpredict.perplexity")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PerplexitySearchEntry:
    title: str
    url: str
    snippet: str = ""
    published_at: Optional[str] = None
    last_updated: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "published_at": self.published_at,
            "last_updated": self.last_updated,
        }


@dataclass
class PerplexitySearchResult:
    query: str
    fetched_at: str
    provider: str = "perplexity_search"
    entries: List[PerplexitySearchEntry] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            "## Web Search Discovery",
            f"Query: {self.query}",
            f"Provider: {self.provider}",
            f"Fetched at: {self.fetched_at}",
        ]
        if self.entries:
            lines.append("")
            lines.append("### Search results")
            for index, entry in enumerate(self.entries, start=1):
                lines.append(f"{index}. {entry.title or entry.url}")
                if entry.snippet:
                    lines.append(f'   Snippet: "{entry.snippet}"')
                if entry.published_at or entry.last_updated:
                    meta_parts = []
                    if entry.published_at:
                        meta_parts.append(f"published={entry.published_at}")
                    if entry.last_updated:
                        meta_parts.append(f"updated={entry.last_updated}")
                    lines.append(f"   Meta: {' | '.join(meta_parts)}")
                if entry.url:
                    lines.append(f"   Link: {entry.url}")
        else:
            lines.append("")
            lines.append("No web discovery results were available for this query.")
        if self.warnings:
            lines.append("")
            lines.append("### Warnings")
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


class PerplexityProvider:
    API_URL = "https://api.perplexity.ai/search"
    REQUEST_TIMEOUT_SECONDS = 10

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.PERPLEXITY_API_KEY

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, *, max_results: int = 5) -> PerplexitySearchResult:
        result = PerplexitySearchResult(
            query=(query or "").strip(),
            fetched_at=_utcnow_iso(),
        )

        if not self.available:
            result.warnings.append("PERPLEXITY_API_KEY is not configured; web search is unavailable.")
            return result

        if not result.query:
            result.warnings.append("No query provided for web search.")
            return result

        request_body = json.dumps({"query": result.query}).encode("utf-8")
        request = Request(
            self.API_URL,
            data=request_body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "AgenikPredict/1.0",
            },
        )

        try:
            with urlopen(request, timeout=self.REQUEST_TIMEOUT_SECONDS) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            logger.warning("Perplexity search HTTP failure for query '%s': %s", result.query, exc)
            result.warnings.append(f"Perplexity search failed: HTTP {exc.code}")
            return result
        except URLError as exc:
            logger.warning("Perplexity search network failure for query '%s': %s", result.query, exc)
            result.warnings.append(f"Perplexity search failed: {exc.reason}")
            return result
        except Exception as exc:
            logger.warning("Perplexity search unexpected failure for query '%s': %s", result.query, exc)
            result.warnings.append(f"Perplexity search failed: {exc}")
            return result

        entries = payload.get("results")
        if not isinstance(entries, list):
            logger.warning("Perplexity search returned malformed payload for query '%s': %s", result.query, payload)
            result.warnings.append("Perplexity search returned an unexpected payload shape.")
            return result

        for item in entries[: max(1, min(max_results, 10))]:
            if not isinstance(item, dict):
                continue
            result.entries.append(
                PerplexitySearchEntry(
                    title=str(item.get("title") or "").strip(),
                    url=str(item.get("url") or "").strip(),
                    snippet=str(item.get("snippet") or "").strip(),
                    published_at=item.get("date"),
                    last_updated=item.get("last_updated"),
                )
            )
        return result

"""
Live evidence service for ReportAgent.

Provides lightweight, read-only access to current-world context with graceful
degradation:
1. Recent news headlines via Google News RSS search
2. Live market snapshots via the existing Twelve Data integration
"""

from __future__ import annotations

import html
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ..config import Config
from ..utils.logger import get_logger
from .market_data import MarketDataService

logger = get_logger("agenikpredict.live_evidence")


@dataclass
class LiveNewsItem:
    title: str
    link: str
    source: str
    published_at: Optional[str] = None

    def to_text(self) -> str:
        parts = [f"- {self.title}"]
        meta = []
        if self.source:
            meta.append(self.source)
        if self.published_at:
            meta.append(self.published_at)
        if meta:
            parts.append(f"  Source: {' | '.join(meta)}")
        if self.link:
            parts.append(f"  Link: {self.link}")
        return "\n".join(parts)


@dataclass
class LiveNewsResult:
    query: str
    provider: str
    fetched_at: str
    items: List[LiveNewsItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            "## Live News Brief",
            f"Query: {self.query}",
            f"Provider: {self.provider}",
            f"Fetched at: {self.fetched_at}",
        ]
        if self.items:
            lines.append("\n### Recent headlines")
            for item in self.items:
                lines.append(item.to_text())
        else:
            lines.append("\nNo live headlines were available for this query.")
        if self.warnings:
            lines.append("\n### Warnings")
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


@dataclass
class LiveMarketSnapshotResult:
    query: str
    fetched_at: str
    symbols: List[str] = field(default_factory=list)
    quotes: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = [
            "## Live Market Snapshot",
            f"Query: {self.query}",
            f"Fetched at: {self.fetched_at}",
        ]
        if self.quotes:
            lines.append("\n### Market quotes")
            for quote in self.quotes:
                symbol = quote.get("symbol", "UNKNOWN")
                name = quote.get("name", symbol)
                price = quote.get("price", "N/A")
                change = quote.get("change", "N/A")
                percent_change = quote.get("percent_change", "N/A")
                exchange = quote.get("exchange", "N/A")
                currency = quote.get("currency", "USD")
                lines.append(
                    f"- {name} ({symbol}) on {exchange}: {price} {currency} "
                    f"(change: {change}, {percent_change}%)"
                )
        else:
            lines.append("\nNo live market quotes were available for this query.")
        if self.warnings:
            lines.append("\n### Warnings")
            lines.extend(f"- {warning}" for warning in self.warnings)
        return "\n".join(lines)


class LiveEvidenceService:
    """Lightweight live-current-world evidence retrieval with caching."""

    NEWS_PROVIDER = "google_news_rss"
    NEWS_URL_TEMPLATE = (
        "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    )

    def __init__(self, market_data: Optional[MarketDataService] = None):
        self.market_data = market_data or MarketDataService()
        self.enabled = Config.LIVE_EVIDENCE_ENABLED
        self.news_timeout = Config.LIVE_NEWS_TIMEOUT_SECONDS
        self.default_news_limit = Config.LIVE_NEWS_MAX_ITEMS
        self.cache_ttl = Config.LIVE_EVIDENCE_CACHE_TTL_SECONDS
        self._cache: Dict[Tuple[str, str, int], Tuple[float, object]] = {}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _cache_get(self, key: Tuple[str, str, int]):
        cached = self._cache.get(key)
        if not cached:
            return None
        cached_at, value = cached
        if (time.time() - cached_at) > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_put(self, key: Tuple[str, str, int], value) -> None:
        self._cache[key] = (time.time(), value)

    def live_news_brief(self, query: str, max_items: Optional[int] = None) -> LiveNewsResult:
        query = (query or "").strip()
        max_items = max(1, min(max_items or self.default_news_limit, 10))
        result = LiveNewsResult(
            query=query,
            provider=self.NEWS_PROVIDER,
            fetched_at=self._now_iso(),
        )

        if not self.enabled:
            result.warnings.append("Live evidence is disabled by configuration.")
            return result
        if not query:
            result.warnings.append("No query provided for live news search.")
            return result

        cache_key = ("news", query.lower(), max_items)
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        try:
            url = self.NEWS_URL_TEMPLATE.format(query=quote_plus(query))
            request = Request(
                url,
                headers={"User-Agent": "AgenikPredict/1.0 (+https://app.agenikpredict.com)"},
            )
            with urlopen(request, timeout=self.news_timeout) as response:
                xml_data = response.read()

            root = ET.fromstring(xml_data)
            items = self._parse_news_items(root, max_items=max_items)
            result.items = items
            if not items:
                result.warnings.append("No live headlines were returned by the RSS provider.")
        except Exception as exc:
            logger.warning("Live news retrieval failed for query '%s': %s", query, exc)
            result.warnings.append(f"Live news retrieval failed: {exc}")

        self._cache_put(cache_key, result)
        return result

    def live_market_snapshot(
        self,
        query: str,
        max_symbols: int = 5,
        context: str = "",
    ) -> LiveMarketSnapshotResult:
        query = (query or "").strip()
        context = (context or "").strip()
        max_symbols = max(1, min(max_symbols, 10))
        result = LiveMarketSnapshotResult(
            query=query,
            fetched_at=self._now_iso(),
        )

        if not self.enabled:
            result.warnings.append("Live evidence is disabled by configuration.")
            return result
        if not self.market_data.is_available:
            result.warnings.append("TWELVE_DATA_API_KEY is not configured; live market quotes are unavailable.")
            return result

        search_text = " ".join(part for part in [query, context] if part).strip()
        if not search_text:
            result.warnings.append("No query or context provided for market snapshot.")
            return result

        cache_key = ("market", search_text.lower(), max_symbols)
        cached = self._cache_get(cache_key)
        if cached:
            return cached

        symbols = []
        for symbol in self.market_data.detect_tickers(search_text):
            if symbol not in symbols:
                symbols.append(symbol)

        result.symbols = symbols[:max_symbols]
        if not result.symbols:
            result.warnings.append("No ticker symbols were detected in the query/context.")
            self._cache_put(cache_key, result)
            return result

        try:
            result.quotes = self.market_data.get_market_summary(result.symbols)
            if not result.quotes:
                result.warnings.append("No market quotes were returned for the detected symbols.")
        except Exception as exc:
            logger.warning("Live market snapshot failed for query '%s': %s", search_text, exc)
            result.warnings.append(f"Live market snapshot failed: {exc}")

        self._cache_put(cache_key, result)
        return result

    def _parse_news_items(self, root: ET.Element, max_items: int) -> List[LiveNewsItem]:
        items: List[LiveNewsItem] = []
        seen_titles = set()
        for item in root.findall(".//item"):
            title = self._get_child_text(item, "title")
            link = self._get_child_text(item, "link")
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            source = self._get_source_text(item)
            published_at = self._normalize_pubdate(self._get_child_text(item, "pubDate"))

            items.append(
                LiveNewsItem(
                    title=title,
                    link=link,
                    source=source,
                    published_at=published_at,
                )
            )
            if len(items) >= max_items:
                break
        return items

    @staticmethod
    def _get_child_text(item: ET.Element, local_name: str) -> str:
        for child in item:
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == local_name and child.text:
                return html.unescape(child.text.strip())
        return ""

    @classmethod
    def _get_source_text(cls, item: ET.Element) -> str:
        source = cls._get_child_text(item, "source")
        if source:
            return source

        title = cls._get_child_text(item, "title")
        if " - " in title:
            return title.rsplit(" - ", 1)[-1].strip()
        return ""

    @staticmethod
    def _normalize_pubdate(pubdate: str) -> Optional[str]:
        if not pubdate:
            return None
        try:
            return parsedate_to_datetime(pubdate).isoformat()
        except Exception:
            return pubdate

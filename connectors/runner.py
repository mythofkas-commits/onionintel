from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urlparse

from connectors.api_feed import ApiFeedConnector
from connectors.base import ConnectorRunResult
from connectors.search_engine import SearchEngineConnector
from connectors.site_monitor import KnownSiteMonitorConnector
from domain.models import Document, QueryTask, SearchHit
from registry.loaders import load_source_specs
from registry.schema import SourceSpec

_UNHEALTHY_SOURCE_IDS: set[str] = set()
_LAST_CONNECTOR_STATUS: list[dict[str, object]] = []


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connector_for(source: SourceSpec):
    if source.category == "search_engine":
        return SearchEngineConnector()
    if source.category in {"api_feed", "web_feed"}:
        return ApiFeedConnector()
    if source.category == "known_site":
        return KnownSiteMonitorConnector()
    raise ValueError(f"Unsupported source category: {source.category}")


def _source_status(
    source: SourceSpec,
    status: str,
    result_count: int = 0,
    error: str | None = None,
    connector_id: str = "",
) -> dict[str, object]:
    return {
        "name": source.name,
        "source_id": source.id,
        "category": source.category,
        "access": source.access,
        "status": status,
        "latency_ms": None,
        "result_count": result_count,
        "error": error,
        "parser": source.parser,
        "enabled": source.enabled,
        "notes": source.notes,
        "connector_id": connector_id,
    }


def _hit_to_legacy_result(hit: SearchHit) -> dict[str, object]:
    discovered = hit.discovered_at.isoformat() if hasattr(hit.discovered_at, "isoformat") else str(hit.discovered_at)
    source_name = str(hit.metadata.get("source") or hit.metadata.get("source_name") or hit.source_id)
    return {
        "title": hit.title,
        "link": hit.url,
        "raw_url": hit.raw_url,
        "snippet": hit.snippet,
        "source": source_name,
        "discovered_at": discovered,
        "matched_query": hit.query,
        "connector_id": hit.connector_id,
        "source_id": hit.source_id,
        "source_category": hit.metadata.get("source_category", "search_engine"),
    }


def _canonical_link(url: str) -> str:
    parsed = urlparse(url or "")
    return parsed._replace(fragment="", netloc=parsed.netloc.lower()).geturl().rstrip("/")


def _dedupe_results(results: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for result in results or []:
        key = _canonical_link(str(result.get("link") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(result)
    return unique


def _has_usable_source_signal(statuses: Iterable[dict[str, object]]) -> bool:
    return any(status.get("status") in {"success", "zero_results", "up"} for status in statuses or [])


def clear_unhealthy_sources() -> None:
    _UNHEALTHY_SOURCE_IDS.clear()


def set_unhealthy_sources(statuses: Iterable[dict[str, object]]) -> None:
    for status in statuses or []:
        source_id = str(status.get("source_id") or "")
        state = status.get("status")
        if source_id and state not in {"up", "success", "zero_results", "disabled", "skipped_unhealthy"}:
            _UNHEALTHY_SOURCE_IDS.add(source_id)


def get_last_connector_status() -> list[dict[str, object]]:
    return list(_LAST_CONNECTOR_STATUS)


def collect_sources(
    query: str,
    max_workers: int = 5,
    skip_unhealthy: bool = True,
    sources: list[SourceSpec] | None = None,
    catalog_path=None,
) -> dict[str, object]:
    global _LAST_CONNECTOR_STATUS

    max_workers = max(1, min(int(max_workers or 1), 16))
    all_sources = sources if sources is not None else load_source_specs(catalog_path)
    task = QueryTask(query=query, query_type="refined", reason="Connector catalog collection.")

    runnable: list[SourceSpec] = []
    statuses: list[dict[str, object]] = []
    collected_results: list[dict[str, object]] = []
    collected_hits: list[SearchHit] = []
    collected_documents: list[Document] = []

    for source in all_sources:
        if not source.enabled:
            statuses.append(_source_status(source, "disabled"))
            continue
        if skip_unhealthy and source.id in _UNHEALTHY_SOURCE_IDS:
            statuses.append(_source_status(source, "skipped_unhealthy"))
            continue
        if source.supports_query is False and source.category == "search_engine":
            statuses.append(_source_status(source, "unsupported_query_mode"))
            continue
        runnable.append(source)

    def run_source(source: SourceSpec) -> ConnectorRunResult:
        connector = _connector_for(source)
        if hasattr(connector, "collect_payload"):
            return connector.collect_payload(task, source)
        items = connector.collect(task, source)
        hits = [item for item in items if isinstance(item, SearchHit)]
        documents = [item for item in items if isinstance(item, Document)]
        return ConnectorRunResult(
            source=source,
            status=_source_status(source, "success", result_count=len(hits) + len(documents), connector_id=connector.connector_id),
            search_hits=hits,
            documents=documents,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {executor.submit(run_source, source): source for source in runnable}
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                result = future.result()
            except Exception as exc:
                statuses.append(_source_status(source, "connector_error", error=str(exc)[:200]))
                continue

            status = dict(result.status)
            status.setdefault("checked_at", _utc_now())
            status.setdefault("source_id", result.source.id)
            status.setdefault("category", result.source.category)
            status.setdefault("access", result.source.access)
            statuses.append(status)
            collected_hits.extend(result.search_hits)
            collected_documents.extend(result.documents)
            collected_results.extend(result.legacy_results or [_hit_to_legacy_result(hit) for hit in result.search_hits])

    order = {source.id: idx for idx, source in enumerate(all_sources)}
    statuses.sort(key=lambda item: order.get(str(item.get("source_id")), 999))
    if _has_usable_source_signal(statuses):
        set_unhealthy_sources(statuses)
    _LAST_CONNECTOR_STATUS = statuses
    return {
        "results": _dedupe_results(collected_results),
        "sources": statuses,
        "search_hits": [hit.model_dump(mode="json") for hit in collected_hits],
        "documents": [document.model_dump(mode="json") for document in collected_documents],
    }

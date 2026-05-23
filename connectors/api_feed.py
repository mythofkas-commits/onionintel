from __future__ import annotations

import requests

from connectors.base import ConnectorRunResult
from domain.models import Document, QueryTask
from registry.schema import SourceSpec


class ApiFeedConnector:
    connector_id = "api_feed"

    def collect_payload(self, task: QueryTask, source: SourceSpec) -> ConnectorRunResult:
        url = source.url_template.replace("{query}", task.query) if source.url_template else source.feed_url
        if not url:
            return ConnectorRunResult(source=source, status=self._status(source, "misconfigured", error="missing feed URL"))

        try:
            response = requests.get(url, headers=source.headers, timeout=source.timeout)
        except requests.RequestException as exc:
            return ConnectorRunResult(source=source, status=self._status(source, "request_error", error=str(exc)[:200]))

        document = Document.from_fetch(
            url=url,
            final_url=response.url or url,
            title=source.name,
            content_type=response.headers.get("Content-Type", ""),
            status_code=response.status_code,
            raw_html=response.text,
            extracted_text=response.text[:50_000],
            source_id=source.id,
            metadata={"connector_id": self.connector_id, "source_category": source.category},
        )
        status = "success" if 200 <= response.status_code < 300 else "http_error"
        return ConnectorRunResult(
            source=source,
            status=self._status(source, status, result_count=1 if status == "success" else 0, error=None if status == "success" else f"HTTP {response.status_code}"),
            documents=[document],
        )

    def collect(self, task: QueryTask, source: SourceSpec) -> list[Document]:
        return self.collect_payload(task, source).documents

    def _status(self, source: SourceSpec, status: str, result_count: int = 0, error: str | None = None) -> dict[str, object]:
        return {
            "name": source.name,
            "source_id": source.id,
            "category": source.category,
            "access": source.access,
            "status": status,
            "result_count": result_count,
            "error": error,
            "parser": source.parser,
            "enabled": source.enabled,
            "notes": source.notes,
            "connector_id": self.connector_id,
        }

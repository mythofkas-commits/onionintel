from __future__ import annotations

from connectors.base import ConnectorRunResult
from domain.models import Document, QueryTask
from registry.schema import SourceSpec
from scrape import scrape_single_document


class KnownSiteMonitorConnector:
    connector_id = "known_site_monitor"

    def collect_payload(self, task: QueryTask, source: SourceSpec) -> ConnectorRunResult:
        url = source.url_template.replace("{query}", task.query) if source.url_template else source.site_url
        if not url:
            return ConnectorRunResult(source=source, status=self._status(source, "misconfigured", error="missing site URL"))

        fetch_record, document, _display_text = scrape_single_document(
            {"link": url, "title": source.name, "source": source.name}
        )
        status = fetch_record.status if fetch_record else "error"
        return ConnectorRunResult(
            source=source,
            status=self._status(
                source,
                status,
                result_count=1 if document is not None and status == "success" else 0,
                error=fetch_record.error if fetch_record else None,
            ),
            documents=[document] if document is not None else [],
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

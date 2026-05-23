from __future__ import annotations

from domain.models import QueryTask, SearchHit
from connectors.base import ConnectorRunResult
from registry.loaders import source_spec_to_config
from registry.schema import SourceSpec
from sources import fetch_source_results


class SearchEngineConnector:
    connector_id = "search_engine"

    def collect_payload(self, task: QueryTask, source: SourceSpec) -> ConnectorRunResult:
        source_config = source_spec_to_config(source)
        payload = fetch_source_results(source_config, task.query)
        legacy_results = list(payload.get("results", []))
        hits = [
            SearchHit.from_result(result, query=task.query, rank=idx + 1)
            for idx, result in enumerate(legacy_results)
        ]
        for hit in hits:
            hit.connector_id = self.connector_id
            hit.source_id = source.id
            hit.metadata.setdefault("source", source.name)
            hit.metadata.setdefault("source_category", source.category)

        status = {key: value for key, value in payload.items() if key != "results"}
        status.update(
            {
                "source_id": source.id,
                "category": source.category,
                "access": source.access,
                "connector_id": self.connector_id,
            }
        )
        return ConnectorRunResult(source=source, status=status, search_hits=hits, legacy_results=legacy_results)

    def collect(self, task: QueryTask, source: SourceSpec) -> list[SearchHit]:
        return self.collect_payload(task, source).search_hits

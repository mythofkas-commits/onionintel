from __future__ import annotations

from domain.models import QueryTask, SearchHit
from registry.loaders import source_spec_to_config
from registry.schema import SourceSpec
from sources import fetch_source_results


class SearchEngineConnector:
    connector_id = "search_engine"

    def collect(self, task: QueryTask, source: SourceSpec) -> list[SearchHit]:
        source_config = source_spec_to_config(source)
        payload = fetch_source_results(source_config, task.query)
        return [
            SearchHit.from_result(result, query=task.query, rank=idx + 1)
            for idx, result in enumerate(payload.get("results", []))
        ]

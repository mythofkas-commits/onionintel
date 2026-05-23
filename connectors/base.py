from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from domain.models import Document, QueryTask, SearchHit
from registry.schema import SourceSpec


@dataclass
class ConnectorRunResult:
    source: SourceSpec
    status: dict[str, object]
    search_hits: list[SearchHit] = field(default_factory=list)
    documents: list[Document] = field(default_factory=list)
    legacy_results: list[dict[str, object]] = field(default_factory=list)


class BaseConnector(Protocol):
    connector_id: str

    def collect(self, task: QueryTask, source: SourceSpec) -> list[SearchHit] | list[Document]:
        ...

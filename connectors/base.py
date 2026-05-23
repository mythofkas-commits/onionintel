from __future__ import annotations

from typing import Protocol

from domain.models import Document, QueryTask, SearchHit
from registry.schema import SourceSpec


class BaseConnector(Protocol):
    connector_id: str

    def collect(self, task: QueryTask, source: SourceSpec) -> list[SearchHit] | list[Document]:
        ...

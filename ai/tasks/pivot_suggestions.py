from __future__ import annotations

from pydantic import BaseModel, Field


class PivotSuggestion(BaseModel):
    query: str
    reason: str = ""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    source_entity_ids: list[str] = Field(default_factory=list)


class PivotSuggestionResult(BaseModel):
    pivots: list[PivotSuggestion] = Field(default_factory=list)

from __future__ import annotations

from pydantic import BaseModel, Field


class RelevanceDecision(BaseModel):
    hit_id: str
    relevant: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""


class RelevanceResult(BaseModel):
    decisions: list[RelevanceDecision] = Field(default_factory=list)

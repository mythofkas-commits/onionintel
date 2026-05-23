from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSynthesisResult(BaseModel):
    summary: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)

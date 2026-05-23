from __future__ import annotations

from pydantic import BaseModel, Field


class ClaimRecord(BaseModel):
    claim_text: str
    claim_type: str = "observation"
    subject_entities: list[str] = Field(default_factory=list)
    object_entities: list[str] = Field(default_factory=list)
    evidence_doc_ids: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ClaimExtractionResult(BaseModel):
    claims: list[ClaimRecord] = Field(default_factory=list)

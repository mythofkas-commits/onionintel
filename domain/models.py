from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "2.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="replace")).hexdigest()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def stable_id(prefix: str, *parts: object) -> str:
    payload = "\n".join(str(part or "") for part in parts)
    return f"{prefix}_{stable_hash(payload)[:16]}"


class OnionIntelModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RunConfig(OnionIntelModel):
    query: str
    model: str
    preset: str = "threat_intel"
    preset_label: str = "Threat Intel"
    custom_instructions: str = ""
    expansion_mode: Literal["off", "conservative", "exploratory"] = "off"
    selected_search_intent: str = "freeform_threat"
    expansion_context: dict[str, Any] = Field(default_factory=dict)
    model_routing: dict[str, Any] = Field(default_factory=dict)
    max_results: int = 50
    max_scrape: int = 10
    search_workers: int = 12
    scrape_workers: int = 4
    use_legacy_llm_filter: bool = False
    enable_ai_relevance: bool = False
    enable_claim_extraction: bool = True
    enable_claim_synthesis: bool = True
    enable_pivot_suggestions: bool = True
    run_id: str = Field(default_factory=lambda: new_id("run"))
    created_at: datetime = Field(default_factory=utc_now)


class QueryTask(OnionIntelModel):
    query: str
    query_type: str = "refined"
    reason: str = ""
    phase: str = "initial"
    intent: str = "freeform_threat"
    origin: str = "system"
    sensitive: bool = False


class QueryPlan(OnionIntelModel):
    mode: str = "off"
    selected_intent: str = "freeform_threat"
    inferred_intent: dict[str, Any] = Field(default_factory=dict)
    queries: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceRecord(OnionIntelModel):
    source_id: str
    name: str
    status: str
    connector_id: str = "search_engine"
    parser: str = "generic"
    enabled: bool = True
    result_count: int = 0
    latency_ms: int | None = None
    error: str | None = None
    checked_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_status(cls, item: dict[str, Any]) -> "SourceRecord":
        name = str(item.get("name") or "unknown")
        return cls(
            source_id=stable_id("src", name),
            name=name,
            status=str(item.get("status") or "unknown"),
            parser=str(item.get("parser") or "generic"),
            enabled=bool(item.get("enabled", True)),
            result_count=int(item.get("result_count") or 0),
            latency_ms=item.get("latency_ms"),
            error=item.get("error"),
            metadata={k: v for k, v in item.items() if k not in {"name", "status", "parser", "enabled", "result_count", "latency_ms", "error"}},
        )


class SearchHit(OnionIntelModel):
    hit_id: str
    source_id: str
    connector_id: str = "search_engine"
    query: str = ""
    title: str
    url: str
    raw_url: str | None = None
    snippet: str = ""
    discovered_at: datetime = Field(default_factory=utc_now)
    source_rank: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_result(cls, result: dict[str, Any], query: str = "", rank: int | None = None) -> "SearchHit":
        source_name = str(result.get("source") or (result.get("found_by_sources") or ["unknown"])[0] or "unknown")
        url = str(result.get("link") or result.get("url") or "")
        discovered = result.get("discovered_at")
        if isinstance(discovered, str):
            try:
                discovered_at = datetime.fromisoformat(discovered)
            except ValueError:
                discovered_at = utc_now()
        elif isinstance(discovered, datetime):
            discovered_at = discovered
        else:
            discovered_at = utc_now()
        return cls(
            hit_id=stable_id("hit", source_name, url, result.get("title")),
            source_id=stable_id("src", source_name),
            query=str(result.get("matched_query") or query or ""),
            title=str(result.get("title") or "Untitled"),
            url=url,
            raw_url=result.get("raw_url"),
            snippet=str(result.get("snippet") or ""),
            discovered_at=discovered_at,
            source_rank=rank,
            metadata={k: v for k, v in result.items() if k not in {"title", "link", "url", "raw_url", "snippet", "discovered_at"}},
        )


class FetchRecord(OnionIntelModel):
    fetch_id: str
    url: str
    final_url: str = ""
    status: str = "pending"
    status_code: int | None = None
    content_type: str = ""
    error: str | None = None
    fetched_at: datetime = Field(default_factory=utc_now)
    bytes_read: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(OnionIntelModel):
    doc_id: str
    source_id: str = ""
    connector_id: str = "http_fetch"
    url: str
    final_url: str
    title: str = "Untitled"
    content_type: str = ""
    status_code: int | None = None
    raw_html: str = ""
    extracted_text: str = ""
    text_hash: str = ""
    content_hash: str = ""
    outlinks: list[str] = Field(default_factory=list)
    language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @classmethod
    def from_fetch(
        cls,
        url: str,
        final_url: str,
        title: str,
        content_type: str,
        status_code: int | None,
        raw_html: str,
        extracted_text: str,
        source_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "Document":
        canonical_url = final_url or url
        text_hash = stable_hash(extracted_text)
        content_hash = stable_hash(raw_html or extracted_text)
        return cls(
            doc_id=stable_id("doc", canonical_url, text_hash),
            source_id=source_id,
            url=url,
            final_url=canonical_url,
            title=title or "Untitled",
            content_type=content_type or "",
            status_code=status_code,
            raw_html=raw_html or "",
            extracted_text=extracted_text or "",
            text_hash=text_hash,
            content_hash=content_hash,
            metadata=metadata or {},
        )


class Artifact(OnionIntelModel):
    artifact_id: str
    artifact_type: str
    value: str
    normalized_value: str
    doc_id: str = ""
    source_url: str = ""
    evidence_text: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_row(cls, artifact_type: str, row: dict[str, Any], doc_id: str = "") -> "Artifact":
        value = str(row.get("value") or "")
        source_url = str(row.get("source_url") or "")
        normalized = value.lower() if artifact_type in {"domains", "emails", "onion_urls", "clearnet_urls"} else value
        return cls(
            artifact_id=stable_id("art", artifact_type, normalized, source_url, doc_id),
            artifact_type=artifact_type,
            value=value,
            normalized_value=normalized,
            doc_id=doc_id,
            source_url=source_url,
            evidence_text=str(row.get("evidence") or row.get("evidence_text") or ""),
            start_offset=row.get("start_offset"),
            end_offset=row.get("end_offset"),
            metadata={k: v for k, v in row.items() if k not in {"value", "source_url", "evidence", "evidence_text", "start_offset", "end_offset"}},
        )


class Entity(OnionIntelModel):
    entity_id: str
    entity_type: str
    canonical_value: str
    raw_values: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    enrichment: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Relationship(OnionIntelModel):
    relationship_id: str
    source_id: str
    target_id: str
    relationship_type: str
    evidence_doc_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelevanceScore(OnionIntelModel):
    target_id: str
    target_type: str
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    model_assisted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PivotCandidate(OnionIntelModel):
    pivot_id: str
    query: str
    pivot_type: str
    value: str
    score: float = 0.0
    reason: str = ""
    source_entity_ids: list[str] = Field(default_factory=list)
    evidence_doc_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EnrichmentRecord(OnionIntelModel):
    enrichment_id: str
    entity_id: str
    provider: str
    status: str
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class Claim(OnionIntelModel):
    claim_id: str
    claim_text: str
    claim_type: str = "observation"
    subject_entities: list[str] = Field(default_factory=list)
    object_entities: list[str] = Field(default_factory=list)
    evidence_doc_ids: list[str] = Field(default_factory=list)
    evidence_quotes: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    confidence_label: str = "low"
    requires_review: bool = True
    extraction_method: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class SynthesisReport(OnionIntelModel):
    report_id: str = Field(default_factory=lambda: new_id("report"))
    summary: str = ""
    generated_at: datetime = Field(default_factory=utc_now)
    claim_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunState(OnionIntelModel):
    schema_version: str = SCHEMA_VERSION
    run_id: str = Field(default_factory=lambda: new_id("run"))
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    query: str
    refined_query: str = ""
    model: str = ""
    preset: str = "threat_intel"
    preset_label: str = "Threat Intel"
    raw_results: list[dict[str, Any]] = Field(default_factory=list)
    qualified_results: list[dict[str, Any]] = Field(default_factory=list)
    filtered_results: list[dict[str, Any]] = Field(default_factory=list)
    scraped_content: dict[str, str] = Field(default_factory=dict)
    search_hits: list[SearchHit] = Field(default_factory=list)
    source_records: list[SourceRecord] = Field(default_factory=list)
    fetch_records: list[FetchRecord] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    artifacts: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    typed_artifacts: list[Artifact] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)
    relevance_scores: list[RelevanceScore] = Field(default_factory=list)
    ranked_documents: list[dict[str, Any]] = Field(default_factory=list)
    pivot_suggestions: list[PivotCandidate] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    synthesis_report: SynthesisReport = Field(default_factory=SynthesisReport)
    search_status: list[dict[str, Any]] = Field(default_factory=list)
    scrape_status: list[dict[str, Any]] = Field(default_factory=list)
    query_plan: dict[str, Any] = Field(default_factory=dict)
    query_runs: list[dict[str, Any]] = Field(default_factory=list)
    query_expansion_mode: str = "off"
    intent_metadata: dict[str, Any] = Field(default_factory=dict)
    model_routing: dict[str, Any] = Field(default_factory=dict)
    stage_status: list[dict[str, Any]] = Field(default_factory=list)
    investigation_file: str = ""

    def add_stage(self, stage: str, status: str, **metadata: Any) -> None:
        self.stage_status.append(
            {
                "run_id": self.run_id,
                "stage": stage,
                "status": status,
                "timestamp": utc_now().isoformat(),
                **metadata,
            }
        )


def host_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower()

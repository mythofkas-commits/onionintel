from __future__ import annotations

from typing import Any, Iterable

from artifacts import DOMAIN_RE, IPV4_RE, PATTERNS, _clean_value, _evidence, _valid_ipv4
from domain.models import Artifact, Document, SearchHit, stable_id


def _normalize_value(artifact_type: str, value: str) -> str:
    if artifact_type == "cves":
        return value.upper()
    if artifact_type == "handles":
        cleaned = value.lower()
        return cleaned if cleaned.startswith("@") else f"@{cleaned}"
    if artifact_type in {"domains", "emails", "onion_urls", "clearnet_urls", "hashes"}:
        return value.lower()
    if artifact_type == "crypto_addresses" and value.startswith("0x"):
        return value.lower()
    return value


def _metadata(document: Document | None, extractor: str) -> dict[str, Any]:
    data: dict[str, Any] = {"extractor": extractor}
    if document is not None:
        data.update({"text_hash": document.text_hash, "document_title": document.title})
    return data


def _artifact(
    artifact_type: str,
    value: str,
    source_url: str,
    evidence_text: str,
    start_offset: int | None,
    end_offset: int | None,
    *,
    document: Document | None = None,
    extractor: str = "regex_document_v1",
) -> Artifact | None:
    clean = _clean_value(value)
    if not clean:
        return None
    normalized = _normalize_value(artifact_type, clean)
    doc_id = document.doc_id if document is not None else ""
    return Artifact(
        artifact_id=stable_id("art", artifact_type, normalized, source_url, doc_id, start_offset, end_offset),
        artifact_type=artifact_type,
        value=clean,
        normalized_value=normalized,
        doc_id=doc_id,
        source_url=source_url,
        evidence_text=evidence_text,
        start_offset=start_offset,
        end_offset=end_offset,
        metadata=_metadata(document, extractor),
    )


def _scan_text(
    text: str,
    source_url: str,
    *,
    document: Document | None,
    extractor: str,
) -> list[Artifact]:
    artifacts: list[Artifact] = []
    text = str(text or "")
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            artifact = _artifact(
                category,
                match.group(0),
                source_url,
                _evidence(text, match.start(), match.end()),
                match.start(),
                match.end(),
                document=document,
                extractor=extractor,
            )
            if artifact:
                artifacts.append(artifact)

    for match in DOMAIN_RE.finditer(text):
        value = _clean_value(match.group(0))
        if value.lower().endswith(".onion"):
            continue
        artifact = _artifact(
            "domains",
            value,
            source_url,
            _evidence(text, match.start(), match.end()),
            match.start(),
            match.end(),
            document=document,
            extractor=extractor,
        )
        if artifact:
            artifacts.append(artifact)

    for match in IPV4_RE.finditer(text):
        value = match.group(0)
        if not _valid_ipv4(value):
            continue
        artifact = _artifact(
            "ipv4_addresses",
            value,
            source_url,
            _evidence(text, match.start(), match.end()),
            match.start(),
            match.end(),
            document=document,
            extractor=extractor,
        )
        if artifact:
            artifacts.append(artifact)
    return artifacts


def merge_typed_artifacts(*artifact_lists: Iterable[Artifact]) -> list[Artifact]:
    merged: dict[str, Artifact] = {}
    for artifacts in artifact_lists:
        for artifact in artifacts or []:
            key = "|".join(
                [
                    artifact.artifact_type,
                    artifact.normalized_value,
                    artifact.doc_id,
                    artifact.source_url,
                    str(artifact.start_offset),
                    str(artifact.end_offset),
                ]
            )
            merged.setdefault(key, artifact)
    return list(merged.values())


def extract_artifacts_from_documents(documents: list[Document]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for document in documents or []:
        source_url = document.final_url or document.url
        artifacts.extend(
            _scan_text(
                document.extracted_text,
                source_url,
                document=document,
                extractor="regex_document_v1",
            )
        )
    return merge_typed_artifacts(artifacts)


def extract_artifacts_from_search_hits(hits: list[SearchHit]) -> list[Artifact]:
    artifacts: list[Artifact] = []
    for hit in hits or []:
        source_url = hit.url or hit.raw_url or hit.source_id
        text = " ".join([hit.title or "", hit.url or "", hit.raw_url or "", hit.snippet or ""])
        artifacts.extend(_scan_text(text, source_url, document=None, extractor="regex_search_hit_v1"))
    return merge_typed_artifacts(artifacts)


def typed_artifacts_to_legacy_dict(artifacts: list[Artifact]) -> dict[str, list[dict[str, str]]]:
    categories = list(PATTERNS.keys()) + ["domains", "ipv4_addresses"]
    legacy: dict[str, list[dict[str, str]]] = {category: [] for category in categories}
    seen: dict[str, set[tuple[str, str, str]]] = {category: set() for category in categories}
    for artifact in artifacts or []:
        if artifact.artifact_type not in legacy:
            legacy[artifact.artifact_type] = []
            seen[artifact.artifact_type] = set()
        key = (artifact.normalized_value, artifact.source_url, artifact.doc_id)
        if key in seen[artifact.artifact_type]:
            continue
        seen[artifact.artifact_type].add(key)
        legacy[artifact.artifact_type].append(
            {
                "value": artifact.value,
                "source_url": artifact.source_url,
                "evidence": artifact.evidence_text,
            }
        )
    return legacy

from __future__ import annotations

from domain.models import Entity, PivotCandidate, stable_id


PIVOT_WEIGHTS = {
    "email": 90,
    "handle": 85,
    "onion_url": 82,
    "onion_service": 82,
    "crypto_address": 80,
    "hash": 78,
    "cve": 72,
    "domain": 65,
    "url": 55,
    "ipv4": 50,
}


def generate_pivot_candidates(entities: list[Entity], max_pivots: int = 12) -> list[PivotCandidate]:
    candidates: list[PivotCandidate] = []
    for entity in entities or []:
        base_score = PIVOT_WEIGHTS.get(entity.entity_type, 25)
        artifact_count = int(entity.metadata.get("artifact_count") or len(entity.artifact_ids) or 0)
        source_urls = entity.metadata.get("source_urls", []) or []
        doc_ids = entity.metadata.get("first_seen_doc_ids", []) or []
        score = min(100.0, base_score + min(10, artifact_count * 2) + min(8, len(source_urls) * 2))
        if entity.entity_type in {"url"}:
            query = entity.canonical_value
        else:
            query = entity.canonical_value
        candidates.append(
            PivotCandidate(
                pivot_id=stable_id("pivot", entity.entity_type, entity.canonical_value),
                query=query,
                pivot_type=entity.entity_type,
                value=entity.canonical_value,
                score=score,
                reason=f"{entity.entity_type} appears in collected evidence and can be searched directly.",
                source_entity_ids=[entity.entity_id],
                evidence_doc_ids=list(doc_ids),
                metadata={"artifact_count": artifact_count, "source_urls": source_urls[:5]},
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    return candidates[:max_pivots]

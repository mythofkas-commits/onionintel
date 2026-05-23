from __future__ import annotations

import re
from typing import Any

from domain.models import Artifact, Document, Entity, RelevanceScore, stable_id


NOISY_SOURCES = {"directory", "wiki", "generic", "link list", "hidden wiki"}


def _terms(query: str, context: dict[str, Any] | None = None) -> list[str]:
    values = [query or ""]
    for value in (context or {}).values():
        if isinstance(value, str):
            values.extend(re.split(r"[\s,;\n]+", value))
        elif isinstance(value, list):
            values.extend(str(item) for item in value)
    cleaned = []
    for value in values:
        item = str(value or "").strip().lower()
        if len(item) >= 3 and item not in cleaned:
            cleaned.append(item)
    return cleaned


def _score_text(terms: list[str], title: str, body: str, url: str) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    matched: list[str] = []
    title_l = title.lower()
    body_l = body.lower()
    url_l = url.lower()
    for term in terms:
        term_score = 0.0
        if term in title_l:
            term_score += 30
        if term in body_l:
            term_score += 25
        if term in url_l:
            term_score += 15
        if term_score:
            score += term_score
            matched.append(term)
    if matched:
        reasons.append("matched query/context terms")
    if title.strip() or body.strip():
        score += 5
        reasons.append("has useful title or snippet")
    return score, reasons, matched


def rank_search_results(
    query: str,
    results: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
    intent: str = "freeform_threat",
) -> list[dict[str, Any]]:
    terms = _terms(query, context)
    ranked = []
    seen_urls: set[str] = set()
    for idx, result in enumerate(results or []):
        title = str(result.get("title") or "")
        snippet = str(result.get("snippet") or "")
        url = str(result.get("link") or result.get("url") or result.get("raw_url") or "")
        score, reasons, matched = _score_text(terms, title, snippet, url)
        source = str(result.get("source") or "").lower()
        if any(noisy in source for noisy in NOISY_SOURCES):
            score -= 10
            reasons.append("noisy or generic source")
        if url in seen_urls:
            score -= 10
            reasons.append("duplicate url")
        seen_urls.add(url)
        quality = result.get("quality", {}) or {}
        if quality.get("direct_mention"):
            score += 20
            reasons.append("query expansion marked direct mention")
        if quality.get("infrastructure_only") or quality.get("no_direct_mention"):
            score -= 15
            reasons.append("weak direct-evidence signal")
        item = dict(result)
        item["relevance"] = {
            "score": max(0.0, score),
            "reasons": reasons or ["deterministic baseline"],
            "matched_terms": matched,
            "stage": "pre_fetch_v1",
            "intent": intent,
            "rank_input_index": idx,
        }
        ranked.append(item)
    return sorted(ranked, key=lambda item: item.get("relevance", {}).get("score", 0), reverse=True)


def rank_documents(
    query: str,
    documents: list[Document],
    entities: list[Entity],
    artifacts: list[Artifact],
    context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[RelevanceScore]]:
    terms = _terms(query, context)
    artifacts_by_doc: dict[str, list[Artifact]] = {}
    for artifact in artifacts or []:
        if artifact.doc_id:
            artifacts_by_doc.setdefault(artifact.doc_id, []).append(artifact)
    entity_artifact_ids = {artifact_id for entity in entities or [] for artifact_id in entity.artifact_ids}

    ranked: list[dict[str, Any]] = []
    scores: list[RelevanceScore] = []
    for document in documents or []:
        doc_artifacts = artifacts_by_doc.get(document.doc_id, [])
        score, reasons, matched = _score_text(terms, document.title, document.extracted_text, document.final_url or document.url)
        if matched:
            score += 15
            reasons.append("full document contains target/context")
        useful_artifacts = [artifact for artifact in doc_artifacts if artifact.artifact_id in entity_artifact_ids]
        if useful_artifacts:
            score += min(30, 5 * len({artifact.artifact_type for artifact in useful_artifacts}))
            reasons.append("document contains normalized artifacts")
        if document.metadata.get("unsupported_content_type"):
            score -= 20
            reasons.append("unsupported content type")
        if not document.extracted_text or document.extracted_text == document.title:
            score -= 25
            reasons.append("no fetched body evidence")
        relevance = RelevanceScore(
            target_id=document.doc_id,
            target_type="document",
            score=max(0.0, score),
            reasons=reasons or ["deterministic baseline"],
            matched_terms=matched,
            metadata={"stage": "post_fetch_v1", "artifact_count": len(doc_artifacts)},
        )
        scores.append(relevance)
        ranked.append(
            {
                "doc_id": document.doc_id,
                "url": document.final_url or document.url,
                "title": document.title,
                "score": relevance.score,
                "reasons": relevance.reasons,
                "matched_terms": relevance.matched_terms,
            }
        )
    ranked.sort(key=lambda item: item["score"], reverse=True)
    scores.sort(key=lambda item: item.score, reverse=True)
    return ranked, scores

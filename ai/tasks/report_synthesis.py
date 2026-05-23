from __future__ import annotations

import json

from pydantic import BaseModel, Field

from domain.models import Claim, Document, Entity, PivotCandidate, Relationship, SynthesisReport


class ReportSynthesisResult(BaseModel):
    summary: str = ""
    claim_ids: list[str] = Field(default_factory=list)
    uncertainty_notes: list[str] = Field(default_factory=list)


def deterministic_report_from_claims(
    query: str,
    claims: list[Claim],
    documents: list[Document],
    entities: list[Entity],
    relationships: list[Relationship],
    pivot_suggestions: list[PivotCandidate] | None = None,
    *,
    method: str = "deterministic_claim_report_v1",
) -> SynthesisReport:
    lines = [
        "## Executive summary",
        f"Query: `{query}`.",
        f"Reviewed {len(documents)} fetched documents and generated {len(claims)} evidence-linked claims.",
        "",
        "## Evidence-backed findings",
    ]
    if claims:
        for claim in claims[:20]:
            docs = ", ".join(f"`{doc_id}`" for doc_id in claim.evidence_doc_ids)
            lines.append(f"- `{claim.claim_id}` ({claim.confidence_label}): {claim.claim_text} Evidence: {docs}.")
    else:
        lines.append("- No evidence-linked claims were generated from the fetched documents.")
    lines.extend(["", "## Key entities"])
    for entity in entities[:20]:
        lines.append(f"- `{entity.entity_id}` {entity.entity_type}: `{entity.canonical_value}`")
    lines.extend(["", "## Relationship notes"])
    for relationship in relationships[:20]:
        lines.append(
            f"- `{relationship.relationship_id}` {relationship.source_id} "
            f"{relationship.relationship_type} {relationship.target_id}"
        )
    lines.extend(["", "## Contradictions / uncertainty"])
    if any(claim.requires_review for claim in claims):
        lines.append("- Some claims require analyst review because confidence is below high.")
    else:
        lines.append("- No contradictions detected by deterministic synthesis.")
    lines.extend(["", "## Suggested pivots"])
    for pivot in (pivot_suggestions or [])[:10]:
        lines.append(f"- `{pivot.query}` ({pivot.pivot_type}, score {pivot.score:.0f}): {pivot.reason}")
    lines.extend(["", "## Evidence appendix"])
    for document in documents[:20]:
        lines.append(f"- `{document.doc_id}` {document.title} - {document.final_url or document.url}")
    return SynthesisReport(
        summary="\n".join(lines),
        claim_ids=[claim.claim_id for claim in claims],
        metadata={"synthesis_method": method},
    )


def synthesize_report_from_claims(
    llm,
    query: str,
    claims: list[Claim],
    documents: list[Document],
    entities: list[Entity],
    relationships: list[Relationship],
    pivot_suggestions: list[PivotCandidate] | None = None,
) -> SynthesisReport:
    if llm is None:
        return deterministic_report_from_claims(
            query, claims, documents, entities, relationships, pivot_suggestions
        )
    payload = {
        "query": query,
        "claims": [claim.model_dump(mode="json") for claim in claims],
        "documents": [{"doc_id": doc.doc_id, "title": doc.title, "url": doc.final_url or doc.url} for doc in documents],
        "entities": [entity.model_dump(mode="json") for entity in entities[:50]],
        "relationships": [relationship.model_dump(mode="json") for relationship in relationships[:100]],
        "pivots": [pivot.model_dump(mode="json") for pivot in (pivot_suggestions or [])[:20]],
    }
    prompt = (
        "Return JSON only with keys summary, claim_ids, uncertainty_notes. "
        "Write a concise intelligence report with sections: Executive summary, "
        "Evidence-backed findings, Key entities, Relationship notes, "
        "Contradictions / uncertainty, Suggested pivots, Evidence appendix. "
        "Every finding must reference claim IDs and document IDs."
    )
    try:
        if hasattr(llm, "invoke"):
            raw = llm.invoke({"instructions": prompt, "evidence": json.dumps(payload, ensure_ascii=False)})
        else:
            raw = llm(prompt + "\n" + json.dumps(payload, ensure_ascii=False))
        if not isinstance(raw, str):
            raw = getattr(raw, "content", str(raw))
        result = ReportSynthesisResult(**json.loads(raw))
        if result.summary and all(claim_id in {claim.claim_id for claim in claims} for claim_id in result.claim_ids):
            return SynthesisReport(
                summary=result.summary,
                claim_ids=result.claim_ids,
                metadata={"synthesis_method": "llm_claim_synthesis_v1", "uncertainty_notes": result.uncertainty_notes},
            )
    except Exception:
        pass
    return deterministic_report_from_claims(
        query, claims, documents, entities, relationships, pivot_suggestions, method="deterministic_claim_report_fallback_v1"
    )

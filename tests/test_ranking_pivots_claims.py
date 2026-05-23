import unittest

from ai.tasks.claim_extraction import extract_claims_with_llm_or_fallback
from ai.tasks.report_synthesis import synthesize_report_from_claims
from domain.models import Artifact, Document
from normalize.entities import artifacts_to_entities_v2
from pipeline.pivots import generate_pivot_candidates
from ranking.relevance import rank_documents, rank_search_results


class FakeJsonLlm:
    def __init__(self, payload):
        self.payload = payload

    def invoke(self, _payload):
        return self.payload


class RankingPivotsClaimsTests(unittest.TestCase):
    def test_search_and_document_ranking_are_deterministic(self):
        results = [
            {"title": "Unrelated", "link": "http://a.onion", "snippet": "nothing", "source": "Fixture"},
            {"title": "Target admin@example.com", "link": "http://b.onion", "snippet": "target", "source": "Fixture"},
        ]
        ranked = rank_search_results("admin@example.com", results)
        self.assertEqual(ranked[0]["link"], "http://b.onion")

        document = Document.from_fetch(
            url="http://b.onion",
            final_url="http://b.onion",
            title="Target",
            content_type="text/html",
            status_code=200,
            raw_html="admin@example.com",
            extracted_text="Target admin@example.com",
        )
        artifacts = [Artifact.from_row("emails", {"value": "admin@example.com", "source_url": "http://b.onion", "evidence": "admin@example.com"}, doc_id=document.doc_id)]
        entities = artifacts_to_entities_v2(artifacts)
        ranked_docs, scores = rank_documents("admin@example.com", [document], entities, artifacts)
        self.assertEqual(ranked_docs[0]["doc_id"], document.doc_id)
        self.assertEqual(scores[0].target_type, "document")

    def test_pivots_claims_and_synthesis_use_evidence_ids(self):
        document = Document.from_fetch(
            url="http://b.onion",
            final_url="http://b.onion",
            title="Target",
            content_type="text/html",
            status_code=200,
            raw_html="admin@example.com",
            extracted_text="Target admin@example.com",
        )
        artifacts = [Artifact.from_row("emails", {"value": "admin@example.com", "source_url": "http://b.onion", "evidence": "admin@example.com"}, doc_id=document.doc_id)]
        entities = artifacts_to_entities_v2(artifacts)

        pivots = generate_pivot_candidates(entities)
        claims = extract_claims_with_llm_or_fallback(None, "admin@example.com", [document], entities, artifacts)
        report = synthesize_report_from_claims(None, "admin@example.com", claims, [document], entities, [], pivots)

        self.assertTrue(pivots)
        self.assertTrue(claims)
        self.assertIn(document.doc_id, claims[0].evidence_doc_ids)
        self.assertIn(claims[0].claim_id, report.summary)
        self.assertEqual(report.metadata["synthesis_method"], "deterministic_claim_report_v1")

    def test_claim_llm_accepts_valid_json_and_rejects_unsupported_quotes(self):
        document = Document.from_fetch(
            url="http://b.onion",
            final_url="http://b.onion",
            title="Target",
            content_type="text/html",
            status_code=200,
            raw_html="contact admin@example.com",
            extracted_text="contact admin@example.com",
        )
        artifacts = [Artifact.from_row("emails", {"value": "admin@example.com", "source_url": "http://b.onion", "evidence": "admin@example.com"}, doc_id=document.doc_id)]
        entities = artifacts_to_entities_v2(artifacts)
        entity_id = next(entity.entity_id for entity in entities if entity.entity_type == "email")

        valid = FakeJsonLlm(
            '{"claims":[{"claim_text":"The document lists admin@example.com.",'
            '"claim_type":"observation","subject_entities":["%s"],"object_entities":[],'
            '"evidence_doc_ids":["%s"],"evidence_quotes":["admin@example.com"],"confidence":0.8}]}'
            % (entity_id, document.doc_id)
        )
        claims = extract_claims_with_llm_or_fallback(valid, "admin@example.com", [document], entities, artifacts)
        self.assertEqual(claims[0].extraction_method, "llm_structured_v1")

        invalid_quote = FakeJsonLlm(
            '{"claims":[{"claim_text":"Unsupported claim.","claim_type":"observation",'
            '"subject_entities":[],"object_entities":[],"evidence_doc_ids":["%s"],'
            '"evidence_quotes":["not in document"],"confidence":0.9}]}'
            % document.doc_id
        )
        fallback_claims = extract_claims_with_llm_or_fallback(invalid_quote, "admin@example.com", [document], entities, artifacts)
        self.assertEqual(fallback_claims[0].extraction_method, "deterministic_fallback_v1")

    def test_synthesis_llm_validates_claim_ids_and_falls_back(self):
        document = Document.from_fetch(
            url="http://b.onion",
            final_url="http://b.onion",
            title="Target",
            content_type="text/html",
            status_code=200,
            raw_html="admin@example.com",
            extracted_text="admin@example.com",
        )
        artifacts = [Artifact.from_row("emails", {"value": "admin@example.com", "source_url": "http://b.onion", "evidence": "admin@example.com"}, doc_id=document.doc_id)]
        entities = artifacts_to_entities_v2(artifacts)
        claims = extract_claims_with_llm_or_fallback(None, "admin@example.com", [document], entities, artifacts)

        valid = FakeJsonLlm('{"summary":"Finding references %s and %s.","claim_ids":["%s"],"uncertainty_notes":[]}' % (claims[0].claim_id, document.doc_id, claims[0].claim_id))
        report = synthesize_report_from_claims(valid, "admin@example.com", claims, [document], entities, [], [])
        self.assertEqual(report.metadata["synthesis_method"], "llm_claim_synthesis_v1")

        bad = FakeJsonLlm('{"summary":"Bad","claim_ids":["missing"],"uncertainty_notes":[]}')
        fallback = synthesize_report_from_claims(bad, "admin@example.com", claims, [document], entities, [], [])
        self.assertEqual(fallback.metadata["synthesis_method"], "deterministic_claim_report_fallback_v1")


if __name__ == "__main__":
    unittest.main()

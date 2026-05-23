import unittest

from domain.models import Document, SearchHit
from extractors.document_artifacts import (
    extract_artifacts_from_documents,
    extract_artifacts_from_search_hits,
    typed_artifacts_to_legacy_dict,
)


class DocumentArtifactExtractionTests(unittest.TestCase):
    def test_extracts_typed_artifacts_with_doc_offsets_and_legacy_output(self):
        text = "Contact Admin@Example.com about CVE-2024-12345 at http://alphaabcdefghijklmnop.onion/path and @operator."
        document = Document.from_fetch(
            url="http://source.onion",
            final_url="http://source.onion",
            title="Fixture",
            content_type="text/html",
            status_code=200,
            raw_html=text,
            extracted_text=text,
        )

        artifacts = extract_artifacts_from_documents([document])
        values = {artifact.value for artifact in artifacts}

        self.assertIn("Admin@Example.com", values)
        self.assertIn("CVE-2024-12345", values)
        email = next(artifact for artifact in artifacts if artifact.value == "Admin@Example.com")
        self.assertEqual(email.doc_id, document.doc_id)
        self.assertEqual(text[email.start_offset : email.end_offset], "Admin@Example.com")
        self.assertEqual(email.metadata["extractor"], "regex_document_v1")

        legacy = typed_artifacts_to_legacy_dict(artifacts)
        self.assertEqual(legacy["emails"][0]["value"], "Admin@Example.com")

    def test_extracts_from_search_hits_without_document_id(self):
        hit = SearchHit.from_result(
            {
                "title": "Target @operator",
                "link": "http://result.onion",
                "snippet": "admin@example.com",
                "source": "Fixture",
            },
            query="operator",
        )
        artifacts = extract_artifacts_from_search_hits([hit])
        self.assertTrue(any(artifact.value == "admin@example.com" for artifact in artifacts))
        self.assertTrue(all(artifact.doc_id == "" for artifact in artifacts))


if __name__ == "__main__":
    unittest.main()

import unittest

from domain.models import Artifact
from normalize.canonicalize import canonicalize_cve, canonicalize_domain, canonicalize_handle, canonicalize_url
from normalize.entities import artifacts_to_entities_v2


class NormalizationTests(unittest.TestCase):
    def test_canonicalizers(self):
        self.assertEqual(canonicalize_url("HTTP://Example.COM/path#frag"), "http://example.com/path")
        self.assertEqual(canonicalize_domain(".Example.COM."), "example.com")
        self.assertEqual(canonicalize_cve("cve-2024-1234"), "CVE-2024-1234")
        self.assertEqual(canonicalize_handle("Operator"), "@operator")

    def test_entities_are_deduped_and_email_domain_is_derived(self):
        artifacts = [
            Artifact.from_row("emails", {"value": "Admin@Example.com", "source_url": "http://source", "evidence": "x"}, doc_id="doc1"),
            Artifact.from_row("emails", {"value": "admin@example.com", "source_url": "http://source2", "evidence": "y"}, doc_id="doc2"),
        ]
        entities = artifacts_to_entities_v2(artifacts)
        emails = [entity for entity in entities if entity.entity_type == "email"]
        domains = [entity for entity in entities if entity.entity_type == "domain"]

        self.assertEqual(len(emails), 1)
        self.assertEqual(emails[0].canonical_value, "admin@example.com")
        self.assertEqual(emails[0].metadata["artifact_count"], 2)
        self.assertTrue(any(entity.canonical_value == "example.com" for entity in domains))


if __name__ == "__main__":
    unittest.main()

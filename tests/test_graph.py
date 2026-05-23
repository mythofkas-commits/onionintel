import unittest

from domain.models import Artifact, stable_id
from graph import artifacts_to_entities, build_relationship_graph, build_relationships


class RelationshipGraphTests(unittest.TestCase):
    def test_builds_mentions_domain_and_seen_with_relationships(self):
        doc_id = stable_id("doc", "http://source")
        artifacts = [
            Artifact.from_row(
                "emails",
                {"value": "Admin@Example.com", "source_url": "http://source", "evidence": "email"},
                doc_id=doc_id,
            ),
            Artifact.from_row(
                "clearnet_urls",
                {"value": "https://example.com/path", "source_url": "http://source", "evidence": "url"},
                doc_id=doc_id,
            ),
        ]

        entities = artifacts_to_entities(artifacts)
        relationships = build_relationships(artifacts, entities)
        graph = build_relationship_graph(entities, relationships)

        rel_types = {relationship.relationship_type for relationship in relationships}
        self.assertIn("DOCUMENT_MENTIONS_ENTITY", rel_types)
        self.assertIn("URL_HAS_HOST", rel_types)
        self.assertIn("ENTITY_CO_OCCURS_WITH_ENTITY", rel_types)
        self.assertGreaterEqual(graph.number_of_nodes(), 2)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

from connectors.base import ConnectorRunResult
from connectors.runner import clear_unhealthy_sources, collect_sources
from domain.models import SearchHit, stable_id
from registry.schema import SourceSpec


class FakeConnector:
    connector_id = "fake"

    def collect_payload(self, task, source):
        hit = SearchHit(
            hit_id=stable_id("hit", source.id, task.query),
            source_id=source.id,
            connector_id=self.connector_id,
            query=task.query,
            title=f"{source.name} result",
            url=f"http://{source.id}.example/onion",
            snippet="fixture",
            metadata={"source": source.name, "source_category": source.category},
        )
        return ConnectorRunResult(
            source=source,
            status={
                "name": source.name,
                "source_id": source.id,
                "category": source.category,
                "status": "success",
                "result_count": 1,
                "connector_id": self.connector_id,
            },
            search_hits=[hit],
        )


class ConnectorRunnerTests(unittest.TestCase):
    def tearDown(self):
        clear_unhealthy_sources()

    def test_dispatches_enabled_catalog_sources_and_skips_disabled(self):
        sources = [
            SourceSpec(
                id="search_fixture",
                name="Search Fixture",
                category="search_engine",
                access="tor",
                url_template="http://fixtureabcdefghijklmnop.onion/search?q={query}",
            ),
            SourceSpec(
                id="feed_fixture",
                name="Feed Fixture",
                category="api_feed",
                access="direct",
                enabled=False,
                supports_query=False,
                feed_url="https://example.com/feed.json",
            ),
        ]

        with patch("connectors.runner._connector_for", return_value=FakeConnector()):
            payload = collect_sources("fixture query", max_workers=1, sources=sources)

        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["connector_id"], "fake")
        self.assertEqual(payload["results"][0]["source_id"], "search_fixture")
        self.assertEqual([status["status"] for status in payload["sources"]], ["success", "disabled"])


if __name__ == "__main__":
    unittest.main()

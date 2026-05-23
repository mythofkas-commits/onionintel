import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connectors.base import ConnectorRunResult
from connectors.runner import clear_unhealthy_sources, collect_sources
from domain.models import SearchHit, stable_id
from domain.models import RunConfig
from pipeline import run_pipeline
from registry.schema import SourceSpec


class PipelineSmokeTests(unittest.TestCase):
    def tearDown(self):
        clear_unhealthy_sources()

    def test_pipeline_returns_run_state_and_saves_audit_fields(self):
        search_payload = {
            "results": [
                {
                    "title": "Target",
                    "link": "http://targetabcdefghijklmnop.onion",
                    "source": "Fixture",
                    "snippet": "admin@example.com",
                }
            ],
            "qualified_results": [
                {
                    "title": "Target",
                    "link": "http://targetabcdefghijklmnop.onion",
                    "source": "Fixture",
                    "snippet": "admin@example.com",
                }
            ],
            "sources": [{"name": "Fixture", "status": "success", "result_count": 1}],
            "query_plan": {"mode": "off", "selected_intent": "freeform_threat", "queries": []},
            "query_runs": [{"query": "refined", "result_count": 1}],
            "query_expansion_mode": "off",
        }
        scrape_payload = {
            "content": {"http://targetabcdefghijklmnop.onion": "Target admin@example.com"},
            "status": [{"url": "http://targetabcdefghijklmnop.onion", "status": "success"}],
            "documents": [
                {
                    "doc_id": "doc_fixture",
                    "source_id": "src_fixture",
                    "connector_id": "http_fetch",
                    "url": "http://targetabcdefghijklmnop.onion",
                    "final_url": "http://targetabcdefghijklmnop.onion",
                    "title": "Target",
                    "content_type": "text/html",
                    "status_code": 200,
                    "raw_html": "<html>admin@example.com</html>",
                    "extracted_text": "Target admin@example.com",
                    "text_hash": "text_hash",
                    "content_hash": "content_hash",
                }
            ],
            "fetches": [
                {
                    "fetch_id": "fetch_fixture",
                    "url": "http://targetabcdefghijklmnop.onion",
                    "final_url": "http://targetabcdefghijklmnop.onion",
                    "status": "success",
                    "status_code": 200,
                    "content_type": "text/html",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            with patch("pipeline.run.refine_query", return_value="refined"):
                with patch("pipeline.run.filter_results", side_effect=lambda _llm, _query, results: results):
                    with patch("pipeline.run.generate_summary", return_value="summary"):
                        with patch("pipeline.run.save_investigation") as save_mock:
                            save_mock.return_value = "investigation.json"
                            state = run_pipeline(
                                RunConfig(query="query", model="gpt-4.1", max_results=10, max_scrape=5),
                                refine_llm=object(),
                                expansion_llm=object(),
                                triage_llm=object(),
                                report_llm=object(),
                                search_func=lambda *_args, **_kwargs: search_payload,
                                scrape_func=lambda *_args, **_kwargs: scrape_payload,
                                tor_check_func=lambda: {"status": "up"},
                            )

        self.assertEqual(state.refined_query, "refined")
        self.assertIn("Evidence-backed findings", state.synthesis_report.summary)
        self.assertEqual(len(state.documents), 1)
        self.assertTrue(state.typed_artifacts)
        self.assertTrue(state.entities)
        self.assertTrue(state.relationships)
        self.assertTrue(state.relevance_scores)
        self.assertTrue(state.ranked_documents)
        self.assertTrue(state.pivot_suggestions)
        self.assertTrue(state.claims)
        save_kwargs = save_mock.call_args.kwargs
        self.assertEqual(save_kwargs["schema_version"], "2.0")
        self.assertEqual(save_kwargs["run_id"], state.run_id)
        self.assertTrue(save_kwargs["stage_status"])
        self.assertTrue(save_kwargs["documents"])
        self.assertTrue(save_kwargs["claims"])
        self.assertTrue(save_kwargs["synthesis_report"])

    def test_pipeline_can_collect_search_hits_through_connector_runner(self):
        source = SourceSpec(
            id="connector_fixture",
            name="Connector Fixture",
            category="search_engine",
            access="tor",
            url_template="http://fixtureabcdefghijklmnop.onion/search?q={query}",
        )

        class FakeConnector:
            connector_id = "fake_search"

            def collect_payload(self, task, source_spec):
                hit = SearchHit(
                    hit_id=stable_id("hit", source_spec.id, task.query),
                    source_id=source_spec.id,
                    connector_id=self.connector_id,
                    query=task.query,
                    title="Target admin@example.com",
                    url="http://targetabcdefghijklmnop.onion",
                    snippet="admin@example.com",
                    metadata={"source": source_spec.name, "source_category": source_spec.category},
                )
                return ConnectorRunResult(
                    source=source_spec,
                    status={
                        "name": source_spec.name,
                        "source_id": source_spec.id,
                        "category": source_spec.category,
                        "status": "success",
                        "result_count": 1,
                        "connector_id": self.connector_id,
                    },
                    search_hits=[hit],
                )

        scrape_payload = {
            "content": {"http://targetabcdefghijklmnop.onion": "Target admin@example.com"},
            "status": [{"url": "http://targetabcdefghijklmnop.onion", "status": "success"}],
            "documents": [
                {
                    "doc_id": "doc_connector",
                    "source_id": "connector_fixture",
                    "connector_id": "http_fetch",
                    "url": "http://targetabcdefghijklmnop.onion",
                    "final_url": "http://targetabcdefghijklmnop.onion",
                    "title": "Target",
                    "content_type": "text/html",
                    "status_code": 200,
                    "raw_html": "<html>admin@example.com</html>",
                    "extracted_text": "Target admin@example.com",
                    "text_hash": "text_hash",
                    "content_hash": "content_hash",
                }
            ],
            "fetches": [],
        }

        with patch("pipeline.run.refine_query", return_value="refined"):
            with patch("connectors.runner._connector_for", return_value=FakeConnector()):
                with patch("pipeline.run.save_investigation") as save_mock:
                    save_mock.return_value = "investigation.json"
                    state = run_pipeline(
                        RunConfig(query="admin@example.com", model="gpt-4.1", max_results=10, max_scrape=5),
                        refine_llm=object(),
                        expansion_llm=object(),
                        triage_llm=object(),
                        report_llm=None,
                        search_func=lambda query, max_workers=1: collect_sources(query, max_workers=max_workers, sources=[source]),
                        scrape_func=lambda *_args, **_kwargs: scrape_payload,
                        tor_check_func=lambda: {"status": "up"},
                    )

        self.assertEqual(state.raw_results[0]["connector_id"], "fake_search")
        self.assertEqual(state.source_records[0].connector_id, "fake_search")
        self.assertTrue(state.claims)
        self.assertTrue(save_mock.call_args.kwargs["claims"])


if __name__ == "__main__":
    unittest.main()

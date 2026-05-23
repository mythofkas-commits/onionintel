import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from domain.models import RunConfig
from pipeline import run_pipeline


class PipelineSmokeTests(unittest.TestCase):
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
        self.assertEqual(state.synthesis_report.summary, "summary")
        self.assertEqual(len(state.documents), 1)
        self.assertTrue(state.typed_artifacts)
        self.assertTrue(state.entities)
        self.assertTrue(state.relationships)
        save_kwargs = save_mock.call_args.kwargs
        self.assertEqual(save_kwargs["schema_version"], "2.0")
        self.assertEqual(save_kwargs["run_id"], state.run_id)
        self.assertTrue(save_kwargs["stage_status"])
        self.assertTrue(save_kwargs["documents"])


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from investigations import load_investigations, save_investigation


class InvestigationPersistenceTests(unittest.TestCase):
    def test_saves_metadata_rich_investigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            save_investigation(
                query="query",
                refined_query="refined",
                model="gpt-4.1",
                preset_label="Threat Intel",
                sources=[{"title": "Hit", "link": "http://hitabcdefghijklmnop.onion"}],
                source_provenance=[{"title": "Raw", "link": "http://rawabcdefghijklmnop.onion"}],
                search_status=[{"name": "Fixture", "status": "success"}],
                artifacts={"emails": [{"value": "admin@example.com"}]},
                scraped_urls=["http://hitabcdefghijklmnop.onion"],
                query_plan={"mode": "conservative", "queries": [{"query": "query"}]},
                query_runs=[{"query": "query", "result_count": 1}],
                query_expansion_mode="conservative",
                intent_metadata={"selected_intent": "person_name", "warnings": []},
                model_routing={
                    "enabled": True,
                    "query_refinement": "gpt-5.4-mini",
                    "query_expansion": "gpt-5.4-mini",
                    "result_triage": "gpt-5.4-nano",
                    "final_report": "gpt-5.4",
                },
                summary="summary",
                directory=directory,
            )
            loaded = load_investigations(directory)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["schema_version"], "2.0")
        self.assertTrue(loaded[0]["run_id"].startswith("run_"))
        self.assertEqual(loaded[0]["query"], "query")
        self.assertEqual(loaded[0]["search_status"][0]["name"], "Fixture")
        self.assertEqual(loaded[0]["artifacts"]["emails"][0]["value"], "admin@example.com")
        self.assertEqual(loaded[0]["query_expansion_mode"], "conservative")
        self.assertEqual(loaded[0]["query_runs"][0]["query"], "query")
        self.assertEqual(loaded[0]["intent_metadata"]["selected_intent"], "person_name")
        self.assertEqual(loaded[0]["model_routing"]["final_report"], "gpt-5.4")

    def test_loads_old_investigation_without_new_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "investigation_20260101_000000.json").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-01-01T00:00:00",
                        "query": "old",
                        "refined_query": "old",
                        "model": "gpt-4.1",
                        "preset": "Threat Intel",
                        "sources": [],
                        "summary": "summary",
                    }
                ),
                encoding="utf-8",
            )
            loaded = load_investigations(directory)

        self.assertEqual(loaded[0]["search_status"], [])
        self.assertEqual(loaded[0]["artifacts"], {})
        self.assertEqual(loaded[0]["scraped_urls"], [])
        self.assertEqual(loaded[0]["query_plan"], {})
        self.assertEqual(loaded[0]["query_runs"], [])
        self.assertEqual(loaded[0]["query_expansion_mode"], "off")
        self.assertEqual(loaded[0]["intent_metadata"], {})
        self.assertEqual(loaded[0]["model_routing"], {})
        self.assertEqual(loaded[0]["schema_version"], "1.0")
        self.assertEqual(loaded[0]["run_id"], "")
        self.assertEqual(loaded[0]["documents"], [])
        self.assertEqual(loaded[0]["stage_status"], [])


if __name__ == "__main__":
    unittest.main()

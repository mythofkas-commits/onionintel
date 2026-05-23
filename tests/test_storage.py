import tempfile
import unittest
from pathlib import Path

from domain.models import (
    Claim,
    Document,
    Entity,
    FetchRecord,
    RunState,
    SearchHit,
    SourceRecord,
    SynthesisReport,
    stable_id,
)
from storage.repository import (
    export_investigation_json,
    export_investigation_markdown,
    get_run_payload,
    initialize_storage,
    list_investigations,
    list_source_health,
    save_run_state,
)


class StorageRepositoryTests(unittest.TestCase):
    def test_run_state_round_trips_to_sqlite_tables_and_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "onionintel.sqlite3"
            initialize_storage(db_path)
            document = Document.from_fetch(
                url="http://targetabcdefghijklmnop.onion",
                final_url="http://targetabcdefghijklmnop.onion",
                title="Target",
                content_type="text/html",
                status_code=200,
                raw_html="<html>admin@example.com</html>",
                extracted_text="Target admin@example.com",
                source_id="fixture",
            )
            claim = Claim(
                claim_id=stable_id("claim", "admin@example.com"),
                claim_text="Document mentions admin@example.com.",
                evidence_doc_ids=[document.doc_id],
                evidence_quotes=["admin@example.com"],
                confidence=0.55,
                confidence_label="medium",
            )
            state = RunState(
                run_id="run_storage_fixture",
                query="admin@example.com",
                refined_query="admin@example.com",
                model="gpt-4.1",
                source_records=[
                    SourceRecord(
                        source_id="fixture",
                        name="Fixture",
                        status="success",
                        connector_id="search_engine",
                        result_count=1,
                    )
                ],
                search_hits=[
                    SearchHit(
                        hit_id="hit_fixture",
                        source_id="fixture",
                        title="Target",
                        url="http://targetabcdefghijklmnop.onion",
                        snippet="admin@example.com",
                    )
                ],
                fetch_records=[FetchRecord(fetch_id="fetch_fixture", url=document.url, status="success")],
                documents=[document],
                entities=[Entity(entity_id="ent_fixture", entity_type="email", canonical_value="admin@example.com")],
                claims=[claim],
                synthesis_report=SynthesisReport(summary="Finding references claim."),
            )
            state.add_stage("pipeline", "success")

            save_run_state(state, db_path=db_path)
            loaded = get_run_payload("run_storage_fixture", db_path=db_path)
            exported = export_investigation_json("run_storage_fixture", db_path=db_path)
            markdown = export_investigation_markdown("run_storage_fixture", db_path=db_path)
            listed = list_investigations(db_path=db_path)
            health = list_source_health(db_path=db_path)

        self.assertEqual(loaded["run_id"], "run_storage_fixture")
        self.assertEqual(exported["documents"][0]["doc_id"], document.doc_id)
        self.assertIn("admin@example.com", markdown)
        self.assertEqual(listed[0]["run_id"], "run_storage_fixture")
        self.assertEqual(health[0]["last_status"], "success")


if __name__ == "__main__":
    unittest.main()

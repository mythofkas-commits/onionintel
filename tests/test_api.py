import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from domain.models import Claim, Document, RunState, SynthesisReport, stable_id
from storage.repository import save_run_state


class ApiBoundaryTests(unittest.TestCase):
    def test_read_endpoints_and_exports_use_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "api.sqlite3"
            document = Document.from_fetch(
                url="http://targetabcdefghijklmnop.onion",
                final_url="http://targetabcdefghijklmnop.onion",
                title="Target",
                content_type="text/html",
                status_code=200,
                raw_html="<html>admin@example.com</html>",
                extracted_text="Target admin@example.com",
            )
            claim = Claim(
                claim_id=stable_id("claim", "api"),
                claim_text="Document mentions admin@example.com.",
                evidence_doc_ids=[document.doc_id],
                evidence_quotes=["admin@example.com"],
                confidence=0.55,
                confidence_label="medium",
            )
            state = RunState(
                run_id="run_api_fixture",
                query="admin@example.com",
                refined_query="admin@example.com",
                model="gpt-4.1",
                documents=[document],
                claims=[claim],
                synthesis_report=SynthesisReport(summary="Evidence-backed summary."),
            )
            save_run_state(state, db_path=db_path)
            client = TestClient(app)
            with patch("api.main.get_run_payload", side_effect=lambda run_id: __import__("storage.repository", fromlist=["get_run_payload"]).get_run_payload(run_id, db_path=db_path)):
                with patch("api.main.list_investigations", side_effect=lambda: __import__("storage.repository", fromlist=["list_investigations"]).list_investigations(db_path=db_path)):
                    with patch("api.main.export_investigation_json", side_effect=lambda run_id: __import__("storage.repository", fromlist=["export_investigation_json"]).export_investigation_json(run_id, db_path=db_path)):
                        with patch("api.main.export_investigation_markdown", side_effect=lambda run_id: __import__("storage.repository", fromlist=["export_investigation_markdown"]).export_investigation_markdown(run_id, db_path=db_path)):
                            run_resp = client.get("/runs/run_api_fixture")
                            docs_resp = client.get("/runs/run_api_fixture/documents")
                            claims_resp = client.get("/runs/run_api_fixture/claims")
                            investigations_resp = client.get("/investigations")
                            json_resp = client.get("/runs/run_api_fixture/export.json")
                            md_resp = client.get("/runs/run_api_fixture/export.md")

        self.assertEqual(run_resp.status_code, 200)
        self.assertEqual(docs_resp.json()[0]["doc_id"], document.doc_id)
        self.assertEqual(claims_resp.json()[0]["claim_id"], claim.claim_id)
        self.assertEqual(investigations_resp.json()[0]["run_id"], "run_api_fixture")
        self.assertEqual(json_resp.json()["run_id"], "run_api_fixture")
        self.assertIn("Evidence-backed summary", md_resp.text)

    def test_post_run_uses_pipeline_and_returns_state(self):
        client = TestClient(app)
        state = RunState(run_id="run_created_fixture", query="query", model="gpt-4.1")
        with patch("api.main.get_model_choices", return_value=["gpt-4.1"]):
            with patch("api.main.get_llm", return_value=object()):
                with patch("api.main.run_pipeline", return_value=state):
                    response = client.post("/runs", json={"query": "query", "model": "gpt-4.1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["run_id"], "run_created_fixture")


if __name__ == "__main__":
    unittest.main()

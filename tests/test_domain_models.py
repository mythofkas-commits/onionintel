import unittest

from domain.models import Document, RunConfig, SearchHit, stable_id


class DomainModelTests(unittest.TestCase):
    def test_run_config_defaults_are_serializable(self):
        config = RunConfig(query="example", model="gpt-4.1")
        payload = config.model_dump(mode="json")

        self.assertEqual(payload["query"], "example")
        self.assertTrue(payload["run_id"].startswith("run_"))
        self.assertEqual(payload["expansion_mode"], "off")

    def test_search_hit_adapts_existing_result_dict(self):
        hit = SearchHit.from_result(
            {"title": "Hit", "link": "http://targetabcdefghijklmnop.onion", "source": "Fixture"},
            query="target",
            rank=1,
        )

        self.assertEqual(hit.title, "Hit")
        self.assertEqual(hit.query, "target")
        self.assertEqual(hit.source_id, stable_id("src", "Fixture"))

    def test_document_hashes_text_and_content(self):
        document = Document.from_fetch(
            url="http://targetabcdefghijklmnop.onion",
            final_url="http://targetabcdefghijklmnop.onion/final",
            title="Title",
            content_type="text/html",
            status_code=200,
            raw_html="<html>Body</html>",
            extracted_text="Body",
        )

        self.assertTrue(document.doc_id.startswith("doc_"))
        self.assertTrue(document.text_hash)
        self.assertTrue(document.content_hash)


if __name__ == "__main__":
    unittest.main()

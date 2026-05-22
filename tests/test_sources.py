import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sources
from sources import SourceConfig, SourceRegistryError, parse_search_html


class SourceRegistryTests(unittest.TestCase):
    def test_load_source_configs_from_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yml"
            path.write_text(
                """
sources:
  - name: Example
    url_template: "http://engine.onion/search?q={query}"
    enabled: true
    parser: generic
    timeout: 12
    notes: "fixture"
""",
                encoding="utf-8",
            )
            configs = sources.load_source_configs(path)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].name, "Example")
        self.assertTrue(configs[0].enabled)
        self.assertEqual(configs[0].timeout, 12)

    def test_disabled_source_is_not_enabled(self):
        with patch.object(
            sources,
            "load_source_configs",
            return_value=[
                SourceConfig("Enabled", "http://enabled.onion/search?q={query}", enabled=True),
                SourceConfig("Disabled", "http://disabled.onion/search?q={query}", enabled=False),
            ],
        ):
            self.assertEqual([source.name for source in sources.get_enabled_sources()], ["Enabled"])

    def test_missing_query_placeholder_is_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yml"
            path.write_text(
                """
sources:
  - name: Broken
    url_template: "http://engine.onion/search"
""",
                encoding="utf-8",
            )
            with self.assertRaises(SourceRegistryError):
                sources.load_source_configs(path)


class ParserTests(unittest.TestCase):
    def test_generic_parser_handles_direct_redirect_relative_and_deduped_links(self):
        source = SourceConfig("Fixture", "http://engineexampleabcdefghijklmnop.onion/search?q={query}")
        html = """
        <a href="http://targetabcdefghijklmnop.onion/path">Direct Result</a>
        <a href="/redirect?url=http%3A%2F%2Fsecondabcdefghijklmnop.onion%2Fitem">Redirect Result</a>
        <a href="/search?q=test">Self Search</a>
        <a href="http://targetabcdefghijklmnop.onion/path">Duplicate Result</a>
        """
        results = parse_search_html(html, source, "http://engineexampleabcdefghijklmnop.onion/search?q=test")

        self.assertEqual([result["title"] for result in results], ["Direct Result", "Redirect Result"])
        self.assertEqual([result["source"] for result in results], ["Fixture", "Fixture"])
        self.assertIn("raw_url", results[0])
        self.assertIn("discovered_at", results[0])

    def test_generic_parser_ignores_source_self_links_and_redirects(self):
        source = SourceConfig("Fixture", "http://engineexampleabcdefghijklmnop.onion/search?q={query}")
        html = """
        <a href="http://engineexampleabcdefghijklmnop.onion/">Self Result</a>
        <a href="/redirect?url=http%3A%2F%2Fengineexampleabcdefghijklmnop.onion%2F">Self Redirect</a>
        <a href="/redirect?url=http%3A%2F%2Ftargetabcdefghijklmnop.onion%2F">Valid Redirect</a>
        """
        results = parse_search_html(html, source, "http://engineexampleabcdefghijklmnop.onion/search?q=test")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["link"], "http://targetabcdefghijklmnop.onion/")

    def test_torch_parser_uses_result_containers(self):
        source = SourceConfig("Torch", "http://torchabcdefghijklmnop.onion/search?query={query}", parser="torch")
        html = """
        <nav><a href="http://navabcdefghijklmnop.onion/">Navigation</a></nav>
        <div class="result">
            <h5><a href="http://targetabcdefghijklmnop.onion/path">Target Title</a></h5>
            <h6><a href="http://targetabcdefghijklmnop.onion/path">http://targetabcdefghijklmnop.onion/path</a></h6>
        </div>
        """
        results = parse_search_html(html, source, "http://torchabcdefghijklmnop.onion/search?query=test")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Target Title")
        self.assertEqual(results[0]["link"], "http://targetabcdefghijklmnop.onion/path")

    def test_ahmia_parser_uses_result_containers(self):
        source = SourceConfig("Ahmia", "http://ahmiaabcdefghijklmnop.onion/search/?q={query}", parser="ahmia")
        html = """
        <a href="http://navabcdefghijklmnop.onion/">Navigation</a>
        <li class="result">
            <a href="/search/redirect?redirect_url=http%3A%2F%2Ftargetabcdefghijklmnop.onion%2F">Target Title</a>
        </li>
        """
        results = parse_search_html(html, source, "http://ahmiaabcdefghijklmnop.onion/search/?q=test")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["link"], "http://targetabcdefghijklmnop.onion/")

    def test_vormweb_parser_uses_query_boxes(self):
        source = SourceConfig("VormWeb", "http://vormwebabcdefghijklmnop.onion/search?q={query}", parser="vormweb")
        html = """
        <a href="http://navabcdefghijklmnop.onion/">Navigation</a>
        <div class="query-box">
            <a href="http://targetabcdefghijklmnop.onion/">Target Title</a>
            <a href="/navigation/reports/index.php?url=http%3A%2F%2Ftargetabcdefghijklmnop.onion%2F">Melden</a>
        </div>
        """
        results = parse_search_html(html, source, "http://vormwebabcdefghijklmnop.onion/search?q=test")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Target Title")

    def test_lantern_parser_uses_search_cards_and_skips_ads(self):
        source = SourceConfig("Lantern", "http://lanternabcdefghijklmnop.onion/search?q={query}", parser="lantern")
        html = """
        <section class="search-ads"><article class="search-card search-card-ad">
            <a href="/out?u=http%3A%2F%2Fadtargetabcdefghijklmnop.onion%2F">Ad Title</a>
        </article></section>
        <ol class="search-list"><li class="search-item"><article class="search-card">
            <a href="/out?u=http%3A%2F%2Ftargetabcdefghijklmnop.onion%2Fprivacy">Privacy Target</a>
        </article></li></ol>
        """
        results = parse_search_html(html, source, "http://lanternabcdefghijklmnop.onion/search?q=privacy")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Privacy Target")
        self.assertEqual(results[0]["link"], "http://targetabcdefghijklmnop.onion/privacy")

    def test_onionfind_parser_uses_result_items(self):
        source = SourceConfig("OnionFind", "https://onionfind.com/search?q={query}", parser="onionfind")
        html = """
        <footer><a href="https://onionfind.com/about">About</a></footer>
        <div class="results-list">
            <div class="result-item"><a href="http://targetabcdefghijklmnop.onion/">Target Title</a></div>
            <div><a href="https://onionfind.com/search?q=related">Related Search</a></div>
        </div>
        """
        results = parse_search_html(html, source, "https://onionfind.com/search?q=privacy")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["link"], "http://targetabcdefghijklmnop.onion/")

    def test_torsearch_parser_requires_query_match(self):
        source = SourceConfig("TorSearch", "https://torsearch.com/search?query={query}", parser="torsearch")
        html = """
        <div class="result">
            <h5><a href="http://targetabcdefghijklmnop.onion/privacy">Privacy Target</a></h5>
        </div>
        <div class="result">
            <h5><a href="http://fixedabcdefghijklmnop.onion/market">Fixed Market Link</a></h5>
        </div>
        """
        matched = parse_search_html(html, source, "https://torsearch.com/search?query=privacy", query="privacy")
        unmatched = parse_search_html(html, source, "https://torsearch.com/search?query=zzrobinnohit20260519", query="zzrobinnohit20260519")

        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["link"], "http://targetabcdefghijklmnop.onion/privacy")
        self.assertEqual(unmatched, [])

    def test_source_result_limit_caps_broad_engines(self):
        results = [{"title": f"Hit {idx}", "link": f"http://target{idx}.onion", "source": "Fixture"} for idx in range(150)]

        self.assertEqual(len(sources._limit_source_results(results)), sources.MAX_RESULTS_PER_SOURCE_QUERY)

    def test_transport_wide_failure_does_not_mark_all_sources_unhealthy(self):
        self.assertFalse(
            sources._has_usable_source_signal(
                [
                    {"name": "A", "status": "timeout"},
                    {"name": "B", "status": "tor_error"},
                ]
            )
        )
        self.assertTrue(
            sources._has_usable_source_signal(
                [
                    {"name": "A", "status": "timeout"},
                    {"name": "B", "status": "zero_results"},
                ]
            )
        )

    def test_search_sources_skips_unhealthy_sources_for_current_process(self):
        enabled = SourceConfig("Enabled", "http://enabledabcdefghijklmnop.onion/search?q={query}")
        failing = SourceConfig("Failing", "http://failingabcdefghijklmnop.onion/search?q={query}")
        sources.clear_unhealthy_sources()
        sources.set_unhealthy_sources([{"name": "Failing", "status": "down"}])

        def fake_fetch(source, query):
            return {
                "name": source.name,
                "status": "success",
                "latency_ms": 1,
                "result_count": 1,
                "error": None,
                "parser": source.parser,
                "enabled": source.enabled,
                "notes": source.notes,
                "results": [{"title": "Hit", "link": "http://hitabcdefghijklmnop.onion", "source": source.name}],
            }

        with patch.object(sources, "load_source_configs", return_value=[enabled, failing]):
            with patch.object(sources, "fetch_source_results", side_effect=fake_fetch):
                payload = sources.search_sources("test", max_workers=1)

        self.assertEqual([result["source"] for result in payload["results"]], ["Enabled"])
        self.assertIn("skipped_unhealthy", [status["status"] for status in payload["sources"]])
        sources.clear_unhealthy_sources()


if __name__ == "__main__":
    unittest.main()

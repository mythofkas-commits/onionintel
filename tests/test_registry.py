import tempfile
import unittest
from pathlib import Path

from registry.loaders import load_source_catalog, load_source_specs, source_config_to_spec, source_spec_to_config
from sources import SourceConfig


class RegistrySchemaTests(unittest.TestCase):
    def test_loads_existing_source_shape_as_source_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sources.yml"
            path.write_text(
                """
sources:
  - name: Fixture
    url_template: "http://fixtureabcdefghijklmnop.onion/search?q={query}"
    enabled: true
    parser: generic
    timeout: 12
    notes: test source
""",
                encoding="utf-8",
            )
            specs = load_source_specs(path)

        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].id, "fixture")
        self.assertEqual(specs[0].category, "search_engine")
        self.assertEqual(specs[0].access, "tor")

    def test_source_config_round_trip_adapter(self):
        config = SourceConfig("Fixture", "http://fixtureabcdefghijklmnop.onion/search?q={query}", parser="torch")
        spec = source_config_to_spec(config)
        round_tripped = source_spec_to_config(spec)

        self.assertEqual(round_tripped.name, config.name)
        self.assertEqual(round_tripped.url_template, config.url_template)
        self.assertEqual(round_tripped.parser, "torch")

    def test_loads_mixed_catalog_files_in_canonical_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "search_engines.yml").write_text(
                """
sources:
  - id: search_fixture
    name: Search Fixture
    category: search_engine
    access: tor
    url_template: "http://fixtureabcdefghijklmnop.onion/search?q={query}"
""",
                encoding="utf-8",
            )
            (root / "public_feeds.yml").write_text(
                """
sources:
  - id: feed_fixture
    name: Feed Fixture
    category: api_feed
    access: direct
    enabled: false
    supports_query: false
    feed_url: "https://example.com/feed.json"
""",
                encoding="utf-8",
            )
            (root / "site_monitors.yml").write_text(
                """
sources:
  - id: site_fixture
    name: Site Fixture
    category: known_site
    access: direct
    enabled: false
    supports_query: false
    site_url: "https://example.com/"
""",
                encoding="utf-8",
            )

            specs = load_source_catalog(root)

        self.assertEqual([spec.id for spec in specs], ["search_fixture", "feed_fixture", "site_fixture"])
        self.assertEqual([spec.category for spec in specs], ["search_engine", "api_feed", "known_site"])


if __name__ == "__main__":
    unittest.main()

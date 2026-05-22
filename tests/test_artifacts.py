import unittest

from artifacts import extract_artifacts, flatten_artifacts


class ArtifactExtractionTests(unittest.TestCase):
    def test_extracts_common_osint_artifacts_with_evidence(self):
        content = {
            "http://sourceabcdefghijklmnop.onion": (
                "Contact admin@example.com about CVE-2024-12345. "
                "Payload hash d41d8cd98f00b204e9800998ecf8427e and sha256 "
                "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855. "
                "Wallet 0x1111111111111111111111111111111111111111, IP 8.8.8.8, "
                "handle @threat_actor and portal https://example.com/login."
            )
        }
        results = [{"title": "Leak", "link": "http://leakabcdefghijklmnop.onion/path", "source": "Fixture"}]

        artifacts = extract_artifacts(search_results=results, scraped_content=content)
        rows = flatten_artifacts(artifacts)
        values = {row["value"].lower() for row in rows}

        self.assertIn("admin@example.com", values)
        self.assertIn("cve-2024-12345", values)
        self.assertIn("d41d8cd98f00b204e9800998ecf8427e", values)
        self.assertIn("0x1111111111111111111111111111111111111111", values)
        self.assertIn("8.8.8.8", values)
        self.assertIn("@threat_actor", values)
        self.assertTrue(any(row["evidence"] for row in rows))

    def test_avoids_email_local_part_as_handle_and_invalid_ipv4(self):
        artifacts = extract_artifacts(
            scraped_content={
                "fixture": "Email user@example.com should not produce a handle. Bad IP 999.1.1.1."
            }
        )
        handles = {item["value"] for item in artifacts["handles"]}
        ips = {item["value"] for item in artifacts["ipv4_addresses"]}

        self.assertNotIn("@example", handles)
        self.assertNotIn("999.1.1.1", ips)


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

import scrape


class FakeResponse:
    def __init__(self, status_code=200, headers=None, chunks=None):
        self.status_code = status_code
        self.headers = headers or {"Content-Type": "text/html"}
        self._chunks = chunks or [b"<html><body>Hello world</body></html>"]
        self.encoding = "utf-8"
        self.is_redirect = status_code in (301, 302, 303, 307, 308)
        self.is_permanent_redirect = status_code in (301, 308)

    def iter_content(self, chunk_size=8192):
        yield from self._chunks

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requested = []

    def get(self, url, **kwargs):
        self.requested.append((url, kwargs))
        if not self.responses:
            raise AssertionError("No fake responses left")
        return self.responses.pop(0)


class ScrapeSafetyTests(unittest.TestCase):
    def test_rejects_non_http_urls(self):
        self.assertEqual(scrape.scrape_multiple([{"link": "file:///etc/passwd", "title": "bad"}]), {})

    def test_rejects_credentialed_urls(self):
        self.assertEqual(scrape.scrape_multiple([{"link": "http://user:pass@example.com", "title": "bad"}]), {})

    def test_redirect_policy_follows_limited_safe_redirects(self):
        session = FakeSession(
            [
                FakeResponse(302, headers={"Location": "http://targetabcdefghijklmnop.onion/page"}),
                FakeResponse(200, chunks=[b"<html><body>Done</body></html>"]),
            ]
        )
        response = scrape._request_with_redirect_policy(
            session,
            "http://startabcdefghijklmnop.onion",
            headers={},
            timeout=(1, 1),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(session.requested), 2)

    def test_unsupported_content_type_returns_title_only(self):
        session = FakeSession([FakeResponse(200, headers={"Content-Type": "application/pdf"})])
        with patch.object(scrape, "_get_session", return_value=session):
            url, text = scrape.scrape_single({"link": "http://targetabcdefghijklmnop.onion/doc", "title": "Doc"})

        self.assertEqual(url, "http://targetabcdefghijklmnop.onion/doc")
        self.assertEqual(text, "Doc")

    def test_duplicate_urls_are_scraped_once(self):
        session = FakeSession([FakeResponse(200)])
        with patch.object(scrape, "_get_session", return_value=session):
            result = scrape.scrape_multiple(
                [
                    {"link": "http://targetabcdefghijklmnop.onion", "title": "One"},
                    {"link": "http://targetabcdefghijklmnop.onion", "title": "Two"},
                ],
                max_workers=1,
            )

        self.assertEqual(list(result), ["http://targetabcdefghijklmnop.onion"])


if __name__ == "__main__":
    unittest.main()

import random
import requests
import threading
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

import warnings
warnings.filterwarnings("ignore")

from domain.models import Document, FetchRecord, stable_id

# Define a list of rotating user agents.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54"
]

MAX_DOWNLOAD_BYTES = 1_000_000
MAX_EXTRACTED_TEXT_CHARS = 50_000
MAX_RETURN_CHARS = 2_000
MAX_REDIRECTS = 3
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_thread_local = threading.local()
_logger = logging.getLogger(__name__)
_last_scrape_status = []
_last_scrape_documents = []
_last_fetch_records = []


def _normalize_url_data(url_data):
    if not isinstance(url_data, dict):
        return "", "Untitled"
    url = str(url_data.get("link") or "").strip()
    title = str(url_data.get("title") or "Untitled").strip() or "Untitled"
    return url, title


def _is_safe_http_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    return True


def _build_session(use_tor=False):
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    if use_tor:
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }

    return session


def _get_session(use_tor=False):
    key = "tor_session" if use_tor else "direct_session"
    if not hasattr(_thread_local, key):
        setattr(_thread_local, key, _build_session(use_tor=use_tor))
    return getattr(_thread_local, key)

def get_tor_session():
    """
    Creates a requests Session with Tor SOCKS proxy and automatic retries.
    """
    return _build_session(use_tor=True)


def _request_with_redirect_policy(session, url, headers, timeout):
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        if not _is_safe_http_url(current_url):
            raise ValueError(f"Unsafe URL rejected: {current_url}")

        response = session.get(
            current_url,
            headers=headers,
            timeout=timeout,
            stream=True,
            allow_redirects=False,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise requests.exceptions.TooManyRedirects("Redirect response without Location header")
            current_url = urljoin(current_url, location)
            continue
        return response

    raise requests.exceptions.TooManyRedirects(f"Exceeded {MAX_REDIRECTS} redirects")

def scrape_single(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL using a robust Tor session.
    Returns a tuple (url, scraped_text).
    """
    fetch_record, document, display_text = scrape_single_document(
        url_data,
        rotate=rotate,
        rotate_interval=rotate_interval,
        control_port=control_port,
        control_password=control_password,
    )
    return fetch_record.url, display_text


def scrape_single_document(url_data, rotate=False, rotate_interval=5, control_port=9051, control_password=None):
    """
    Scrapes a single URL and returns typed fetch/document records plus UI display text.
    Internal document text is capped by MAX_EXTRACTED_TEXT_CHARS, not MAX_RETURN_CHARS.
    """
    url, title = _normalize_url_data(url_data)
    if not url:
        fetch_record = FetchRecord(fetch_id=stable_id("fetch", ""), url="", status="invalid_url")
        return fetch_record, None, title

    if not _is_safe_http_url(url):
        fetch_record = FetchRecord(fetch_id=stable_id("fetch", url), url=url, status="invalid_url")
        return fetch_record, None, title

    use_tor = (urlparse(url).hostname or "").lower().endswith(".onion")
    source_name = str(url_data.get("source") or (url_data.get("found_by_sources") or [""])[0] or "")
    source_id = stable_id("src", source_name) if source_name else ""

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
    }

    response = None
    fetch_record = FetchRecord(fetch_id=stable_id("fetch", url), url=url, status="pending")
    document = None
    try:
        session = _get_session(use_tor=use_tor)
        if use_tor:
            # Increased timeout for Tor latency
            response = _request_with_redirect_policy(session, url, headers=headers, timeout=(10, 45))
        else:
            # Fallback for clearweb if needed, though tool focuses on dark web
            response = _request_with_redirect_policy(session, url, headers=headers, timeout=(5, 25))

        final_url = getattr(response, "url", None) or url
        content_type = (response.headers.get("Content-Type") or "").lower()
        fetch_record.final_url = final_url
        fetch_record.status_code = response.status_code
        fetch_record.content_type = content_type
        fetch_record.metadata = {"headers": dict(response.headers)}

        if response.status_code == 200:
            if content_type and not any(t in content_type for t in ALLOWED_CONTENT_TYPES):
                fetch_record.status = "unsupported_content_type"
                document = Document.from_fetch(
                    url=url,
                    final_url=final_url,
                    title=title,
                    content_type=content_type,
                    status_code=response.status_code,
                    raw_html="",
                    extracted_text=title,
                    source_id=source_id,
                    metadata={"unsupported_content_type": True},
                )
                return fetch_record, document, title

            chunks = []
            bytes_read = 0
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                bytes_read += len(chunk)
                if bytes_read > MAX_DOWNLOAD_BYTES:
                    break
                chunks.append(chunk)
            fetch_record.bytes_read = bytes_read

            html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")

            soup = BeautifulSoup(html, "html.parser")
            page_title = title
            if soup.title and soup.title.get_text(strip=True):
                page_title = soup.title.get_text(" ", strip=True)
            # Clean up text: remove scripts/styles
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ')
            # Normalize whitespace
            text = ' '.join(text.split())
            text = text[:MAX_EXTRACTED_TEXT_CHARS]
            scraped_text = f"{title} - {text}" if text else title
            document = Document.from_fetch(
                url=url,
                final_url=final_url,
                title=page_title or title,
                content_type=content_type,
                status_code=response.status_code,
                raw_html=html,
                extracted_text=scraped_text,
                source_id=source_id,
                metadata={"display_title": title, "truncated_at_chars": MAX_EXTRACTED_TEXT_CHARS if len(text) >= MAX_EXTRACTED_TEXT_CHARS else None},
            )
            fetch_record.status = "success"
        else:
            scraped_text = title
            fetch_record.status = "http_error"
            document = Document.from_fetch(
                url=url,
                final_url=final_url,
                title=title,
                content_type=content_type,
                status_code=response.status_code,
                raw_html="",
                extracted_text=title,
                source_id=source_id,
            )
    except Exception as exc:
        # Return title only on failure, so we don't lose the reference
        _logger.debug("Failed to scrape url=%s: %s", url, exc)
        scraped_text = title
        fetch_record.status = "error"
        fetch_record.error = str(exc)[:200]
        document = Document.from_fetch(
            url=url,
            final_url=url,
            title=title,
            content_type="",
            status_code=None,
            raw_html="",
            extracted_text=title,
            source_id=source_id,
            metadata={"error": fetch_record.error},
        )
    finally:
        if response is not None:
            response.close()

    return fetch_record, document, scraped_text


def _truncate_for_display(content: str) -> str:
    if len(content) <= MAX_RETURN_CHARS:
        return content
    suffix = "...(truncated)"
    if len(suffix) >= MAX_RETURN_CHARS:
        return suffix[:MAX_RETURN_CHARS]
    available = MAX_RETURN_CHARS - len(suffix)
    return content[:available] + suffix


def scrape_multiple_documents(urls_data, max_workers=5):
    """
    Scrapes multiple URLs concurrently and returns display content plus typed records.
    """
    global _last_scrape_status
    global _last_scrape_documents
    global _last_fetch_records
    results = {}
    statuses = []
    documents = []
    fetch_records = []
    max_workers = max(1, min(int(max_workers), 16))
    if not isinstance(urls_data, (list, tuple)):
        return {"content": results, "status": statuses, "documents": documents, "fetches": fetch_records}

    # Deduplicate links to reduce unnecessary requests under real workloads.
    unique_urls_data = []
    seen_links = set()
    for item in urls_data:
        url, title = _normalize_url_data(item)
        if not url:
            continue
        if not _is_safe_http_url(url):
            statuses.append({"url": url, "status": "invalid_url", "title": title})
            continue
        if url in seen_links:
            continue
        seen_links.add(url)
        unique_urls_data.append({"link": url, "title": title})

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_single_document, url_data): url_data
            for url_data in unique_urls_data
        }
        for future in as_completed(future_to_url):
            try:
                fetch_record, document, content = future.result()
                url = fetch_record.url
                if not url:
                    continue
                display_content = _truncate_for_display(content)
                results[url] = display_content
                fetch_records.append(fetch_record)
                if document is not None:
                    documents.append(document)
                statuses.append(
                    {
                        "url": url,
                        "status": fetch_record.status,
                        "status_code": fetch_record.status_code,
                        "chars": len(display_content),
                        "document_chars": len(document.extracted_text) if document else 0,
                        "doc_id": document.doc_id if document else "",
                        "text_hash": document.text_hash if document else "",
                    }
                )
            except Exception as exc:
                _logger.debug("Worker failed to scrape a URL: %s", exc)
                source = future_to_url.get(future, {})
                statuses.append({"url": source.get("link", ""), "status": "error", "error": str(exc)[:200]})
                continue

    _last_scrape_status = statuses
    _last_scrape_documents = [document.model_dump(mode="json") for document in documents]
    _last_fetch_records = [record.model_dump(mode="json") for record in fetch_records]
    return {
        "content": results,
        "status": statuses,
        "documents": _last_scrape_documents,
        "fetches": _last_fetch_records,
    }


def scrape_multiple(urls_data, max_workers=5):
    """
    Backward-compatible scraper API returning only url -> display text.
    """
    return scrape_multiple_documents(urls_data, max_workers=max_workers).get("content", {})


def get_last_scrape_status():
    return list(_last_scrape_status)


def get_last_scrape_documents():
    return list(_last_scrape_documents)


def get_last_fetch_records():
    return list(_last_fetch_records)
    

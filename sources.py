import html
import json
import logging
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (X11; Linux i686; rv:137.0) Gecko/20100101 Firefox/137.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.3 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.3179.54",
]

SOURCE_REGISTRY_PATH = Path(__file__).with_name("sources.yml")
RESULT_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
ONION_URL_RE = re.compile(r"https?://[a-z0-9.-]+\.onion[^\s\"'<>)]*", re.IGNORECASE)
REDIRECT_PARAM_NAMES = ("url", "u", "q", "target", "redirect", "redirect_url", "link", "to")
MAX_RESULTS_PER_SOURCE_QUERY = 100

_logger = logging.getLogger(__name__)
_UNHEALTHY_SOURCE_NAMES = set()
_LAST_SEARCH_STATUS: List[Dict[str, object]] = []


class SourceRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url_template: str
    enabled: bool = True
    parser: str = "generic"
    timeout: int = 40
    notes: str = ""


def _parse_scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "none"):
        return None
    try:
        return int(value)
    except ValueError:
        return value


def _parse_key_value(line: str) -> Dict[str, object]:
    if ":" not in line:
        raise SourceRegistryError(f"Invalid source registry line: {line}")
    key, value = line.split(":", 1)
    key = key.strip()
    if not key:
        raise SourceRegistryError(f"Invalid source registry key: {line}")
    return {key: _parse_scalar(value)}


def _load_simple_sources_yaml(text: str) -> List[Dict[str, object]]:
    stripped = text.strip()
    if not stripped:
        raise SourceRegistryError("Source registry is empty")
    if stripped[0] in "[{":
        data = json.loads(stripped)
        return data.get("sources", data) if isinstance(data, dict) else data

    entries: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None
    in_sources = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "sources:":
            in_sources = True
            continue
        if not in_sources:
            raise SourceRegistryError("Expected top-level 'sources:' key")
        if line.startswith("- "):
            if current:
                entries.append(current)
            current = {}
            remainder = line[2:].strip()
            if remainder:
                current.update(_parse_key_value(remainder))
            continue
        if current is None:
            raise SourceRegistryError("Expected a source list item")
        current.update(_parse_key_value(line))

    if current:
        entries.append(current)
    if not entries:
        raise SourceRegistryError("Source registry contains no sources")
    return entries


def load_source_configs(path: Path = SOURCE_REGISTRY_PATH) -> List[SourceConfig]:
    try:
        raw_entries = _load_simple_sources_yaml(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SourceRegistryError(f"Invalid JSON/YAML source registry: {exc}") from exc

    configs: List[SourceConfig] = []
    for idx, entry in enumerate(raw_entries, start=1):
        if not isinstance(entry, dict):
            raise SourceRegistryError(f"Source #{idx} must be a mapping")
        name = str(entry.get("name") or "").strip()
        url_template = str(entry.get("url_template") or entry.get("url") or "").strip()
        if not name:
            raise SourceRegistryError(f"Source #{idx} is missing name")
        if not url_template or "{query}" not in url_template:
            raise SourceRegistryError(f"Source '{name}' must include url_template with {{query}}")
        configs.append(
            SourceConfig(
                name=name,
                url_template=url_template,
                enabled=bool(entry.get("enabled", True)),
                parser=str(entry.get("parser") or "generic").strip() or "generic",
                timeout=int(entry.get("timeout") or 40),
                notes=str(entry.get("notes") or "").strip(),
            )
        )
    return configs


def get_enabled_sources(skip_unhealthy: bool = True) -> List[SourceConfig]:
    sources = [source for source in load_source_configs() if source.enabled]
    if not skip_unhealthy:
        return sources
    return [source for source in sources if source.name not in _UNHEALTHY_SOURCE_NAMES]


def get_source_count() -> int:
    return len(load_source_configs())


def get_tor_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=0,
        read=0,
        connect=0,
        backoff_factor=0,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD"]),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.proxies = {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050",
    }
    return session


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_status(
    source: SourceConfig,
    status: str,
    latency_ms: Optional[int] = None,
    result_count: int = 0,
    error: Optional[str] = None,
) -> Dict[str, object]:
    return {
        "name": source.name,
        "status": status,
        "latency_ms": latency_ms,
        "result_count": result_count,
        "error": error,
        "parser": source.parser,
        "enabled": source.enabled,
        "notes": source.notes,
    }


def _clean_url(value: str) -> str:
    return html.unescape(value).strip().strip("\"'<>.,);]")


def _is_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def _is_onion_url(url: str) -> bool:
    parsed = urlparse(url)
    return _is_http_url(url) and (parsed.hostname or "").lower().endswith(".onion")


def _canonical_link(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="", netloc=parsed.netloc.lower()).geturl().rstrip("/")


def _extract_redirect_target(href: str) -> Optional[str]:
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    for key in REDIRECT_PARAM_NAMES:
        for value in params.get(key, []):
            decoded = _clean_url(unquote(value))
            if _is_onion_url(decoded):
                return decoded
    return None


def _matches_reference_host(candidate: str, *reference_urls: str) -> bool:
    candidate_host = (urlparse(candidate).hostname or "").lower()
    if not candidate_host:
        return False
    for reference_url in reference_urls:
        reference_host = (urlparse(reference_url).hostname or "").lower()
        if reference_host and candidate_host == reference_host:
            return True
    return False


def _extract_candidate_url(href: str, base_url: str, source_url: str) -> Optional[str]:
    decoded = _clean_url(unquote(html.unescape(href)))
    redirect_target = _extract_redirect_target(decoded)
    if redirect_target:
        if _matches_reference_host(redirect_target, base_url, source_url):
            return None
        return redirect_target

    for match in ONION_URL_RE.findall(decoded):
        candidate = _clean_url(match)
        if _is_onion_url(candidate):
            if _matches_reference_host(candidate, base_url, source_url):
                continue
            return candidate

    absolute = _clean_url(urljoin(base_url, decoded))
    if not _is_onion_url(absolute):
        return None

    if _matches_reference_host(absolute, base_url, source_url):
        return None
    return absolute


def _short_text(value: str, limit: int = 300) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _query_tokens(query: Optional[str]) -> List[str]:
    return [token.lower() for token in re.findall(r"[a-z0-9]{3,}", query or "", re.IGNORECASE)]


def _matches_query_text(text: str, query: Optional[str]) -> bool:
    tokens = _query_tokens(query)
    if not tokens:
        return True
    haystack = (text or "").lower()
    return all(token in haystack for token in tokens)


def _append_result(
    results: List[Dict[str, object]],
    seen: set,
    source: SourceConfig,
    link: str,
    raw_url: str,
    anchor,
    container=None,
) -> bool:
    clean_link = _canonical_link(link)
    if clean_link in seen:
        return False
    seen.add(clean_link)

    title = _short_text(anchor.get_text(" ", strip=True), limit=160)
    if not title:
        title = urlparse(link).hostname or "Untitled"
    text_node = container if container is not None else anchor.parent
    parent_text = _short_text(text_node.get_text(" ", strip=True) if text_node else "", limit=300)
    results.append(
        {
            "title": title,
            "link": link,
            "source": source.name,
            "raw_url": raw_url,
            "discovered_at": _utc_now(),
            "snippet": parent_text if parent_text and parent_text != title else "",
        }
    )
    return True


def _parse_container_results(
    soup: BeautifulSoup,
    source: SourceConfig,
    fetched_url: str,
    selector: str,
    query: Optional[str] = None,
    require_query_match: bool = False,
) -> List[Dict[str, object]]:
    results: List[Dict[str, object]] = []
    seen = set()
    for container in soup.select(selector):
        if require_query_match and not _matches_query_text(container.get_text(" ", strip=True), query):
            continue
        for anchor in container.find_all("a", href=True):
            href = str(anchor.get("href") or "")
            link = _extract_candidate_url(href, fetched_url, source.url_template)
            if not link:
                continue
            if _append_result(results, seen, source, link, href, anchor, container=container):
                break
    return results


def parse_search_html(
    html_text: str,
    source: SourceConfig,
    fetched_url: str,
    query: Optional[str] = None,
) -> List[Dict[str, object]]:
    soup = BeautifulSoup(html_text or "", "html.parser")
    if source.parser == "ahmia":
        scoped_results = _parse_container_results(
            soup,
            source,
            fetched_url,
            "li.result, div.result, article.result, .search-result, .results li",
        )
        if scoped_results:
            return scoped_results
    if source.parser == "torch":
        scoped_results = _parse_container_results(soup, source, fetched_url, ".result")
        if scoped_results:
            return scoped_results
    if source.parser == "vormweb":
        scoped_results = _parse_container_results(soup, source, fetched_url, ".query-box")
        if scoped_results:
            return scoped_results
    if source.parser == "lantern":
        return _parse_container_results(
            soup,
            source,
            fetched_url,
            "ol.search-list li.search-item article.search-card",
        )
    if source.parser == "onionfind":
        return _parse_container_results(soup, source, fetched_url, ".results-list .result-item")
    if source.parser == "torsearch":
        return _parse_container_results(
            soup,
            source,
            fetched_url,
            ".result",
            query=query,
            require_query_match=True,
        )

    results: List[Dict[str, object]] = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "")
        link = _extract_candidate_url(href, fetched_url, source.url_template)
        if not link:
            continue

        clean_link = _canonical_link(link)
        if clean_link in seen:
            continue
        _append_result(results, seen, source, link, href, anchor)
    return results


def _request_ahmia_search(session: requests.Session, source: SourceConfig, query: str, headers: Dict[str, str]) -> requests.Response:
    parsed = urlparse(source.url_template)
    root_url = f"{parsed.scheme}://{parsed.netloc}/"
    landing = session.get(root_url, headers=headers, timeout=source.timeout)
    if landing.status_code != 200:
        return landing

    soup = BeautifulSoup(landing.text or "", "html.parser")
    form = None
    for candidate in soup.find_all("form"):
        if candidate.find(["input", "textarea"], attrs={"name": "q"}):
            form = candidate
            break
    if form is None:
        raise SourceRegistryError(f"Ahmia source '{source.name}' did not expose a query form")

    params = {}
    for input_node in form.find_all(["input", "textarea"]):
        name = input_node.get("name")
        if not name:
            continue
        params[name] = input_node.get("value") or ""
    params["q"] = str(query or "")

    action = urljoin(landing.url or root_url, form.get("action") or source.url_template)
    return session.get(action, params=params, headers=headers, timeout=source.timeout)


def fetch_source_results(source: SourceConfig, query: str) -> Dict[str, object]:
    encoded_query = quote_plus(str(query or "").replace("+", " "))
    url = source.url_template.format(query=encoded_query)
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    session = get_tor_session()
    started = time.time()

    try:
        if source.parser == "ahmia":
            response = _request_ahmia_search(session, source, query, headers)
        else:
            response = session.get(url, headers=headers, timeout=source.timeout)
        latency_ms = round((time.time() - started) * 1000)
    except requests.exceptions.Timeout as exc:
        return {**_source_status(source, "timeout", error=str(exc)[:200]), "results": []}
    except requests.exceptions.ConnectionError as exc:
        message = str(exc)
        status = "tor_error" if "SOCKS" in message or ".onion" in message else "request_error"
        return {**_source_status(source, status, error=message[:200]), "results": []}
    except requests.exceptions.RequestException as exc:
        return {**_source_status(source, "request_error", error=str(exc)[:200]), "results": []}
    except SourceRegistryError as exc:
        return {**_source_status(source, "parse_failure", error=str(exc)[:200]), "results": []}

    if response.status_code != 200:
        return {
            **_source_status(source, "http_error", latency_ms=latency_ms, error=f"HTTP {response.status_code}"),
            "results": [],
        }

    try:
        results = parse_search_html(response.text, source, response.url or url, query=query)
    except Exception as exc:
        _logger.debug("Failed to parse source=%s: %s", source.name, exc)
        return {
            **_source_status(source, "parse_failure", latency_ms=latency_ms, error=str(exc)[:200]),
            "results": [],
        }

    raw_result_count = len(results)
    results = _limit_source_results(results)
    status = "success" if results else "zero_results"
    status_payload = _source_status(source, status, latency_ms=latency_ms, result_count=len(results))
    if raw_result_count > len(results):
        status_payload["truncated_result_count"] = raw_result_count - len(results)
    return {
        **status_payload,
        "results": results,
    }


def _dedupe_results(results: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    seen = set()
    unique = []
    for result in results:
        link = str(result.get("link") or "")
        if not link:
            continue
        clean_link = _canonical_link(link)
        if clean_link in seen:
            continue
        seen.add(clean_link)
        unique.append(result)
    return unique


def _limit_source_results(results: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return list(results or [])[:MAX_RESULTS_PER_SOURCE_QUERY]


def _has_usable_source_signal(statuses: Iterable[Dict[str, object]]) -> bool:
    return any(status.get("status") in ("success", "zero_results", "up") for status in statuses or [])


def set_unhealthy_sources(statuses: Iterable[Dict[str, object]]) -> None:
    for status in statuses:
        name = str(status.get("name") or "")
        state = status.get("status")
        if name and state not in ("up", "success", "zero_results"):
            _UNHEALTHY_SOURCE_NAMES.add(name)


def clear_unhealthy_sources() -> None:
    _UNHEALTHY_SOURCE_NAMES.clear()


def get_last_search_status() -> List[Dict[str, object]]:
    return list(_LAST_SEARCH_STATUS)


def search_sources(query: str, max_workers: int = 5, skip_unhealthy: bool = True) -> Dict[str, object]:
    global _LAST_SEARCH_STATUS

    max_workers = max(1, min(int(max_workers or 1), 16))
    all_sources = load_source_configs()
    runnable_sources: List[SourceConfig] = []
    statuses: List[Dict[str, object]] = []

    for source in all_sources:
        if not source.enabled:
            statuses.append(_source_status(source, "disabled"))
            continue
        if skip_unhealthy and source.name in _UNHEALTHY_SOURCE_NAMES:
            statuses.append(_source_status(source, "skipped_unhealthy"))
            continue
        runnable_sources.append(source)

    collected: List[Dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {executor.submit(fetch_source_results, source, query): source for source in runnable_sources}
        for future in as_completed(future_to_source):
            source_result = future.result()
            statuses.append({key: value for key, value in source_result.items() if key != "results"})
            collected.extend(source_result.get("results", []))

    order = {source.name: idx for idx, source in enumerate(all_sources)}
    statuses.sort(key=lambda item: order.get(str(item.get("name")), 999))
    if _has_usable_source_signal(statuses):
        set_unhealthy_sources(statuses)
    results = _dedupe_results(collected)
    _LAST_SEARCH_STATUS = statuses
    return {"results": results, "sources": statuses}


def get_search_results(query: str, max_workers: int = 5) -> List[Dict[str, object]]:
    return list(search_sources(query, max_workers=max_workers).get("results", []))

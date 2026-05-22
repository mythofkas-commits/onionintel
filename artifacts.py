import re
from typing import Dict, Iterable, List, Optional

MAX_EVIDENCE_CHARS = 180

PATTERNS = {
    "onion_urls": re.compile(r"\bhttps?://[a-z0-9.-]+\.onion[^\s\"'<>)]*", re.IGNORECASE),
    "clearnet_urls": re.compile(r"\bhttps?://(?![a-z0-9.-]+\.onion\b)[^\s\"'<>)]*", re.IGNORECASE),
    "emails": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "cves": re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    "hashes": re.compile(r"\b(?:[a-fA-F0-9]{32}|[a-fA-F0-9]{40}|[a-fA-F0-9]{64})\b"),
    "crypto_addresses": re.compile(
        r"\b(?:bc1[ac-hj-np-z02-9]{11,71}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|0x[a-fA-F0-9]{40})\b"
    ),
    "handles": re.compile(r"(?<![\w@])@[A-Za-z0-9_]{3,32}\b"),
}

DOMAIN_RE = re.compile(
    r"\b(?!(?:\d{1,3}\.){3}\d{1,3}\b)(?:[a-zA-Z0-9-]{1,63}\.)+(?:com|net|org|io|co|info|biz|ru|cn|uk|de|fr|nl|site|xyz|online|dev|app|gov|edu)\b",
    re.IGNORECASE,
)
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _clean_value(value: str) -> str:
    return str(value or "").strip().strip("\"'<>.,);]")


def _evidence(text: str, start: int, end: int) -> str:
    left = max(0, start - 70)
    right = min(len(text), end + 70)
    snippet = " ".join(text[left:right].split())
    if len(snippet) > MAX_EVIDENCE_CHARS:
        return snippet[: MAX_EVIDENCE_CHARS - 3] + "..."
    return snippet


def _valid_ipv4(value: str) -> bool:
    try:
        parts = [int(part) for part in value.split(".")]
    except ValueError:
        return False
    return len(parts) == 4 and all(0 <= part <= 255 for part in parts)


def _add_artifact(bucket: List[Dict[str, str]], seen: set, value: str, source_url: str, evidence: str) -> None:
    clean = _clean_value(value)
    key = clean.lower()
    if not clean or key in seen:
        return
    seen.add(key)
    bucket.append({"value": clean, "source_url": source_url, "evidence": evidence})


def _scan_text(text: str, source_url: str, artifacts: Dict[str, List[Dict[str, str]]], seen: Dict[str, set]) -> None:
    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            _add_artifact(artifacts[category], seen[category], match.group(0), source_url, _evidence(text, match.start(), match.end()))

    for match in DOMAIN_RE.finditer(text):
        value = _clean_value(match.group(0))
        if value.lower().endswith(".onion"):
            continue
        _add_artifact(artifacts["domains"], seen["domains"], value, source_url, _evidence(text, match.start(), match.end()))

    for match in IPV4_RE.finditer(text):
        value = match.group(0)
        if _valid_ipv4(value):
            _add_artifact(artifacts["ipv4_addresses"], seen["ipv4_addresses"], value, source_url, _evidence(text, match.start(), match.end()))


def extract_artifacts(search_results: Optional[Iterable[Dict[str, object]]] = None, scraped_content: Optional[Dict[str, str]] = None) -> Dict[str, List[Dict[str, str]]]:
    categories = [
        "onion_urls",
        "clearnet_urls",
        "emails",
        "domains",
        "ipv4_addresses",
        "cves",
        "hashes",
        "crypto_addresses",
        "handles",
    ]
    artifacts: Dict[str, List[Dict[str, str]]] = {category: [] for category in categories}
    seen = {category: set() for category in categories}

    for result in search_results or []:
        link = str(result.get("link") or "")
        source_url = link or str(result.get("source") or "")
        text = " ".join(
            str(result.get(key) or "")
            for key in ("title", "link", "raw_url", "snippet", "source")
        )
        _scan_text(text, source_url, artifacts, seen)

    for source_url, text in (scraped_content or {}).items():
        _scan_text(str(text or ""), str(source_url or ""), artifacts, seen)

    return artifacts


def flatten_artifacts(artifacts: Dict[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for category, items in (artifacts or {}).items():
        for item in items:
            rows.append(
                {
                    "type": category,
                    "value": item.get("value", ""),
                    "source_url": item.get("source_url", ""),
                    "evidence": item.get("evidence", ""),
                }
            )
    return rows

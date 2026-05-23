from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse, urlunparse


def canonicalize_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return str(value or "").strip()
    netloc = parsed.netloc.lower()
    scheme = parsed.scheme.lower()
    return urlunparse((scheme, netloc, parsed.path or "", "", parsed.query or "", ""))


def canonicalize_onion_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if parsed.scheme and parsed.netloc:
        return canonicalize_url(value)
    return str(value or "").strip().lower()


def canonicalize_domain(value: str) -> str:
    return str(value or "").strip().strip(".").lower()


def canonicalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def canonicalize_ipv4(value: str) -> str:
    try:
        return str(ip_address(str(value or "").strip()))
    except ValueError:
        return str(value or "").strip()


def canonicalize_cve(value: str) -> str:
    return str(value or "").strip().upper()


def canonicalize_hash(value: str) -> str:
    return str(value or "").strip().lower()


def canonicalize_crypto_address(value: str) -> str:
    cleaned = str(value or "").strip()
    if cleaned.startswith("0x"):
        return cleaned.lower()
    return cleaned


def canonicalize_handle(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    if not cleaned:
        return ""
    return cleaned if cleaned.startswith("@") else f"@{cleaned}"


def canonicalize_artifact(artifact_type: str, value: str) -> str:
    if artifact_type == "onion_urls":
        return canonicalize_onion_url(value)
    if artifact_type == "clearnet_urls":
        return canonicalize_url(value)
    if artifact_type == "domains":
        return canonicalize_domain(value)
    if artifact_type == "emails":
        return canonicalize_email(value)
    if artifact_type == "ipv4_addresses":
        return canonicalize_ipv4(value)
    if artifact_type == "cves":
        return canonicalize_cve(value)
    if artifact_type == "hashes":
        return canonicalize_hash(value)
    if artifact_type == "crypto_addresses":
        return canonicalize_crypto_address(value)
    if artifact_type == "handles":
        return canonicalize_handle(value)
    return str(value or "").strip()

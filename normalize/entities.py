from __future__ import annotations

from urllib.parse import urlparse

from domain.models import Artifact, Entity, stable_id
from normalize.canonicalize import canonicalize_artifact, canonicalize_domain


def _entity_type_for_artifact(artifact_type: str, value: str) -> str:
    if artifact_type == "onion_urls":
        return "onion_url"
    if artifact_type == "clearnet_urls":
        return "url"
    if artifact_type == "emails":
        return "email"
    if artifact_type == "domains":
        return "domain"
    if artifact_type == "ipv4_addresses":
        return "ipv4"
    if artifact_type == "cves":
        return "cve"
    if artifact_type == "hashes":
        return "hash"
    if artifact_type == "crypto_addresses":
        return "crypto_address"
    if artifact_type == "handles":
        return "handle"
    return artifact_type.rstrip("s") or "artifact"


def _hash_metadata(value: str) -> dict[str, str]:
    length = len(value)
    if length == 32:
        return {"hash_kind": "md5_like"}
    if length == 40:
        return {"hash_kind": "sha1_like"}
    if length == 64:
        return {"hash_kind": "sha256_like"}
    return {"hash_kind": "unknown"}


def _crypto_metadata(value: str) -> dict[str, str]:
    if value.lower().startswith("0x") and len(value) == 42:
        return {"chain_guess": "ethereum"}
    if value.startswith(("bc1", "1", "3")):
        return {"chain_guess": "bitcoin"}
    return {"chain_guess": "unknown"}


def _extra_entities_for_artifact(artifact: Artifact) -> list[Entity]:
    extras: list[Entity] = []
    if artifact.artifact_type == "emails" and "@" in artifact.normalized_value:
        domain = canonicalize_domain(artifact.normalized_value.rsplit("@", 1)[1])
        extras.append(
            Entity(
                entity_id=stable_id("ent", "domain", domain),
                entity_type="domain",
                canonical_value=domain,
                raw_values=[domain],
                artifact_ids=[artifact.artifact_id],
                metadata={
                    "first_seen_doc_ids": [artifact.doc_id] if artifact.doc_id else [],
                    "source_urls": [artifact.source_url] if artifact.source_url else [],
                    "artifact_count": 1,
                    "entity_key": f"domain:{domain}",
                    "normalizer_version": "normalizer_v1",
                    "derived_from": "email_domain",
                },
            )
        )
    if artifact.artifact_type in {"clearnet_urls", "onion_urls"}:
        host = (urlparse(artifact.normalized_value).hostname or "").lower()
        if host:
            entity_type = "onion_service" if host.endswith(".onion") else "domain"
            extras.append(
                Entity(
                    entity_id=stable_id("ent", entity_type, host),
                    entity_type=entity_type,
                    canonical_value=host,
                    raw_values=[host],
                    artifact_ids=[artifact.artifact_id],
                    metadata={
                        "first_seen_doc_ids": [artifact.doc_id] if artifact.doc_id else [],
                        "source_urls": [artifact.source_url] if artifact.source_url else [],
                        "artifact_count": 1,
                        "entity_key": f"{entity_type}:{host}",
                        "normalizer_version": "normalizer_v1",
                        "derived_from": "url_host",
                    },
                )
            )
    return extras


def _merge_entity(by_key: dict[tuple[str, str], Entity], entity: Entity) -> None:
    key = (entity.entity_type, entity.canonical_value)
    if key not in by_key:
        by_key[key] = entity
        return
    current = by_key[key]
    for value in entity.raw_values:
        if value not in current.raw_values:
            current.raw_values.append(value)
    for artifact_id in entity.artifact_ids:
        if artifact_id not in current.artifact_ids:
            current.artifact_ids.append(artifact_id)
    current.metadata["artifact_count"] = len(current.artifact_ids)
    for field in ("first_seen_doc_ids", "source_urls"):
        merged = list(current.metadata.get(field, []))
        for value in entity.metadata.get(field, []):
            if value and value not in merged:
                merged.append(value)
        current.metadata[field] = merged


def artifacts_to_entities_v2(artifacts: list[Artifact]) -> list[Entity]:
    by_key: dict[tuple[str, str], Entity] = {}
    for artifact in artifacts or []:
        canonical = canonicalize_artifact(artifact.artifact_type, artifact.normalized_value or artifact.value)
        entity_type = _entity_type_for_artifact(artifact.artifact_type, canonical)
        metadata = {
            "first_seen_doc_ids": [artifact.doc_id] if artifact.doc_id else [],
            "source_urls": [artifact.source_url] if artifact.source_url else [],
            "artifact_count": 1,
            "entity_key": f"{entity_type}:{canonical}",
            "normalizer_version": "normalizer_v1",
        }
        if artifact.artifact_type == "hashes":
            metadata.update(_hash_metadata(canonical))
        if artifact.artifact_type == "crypto_addresses":
            metadata.update(_crypto_metadata(canonical))
        entity = Entity(
            entity_id=stable_id("ent", entity_type, canonical),
            entity_type=entity_type,
            canonical_value=canonical,
            raw_values=[artifact.value],
            artifact_ids=[artifact.artifact_id],
            metadata=metadata,
        )
        _merge_entity(by_key, entity)
        for extra in _extra_entities_for_artifact(Artifact(**{**artifact.model_dump(), "normalized_value": canonical})):
            _merge_entity(by_key, extra)
    return list(by_key.values())

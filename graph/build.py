from __future__ import annotations

from itertools import combinations
from urllib.parse import urlparse

import networkx as nx

from domain.models import Artifact, Entity, Relationship, stable_id


def _entity_type_for_artifact(artifact_type: str) -> str:
    mapping = {
        "onion_urls": "onion_url",
        "clearnet_urls": "url",
        "emails": "email",
        "domains": "domain",
        "ipv4_addresses": "ipv4",
        "cves": "cve",
        "hashes": "hash",
        "crypto_addresses": "crypto_address",
        "handles": "handle",
    }
    return mapping.get(artifact_type, artifact_type.rstrip("s") or "artifact")


def artifacts_to_entities(artifacts: list[Artifact]) -> list[Entity]:
    by_key: dict[tuple[str, str], Entity] = {}
    for artifact in artifacts:
        entity_type = _entity_type_for_artifact(artifact.artifact_type)
        key = (entity_type, artifact.normalized_value)
        if key not in by_key:
            by_key[key] = Entity(
                entity_id=stable_id("ent", entity_type, artifact.normalized_value),
                entity_type=entity_type,
                canonical_value=artifact.normalized_value,
                raw_values=[],
                artifact_ids=[],
            )
        entity = by_key[key]
        if artifact.value not in entity.raw_values:
            entity.raw_values.append(artifact.value)
        if artifact.artifact_id not in entity.artifact_ids:
            entity.artifact_ids.append(artifact.artifact_id)
    return list(by_key.values())


def build_relationships(artifacts: list[Artifact], entities: list[Entity]) -> list[Relationship]:
    artifact_to_entity = {}
    for entity in entities:
        for artifact_id in entity.artifact_ids:
            artifact_to_entity[artifact_id] = entity

    relationships: dict[str, Relationship] = {}
    doc_entities: dict[str, set[str]] = {}

    for artifact in artifacts:
        entity = artifact_to_entity.get(artifact.artifact_id)
        if not entity:
            continue
        if artifact.doc_id:
            doc_id = artifact.doc_id
        else:
            doc_id = stable_id("doc", artifact.source_url)
        rel_id = stable_id("rel", doc_id, "MENTIONS", entity.entity_id)
        relationships[rel_id] = Relationship(
            relationship_id=rel_id,
            source_id=doc_id,
            target_id=entity.entity_id,
            relationship_type="MENTIONS",
            evidence_doc_ids=[doc_id],
        )
        doc_entities.setdefault(doc_id, set()).add(entity.entity_id)

        if entity.entity_type in {"url", "onion_url", "email"}:
            if entity.entity_type == "email" and "@" in entity.canonical_value:
                domain = entity.canonical_value.rsplit("@", 1)[1]
                domain_id = stable_id("ent", "domain", domain)
                rel_type = "BELONGS_TO_DOMAIN"
            else:
                domain = (urlparse(entity.canonical_value).hostname or "").lower()
                if not domain:
                    continue
                rel_type = "BELONGS_TO_ONION_SERVICE" if domain.endswith(".onion") else "BELONGS_TO_DOMAIN"
                domain_id = stable_id("ent", "onion_service" if domain.endswith(".onion") else "domain", domain)
            rel_id = stable_id("rel", entity.entity_id, rel_type, domain_id)
            relationships[rel_id] = Relationship(
                relationship_id=rel_id,
                source_id=entity.entity_id,
                target_id=domain_id,
                relationship_type=rel_type,
                evidence_doc_ids=[doc_id],
            )

    for doc_id, entity_ids in doc_entities.items():
        for left, right in combinations(sorted(entity_ids), 2):
            rel_id = stable_id("rel", left, "SEEN_WITH", right, doc_id)
            relationships[rel_id] = Relationship(
                relationship_id=rel_id,
                source_id=left,
                target_id=right,
                relationship_type="SEEN_WITH",
                evidence_doc_ids=[doc_id],
            )

    return list(relationships.values())


def build_relationship_graph(entities: list[Entity], relationships: list[Relationship]) -> nx.Graph:
    graph = nx.Graph()
    for entity in entities:
        graph.add_node(entity.entity_id, type=entity.entity_type, value=entity.canonical_value)
    for relationship in relationships:
        graph.add_edge(
            relationship.source_id,
            relationship.target_id,
            type=relationship.relationship_type,
            evidence_doc_ids=relationship.evidence_doc_ids,
        )
    return graph

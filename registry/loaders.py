from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import SourceSpec

SOURCE_CATALOG_DIR = Path(__file__).with_name("sources")
LEGACY_SOURCE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "sources.yml"
CATALOG_FILE_ORDER = ("search_engines.yml", "public_feeds.yml", "site_monitors.yml")


def _load_raw_sources(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not data:
        raise ValueError("Source registry is empty")
    if isinstance(data, dict):
        entries = data.get("sources", [])
    else:
        entries = data
    if not isinstance(entries, list):
        raise ValueError("Source registry must be a list or contain a sources list")
    return entries


def _load_source_specs_file(path: Path) -> list[SourceSpec]:
    specs = []
    for entry in _load_raw_sources(path):
        if not isinstance(entry, dict):
            raise ValueError("Each source must be a mapping")
        spec = SourceSpec(**entry)
        spec.metadata.setdefault("registry_file", path.name)
        specs.append(spec)
    return specs


def _catalog_files(path: Path) -> list[Path]:
    ordered = [path / name for name in CATALOG_FILE_ORDER if (path / name).exists()]
    extras = sorted(
        file
        for file in path.glob("*.yml")
        if file.name not in CATALOG_FILE_ORDER
    )
    return ordered + extras


def load_source_catalog(path: Path = SOURCE_CATALOG_DIR) -> list[SourceSpec]:
    if not path.exists():
        if LEGACY_SOURCE_REGISTRY_PATH.exists():
            return _load_source_specs_file(LEGACY_SOURCE_REGISTRY_PATH)
        raise ValueError(f"Source catalog does not exist: {path}")
    if path.is_file():
        return _load_source_specs_file(path)

    specs: list[SourceSpec] = []
    seen_ids: set[str] = set()
    files = _catalog_files(path)
    if not files and LEGACY_SOURCE_REGISTRY_PATH.exists():
        files = [LEGACY_SOURCE_REGISTRY_PATH]

    for file in files:
        for spec in _load_source_specs_file(file):
            if spec.id in seen_ids:
                raise ValueError(f"Duplicate source id in catalog: {spec.id}")
            seen_ids.add(spec.id)
            specs.append(spec)
    if not specs:
        raise ValueError("Source catalog contains no sources")
    return specs


def load_source_specs(path: Path | None = None) -> list[SourceSpec]:
    return load_source_catalog(path or SOURCE_CATALOG_DIR)


def source_config_to_spec(config) -> SourceSpec:
    return SourceSpec(
        id=getattr(config, "name", "unknown"),
        name=getattr(config, "name", "unknown"),
        url_template=getattr(config, "url_template", ""),
        enabled=getattr(config, "enabled", True),
        parser=getattr(config, "parser", "generic"),
        timeout=getattr(config, "timeout", 40),
        notes=getattr(config, "notes", ""),
    )


def source_spec_to_config(spec: SourceSpec):
    from sources import SourceConfig

    return SourceConfig(
        name=spec.name,
        url_template=spec.url_template,
        enabled=spec.enabled,
        parser=spec.parser,
        timeout=spec.timeout,
        notes=spec.notes,
    )

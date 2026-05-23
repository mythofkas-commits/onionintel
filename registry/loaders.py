from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .schema import SourceSpec


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


def load_source_specs(path: Path) -> list[SourceSpec]:
    specs = []
    for entry in _load_raw_sources(path):
        if not isinstance(entry, dict):
            raise ValueError("Each source must be a mapping")
        specs.append(SourceSpec(**entry))
    return specs


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

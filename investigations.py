import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

INVESTIGATIONS_DIR = Path("investigations")


def save_investigation(
    query: str,
    refined_query: str,
    model: str,
    preset_label: str,
    sources: list,
    summary: str,
    search_status: Optional[list] = None,
    artifacts: Optional[dict] = None,
    scraped_urls: Optional[list] = None,
    source_provenance: Optional[list] = None,
    query_plan: Optional[dict] = None,
    query_runs: Optional[list] = None,
    query_expansion_mode: Optional[str] = None,
    intent_metadata: Optional[dict] = None,
    model_routing: Optional[dict] = None,
    directory: Path = INVESTIGATIONS_DIR,
) -> str:
    """Save a completed investigation to disk. Returns the filename."""
    directory.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"investigation_{timestamp}.json"
    data = {
        "timestamp": datetime.now().isoformat(),
        "query": query,
        "refined_query": refined_query,
        "model": model,
        "preset": preset_label,
        "sources": sources,
        "source_provenance": source_provenance or sources,
        "search_status": search_status or [],
        "artifacts": artifacts or {},
        "scraped_urls": scraped_urls or [],
        "query_plan": query_plan or {},
        "query_runs": query_runs or [],
        "query_expansion_mode": query_expansion_mode or "off",
        "intent_metadata": intent_metadata or {},
        "model_routing": model_routing or {},
        "summary": summary,
    }
    (directory / fname).write_text(json.dumps(data, indent=2), encoding="utf-8")
    return fname


def load_investigations(directory: Path = INVESTIGATIONS_DIR) -> List[Dict[str, object]]:
    """Return list of saved investigations sorted newest-first."""
    if not directory.exists():
        return []
    files = sorted(directory.glob("investigation_*.json"), reverse=True)
    investigations = []
    for file_path in files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            data.setdefault("sources", [])
            data.setdefault("source_provenance", data.get("sources", []))
            data.setdefault("search_status", [])
            data.setdefault("artifacts", {})
            data.setdefault("scraped_urls", [])
            data.setdefault("query_plan", {})
            data.setdefault("query_runs", [])
            data.setdefault("query_expansion_mode", "off")
            data.setdefault("intent_metadata", {})
            data.setdefault("model_routing", {})
            data["_filename"] = file_path.name
            investigations.append(data)
        except Exception:
            continue
    return investigations

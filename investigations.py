import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from domain.models import SCHEMA_VERSION

INVESTIGATIONS_DIR = Path("investigations")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_run_id() -> str:
    return f"run_{uuid.uuid4().hex}"


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
    run_id: Optional[str] = None,
    schema_version: str = SCHEMA_VERSION,
    stage_status: Optional[list] = None,
    scrape_status: Optional[list] = None,
    documents: Optional[list] = None,
    fetch_records: Optional[list] = None,
    typed_artifacts: Optional[list] = None,
    entities: Optional[list] = None,
    relationships: Optional[list] = None,
    relevance_scores: Optional[list] = None,
    ranked_documents: Optional[list] = None,
    pivot_suggestions: Optional[list] = None,
    claims: Optional[list] = None,
    synthesis_report: Optional[dict] = None,
    directory: Path = INVESTIGATIONS_DIR,
) -> str:
    """Save a completed investigation to disk. Returns the filename."""
    directory.mkdir(exist_ok=True)
    run_id = run_id or _new_run_id()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    fname = f"investigation_{timestamp}_{run_id[-8:]}.json"
    data = {
        "schema_version": schema_version,
        "run_id": run_id,
        "timestamp": _now_iso(),
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
        "stage_status": stage_status or [],
        "scrape_status": scrape_status or [],
        "documents": documents or [],
        "fetch_records": fetch_records or [],
        "typed_artifacts": typed_artifacts or [],
        "entities": entities or [],
        "relationships": relationships or [],
        "relevance_scores": relevance_scores or [],
        "ranked_documents": ranked_documents or [],
        "pivot_suggestions": pivot_suggestions or [],
        "claims": claims or [],
        "synthesis_report": synthesis_report or {},
        "document_hashes": [
            {
                "doc_id": item.get("doc_id"),
                "url": item.get("url"),
                "final_url": item.get("final_url"),
                "text_hash": item.get("text_hash"),
                "content_hash": item.get("content_hash"),
            }
            for item in documents or []
        ],
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
            data.setdefault("schema_version", "1.0")
            data.setdefault("run_id", "")
            data.setdefault("stage_status", [])
            data.setdefault("scrape_status", [])
            data.setdefault("documents", [])
            data.setdefault("fetch_records", [])
            data.setdefault("typed_artifacts", [])
            data.setdefault("entities", [])
            data.setdefault("relationships", [])
            data.setdefault("relevance_scores", [])
            data.setdefault("ranked_documents", [])
            data.setdefault("pivot_suggestions", [])
            data.setdefault("claims", [])
            data.setdefault("synthesis_report", {})
            data.setdefault("document_hashes", [])
            data["_filename"] = file_path.name
            investigations.append(data)
        except Exception:
            continue
    return investigations

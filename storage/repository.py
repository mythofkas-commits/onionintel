from __future__ import annotations

import json
from collections import Counter
from contextlib import closing
from pathlib import Path
from typing import Any

from domain.models import RunState
from storage.database import connect, initialize_schema


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _load(value: str | None, default: Any = None) -> Any:
    if not value:
        return default
    return json.loads(value)


def _jsonable_state(state: RunState | dict[str, Any]) -> dict[str, Any]:
    if isinstance(state, RunState):
        return state.model_dump(mode="json")
    return dict(state)


def initialize_storage(db_path: str | Path | None = None) -> None:
    with closing(connect(db_path)) as conn:
        initialize_schema(conn)


def save_run_state(state: RunState | dict[str, Any], db_path: str | Path | None = None) -> None:
    payload = _jsonable_state(state)
    save_investigation_payload(payload, db_path=db_path)


def save_investigation_payload(payload: dict[str, Any], db_path: str | Path | None = None) -> None:
    payload = dict(payload)
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        raise ValueError("investigation payload must include run_id")

    stage_status = payload.get("stage_status") or []
    status = "completed" if payload.get("completed_at") or any(item.get("stage") == "pipeline" and item.get("status") == "success" for item in stage_status) else "running"
    summary = str(payload.get("summary") or (payload.get("synthesis_report") or {}).get("summary") or "")

    with closing(connect(db_path)) as conn:
        initialize_schema(conn)
        conn.execute(
            """
            INSERT INTO runs (
                run_id, schema_version, query, refined_query, model, preset, preset_label,
                summary, status, created_at, completed_at, timestamp, investigation_file,
                payload_json, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(run_id) DO UPDATE SET
                schema_version=excluded.schema_version,
                query=excluded.query,
                refined_query=excluded.refined_query,
                model=excluded.model,
                preset=excluded.preset,
                preset_label=excluded.preset_label,
                summary=excluded.summary,
                status=excluded.status,
                created_at=excluded.created_at,
                completed_at=excluded.completed_at,
                timestamp=excluded.timestamp,
                investigation_file=excluded.investigation_file,
                payload_json=excluded.payload_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                run_id,
                str(payload.get("schema_version") or "2.0"),
                str(payload.get("query") or ""),
                str(payload.get("refined_query") or ""),
                str(payload.get("model") or ""),
                str(payload.get("preset") or ""),
                str(payload.get("preset_label") or payload.get("preset") or ""),
                summary,
                status,
                str(payload.get("created_at") or payload.get("timestamp") or ""),
                payload.get("completed_at"),
                str(payload.get("timestamp") or payload.get("created_at") or ""),
                str(payload.get("investigation_file") or payload.get("_filename") or ""),
                _dump(payload),
            ),
        )
        _replace_stage_events(conn, run_id, stage_status)
        _replace_sources(conn, run_id, payload.get("source_records") or payload.get("search_status") or [])
        _replace_search_hits(conn, run_id, payload.get("search_hits") or [])
        _replace_fetch_records(conn, run_id, payload.get("fetch_records") or [])
        _replace_documents(conn, run_id, payload.get("documents") or [])
        _replace_artifacts(conn, run_id, payload.get("typed_artifacts") or [])
        _replace_entities(conn, run_id, payload.get("entities") or [])
        _replace_relationships(conn, run_id, payload.get("relationships") or [])
        _replace_relevance_scores(conn, run_id, payload.get("relevance_scores") or [])
        _replace_pivots(conn, run_id, payload.get("pivot_suggestions") or [])
        _replace_claims(conn, run_id, payload.get("claims") or [])
        report = payload.get("synthesis_report") or {}
        if report:
            _replace_report(conn, run_id, report)
        conn.commit()


def get_run_payload(run_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with closing(connect(db_path)) as conn:
        initialize_schema(conn)
        row = conn.execute("SELECT payload_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    payload = _load(row["payload_json"], {})
    payload.setdefault("_filename", payload.get("investigation_file", ""))
    return payload


def list_investigations(db_path: str | Path | None = None, limit: int = 100) -> list[dict[str, Any]]:
    with closing(connect(db_path)) as conn:
        initialize_schema(conn)
        rows = conn.execute(
            """
            SELECT run_id, schema_version, query, refined_query, model, preset_label,
                   summary, status, timestamp, investigation_file, payload_json
            FROM runs
            ORDER BY timestamp DESC, updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    items = []
    for row in rows:
        payload = _load(row["payload_json"], {}) or {}
        payload.setdefault("schema_version", row["schema_version"])
        payload.setdefault("run_id", row["run_id"])
        payload.setdefault("query", row["query"])
        payload.setdefault("refined_query", row["refined_query"])
        payload.setdefault("model", row["model"])
        payload.setdefault("preset", row["preset_label"])
        payload.setdefault("summary", row["summary"])
        payload.setdefault("timestamp", row["timestamp"])
        payload["_filename"] = row["investigation_file"]
        payload["_storage_status"] = row["status"]
        items.append(payload)
    return items


def export_investigation_json(run_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    return get_run_payload(run_id, db_path=db_path)


def export_investigation_markdown(run_id: str, db_path: str | Path | None = None) -> str | None:
    payload = get_run_payload(run_id, db_path=db_path)
    if payload is None:
        return None
    lines = [
        f"# OnionIntel Investigation: {payload.get('query', '')}",
        "",
        f"- Run ID: `{payload.get('run_id', run_id)}`",
        f"- Timestamp: `{payload.get('timestamp', '')}`",
        f"- Model: `{payload.get('model', '')}`",
        f"- Refined query: `{payload.get('refined_query', '')}`",
        "",
        "## Summary",
        "",
        str(payload.get("summary") or (payload.get("synthesis_report") or {}).get("summary") or ""),
        "",
        "## Evidence Objects",
        "",
        f"- Documents: {len(payload.get('documents') or [])}",
        f"- Entities: {len(payload.get('entities') or [])}",
        f"- Claims: {len(payload.get('claims') or [])}",
        f"- Relationships: {len(payload.get('relationships') or [])}",
    ]
    return "\n".join(lines).strip() + "\n"


def list_source_health(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    with closing(connect(db_path)) as conn:
        initialize_schema(conn)
        rows = conn.execute(
            """
            SELECT source_id, name, connector_id, status, result_count, latency_ms, error, checked_at
            FROM source_health_history
            ORDER BY checked_at DESC
            """
        ).fetchall()
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        item = dict(row)
        grouped.setdefault((item["source_id"], item["connector_id"]), []).append(item)
    summaries = []
    for (_source_id, _connector_id), attempts in grouped.items():
        counts = Counter(item["status"] for item in attempts)
        last = attempts[0]
        successes = counts.get("success", 0) + counts.get("up", 0) + counts.get("zero_results", 0)
        summaries.append(
            {
                "source_id": last["source_id"],
                "name": last["name"],
                "connector_id": last["connector_id"],
                "last_status": last["status"],
                "last_checked_at": last["checked_at"],
                "last_error": last["error"],
                "attempts": len(attempts),
                "successes": successes,
                "failures": len(attempts) - successes,
                "status_counts": dict(counts),
            }
        )
    return summaries


def _replace_stage_events(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM stage_events WHERE run_id = ?", (run_id,))
    for idx, item in enumerate(items):
        metadata = {k: v for k, v in item.items() if k not in {"stage", "status", "timestamp"}}
        conn.execute(
            "INSERT INTO stage_events(run_id, event_index, stage, status, timestamp, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, idx, str(item.get("stage") or ""), str(item.get("status") or ""), str(item.get("timestamp") or ""), _dump(metadata)),
        )


def _replace_sources(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM source_records WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM source_health_history WHERE run_id = ?", (run_id,))
    for idx, item in enumerate(items):
        source_id = str(item.get("source_id") or item.get("name") or "unknown")
        values = (
            run_id,
            idx,
            source_id,
            str(item.get("name") or source_id),
            str(item.get("status") or "unknown"),
            str(item.get("connector_id") or ""),
            str(item.get("parser") or ""),
            1 if item.get("enabled", True) else 0,
            int(item.get("result_count") or 0),
            item.get("latency_ms"),
            item.get("error"),
            _dump(item),
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO source_records(
                run_id, record_index, source_id, name, status, connector_id, parser, enabled,
                result_count, latency_ms, error, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )
        conn.execute(
            """
            INSERT OR REPLACE INTO source_health_history(
                run_id, record_index, source_id, name, status, connector_id, result_count,
                latency_ms, error, checked_at, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), ?)
            """,
            (run_id, idx, source_id, str(item.get("name") or source_id), str(item.get("status") or "unknown"), str(item.get("connector_id") or ""), int(item.get("result_count") or 0), item.get("latency_ms"), item.get("error"), item.get("checked_at"), _dump(item)),
        )


def _replace_search_hits(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM search_hits WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO search_hits(run_id, hit_id, source_id, connector_id, query, title, url, raw_url, discovered_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(item.get("hit_id") or ""), str(item.get("source_id") or ""), str(item.get("connector_id") or ""), str(item.get("query") or ""), str(item.get("title") or ""), str(item.get("url") or ""), item.get("raw_url"), item.get("discovered_at"), _dump(item)),
        )


def _replace_fetch_records(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM fetch_records WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO fetch_records(run_id, fetch_id, url, final_url, status, status_code, content_type, error, fetched_at, bytes_read, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(item.get("fetch_id") or ""), str(item.get("url") or ""), str(item.get("final_url") or ""), str(item.get("status") or ""), item.get("status_code"), str(item.get("content_type") or ""), item.get("error"), item.get("fetched_at"), int(item.get("bytes_read") or 0), _dump(item)),
        )


def _replace_documents(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM documents WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO documents(run_id, doc_id, source_id, connector_id, url, final_url, title, content_type, status_code, text_hash, content_hash, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(item.get("doc_id") or ""), str(item.get("source_id") or ""), str(item.get("connector_id") or ""), str(item.get("url") or ""), str(item.get("final_url") or ""), str(item.get("title") or ""), str(item.get("content_type") or ""), item.get("status_code"), str(item.get("text_hash") or ""), str(item.get("content_hash") or ""), _dump(item)),
        )


def _replace_artifacts(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM artifacts WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO artifacts(run_id, artifact_id, artifact_type, value, normalized_value, doc_id, source_url, start_offset, end_offset, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(item.get("artifact_id") or ""), str(item.get("artifact_type") or ""), str(item.get("value") or ""), str(item.get("normalized_value") or ""), str(item.get("doc_id") or ""), str(item.get("source_url") or ""), item.get("start_offset"), item.get("end_offset"), _dump(item)),
        )


def _replace_entities(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM entities WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            "INSERT OR REPLACE INTO entities(run_id, entity_id, entity_type, canonical_value, payload_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, str(item.get("entity_id") or ""), str(item.get("entity_type") or ""), str(item.get("canonical_value") or ""), _dump(item)),
        )


def _replace_relationships(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM relationships WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO relationships(run_id, relationship_id, source_id, target_id, relationship_type, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(item.get("relationship_id") or ""), str(item.get("source_id") or ""), str(item.get("target_id") or ""), str(item.get("relationship_type") or ""), _dump(item)),
        )


def _replace_relevance_scores(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM relevance_scores WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            "INSERT OR REPLACE INTO relevance_scores(run_id, target_id, target_type, score, payload_json) VALUES (?, ?, ?, ?, ?)",
            (run_id, str(item.get("target_id") or ""), str(item.get("target_type") or ""), float(item.get("score") or 0), _dump(item)),
        )


def _replace_pivots(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM pivots WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            "INSERT OR REPLACE INTO pivots(run_id, pivot_id, query, pivot_type, value, score, payload_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, str(item.get("pivot_id") or ""), str(item.get("query") or ""), str(item.get("pivot_type") or ""), str(item.get("value") or ""), float(item.get("score") or 0), _dump(item)),
        )


def _replace_claims(conn, run_id: str, items: list[dict[str, Any]]) -> None:
    conn.execute("DELETE FROM claims WHERE run_id = ?", (run_id,))
    for item in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO claims(run_id, claim_id, claim_type, confidence, confidence_label, requires_review, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, str(item.get("claim_id") or ""), str(item.get("claim_type") or ""), float(item.get("confidence") or 0), str(item.get("confidence_label") or ""), 1 if item.get("requires_review", True) else 0, _dump(item)),
        )


def _replace_report(conn, run_id: str, item: dict[str, Any]) -> None:
    conn.execute("DELETE FROM reports WHERE run_id = ?", (run_id,))
    report_id = str(item.get("report_id") or f"report_{run_id}")
    conn.execute(
        "INSERT OR REPLACE INTO reports(run_id, report_id, summary, generated_at, payload_json) VALUES (?, ?, ?, ?, ?)",
        (run_id, report_id, str(item.get("summary") or ""), item.get("generated_at"), _dump(item)),
    )

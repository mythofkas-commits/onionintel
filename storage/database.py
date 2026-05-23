from __future__ import annotations

import sqlite3
from pathlib import Path

from config import ONIONINTEL_DB_PATH

SCHEMA_VERSION = 1


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    path = Path(db_path or ONIONINTEL_DB_PATH)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            schema_version TEXT NOT NULL,
            query TEXT NOT NULL,
            refined_query TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            preset TEXT NOT NULL DEFAULT '',
            preset_label TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'running',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            investigation_file TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS source_records (
            run_id TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            connector_id TEXT NOT NULL DEFAULT '',
            parser TEXT NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            result_count INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER,
            error TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, record_index),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS source_health_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            source_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            connector_id TEXT NOT NULL DEFAULT '',
            result_count INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER,
            error TEXT,
            checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            payload_json TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS search_hits (
            run_id TEXT NOT NULL,
            hit_id TEXT NOT NULL,
            source_id TEXT NOT NULL DEFAULT '',
            connector_id TEXT NOT NULL DEFAULT '',
            query TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            raw_url TEXT,
            discovered_at TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, hit_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS fetch_records (
            run_id TEXT NOT NULL,
            fetch_id TEXT NOT NULL,
            url TEXT NOT NULL DEFAULT '',
            final_url TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '',
            status_code INTEGER,
            content_type TEXT NOT NULL DEFAULT '',
            error TEXT,
            fetched_at TEXT,
            bytes_read INTEGER NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, fetch_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS documents (
            run_id TEXT NOT NULL,
            doc_id TEXT NOT NULL,
            source_id TEXT NOT NULL DEFAULT '',
            connector_id TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL DEFAULT '',
            final_url TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            content_type TEXT NOT NULL DEFAULT '',
            status_code INTEGER,
            text_hash TEXT NOT NULL DEFAULT '',
            content_hash TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, doc_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            run_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL,
            artifact_type TEXT NOT NULL DEFAULT '',
            value TEXT NOT NULL DEFAULT '',
            normalized_value TEXT NOT NULL DEFAULT '',
            doc_id TEXT NOT NULL DEFAULT '',
            source_url TEXT NOT NULL DEFAULT '',
            start_offset INTEGER,
            end_offset INTEGER,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, artifact_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS entities (
            run_id TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            entity_type TEXT NOT NULL DEFAULT '',
            canonical_value TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, entity_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS relationships (
            run_id TEXT NOT NULL,
            relationship_id TEXT NOT NULL,
            source_id TEXT NOT NULL DEFAULT '',
            target_id TEXT NOT NULL DEFAULT '',
            relationship_type TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, relationship_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS relevance_scores (
            run_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            target_type TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, target_id, target_type),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pivots (
            run_id TEXT NOT NULL,
            pivot_id TEXT NOT NULL,
            query TEXT NOT NULL DEFAULT '',
            pivot_type TEXT NOT NULL DEFAULT '',
            value TEXT NOT NULL DEFAULT '',
            score REAL NOT NULL DEFAULT 0,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, pivot_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS claims (
            run_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            claim_type TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            confidence_label TEXT NOT NULL DEFAULT '',
            requires_review INTEGER NOT NULL DEFAULT 1,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, claim_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS reports (
            run_id TEXT NOT NULL,
            report_id TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            generated_at TEXT,
            payload_json TEXT NOT NULL,
            PRIMARY KEY (run_id, report_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS stage_events (
            run_id TEXT NOT NULL,
            event_index INTEGER NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY (run_id, event_index),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(text_hash, content_hash);
        CREATE INDEX IF NOT EXISTS idx_source_health_source ON source_health_history(source_id, checked_at DESC);
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    conn.commit()

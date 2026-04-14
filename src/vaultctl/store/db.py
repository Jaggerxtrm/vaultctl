from __future__ import annotations

import sqlite3
from pathlib import Path

from vaultctl.core.paths import ensure_parent


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_parent(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _recreate_document_links(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS document_links")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS document_links (
          document_id INTEGER NOT NULL,
          raw_target TEXT NOT NULL,
          link_target TEXT NOT NULL,
          link_target_ci TEXT NOT NULL,
          link_target_slug TEXT NOT NULL,
          target_fragment TEXT,
          resolved_document_id INTEGER,
          resolution_state TEXT NOT NULL DEFAULT 'dangling',
          resolution_method TEXT,
          ambiguous_count INTEGER NOT NULL DEFAULT 0,
          occurrences INTEGER NOT NULL DEFAULT 1,
          UNIQUE(document_id, raw_target, target_fragment),
          FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
          FOREIGN KEY(resolved_document_id) REFERENCES documents(id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_links_document_id ON document_links(document_id);
        CREATE INDEX IF NOT EXISTS idx_links_target_ci ON document_links(link_target_ci);
        CREATE INDEX IF NOT EXISTS idx_links_target_slug ON document_links(link_target_slug);
        CREATE INDEX IF NOT EXISTS idx_links_state ON document_links(resolution_state);
        CREATE INDEX IF NOT EXISTS idx_links_resolved ON document_links(resolved_document_id);
        """
    )


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def _ensure_schema(conn: sqlite3.Connection) -> None:
    if _table_exists(conn, "documents"):
        document_columns = _table_columns(conn, "documents")
        if "title_ci" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN title_ci TEXT NOT NULL DEFAULT ''")
        if "title_slug" not in document_columns:
            conn.execute("ALTER TABLE documents ADD COLUMN title_slug TEXT NOT NULL DEFAULT ''")

    if _table_exists(conn, "document_links"):
        link_columns = _table_columns(conn, "document_links")
        if "resolution_state" not in link_columns:
            _recreate_document_links(conn)

    schema_path = Path(__file__).resolve().parent / "schema.sql"
    conn.executescript(schema_path.read_text(encoding="utf-8"))
    conn.commit()

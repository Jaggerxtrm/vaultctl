from __future__ import annotations

import sqlite3
from typing import Any

from vaultctl.core.config import load_config
from vaultctl.core.errors import NotFoundError
from vaultctl.store.db import connect
from vaultctl.store import graph as graph_store


def _open_conn() -> sqlite3.Connection:
    config = load_config()
    return connect(config.db_path)


def resolve_note(conn: sqlite3.Connection, target: str) -> dict[str, Any]:
    if ":" not in target:
        raise NotFoundError("Target must be source_id:rel/path.md")
    source_id, rel_path = target.split(":", 1)
    row = conn.execute(
        "SELECT id, source_id, rel_path, title FROM documents WHERE source_id=? AND rel_path=?",
        (source_id, rel_path),
    ).fetchone()
    if not row:
        raise NotFoundError(f"No indexed document for {target}")
    return dict(row)


def outgoing(target: str, recursive: bool, max_distance: int, folder: str | None, tag: str | None, status: str | None, limit: int) -> list[dict[str, Any]]:
    conn = _open_conn()
    doc = resolve_note(conn, target)
    return graph_store.outgoing(conn, int(doc["id"]), max_distance, recursive, {"folder": folder, "tag": tag, "status": status}, limit)


def backlinks(target: str, recursive: bool, max_distance: int, folder: str | None, tag: str | None, status: str | None, limit: int) -> list[dict[str, Any]]:
    conn = _open_conn()
    doc = resolve_note(conn, target)
    return graph_store.backlinks(conn, int(doc["id"]), max_distance, recursive, {"folder": folder, "tag": tag, "status": status}, limit)


def path(source_note: str, target_note: str, max_distance: int) -> list[dict[str, Any]]:
    conn = _open_conn()
    src = resolve_note(conn, source_note)
    dst = resolve_note(conn, target_note)
    return graph_store.path(conn, int(src["id"]), int(dst["id"]), max_distance)


def broken(source: str | None, folder: str | None, tag: str | None, status: str | None, state: str | None, limit: int) -> list[dict[str, Any]]:
    conn = _open_conn()
    return graph_store.broken(conn, source, folder, tag, status, state, limit)


def orphans(source: str | None, folder: str | None, tag: str | None, status: str | None, limit: int) -> list[dict[str, Any]]:
    conn = _open_conn()
    return graph_store.orphans(conn, source, folder, tag, status, limit)


def rank(source: str | None, folder: str | None, tag: str | None, status: str | None, metric: str, limit: int) -> list[dict[str, Any]]:
    conn = _open_conn()
    return graph_store.rank(conn, source, folder, tag, status, metric, limit)


def export_graph(target: str | None, source: str | None, folder: str | None, direction: str, recursive: bool, max_distance: int, limit: int) -> dict[str, Any]:
    conn = _open_conn()
    from_doc_id = None
    if target:
        from_doc_id = int(resolve_note(conn, target)["id"])
    return graph_store.export_graph(conn, source, folder, direction, from_doc_id, recursive, max_distance, limit)

from __future__ import annotations

import sqlite3


def find_orphans(conn: sqlite3.Connection, source: str | None, limit: int) -> list[dict[str, str]]:
    query = """
    SELECT d.source_id, d.rel_path, d.title
    FROM documents d
    LEFT JOIN document_graph_stats gs ON gs.document_id = d.id
    WHERE COALESCE(gs.in_degree, 0) = 0
    """
    params: list[object] = []
    if source:
        query += " AND d.source_id = ?"
        params.append(source)
    query += " ORDER BY d.source_id, d.rel_path LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def find_linked(conn: sqlite3.Connection, source: str | None, limit: int) -> list[dict[str, str]]:
    query = """
    SELECT DISTINCT d.source_id, d.rel_path, d.title
    FROM documents d
    INNER JOIN document_links l ON l.document_id = d.id AND l.resolution_state='resolved'
    """
    params: list[object] = []
    if source:
        query += " WHERE d.source_id = ?"
        params.append(source)
    query += " ORDER BY d.source_id, d.rel_path LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def find_duplicates(conn: sqlite3.Connection, source: str | None, limit: int) -> list[dict[str, str]]:
    query = """
    SELECT d.source_id, d.title, COUNT(*) AS count
    FROM documents d
    """
    params: list[object] = []
    if source:
        query += " WHERE d.source_id = ?"
        params.append(source)
    query += " GROUP BY d.source_id, d.title HAVING COUNT(*) > 1 ORDER BY count DESC, d.title LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(query, params).fetchall()]

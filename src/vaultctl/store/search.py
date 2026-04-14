from __future__ import annotations

import sqlite3
from typing import Any


def search_documents(
    conn: sqlite3.Connection,
    query: str,
    limit: int,
    source: str | None = None,
    folder: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    rank: str = "bm25",
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"query": query, "limit": limit}
    extra: list[str] = []

    if source:
        extra.append("sections_fts.source_id = :source")
        params["source"] = source

    if folder:
        folder_clean = folder.rstrip("/")
        extra.append(
            "(sections_fts.rel_path = :folder OR sections_fts.rel_path LIKE :folder_prefix)"
        )
        params["folder"] = folder_clean
        params["folder_prefix"] = folder_clean + "/%"

    if tag:
        extra.append("(' ' || d.tags_text || ' ') LIKE :tag_pattern")
        params["tag_pattern"] = f"% {tag} %"

    if status:
        extra.append("d.status = :status")
        params["status"] = status

    where = "sections_fts MATCH :query"
    if extra:
        where += " AND " + " AND ".join(extra)

    score_expr = "bm25(sections_fts, 8.0, 4.0, 2.0, 1.0)"
    if rank == "hybrid":
        score_expr = "bm25(sections_fts, 8.0, 4.0, 2.0, 1.0) - (0.1 * ln(1 + COALESCE(gs.in_degree, 0)))"

    sql = f"""
    SELECT
      {score_expr} AS score,
      sections_fts.source_id,
      sections_fts.rel_path,
      sections_fts.title,
      snippet(sections_fts, 3, '', '', ' … ', 24) AS snippet,
      d.status,
      d.tags_text
    FROM sections_fts
    LEFT JOIN documents d
      ON d.source_id = sections_fts.source_id
      AND d.rel_path = sections_fts.rel_path
    LEFT JOIN document_graph_stats gs
      ON gs.document_id = d.id
    WHERE {where}
    ORDER BY score
    LIMIT :limit
    """

    results: list[dict[str, Any]] = []
    for row in conn.execute(sql, params).fetchall():
        tags_text = str(row["tags_text"] or "")
        doc_status = str(row["status"]) if row["status"] is not None else None
        results.append(
            {
                "score": float(row["score"]),
                "source_id": row["source_id"],
                "rel_path": row["rel_path"],
                "title": row["title"],
                "snippet": row["snippet"],
                "tags": tags_text.split() if tags_text else [],
                "status": doc_status,
            }
        )
    return results

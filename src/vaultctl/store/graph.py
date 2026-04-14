from __future__ import annotations

import sqlite3
from typing import Any


def _document_filter_sql(prefix: str, folder: str | None, tag: str | None, status: str | None) -> tuple[str, dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if folder:
        clean = folder.rstrip("/")
        clauses.append(f"({prefix}.rel_path = :folder OR {prefix}.rel_path LIKE :folder_prefix)")
        params["folder"] = clean
        params["folder_prefix"] = clean + "/%"
    if tag:
        clauses.append(f"(' ' || {prefix}.tags_text || ' ') LIKE :tag_pattern")
        params["tag_pattern"] = f"% {tag} %"
    if status:
        clauses.append(f"{prefix}.status = :status")
        params["status"] = status
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def outgoing(
    conn: sqlite3.Connection,
    document_id: int,
    max_distance: int,
    recursive: bool,
    filters: dict[str, str | None],
    limit: int,
) -> list[dict[str, Any]]:
    effective_distance = max_distance if recursive else 1
    filter_sql, filter_params = _document_filter_sql("target_doc", filters.get("folder"), filters.get("tag"), filters.get("status"))
    params: dict[str, Any] = {
        "start_id": document_id,
        "max_distance": effective_distance,
        "limit": limit,
        **filter_params,
    }
    sql = f"""
    WITH RECURSIVE walk(doc_id, distance, path, traversed) AS (
      SELECT :start_id, 0, ',' || :start_id || ',', 0
      UNION ALL
      SELECT l.resolved_document_id, walk.distance + 1, walk.path || l.resolved_document_id || ',', walk.traversed + 1
      FROM walk
      JOIN document_links l ON l.document_id = walk.doc_id
      JOIN documents target_doc ON target_doc.id = l.resolved_document_id
      WHERE l.resolution_state = 'resolved'
        AND walk.distance < :max_distance
        AND walk.traversed < 100000
        AND instr(walk.path, ',' || l.resolved_document_id || ',') = 0
        {filter_sql}
    )
    SELECT d.source_id, d.rel_path, d.title, MIN(w.distance) AS distance
    FROM walk w
    JOIN documents d ON d.id = w.doc_id
    WHERE w.distance > 0
    GROUP BY d.id
    ORDER BY distance, d.source_id, d.rel_path
    LIMIT :limit
    """
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def backlinks(
    conn: sqlite3.Connection,
    document_id: int,
    max_distance: int,
    recursive: bool,
    filters: dict[str, str | None],
    limit: int,
) -> list[dict[str, Any]]:
    effective_distance = max_distance if recursive else 1
    filter_sql, filter_params = _document_filter_sql("src_doc", filters.get("folder"), filters.get("tag"), filters.get("status"))
    params: dict[str, Any] = {
        "start_id": document_id,
        "max_distance": effective_distance,
        "limit": limit,
        **filter_params,
    }
    sql = f"""
    WITH RECURSIVE walk(doc_id, distance, path, traversed) AS (
      SELECT :start_id, 0, ',' || :start_id || ',', 0
      UNION ALL
      SELECT l.document_id, walk.distance + 1, walk.path || l.document_id || ',', walk.traversed + 1
      FROM walk
      JOIN document_links l ON l.resolved_document_id = walk.doc_id
      JOIN documents src_doc ON src_doc.id = l.document_id
      WHERE l.resolution_state = 'resolved'
        AND walk.distance < :max_distance
        AND walk.traversed < 100000
        AND instr(walk.path, ',' || l.document_id || ',') = 0
        {filter_sql}
    )
    SELECT d.source_id, d.rel_path, d.title, MIN(w.distance) AS distance
    FROM walk w
    JOIN documents d ON d.id = w.doc_id
    WHERE w.distance > 0
    GROUP BY d.id
    ORDER BY distance, d.source_id, d.rel_path
    LIMIT :limit
    """
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def path(conn: sqlite3.Connection, src_id: int, dst_id: int, max_distance: int) -> list[dict[str, Any]]:
    row = conn.execute(
        """
        WITH RECURSIVE walk(doc_id, distance, path, traversed) AS (
          SELECT :src_id, 0, ',' || :src_id || ',', 0
          UNION ALL
          SELECT l.resolved_document_id, walk.distance + 1, walk.path || l.resolved_document_id || ',', walk.traversed + 1
          FROM walk
          JOIN document_links l ON l.document_id = walk.doc_id
          WHERE l.resolution_state = 'resolved'
            AND walk.distance < :max_distance
            AND walk.traversed < 100000
            AND instr(walk.path, ',' || l.resolved_document_id || ',') = 0
        )
        SELECT path, distance
        FROM walk
        WHERE doc_id = :dst_id
        ORDER BY distance
        LIMIT 1
        """,
        {"src_id": src_id, "dst_id": dst_id, "max_distance": max_distance},
    ).fetchone()
    if not row:
        return []

    ids = [int(part) for part in str(row["path"]).strip(",").split(",") if part]
    placeholders = ",".join("?" for _ in ids)
    docs = {int(doc["id"]): dict(doc) for doc in conn.execute(f"SELECT id, source_id, rel_path, title FROM documents WHERE id IN ({placeholders})", ids).fetchall()}
    return [docs[doc_id] for doc_id in ids if doc_id in docs]


def broken(
    conn: sqlite3.Connection,
    source_id: str | None,
    folder: str | None,
    tag: str | None,
    status: str | None,
    state: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    source_clause = ""
    params: dict[str, Any] = {"limit": limit}
    if source_id:
        source_clause = " AND src.source_id = :source_id"
        params["source_id"] = source_id
    filter_sql, filter_params = _document_filter_sql("src", folder, tag, status)
    params.update(filter_params)

    state_clause = " AND l.resolution_state IN ('dangling', 'ambiguous')"
    if state:
        state_clause = " AND l.resolution_state = :state"
        params["state"] = state

    sql = f"""
    SELECT
      src.source_id,
      src.rel_path,
      src.title,
      l.raw_target,
      l.link_target,
      l.target_fragment,
      l.resolution_state,
      l.resolution_method,
      l.ambiguous_count,
      l.occurrences
    FROM document_links l
    JOIN documents src ON src.id = l.document_id
    WHERE 1=1
      {source_clause}
      {filter_sql}
      {state_clause}
    ORDER BY src.source_id, src.rel_path, l.raw_target
    LIMIT :limit
    """
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def orphans(
    conn: sqlite3.Connection,
    source_id: str | None,
    folder: str | None,
    tag: str | None,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {"limit": limit}
    source_clause = ""
    if source_id:
        source_clause = " AND d.source_id = :source_id"
        params["source_id"] = source_id
    filter_sql, filter_params = _document_filter_sql("d", folder, tag, status)
    params.update(filter_params)

    sql = f"""
    SELECT d.source_id, d.rel_path, d.title, COALESCE(gs.in_degree, 0) AS in_degree, COALESCE(gs.out_degree, 0) AS out_degree
    FROM documents d
    LEFT JOIN document_graph_stats gs ON gs.document_id = d.id
    WHERE COALESCE(gs.in_degree, 0) = 0
      AND COALESCE(gs.out_degree, 0) = 0
      {source_clause}
      {filter_sql}
    ORDER BY d.source_id, d.rel_path
    LIMIT :limit
    """
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def rank(
    conn: sqlite3.Connection,
    source_id: str | None,
    folder: str | None,
    tag: str | None,
    status: str | None,
    metric: str,
    limit: int,
) -> list[dict[str, Any]]:
    if metric != "in_degree":
        scores = conn.execute(
            """
            SELECT d.source_id, d.rel_path, d.title, g.metric, g.score
            FROM graph_scores g
            JOIN documents d ON d.id = g.document_id
            WHERE g.metric = ?
            ORDER BY g.score DESC, d.source_id, d.rel_path
            LIMIT ?
            """,
            (metric, limit),
        ).fetchall()
        return [dict(row) for row in scores]

    params: dict[str, Any] = {"limit": limit}
    source_clause = ""
    if source_id:
        source_clause = " AND d.source_id = :source_id"
        params["source_id"] = source_id
    filter_sql, filter_params = _document_filter_sql("d", folder, tag, status)
    params.update(filter_params)

    sql = f"""
    SELECT d.source_id, d.rel_path, d.title, COALESCE(gs.in_degree, 0) AS score
    FROM documents d
    LEFT JOIN document_graph_stats gs ON gs.document_id = d.id
    WHERE 1=1
      {source_clause}
      {filter_sql}
    ORDER BY score DESC, d.source_id, d.rel_path
    LIMIT :limit
    """
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def export_graph(
    conn: sqlite3.Connection,
    source_id: str | None,
    folder: str | None,
    direction: str,
    from_doc_id: int | None,
    recursive: bool,
    max_distance: int,
    limit: int,
) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    clauses = ["l.resolution_state = 'resolved'"]
    if source_id:
        clauses.append("src.source_id = :source_id")
        params["source_id"] = source_id
    if folder:
        clean = folder.rstrip("/")
        clauses.append("(src.rel_path = :folder OR src.rel_path LIKE :folder_prefix)")
        params["folder"] = clean
        params["folder_prefix"] = clean + "/%"

    max_hops = max_distance if recursive else 1
    if from_doc_id is not None:
        params["from_doc_id"] = from_doc_id
        params["max_hops"] = max_hops
        step_sql = """
          SELECT l.resolved_document_id, walk.distance + 1, walk.path || l.resolved_document_id || ',', walk.traversed + 1
          FROM walk
          JOIN document_links l ON l.document_id = walk.doc_id
          WHERE l.resolution_state='resolved'
            AND walk.distance < :max_hops
            AND walk.traversed < 100000
            AND instr(walk.path, ',' || l.resolved_document_id || ',') = 0
        """
        if direction == "both":
            step_sql += """
          UNION ALL
          SELECT l.document_id, walk.distance + 1, walk.path || l.document_id || ',', walk.traversed + 1
          FROM walk
          JOIN document_links l ON l.resolved_document_id = walk.doc_id
          WHERE l.resolution_state='resolved'
            AND walk.distance < :max_hops
            AND walk.traversed < 100000
            AND instr(walk.path, ',' || l.document_id || ',') = 0
            """
        edge_source = f"""
        WITH RECURSIVE walk(doc_id, distance, path, traversed) AS (
          SELECT :from_doc_id, 0, ',' || :from_doc_id || ',', 0
          UNION ALL
          {step_sql}
        )
        SELECT l.document_id AS src_id, l.resolved_document_id AS dst_id
        FROM document_links l
        JOIN walk w ON w.doc_id = l.document_id
        WHERE l.resolution_state='resolved' AND w.distance < :max_hops
        LIMIT :limit
        """
    else:
        edge_source = """
        SELECT l.document_id AS src_id, l.resolved_document_id AS dst_id
        FROM document_links l
        WHERE l.resolution_state='resolved'
        LIMIT :limit
        """

    where_suffix = f" AND {' AND '.join(clauses)}" if clauses else ""
    edge_rows = conn.execute(
        f"""
        SELECT src.id AS src_id, src.source_id AS src_source_id, src.rel_path AS src_rel_path, src.title AS src_title,
               dst.id AS dst_id, dst.source_id AS dst_source_id, dst.rel_path AS dst_rel_path, dst.title AS dst_title
        FROM ({edge_source}) e
        JOIN documents src ON src.id = e.src_id
        JOIN documents dst ON dst.id = e.dst_id
        JOIN document_links l ON l.document_id = src.id AND l.resolved_document_id = dst.id AND l.resolution_state='resolved'
        WHERE 1=1 {where_suffix}
        LIMIT :limit
        """,
        params,
    ).fetchall()

    edges: list[dict[str, Any]] = []
    nodes: dict[int, dict[str, Any]] = {}
    for row in edge_rows:
        src = {"id": int(row["src_id"]), "source_id": row["src_source_id"], "rel_path": row["src_rel_path"], "title": row["src_title"]}
        dst = {"id": int(row["dst_id"]), "source_id": row["dst_source_id"], "rel_path": row["dst_rel_path"], "title": row["dst_title"]}
        nodes[src["id"]] = src
        nodes[dst["id"]] = dst
        if direction in {"out", "both"}:
            edges.append({"from": src["id"], "to": dst["id"]})
        if direction in {"in", "both"}:
            edges.append({"from": dst["id"], "to": src["id"]})

    dot_lines = ["digraph vaultctl {"]
    for node in nodes.values():
        safe_title = str(node["title"]).replace('"', "'")
        dot_lines.append(f'  n{node["id"]} [label="{safe_title}"];')
    for edge in edges:
        dot_lines.append(f'  n{edge["from"]} -> n{edge["to"]};')
    dot_lines.append("}")

    return {"nodes": list(nodes.values()), "edges": edges, "dot": "\n".join(dot_lines)}

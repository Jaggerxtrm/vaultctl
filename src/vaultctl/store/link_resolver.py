from __future__ import annotations

import re
import sqlite3

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = _SLUG_RE.sub("-", lowered).strip("-")
    return slug


def _candidate_ids(conn: sqlite3.Connection, source_id: str, row: sqlite3.Row) -> tuple[list[int], str | None]:
    link_target = str(row["link_target"])
    link_target_ci = str(row["link_target_ci"])
    link_target_slug = str(row["link_target_slug"])

    checks = (
        ("exact", "SELECT id FROM documents WHERE source_id=? AND title=?", (source_id, link_target)),
        ("ci", "SELECT id FROM documents WHERE source_id=? AND title_ci=?", (source_id, link_target_ci)),
        ("slug", "SELECT id FROM documents WHERE source_id=? AND title_slug=?", (source_id, link_target_slug)),
        (
            "alias_exact",
            """
            SELECT d.id FROM document_aliases a
            JOIN documents d ON d.id = a.document_id
            WHERE d.source_id=? AND a.alias=?
            """,
            (source_id, link_target),
        ),
        (
            "alias_ci",
            """
            SELECT d.id FROM document_aliases a
            JOIN documents d ON d.id = a.document_id
            WHERE d.source_id=? AND a.alias_ci=?
            """,
            (source_id, link_target_ci),
        ),
        (
            "alias_slug",
            """
            SELECT d.id FROM document_aliases a
            JOIN documents d ON d.id = a.document_id
            WHERE d.source_id=? AND a.alias_slug=?
            """,
            (source_id, link_target_slug),
        ),
    )

    for method, sql, params in checks:
        ids = sorted({int(match[0]) for match in conn.execute(sql, params).fetchall()})
        if ids:
            return ids, method
    return [], None


def resolve_links(conn: sqlite3.Connection, source_id: str) -> None:
    rows = conn.execute(
        """
        SELECT l.rowid, l.link_target, l.link_target_ci, l.link_target_slug
        FROM document_links l
        JOIN documents d ON d.id = l.document_id
        WHERE d.source_id = ?
        """,
        (source_id,),
    ).fetchall()

    for row in rows:
        ids, method = _candidate_ids(conn, source_id, row)
        if len(ids) == 1:
            conn.execute(
                """
                UPDATE document_links
                SET resolved_document_id=?, resolution_state='resolved', resolution_method=?, ambiguous_count=0
                WHERE rowid=?
                """,
                (ids[0], method, row["rowid"]),
            )
            continue
        if len(ids) > 1:
            conn.execute(
                """
                UPDATE document_links
                SET resolved_document_id=NULL, resolution_state='ambiguous', resolution_method=?, ambiguous_count=?
                WHERE rowid=?
                """,
                (method, len(ids), row["rowid"]),
            )
            continue
        conn.execute(
            """
            UPDATE document_links
            SET resolved_document_id=NULL, resolution_state='dangling', resolution_method=NULL, ambiguous_count=0
            WHERE rowid=?
            """,
            (row["rowid"],),
        )


def recompute_graph_stats(conn: sqlite3.Connection, source_id: str) -> None:
    docs = conn.execute("SELECT id FROM documents WHERE source_id=?", (source_id,)).fetchall()

    for doc in docs:
        document_id = int(doc["id"])
        out_degree = int(
            conn.execute(
                "SELECT COUNT(*) FROM document_links WHERE document_id=? AND resolution_state='resolved'",
                (document_id,),
            ).fetchone()[0]
        )
        dangling = int(
            conn.execute(
                "SELECT COUNT(*) FROM document_links WHERE document_id=? AND resolution_state='dangling'",
                (document_id,),
            ).fetchone()[0]
        )
        ambiguous = int(
            conn.execute(
                "SELECT COUNT(*) FROM document_links WHERE document_id=? AND resolution_state='ambiguous'",
                (document_id,),
            ).fetchone()[0]
        )
        in_degree = int(
            conn.execute(
                """
                SELECT COUNT(DISTINCT l.document_id)
                FROM document_links l
                JOIN documents s ON s.id = l.document_id
                WHERE s.source_id=?
                  AND l.resolution_state='resolved'
                  AND l.resolved_document_id=?
                """,
                (source_id, document_id),
            ).fetchone()[0]
        )

        conn.execute(
            """
            INSERT INTO document_graph_stats(document_id, in_degree, out_degree, dangling_outgoing, ambiguous_outgoing)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(document_id) DO UPDATE SET
                in_degree=excluded.in_degree,
                out_degree=excluded.out_degree,
                dangling_outgoing=excluded.dangling_outgoing,
                ambiguous_outgoing=excluded.ambiguous_outgoing
            """,
            (document_id, in_degree, out_degree, dangling, ambiguous),
        )

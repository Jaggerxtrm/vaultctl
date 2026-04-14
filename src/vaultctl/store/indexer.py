from __future__ import annotations

import sqlite3
from collections import Counter

from vaultctl.core.models import SourceConfig
from vaultctl.ingest.markdown import parse_markdown
from vaultctl.ingest.normalizers import normalize_rel_path
from vaultctl.ingest.sources import iter_source_paths
from vaultctl.ingest.transcripts import parse_transcript
from vaultctl.store.link_resolver import recompute_graph_stats, resolve_links, slugify


def upsert_source(conn: sqlite3.Connection, source: SourceConfig) -> None:
    conn.execute(
        """
        INSERT INTO sources(id, root, include_glob)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET root=excluded.root, include_glob=excluded.include_glob, updated_at=CURRENT_TIMESTAMP
        """,
        (source.id, str(source.root), source.include_glob),
    )


def index_source(conn: sqlite3.Connection, source: SourceConfig, full: bool = False) -> int:
    upsert_source(conn, source)
    changed = 0
    seen_paths: set[str] = set()

    for path in iter_source_paths(source):
        rel_path = normalize_rel_path(path, source.root)
        seen_paths.add(rel_path)
        mtime = path.stat().st_mtime
        row = conn.execute(
            "SELECT id, mtime FROM documents WHERE source_id = ? AND rel_path = ?",
            (source.id, rel_path),
        ).fetchone()
        if row and not full and float(row["mtime"]) >= mtime:
            continue

        content = path.read_text(encoding="utf-8", errors="replace")
        parser = parse_transcript if source.id == "transcripts" else parse_markdown
        parsed = parser(content, path.stem)
        heading_text = " / ".join(parsed.heading_paths)
        tags_text = " ".join(parsed.tags)
        title_ci = parsed.title.casefold()
        title_slug = slugify(parsed.title)

        if row:
            document_id = int(row["id"])
            conn.execute(
                """
                UPDATE documents SET abs_path=?, title=?, title_ci=?, title_slug=?, status=?, body=?, heading_path=?, tags_text=?, mtime=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    str(path),
                    parsed.title,
                    title_ci,
                    title_slug,
                    parsed.status,
                    parsed.body,
                    heading_text,
                    tags_text,
                    mtime,
                    document_id,
                ),
            )
            conn.execute("DELETE FROM document_tags WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM document_aliases WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM document_links WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM document_graph_stats WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM sections WHERE document_id=?", (document_id,))
            conn.execute("DELETE FROM sections_fts WHERE source_id=? AND rel_path=?", (source.id, rel_path))
        else:
            cursor = conn.execute(
                """
                INSERT INTO documents(source_id, rel_path, abs_path, title, title_ci, title_slug, status, body, heading_path, tags_text, mtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.id,
                    rel_path,
                    str(path),
                    parsed.title,
                    title_ci,
                    title_slug,
                    parsed.status,
                    parsed.body,
                    heading_text,
                    tags_text,
                    mtime,
                ),
            )
            document_id = int(cursor.lastrowid)

        for tag in parsed.tags:
            conn.execute("INSERT OR IGNORE INTO document_tags(document_id, tag) VALUES (?, ?)", (document_id, tag))

        for alias in parsed.aliases:
            conn.execute(
                "INSERT OR IGNORE INTO document_aliases(document_id, alias, alias_ci, alias_slug) VALUES (?, ?, ?, ?)",
                (document_id, alias, alias.casefold(), slugify(alias)),
            )

        link_counter = Counter((link.raw, link.target, link.fragment) for link in parsed.links)
        for link in parsed.links:
            key = (link.raw, link.target, link.fragment)
            count = link_counter[key]
            if count == 0:
                continue
            link_counter[key] = 0
            conn.execute(
                """
                INSERT INTO document_links(
                    document_id, raw_target, link_target, link_target_ci, link_target_slug, target_fragment,
                    resolved_document_id, resolution_state, resolution_method, ambiguous_count, occurrences
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, 'dangling', NULL, 0, ?)
                """,
                (
                    document_id,
                    link.raw,
                    link.target,
                    link.target.casefold(),
                    slugify(link.target),
                    link.fragment,
                    count,
                ),
            )

        conn.execute(
            "INSERT INTO sections(document_id, heading_path, body) VALUES (?, ?, ?)",
            (document_id, heading_text, parsed.body),
        )
        conn.execute(
            "INSERT INTO sections_fts(title, heading_path, tags_text, body, source_id, rel_path) VALUES (?, ?, ?, ?, ?, ?)",
            (parsed.title, heading_text, tags_text, parsed.body, source.id, rel_path),
        )
        changed += 1

    if full:
        missing = conn.execute(
            "SELECT rel_path FROM documents WHERE source_id=?", (source.id,)
        ).fetchall()
        for row in missing:
            rel_path = str(row["rel_path"])
            if rel_path in seen_paths:
                continue
            conn.execute("DELETE FROM sections_fts WHERE source_id=? AND rel_path=?", (source.id, rel_path))
            conn.execute("DELETE FROM documents WHERE source_id=? AND rel_path=?", (source.id, rel_path))

    resolve_links(conn, source.id)
    recompute_graph_stats(conn, source.id)
    conn.commit()
    return changed

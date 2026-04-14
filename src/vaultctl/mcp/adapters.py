from __future__ import annotations

from typing import Any, Callable

from vaultctl.services.audit_service import run_audit
from vaultctl.services.graph_service import backlinks, broken, outgoing, path, rank
from vaultctl.services.index_service import index_sources
from vaultctl.services.inspect_service import context, status, tree
from vaultctl.services.note_service import append_note, delete_note, extract_links, read_note, write_note
from vaultctl.services.search_service import run_search
from vaultctl.services.stats_service import stats


def _normalize_note_target(note: str, source: str | None) -> str:
    if ":" in note or not source:
        return note
    return f"{source}:{note}"


def _graph_neighbors(
    note: str,
    direction: str,
    recursive: bool,
    max_distance: int,
    source: str | None,
    folder: str | None,
    tag: str | None,
    status_filter: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    target = _normalize_note_target(note, source)
    if direction == "out":
        return outgoing(target, recursive, max_distance, folder, tag, status_filter, limit)
    if direction == "in":
        return backlinks(target, recursive, max_distance, folder, tag, status_filter, limit)

    combined = outgoing(target, recursive, max_distance, folder, tag, status_filter, limit)
    seen = {(row["source_id"], row["rel_path"]) for row in combined}
    for row in backlinks(target, recursive, max_distance, folder, tag, status_filter, limit):
        key = (row["source_id"], row["rel_path"])
        if key in seen:
            continue
        seen.add(key)
        combined.append(row)
    return combined[:limit]


def _context_with_depth(parent_id: str, depth: int = 1) -> dict[str, Any]:
    payload = context(parent_id)
    if depth <= 1:
        return payload

    payload["links"] = outgoing(parent_id, recursive=True, max_distance=depth, folder=None, tag=None, status=None, limit=100)
    payload["backlinks"] = backlinks(parent_id, recursive=True, max_distance=depth, folder=None, tag=None, status=None, limit=100)
    payload["depth"] = depth
    return payload


def legacy_tool_adapters() -> dict[str, Callable[..., Any]]:
    return {
        "semantic_search": lambda query, folder=None, source=None, tag=None, status=None, n_results=5: run_search(
            query=query,
            folder=folder,
            source=source,
            tag=tag,
            status=status,
            limit=n_results,
        ),
        "get_full_context": lambda parent_id, depth=1: _context_with_depth(parent_id, int(depth)),
        "reindex_vault": lambda force=False: index_sources(source=None, full=bool(force)),
        "get_index_stats": lambda: status(),
        "get_vault_statistics": lambda: stats(),
        "suggest_links": lambda note_path: {"links": extract_links(note_path, None)},
        "index_note": lambda note_path: {"indexed": note_path, "changes": index_sources(source=None)},
        "search_notes": lambda query, n_results=5: run_search(query=query, limit=n_results),
        "read_note": lambda note_path: {"content": read_note(note_path, None)},
        "write_note": lambda note_path, content: write_note(note_path, content, None),
        "append_to_note": lambda note_path, content: append_note(note_path, content, None),
        "delete_note": lambda note_path: delete_note(note_path, None),
        "get_vault_structure": lambda root_path=None, max_depth=3: tree(root_path, None, max_depth),
        "get_orphaned_notes": lambda: run_audit("orphans", None, 100),
        "get_most_linked_notes": lambda n_results=10: run_audit("linked", None, n_results),
        "get_duplicate_content": lambda similarity_threshold=0.95: run_audit("duplicates", None, 100),
        "graph_neighbors": lambda note, direction="out", recursive=False, max_distance=1, source=None, folder=None, tag=None, status=None, limit=20: _graph_neighbors(
            note,
            direction,
            bool(recursive),
            int(max_distance),
            source,
            folder,
            tag,
            status,
            int(limit),
        ),
        "graph_path": lambda source_note, target_note, max_distance=6: path(source_note, target_note, int(max_distance)),
        "graph_broken_links": lambda source=None, folder=None, state=None, limit=20: broken(source, folder, None, None, state, int(limit)),
        "graph_rank": lambda metric="in_degree", source=None, folder=None, tag=None, status=None, limit=20: rank(source, folder, tag, status, metric, int(limit)),
    }

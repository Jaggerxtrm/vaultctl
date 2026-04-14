from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from vaultctl.mcp.adapters import legacy_tool_adapters


@pytest.fixture()
def temp_vault_env(tmp_path: Path) -> dict[str, Path]:
    home = tmp_path / "home"
    config_dir = home / ".config" / "vaultctl"
    data_dir = home / ".local" / "share" / "vaultctl"
    vault_root = tmp_path / "vault"
    transcripts_root = tmp_path / "transcripts"

    config_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (vault_root / "folder-a").mkdir(parents=True)
    (vault_root / "folder-b").mkdir(parents=True)
    (vault_root / "secret").mkdir(parents=True)
    transcripts_root.mkdir(parents=True)

    (vault_root / "folder-a" / "alpha.md").write_text(
        """---
"""
        "title: Alpha Note\n"
        "tags: [repo, finance]\n"
        "status: permanent\n"
        "---\n"
        "# Alpha\n"
        "repo market liquidity alpha signal\n"
        "See [[Beta Note]], [[Beta Alias]], [[Shared Duplicate]], and [[Missing Note]].\n",
        encoding="utf-8",
    )
    (vault_root / "folder-a" / "beta.md").write_text(
        """---
"""
        "title: Beta Note\n"
        "aliases: [Beta Alias]\n"
        "tags: [macro]\n"
        "status: active\n"
        "---\n"
        "# Beta\n"
        "beta macro content with [[Deep Note]]\n",
        encoding="utf-8",
    )
    duplicate_body = (
        """---
"""
        "title: Shared Duplicate\n"
        "tags: [dup]\n"
        "status: active\n"
        "---\n"
        "# Dup\n"
        "duplicated content\n"
    )
    (vault_root / "folder-b" / "duplicate.md").write_text(duplicate_body, encoding="utf-8")
    (vault_root / "folder-b" / "duplicate-copy.md").write_text(duplicate_body, encoding="utf-8")
    (vault_root / "folder-b" / "deep.md").write_text(
        """---
"""
        "title: Deep Note\n"
        "tags: [deep]\n"
        "status: active\n"
        "---\n"
        "deep leaf\n",
        encoding="utf-8",
    )
    (vault_root / "folder-b" / "orphan.md").write_text(
        """---
"""
        "title: Lonely Note\n"
        "tags: [solo]\n"
        "status: draft\n"
        "---\n"
        "No links here\n",
        encoding="utf-8",
    )
    (vault_root / "secret" / "hidden.md").write_text(
        "# Hidden\nShould never be indexed\n", encoding="utf-8"
    )

    (transcripts_root / "lesson.analysis.md").write_text(
        """---
"""
        "title: Transcript Lesson\n"
        "tags: [transcript]\n"
        "status: draft\n"
        "---\n"
        "repo transcript signal\n",
        encoding="utf-8",
    )

    config_content = f"""db_path = \"{(data_dir / 'index.db').as_posix()}\"\n\n[[sources]]\nid = \"vault\"\nroot = \"{vault_root.as_posix()}\"\ninclude_glob = \"**/*.md\"\nexclude_glob = \"secret/**\"\n\n[[sources]]\nid = \"transcripts\"\nroot = \"{transcripts_root.as_posix()}\"\ninclude_glob = \"*.analysis.md\"\n"""
    (config_dir / "config.toml").write_text(config_content, encoding="utf-8")

    return {
        "home": home,
        "vault_root": vault_root,
        "transcripts_root": transcripts_root,
        "db_path": data_dir / "index.db",
    }


def run_vaultctl_json(*args: str, home: Path) -> Any:
    env = os.environ.copy()
    env["HOME"] = str(home)
    src_path = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src_path if "PYTHONPATH" not in env else f"{src_path}:{env['PYTHONPATH']}"
    result = subprocess.run(
        [sys.executable, "-m", "vaultctl.cli.app", *args],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def run_mcp_tool(tool: str, args: dict[str, Any], home: Path) -> Any:
    env = os.environ.copy()
    env["HOME"] = str(home)
    src_path = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src_path if "PYTHONPATH" not in env else f"{src_path}:{env['PYTHONPATH']}"
    request = json.dumps({"tool": tool, "args": args}) + "\n"
    result = subprocess.run(
        [sys.executable, "-m", "vaultctl.cli.app", "mcp", "serve"],
        env=env,
        text=True,
        input=request,
        capture_output=True,
        check=True,
    )
    response = json.loads(result.stdout.strip().splitlines()[-1])
    return response["result"]


def normalize_search_results(results: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "source_id": row["source_id"],
            "rel_path": row["rel_path"],
            "title": row["title"],
            "tags": row["tags"],
            "status": row["status"],
            "score_type": type(row["score"]).__name__,
            "snippet_type": type(row["snippet"]).__name__,
        }
        for row in results
    ]


def test_e2e_vaultctl_features(temp_vault_env: dict[str, Path]) -> None:
    home = temp_vault_env["home"]
    vault_root = temp_vault_env["vault_root"]

    initial = run_vaultctl_json("index", "--json", home=home)
    assert initial == {"vault": 6, "transcripts": 1}

    incremental = run_vaultctl_json("index", "--json", home=home)
    assert incremental == {"vault": 0, "transcripts": 0}

    time.sleep(1.05)
    alpha_path = vault_root / "folder-a" / "alpha.md"
    alpha_path.write_text(alpha_path.read_text(encoding="utf-8") + "\nnew mtime marker\n", encoding="utf-8")
    touched = run_vaultctl_json("index", "--json", home=home)
    assert touched == {"vault": 1, "transcripts": 0}

    full = run_vaultctl_json("index", "--full", "--json", home=home)
    assert full == {"vault": 6, "transcripts": 1}

    search_results = run_vaultctl_json("search", "repo", "-n", "10", "--json", home=home)
    assert isinstance(search_results, list)
    normalized_search = normalize_search_results(search_results)
    expected_search_snapshot = [
        {
            "source_id": "vault",
            "rel_path": "folder-a/alpha.md",
            "title": "Alpha Note",
            "tags": ["finance", "repo"],
            "status": "permanent",
            "score_type": "float",
            "snippet_type": "str",
        },
        {
            "source_id": "transcripts",
            "rel_path": "lesson.analysis.md",
            "title": "Transcript Lesson",
            "tags": ["transcript"],
            "status": "draft",
            "score_type": "float",
            "snippet_type": "str",
        },
    ]
    assert normalized_search[:2] == expected_search_snapshot

    source_filtered = run_vaultctl_json("search", "repo", "--source", "transcripts", "--json", home=home)
    assert [row["source_id"] for row in source_filtered] == ["transcripts"]

    folder_filtered = run_vaultctl_json("search", "repo", "--folder", "folder-a", "--json", home=home)
    assert [row["rel_path"] for row in folder_filtered] == ["folder-a/alpha.md"]

    tag_filtered = run_vaultctl_json("search", "repo", "--tag", "repo", "--json", home=home)
    assert [row["title"] for row in tag_filtered] == ["Alpha Note"]

    status_filtered = run_vaultctl_json("search", "repo", "--status", "draft", "--json", home=home)
    assert [row["source_id"] for row in status_filtered] == ["transcripts"]

    write_result = run_vaultctl_json(
        "note",
        "write",
        "folder-a/new-note.md",
        "new unique token",
        "--source",
        "vault",
        "--json",
        home=home,
    )
    assert write_result["source_id"] == "vault"

    read_result = run_vaultctl_json(
        "note", "read", "folder-a/new-note.md", "--source", "vault", "--json", home=home
    )
    assert read_result == {"content": "new unique token"}

    append_result = run_vaultctl_json(
        "note",
        "append",
        "folder-a/new-note.md",
        "extra line",
        "--source",
        "vault",
        "--json",
        home=home,
    )
    assert append_result["source_id"] == "vault"

    appended_read = run_vaultctl_json(
        "note", "read", "folder-a/new-note.md", "--source", "vault", "--json", home=home
    )
    assert appended_read == {"content": "new unique token\nextra line"}

    auto_reindex_search = run_vaultctl_json("search", "unique token", "--json", home=home)
    assert [row["rel_path"] for row in auto_reindex_search] == ["folder-a/new-note.md"]

    delete_result = run_vaultctl_json(
        "note", "delete", "folder-a/new-note.md", "--source", "vault", "--json", home=home
    )
    assert delete_result["source_id"] == "vault"
    after_delete_search = run_vaultctl_json("search", "unique token", "--json", home=home)
    assert after_delete_search == []

    index_note_result = run_vaultctl_json(
        "note", "index", "folder-a/alpha.md", "--source", "vault", "--json", home=home
    )
    assert index_note_result == {"indexed": "folder-a/alpha.md", "source_id": "vault"}

    find_result = run_vaultctl_json("find", "folder-a", "--json", home=home)
    assert find_result == [
        {"source_id": "vault", "rel_path": "folder-a/alpha.md", "title": "Alpha Note"},
        {"source_id": "vault", "rel_path": "folder-a/beta.md", "title": "Beta Note"},
    ]

    tree_result = run_vaultctl_json("tree", "folder-a", "--depth", "2", "--json", home=home)
    assert tree_result == [
        {"source_id": "vault", "rel_path": "folder-a/alpha.md"},
        {"source_id": "vault", "rel_path": "folder-a/beta.md"},
    ]

    context_result = run_vaultctl_json("context", "vault:folder-a/beta.md", "--json", home=home)
    assert context_result == {
        "source_id": "vault",
        "rel_path": "folder-a/beta.md",
        "title": "Beta Note",
        "status": "active",
        "tags": ["macro"],
        "links": [
            {"source_id": "vault", "rel_path": "folder-b/deep.md", "title": "Deep Note"}
        ],
        "backlinks": [
            {"source_id": "vault", "rel_path": "folder-a/alpha.md", "title": "Alpha Note"}
        ],
    }

    graph_outgoing_hop = run_vaultctl_json("graph", "outgoing", "vault:folder-a/alpha.md", "--json", home=home)
    assert [row["rel_path"] for row in graph_outgoing_hop] == ["folder-a/beta.md"]

    graph_outgoing_recursive = run_vaultctl_json(
        "graph",
        "outgoing",
        "vault:folder-a/alpha.md",
        "--recursive",
        "--max-distance",
        "2",
        "--json",
        home=home,
    )
    assert [row["rel_path"] for row in graph_outgoing_recursive] == ["folder-a/beta.md", "folder-b/deep.md"]

    graph_backlinks = run_vaultctl_json(
        "graph",
        "backlinks",
        "vault:folder-b/deep.md",
        "--recursive",
        "--max-distance",
        "2",
        "--json",
        home=home,
    )
    assert [row["rel_path"] for row in graph_backlinks] == ["folder-a/beta.md", "folder-a/alpha.md"]

    graph_broken = run_vaultctl_json("graph", "broken", "--json", home=home)
    broken_targets = {(row["raw_target"], row["resolution_state"]) for row in graph_broken}
    assert ("Missing Note", "dangling") in broken_targets
    assert ("Shared Duplicate", "ambiguous") in broken_targets
    assert all(row["raw_target"] != "Beta Alias" for row in graph_broken)

    graph_orphans = run_vaultctl_json("graph", "orphans", "--json", home=home)
    orphan_titles = {row["title"] for row in graph_orphans}
    assert "Lonely Note" in orphan_titles
    assert "Transcript Lesson" in orphan_titles
    assert "Alpha Note" not in orphan_titles
    assert "Beta Note" not in orphan_titles

    graph_rank = run_vaultctl_json("graph", "rank", "--json", home=home)
    assert [row["title"] for row in graph_rank[:2]] == ["Beta Note", "Deep Note"]

    graph_folder_filtered = run_vaultctl_json(
        "graph",
        "outgoing",
        "vault:folder-a/alpha.md",
        "--recursive",
        "--max-distance",
        "2",
        "--folder",
        "folder-b",
        "--json",
        home=home,
    )
    assert graph_folder_filtered == []

    graph_export_both = run_vaultctl_json(
        "graph",
        "export",
        "vault:folder-a/alpha.md",
        "--recursive",
        "--max-distance",
        "2",
        "--direction",
        "both",
        "--json",
        home=home,
    )
    export_nodes = {node["rel_path"] for node in graph_export_both["nodes"]}
    assert {"folder-a/alpha.md", "folder-a/beta.md", "folder-b/deep.md"}.issubset(export_nodes)

    status_result = run_vaultctl_json("status", "--json", home=home)
    assert status_result == {
        "db_path": str(temp_vault_env["db_path"]),
        "db_exists": True,
        "documents": 7,
        "sources": ["vault", "transcripts"],
    }

    stats_result = run_vaultctl_json("stats", "--json", home=home)
    stats_snapshot = {
        "documents": stats_result["documents"],
        "sections": stats_result["sections"],
        "last_updated_type": type(stats_result["last_updated"]).__name__,
        "sources": stats_result["sources"],
    }
    assert stats_snapshot == {
        "documents": 7,
        "sections": 7,
        "last_updated_type": "str",
        "sources": [
            {
                "id": "transcripts",
                "root": str(temp_vault_env["transcripts_root"]),
                "include_glob": "*.analysis.md",
            },
            {
                "id": "vault",
                "root": str(temp_vault_env["vault_root"]),
                "include_glob": "**/*.md",
            },
        ],
    }

    orphans = run_vaultctl_json("audit", "orphans", "--json", home=home)
    assert {row["title"] for row in orphans} >= {"Alpha Note", "Lonely Note", "Transcript Lesson"}

    linked = run_vaultctl_json("audit", "linked", "--json", home=home)
    assert linked == [
        {"source_id": "vault", "rel_path": "folder-a/alpha.md", "title": "Alpha Note"},
        {"source_id": "vault", "rel_path": "folder-a/beta.md", "title": "Beta Note"},
    ]

    duplicates = run_vaultctl_json("audit", "duplicates", "--json", home=home)
    assert duplicates == [{"source_id": "vault", "title": "Shared Duplicate", "count": 2}]

    # graph path: alpha -> beta -> deep (returns ordered list of nodes)
    graph_path = run_vaultctl_json(
        "graph", "path", "vault:folder-a/alpha.md", "vault:folder-b/deep.md", "--json", home=home
    )
    path_rels = [n["rel_path"] for n in graph_path]
    assert path_rels == ["folder-a/alpha.md", "folder-a/beta.md", "folder-b/deep.md"]
    assert len(graph_path) == 3

    # graph broken --state dangling only
    dangling_only = run_vaultctl_json("graph", "broken", "--state", "dangling", "--json", home=home)
    assert all(row["resolution_state"] == "dangling" for row in dangling_only)
    assert any(row["raw_target"] == "Missing Note" for row in dangling_only)
    assert not any(row["raw_target"] == "Shared Duplicate" for row in dangling_only)

    # search --rank hybrid returns results without error
    hybrid_results = run_vaultctl_json("search", "repo", "--rank", "hybrid", "-n", "5", "--json", home=home)
    assert isinstance(hybrid_results, list)
    assert len(hybrid_results) > 0
    assert all("score" in row and "rel_path" in row for row in hybrid_results)

    # graph export --format dot
    env = os.environ.copy()
    env["HOME"] = str(home)
    src_path = str(Path(__file__).resolve().parents[2] / "src")
    env["PYTHONPATH"] = src_path if "PYTHONPATH" not in env else f"{src_path}:{env['PYTHONPATH']}"
    dot_result = subprocess.run(
        [
            sys.executable, "-m", "vaultctl.cli.app",
            "graph", "export", "vault:folder-a/alpha.md",
            "--recursive", "--max-distance", "2",
            "--format", "dot",
        ],
        env=env, text=True, capture_output=True, check=True,
    )
    assert "digraph" in dot_result.stdout
    assert "folder-a/alpha.md" in dot_result.stdout or "Alpha Note" in dot_result.stdout


def test_mcp_context_depth_uses_graph_traversal(temp_vault_env: dict[str, Path]) -> None:
    home = temp_vault_env["home"]
    run_vaultctl_json("index", "--json", home=home)
    result = run_mcp_tool("context", {"parent_id": "vault:folder-a/alpha.md", "depth": 2}, home=home)

    link_paths = {row["rel_path"] for row in result["links"]}
    assert "folder-a/beta.md" in link_paths
    assert "folder-b/deep.md" in link_paths
    assert result["depth"] == 2


def test_mcp_legacy_adapter_completeness() -> None:
    adapters = legacy_tool_adapters()
    expected_names = {
        "append_to_note",
        "delete_note",
        "get_duplicate_content",
        "get_full_context",
        "get_index_stats",
        "get_most_linked_notes",
        "get_orphaned_notes",
        "get_vault_statistics",
        "get_vault_structure",
        "graph_broken_links",
        "graph_neighbors",
        "graph_path",
        "graph_rank",
        "index_note",
        "read_note",
        "reindex_vault",
        "search_notes",
        "semantic_search",
        "suggest_links",
        "write_note",
    }
    assert set(adapters.keys()) == expected_names
    assert len(adapters) == 20

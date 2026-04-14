---
name: using-vaultctl
description: >
  Complete reference for using vaultctl — the local-first markdown vault CLI.
  Covers search (BM25 + hybrid), indexing, graph traversal, note operations, audits,
  translation, MCP bridge, and config. Use this skill whenever you need to search the
  vault, navigate wikilinks, find orphans, check broken links, read/write notes, or
  run any vaultctl command. Trigger on any question about vault search, note graph,
  wikilinks, vault statistics, MCP tool calls, or vault maintenance.
---

# using-vaultctl

vaultctl is a local-first CLI for markdown knowledge bases. It uses **SQLite FTS5 + BM25**
for full-text search, builds a **resolved wikilink graph** at index time, and exposes everything
via CLI subcommands and an MCP stdio bridge.

## Quick orientation

```
vaultctl <command> [options] [--json]
```

- All commands support `--json` for machine-readable output.
- Bare `vaultctl <query>` (no subcommand) is shorthand for `vaultctl search <query>`.
- DB: `~/.local/share/vaultctl/index.db`
- Config: `~/.config/vaultctl/config.toml`

---

## Configuration

```toml
# ~/.config/vaultctl/config.toml
db_path = "~/.local/share/vaultctl/index.db"

[[sources]]
id = "vault"
root = "~/second-mind"
include_glob = "**/*.md"
exclude_glob = "**/.obsidian/**"

[[sources]]
id = "transcripts"
root = "~/dev/transcriptoz/transcripts"
include_glob = "*.analysis.md"
```

Rules:
- `[[sources]]` must be non-empty if the config file exists.
- If config is absent, default sources are used (hardcoded in `src/vaultctl/core/config.py`).
- Source `id` is the prefix used in note selectors: `vault:notes/foo.md`.

---

## Note selectors

Wherever a command takes a note target, use `source_id:rel_path`:

```
vault:notes/roadmap.md
transcripts:2024-03-01.analysis.md
```

Some commands (e.g. MCP adapters) accept bare `rel_path` + `--source` flag as an alternative.

---

## Search

```bash
vaultctl search "<query>" [options]

# Options
-n 10                          # result count (default 5)
--rank bm25                    # BM25 only (default)
--rank hybrid                  # BM25 + in-degree structural boost
--source vault                 # restrict to one source
--folder notes/projects        # restrict to folder (prefix match on rel_path)
--tag project                  # filter by frontmatter tag
--status active                # filter by frontmatter status
--json                         # machine-readable output
```

Examples:
```bash
vaultctl search "hybrid retrieval" -n 8 --json
vaultctl search "meeting notes" --folder notes/meetings --rank hybrid --json
vaultctl search "todo" --tag project --status active -n 20
```

**Hybrid rank** adds `0.1 * ln(1 + in_degree)` as a bonus, boosting hub notes.
Use it when you want structurally important notes to surface higher.

**Shorthand** (no subcommand needed):
```bash
vaultctl "hybrid retrieval"        # equivalent to: vaultctl search "hybrid retrieval"
```

Output fields per result: `score`, `source_id`, `rel_path`, `title`, `snippet`, `tags`, `status`.

---

## Indexing

```bash
vaultctl index [--source vault] [--full] [--json]
```

- Without `--full`: incremental (only changed files by mtime).
- `--full`: drop and rebuild from scratch.
- `--source vault`: index one source only.

Index also resolves wikilinks (6-step cascade: exact → CI → slug → alias → ambiguous/dangling)
and populates the graph tables (`document_links`, `document_graph_stats`).

**Watch mode** (live reindex on file changes):
```bash
vaultctl watch [--source vault] [--debounce-ms 1000] [--json]
```

---

## Status & Stats

```bash
vaultctl status --json     # DB path, source counts, indexed doc count, last-indexed timestamps
vaultctl stats --json      # corpus stats: doc count, section count, tag list, status breakdown
```

---

## Content discovery

```bash
# Find files by glob pattern
vaultctl find "planner" --source vault -n 20 --json
vaultctl find "*.analysis.md" --source transcripts

# Directory tree
vaultctl tree --source vault --depth 3 --json
vaultctl tree notes/projects --source vault --depth 2

# Full context for a note (content + backlinks + outgoing links)
vaultctl context "vault:notes/roadmap.md" --json
```

---

## Note operations

```bash
vaultctl note read   <path> [--source vault] [--json]
vaultctl note write  <path> <content> [--source vault] [--json]
vaultctl note append <path> <content> [--source vault] [--json]
vaultctl note delete <path> [--source vault] [--json]
vaultctl note index  <path> [--source vault] [--json]   # reindex single note
vaultctl note links  <path> [--source vault] [--json]   # extract outgoing wikilinks
```

Example:
```bash
vaultctl note read "notes/todo.md" --source vault --json
vaultctl note append "notes/todo.md" "\n- finish migration" --source vault
```

---

## Audits

```bash
vaultctl audit orphans    [--source vault] [-n 50] [--json]   # notes with no links in or out
vaultctl audit linked     [--source vault] [-n 20] [--json]   # most-linked notes
vaultctl audit duplicates [--source vault] [-n 20] [--json]   # near-duplicate content
```

---

## Graph commands

vaultctl resolves all `[[wikilinks]]` at index time into one of three states:
- `resolved` — matched to a unique document
- `ambiguous` — matched 2+ documents
- `dangling` — no match found

### Adjacency

```bash
# Outgoing links from a note (1-hop default)
vaultctl graph outgoing "vault:notes/alpha.md" --json

# Multi-hop traversal (BFS, cycle-safe)
vaultctl graph outgoing "vault:notes/alpha.md" --recursive --max-distance 3 --json

# Backlinks (who links to this note)
vaultctl graph backlinks "vault:notes/alpha.md" --json
vaultctl graph backlinks "vault:notes/alpha.md" --recursive --max-distance 2 --json
```

Default `--max-distance` when `--recursive` is set: **3**.

All graph traversal commands support filters:
```
--source vault     restrict to one source
--folder <prefix>  restrict by folder prefix
--tag <tag>        filter by frontmatter tag
--status <status>  filter by frontmatter status
-n 20              max results
```

### Shortest path

```bash
vaultctl graph path "vault:notes/alpha.md" "vault:notes/deep.md" --json
# --max-distance 6  (default; increase for sparse graphs)
```

Returns ordered list of nodes on the shortest resolved path.
Returns empty list if no path exists within `max-distance`.

### Diagnostics

```bash
# Broken links (dangling + ambiguous)
vaultctl graph broken --json
vaultctl graph broken --state dangling --json
vaultctl graph broken --state ambiguous --json
vaultctl graph broken --source vault --json

# Orphans (in_degree=0 AND out_degree=0 — truly isolated)
vaultctl graph orphans --json
vaultctl graph orphans --source vault -n 100 --json
```

### Structural ranking

```bash
# Rank by in-degree (most-linked notes first)
vaultctl graph rank -n 20 --json
vaultctl graph rank --source vault --metric in_degree -n 10 --json
```

### Export

```bash
# Full graph as JSON
vaultctl graph export --format json --json

# DOT format (Graphviz)
vaultctl graph export --format dot > vault.dot

# Ego-graph: subgraph around a note
vaultctl graph export "vault:notes/alpha.md" --recursive --max-distance 3 --direction both --format dot

# direction: out (default) | in | both
```

---

## Translation

Translates markdown while preserving frontmatter, code blocks, and `[[wikilinks]]`.

```bash
vaultctl translate notes/ricerca.md --target en --output notes/en --json
```

Requirements:
```bash
pip install .[llm]
export VAULTCTL_LLM_PROVIDER=openai      # or anthropic, openrouter
export VAULTCTL_LLM_API_KEY=<key>
export VAULTCTL_LLM_BASE_URL=<url>       # optional custom endpoint
```

---

## MCP bridge (legacy clients)

For clients expecting MCP-style tool calls:

```bash
vaultctl mcp serve --transport stdio
```

### Available MCP tool names

| MCP tool | Equivalent CLI |
|---|---|
| `semantic_search(query, n_results)` | `vaultctl search "<query>" -n N` |
| `search_notes(query, n_results)` | `vaultctl search "<query>" -n N` |
| `get_full_context(parent_id, depth)` | `vaultctl context "<id>"` |
| `reindex_vault(force)` | `vaultctl index [--full]` |
| `get_index_stats()` | `vaultctl status` |
| `get_vault_statistics()` | `vaultctl stats` |
| `read_note(note_path)` | `vaultctl note read "<path>"` |
| `write_note(note_path, content)` | `vaultctl note write "<path>" "<content>"` |
| `append_to_note(note_path, content)` | `vaultctl note append "<path>" "<content>"` |
| `delete_note(note_path)` | `vaultctl note delete "<path>"` |
| `suggest_links(note_path)` | `vaultctl note links "<path>"` |
| `index_note(note_path)` | `vaultctl note index "<path>"` |
| `get_vault_structure(root_path, max_depth)` | `vaultctl tree "<root>" --depth N` |
| `get_orphaned_notes()` | `vaultctl audit orphans` |
| `get_most_linked_notes(n_results)` | `vaultctl audit linked -n N` |
| `get_duplicate_content()` | `vaultctl audit duplicates` |
| `graph_neighbors(note, direction, recursive, max_distance, ...)` | `vaultctl graph outgoing/backlinks` |
| `graph_path(source_note, target_note, max_distance)` | `vaultctl graph path` |
| `graph_broken_links(source, folder, state, limit)` | `vaultctl graph broken` |
| `graph_rank(metric, source, folder, tag, status, limit)` | `vaultctl graph rank` |

`get_full_context` with `depth > 1` returns full recursive link traversal up to that depth.

---

## Common workflows

### "What's connected to this note?"
```bash
vaultctl graph outgoing "vault:notes/roadmap.md" --recursive --max-distance 3 --json
vaultctl graph backlinks "vault:notes/roadmap.md" --json
```

### "Show me everything broken in my vault"
```bash
vaultctl graph broken --json         # dangling + ambiguous links
vaultctl graph orphans --json        # isolated notes (no links in or out)
```

### "Find the most important notes by structure"
```bash
vaultctl graph rank -n 20 --json
vaultctl search "topic" --rank hybrid -n 10 --json   # BM25 + in-degree boost
```

### "How are two notes connected?"
```bash
vaultctl graph path "vault:notes/alpha.md" "vault:notes/deep.md" --json
```

### "Search within a project folder"
```bash
vaultctl search "deadline" --folder notes/projects --source vault --json
```

### "Export the graph for Graphviz visualization"
```bash
vaultctl graph export --format dot > vault.dot
dot -Tsvg vault.dot > vault.svg
```

### "Find all notes tagged 'active' with broken links"
```bash
vaultctl graph broken --tag active --json
```

---

## Known footguns

- **Filter order matters**: all filters (`--folder`, `--source`, `--tag`, `--status`) are pushed into SQL *before* `LIMIT`. This is intentional — never apply them in Python after fetching.
- **`--folder` is a prefix match** on `rel_path`, not a glob. `notes/projects` matches `notes/projects/foo.md` and `notes/projects-v2/bar.md`.
- **`--recursive` default depth is 3**, not unlimited. Pass `--max-distance N` to control.
- **Wikilink resolution is source-scoped by default**: `[[Page]]` resolves within the same source first.
- **`vaultctl index` must run before graph commands** — graph tables are populated at index time, not query time.
- **Hybrid rank uses `ln(1 + in_degree)`** — a log scale, so the boost is gentle. It won't swamp BM25 for genuinely irrelevant hub notes.

---

## Install & dev

```bash
pip install -e .             # exposes the vaultctl CLI
pip install .[llm]           # adds translation support

ruff check .                 # lint
mypy src                     # type check
pytest tests/                # run e2e tests
```

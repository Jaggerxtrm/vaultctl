from __future__ import annotations

import argparse
import sys

from vaultctl.cli import audit, graph, index, inspect, mcp, note, search, stats, translate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vaultctl",
        description="Local-first markdown search, indexing, graph navigation, and translation tooling.",
        epilog=(
            "Translate markdown for multilingual corpora:\n"
            "  vaultctl translate notes/ricerca.md --target en --output notes/en\n"
            "\n"
            "For translate, install extras with: pip install .[llm]"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command")

    search_cmd = subparsers.add_parser("search")
    search_cmd.add_argument("query")
    search_cmd.add_argument("--source")
    search_cmd.add_argument("--folder")
    search_cmd.add_argument("--tag")
    search_cmd.add_argument("--status")
    search_cmd.add_argument("-n", type=int, default=5)
    search_cmd.add_argument("--rank", choices=["bm25", "hybrid"], default="bm25")
    search_cmd.add_argument("--json", action="store_true")

    index_cmd = subparsers.add_parser("index")
    index_cmd.add_argument("--source")
    index_cmd.add_argument("--full", action="store_true")
    index_cmd.add_argument("--json", action="store_true")

    watch_cmd = subparsers.add_parser("watch")
    watch_cmd.add_argument("--source")
    watch_cmd.add_argument("--debounce-ms", type=int, default=1000)
    watch_cmd.add_argument("--json", action="store_true")

    status_cmd = subparsers.add_parser("status")
    status_cmd.add_argument("--json", action="store_true")

    note_cmd = subparsers.add_parser("note")
    note_sub = note_cmd.add_subparsers(dest="note_command", required=True)
    for action in ("read", "write", "append", "delete", "index", "links"):
        action_cmd = note_sub.add_parser(action)
        action_cmd.add_argument("path")
        if action in {"write", "append"}:
            action_cmd.add_argument("content")
        action_cmd.add_argument("--source")
        action_cmd.add_argument("--json", action="store_true")

    find_cmd = subparsers.add_parser("find")
    find_cmd.add_argument("pattern")
    find_cmd.add_argument("--source")
    find_cmd.add_argument("--root")
    find_cmd.add_argument("-n", type=int, default=20)
    find_cmd.add_argument("--json", action="store_true")

    tree_cmd = subparsers.add_parser("tree")
    tree_cmd.add_argument("root_arg", nargs="?")
    tree_cmd.add_argument("--source")
    tree_cmd.add_argument("--depth", type=int)
    tree_cmd.add_argument("--json", action="store_true")

    context_cmd = subparsers.add_parser("context")
    context_cmd.add_argument("target")
    context_cmd.add_argument("--json", action="store_true")

    stats_cmd = subparsers.add_parser("stats")
    stats_cmd.add_argument("--json", action="store_true")

    audit_cmd = subparsers.add_parser("audit")
    audit_cmd.add_argument("audit_mode", choices=["orphans", "linked", "duplicates"])
    audit_cmd.add_argument("--source")
    audit_cmd.add_argument("-n", type=int, default=20)
    audit_cmd.add_argument("--json", action="store_true")

    graph_cmd = subparsers.add_parser("graph")
    graph_sub = graph_cmd.add_subparsers(dest="graph_command", required=True)

    def add_shared_filters(command: argparse.ArgumentParser) -> None:
        command.add_argument("--source")
        command.add_argument("--folder")
        command.add_argument("--tag")
        command.add_argument("--status")
        command.add_argument("-n", type=int, default=20)
        command.add_argument("--json", action="store_true")

    outgoing_cmd = graph_sub.add_parser("outgoing")
    outgoing_cmd.add_argument("note")
    outgoing_cmd.add_argument("--recursive", action="store_true")
    outgoing_cmd.add_argument("--max-distance", type=int)
    add_shared_filters(outgoing_cmd)

    backlinks_cmd = graph_sub.add_parser("backlinks")
    backlinks_cmd.add_argument("note")
    backlinks_cmd.add_argument("--recursive", action="store_true")
    backlinks_cmd.add_argument("--max-distance", type=int)
    add_shared_filters(backlinks_cmd)

    path_cmd = graph_sub.add_parser("path")
    path_cmd.add_argument("source_note")
    path_cmd.add_argument("target_note")
    path_cmd.add_argument("--max-distance", type=int, default=6)
    path_cmd.add_argument("--json", action="store_true")

    broken_cmd = graph_sub.add_parser("broken")
    broken_cmd.add_argument("--state", choices=["dangling", "ambiguous", "resolved"])
    add_shared_filters(broken_cmd)

    orphans_cmd = graph_sub.add_parser("orphans")
    add_shared_filters(orphans_cmd)

    rank_cmd = graph_sub.add_parser("rank")
    rank_cmd.add_argument("--metric", default="in_degree")
    add_shared_filters(rank_cmd)

    export_cmd = graph_sub.add_parser("export")
    export_cmd.add_argument("note", nargs="?")
    export_cmd.add_argument("--recursive", action="store_true")
    export_cmd.add_argument("--max-distance", type=int)
    export_cmd.add_argument("--direction", choices=["out", "in", "both"], default="out")
    export_cmd.add_argument("--format", choices=["json", "dot"], default="json")
    add_shared_filters(export_cmd)

    translate_cmd = subparsers.add_parser(
        "translate",
        help="Translate markdown with an LLM provider",
        description=translate.TRANSLATE_DESCRIPTION,
        epilog=translate.TRANSLATE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    translate_cmd.add_argument("path")
    translate_cmd.add_argument("--target", required=True)
    translate_cmd.add_argument("--output")
    translate_cmd.add_argument("--json", action="store_true")

    mcp_cmd = subparsers.add_parser("mcp")
    mcp_sub = mcp_cmd.add_subparsers(dest="mcp_command", required=True)
    mcp_serve = mcp_sub.add_parser("serve")
    mcp_serve.add_argument("--transport", default="stdio")

    return parser


COMMAND_NAMES = {"search", "index", "watch", "status", "note", "find", "tree", "context", "stats", "audit", "graph", "translate", "mcp"}


def main() -> None:
    parser = build_parser()
    argv = sys.argv[1:]
    if argv and argv[0] not in COMMAND_NAMES and not argv[0].startswith("-"):
        argv = ["search", *argv]
    args = parser.parse_args(argv)

    if args.command == "search":
        search.run(args)
    elif args.command == "index":
        index.run_index(args)
    elif args.command == "watch":
        index.run_watch(args)
    elif args.command == "status":
        inspect.run_status(args)
    elif args.command == "note":
        note.run(args)
    elif args.command == "find":
        inspect.run_find(args)
    elif args.command == "tree":
        inspect.run_tree(args)
    elif args.command == "context":
        inspect.run_context(args)
    elif args.command == "stats":
        stats.run(args)
    elif args.command == "audit":
        audit.run(args)
    elif args.command == "graph":
        graph.run(args)
    elif args.command == "translate":
        translate.run(args)
    elif args.command == "mcp" and args.mcp_command == "serve":
        mcp.run(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

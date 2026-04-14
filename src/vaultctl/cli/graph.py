from __future__ import annotations

from argparse import Namespace

from vaultctl.cli.output import emit
from vaultctl.services import graph_service


def _effective_max_distance(recursive: bool, max_distance: int | None) -> int:
    if max_distance is not None:
        return max_distance
    return 3 if recursive else 1


def run(args: Namespace) -> None:
    max_distance = _effective_max_distance(bool(getattr(args, "recursive", False)), getattr(args, "max_distance", None))

    if args.graph_command == "outgoing":
        result = graph_service.outgoing(args.note, args.recursive, max_distance, args.folder, args.tag, args.status, args.n)
    elif args.graph_command == "backlinks":
        result = graph_service.backlinks(args.note, args.recursive, max_distance, args.folder, args.tag, args.status, args.n)
    elif args.graph_command == "path":
        result = graph_service.path(args.source_note, args.target_note, max_distance)
    elif args.graph_command == "broken":
        result = graph_service.broken(args.source, args.folder, args.tag, args.status, args.state, args.n)
    elif args.graph_command == "orphans":
        result = graph_service.orphans(args.source, args.folder, args.tag, args.status, args.n)
    elif args.graph_command == "rank":
        result = graph_service.rank(args.source, args.folder, args.tag, args.status, args.metric, args.n)
    elif args.graph_command == "export":
        result = graph_service.export_graph(args.note, args.source, args.folder, args.direction, args.recursive, max_distance, args.n)
        if not args.json and args.format == "dot":
            print(result["dot"])
            return
    else:
        result = {"error": f"unknown graph command {args.graph_command}"}

    emit(result, args.json)

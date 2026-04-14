from __future__ import annotations

import json
import sys
from typing import Any

from vaultctl.mcp.adapters import legacy_tool_adapters


def serve_stdio() -> None:
    tools = legacy_tool_adapters()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        request = json.loads(line)
        method = request.get("tool")
        args = request.get("args", {})
        if method == "list_tools":
            listed = sorted(set(tools) | {"context"})
            sys.stdout.write(json.dumps({"tools": listed}) + "\n")
            sys.stdout.flush()
            continue
        if method == "context":
            depth = int(args.pop("depth", 1))
            parent_id = args.pop("parent_id", args.pop("target", None))
            if parent_id is None:
                sys.stdout.write(json.dumps({"error": "context requires parent_id or target"}) + "\n")
                sys.stdout.flush()
                continue
            result: Any = tools["get_full_context"](parent_id=parent_id, depth=depth)
            sys.stdout.write(json.dumps({"result": result}, ensure_ascii=False) + "\n")
            sys.stdout.flush()
            continue
        if method not in tools:
            sys.stdout.write(json.dumps({"error": f"unknown tool {method}"}) + "\n")
            sys.stdout.flush()
            continue
        result: Any = tools[method](**args)
        sys.stdout.write(json.dumps({"result": result}, ensure_ascii=False) + "\n")
        sys.stdout.flush()

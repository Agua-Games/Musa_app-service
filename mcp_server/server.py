"""Minimal MCP stdio server (JSON-RPC 2.0, newline-delimited) — zero deps.

Implements the slice of the Model Context Protocol that tool use needs:
``initialize``, ``notifications/initialized``, ``ping``, ``tools/list`` and
``tools/call``. Deliberately small: the server is platform tooling and travels
with the repository.
"""

import json
import sys

PROTOCOL_VERSION = "2025-06-18"

TOOL_SCHEMAS = [
    {
        "name": "list_collections",
        "description": "List the museum's collections with tier, item counts and gate status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_item",
        "description": "Get the full record (ficha) of one piece, with its gate decision and sources.",
        "inputSchema": {
            "type": "object",
            "properties": {"asset_id": {"type": "string", "description": "the piece's asset_id"}},
            "required": ["asset_id"],
        },
    },
    {
        "name": "search",
        "description": "Search the collection; every result cites its asset_id and ficha path.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "validate_ficha",
        "description": "Validate a ficha against the frozen collection contract (v1).",
        "inputSchema": {
            "type": "object",
            "properties": {"ficha": {"type": "object"}},
            "required": ["ficha"],
        },
    },
    {
        "name": "propose_ficha_correction",
        "description": "Propose fixes for a ficha outside the contract — mechanical fixes applied, content fields flagged for human input. Never writes.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ficha": {"type": "object"},
                "folder": {"type": "string", "description": "the item's folder name (identity rule)"},
                "collection": {"type": "string", "description": "the collection folder it lives in"},
            },
            "required": ["ficha"],
        },
    },
    {
        "name": "upload_asset",
        "description": "Upload a binary asset to the museum's bucket. Blocked until M1.3 (object storage) — returns the workaround.",
        "inputSchema": {
            "type": "object",
            "properties": {"asset_id": {"type": "string"}, "path": {"type": "string"}},
        },
    },
    {
        "name": "set_status",
        "description": "Publish or unpublish a piece (writes website_status in its ficha.json).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string"},
                "status": {"type": "string", "enum": ["draft", "published"]},
            },
            "required": ["asset_id", "status"],
        },
    },
    {
        "name": "build_report",
        "description": "Run the build and return the full report — 'why is this piece not on the site?' in one line.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def _result(request_id, payload) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_result(request_id, payload, is_error=False) -> dict:
    return _result(request_id, {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        **({"isError": True} if is_error else {}),
    })


def make_handler(toolbox):
    """Build a JSON-RPC handler bound to a toolbox instance."""

    def handle(msg: dict) -> dict | None:
        method = msg.get("method")
        request_id = msg.get("id")

        if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            return None
        if method == "initialize":
            return _result(request_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "musa-mcp", "version": toolbox.version},
            })
        if method == "ping":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": TOOL_SCHEMAS})
        if method == "tools/call":
            params = msg.get("params") or {}
            name = params.get("name")
            arguments = params.get("arguments") or {}
            func = toolbox.tools.get(name)
            if func is None:
                return _error(request_id, -32601, f"unknown tool {name!r}")
            try:
                return _tool_result(request_id, func(**arguments))
            except TypeError as exc:
                return _error(request_id, -32602, f"invalid arguments for {name}: {exc}")
            except Exception as exc:  # the tool failed; say so, don't die
                return _tool_result(request_id, {"error": str(exc)}, is_error=True)
        if request_id is not None:
            return _error(request_id, -32601, f"method {method!r} not implemented")
        return None

    return handle


def serve(handle, stdin=None, stdout=None) -> None:
    """The stdio loop: newline-delimited JSON-RPC in, responses out."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout

    def send(msg):
        stdout.write(json.dumps(msg, ensure_ascii=False) + "\n")
        stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            send(_error(None, -32700, "parse error — newline-delimited JSON-RPC expected"))
            continue
        reply = handle(msg)
        if reply is not None:
            send(reply)

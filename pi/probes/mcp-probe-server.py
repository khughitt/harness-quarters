#!/usr/bin/env python3
"""A minimal MCP server over stdio for rpc-probe.py: one tool, secret_word, returning
$MCP_PROBE_WORD, so a reply that contains the word proves the tool was called."""
import json
import os
import sys

TOOL = {"name": "secret_word", "description": "Return the secret word.",
        "inputSchema": {"type": "object", "properties": {}}}

for line in sys.stdin:
    message = json.loads(line)
    method, ident = message.get("method"), message.get("id")
    if ident is None:
        continue  # a notification
    if method == "initialize":
        result = {"protocolVersion": message["params"]["protocolVersion"], "capabilities": {"tools": {}},
                  "serverInfo": {"name": "probe", "version": "1"}}
    elif method == "tools/list":
        result = {"tools": [TOOL]}
    elif method == "tools/call":
        result = {"content": [{"type": "text", "text": os.environ["MCP_PROBE_WORD"]}]}
    elif method == "ping":
        result = {}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": ident, "error": {"code": -32601, "message": method}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": ident, "result": result}), flush=True)

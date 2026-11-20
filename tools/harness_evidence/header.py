"""Held-source headers with the historical fifty-line selection policy."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re

from . import discover
from ._protocol import ProtocolError, _fields, validate
from .lines import ref, _finite_float, _reject_constant
from .stream import serialized


_NEWLINE = re.compile(rb"\r\n|\r|\n")


def _lines(handle, size):
    """Universal physical lines, retaining one line and at most one 64 KiB read ahead."""
    pending, line, offset, remaining = b"", bytearray(), 0, size
    while remaining or pending:
        if remaining:
            chunk = handle.read(min(65536, remaining))
            if not chunk:
                raise ProtocolError("short read within header fixed span")
            remaining -= len(chunk)
            pending += chunk
        start = 0
        for match in _NEWLINE.finditer(pending):
            if match.group() == b"\r" and match.end() == len(pending) and remaining:
                break  # A CRLF split across chunks is one physical newline.
            line.extend(pending[start:match.end()])
            raw, line = line, bytearray()
            yield offset, raw
            offset += len(raw)
            start = match.end()
        line.extend(pending[start:-1] if remaining and pending.endswith(b"\r") else pending[start:])
        pending = b"\r" if remaining and pending.endswith(b"\r") else b""
    if line:
        yield offset, line


def _proof(place, number, offset, raw, envelope, paths):
    return {"native_paths": paths, "basis": "native", "rule": "first_fifty_lines",
            "revision": envelope["decoder"]["revision"], "ref": ref(place, number),
            "line": number, "offset": offset, "sha256": hashlib.sha256(raw).hexdigest()}


def _scan(physical_lines, place, envelope, result):
    for line in range(1, 51):
        item = next(physical_lines, None)
        if item is None:
            break
        offset, raw = item
        try:
            record = json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            raise ValueError("header source record must be an object")
        # Optional evidence only comes from records already visited for CWD.
        session = record.get("sessionId") if place.harness == "claude-code" else (
            (record.get("payload") or {}).get("id") if record.get("type") == "session_meta"
            and isinstance(record.get("payload") or {}, dict) else None)
        session_paths = ["sessionId"] if place.harness == "claude-code" else ["payload.id"]
        if result["header"]["session"] is None and isinstance(session, str) and session:
            result["header"]["session"] = session
            result["provenance"]["session"] = _proof(place, line, offset, raw, envelope, session_paths)
        timestamp = record.get("timestamp")
        if result["header"]["start_ms"] is None and isinstance(timestamp, str):
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                start = int(parsed.timestamp() * 1000) if parsed.tzinfo is not None else None
            except (ValueError, OverflowError, OSError):
                pass
            else:
                # A timestamp without an offset states no UTC instant.
                if start is not None:
                    result["header"]["start_ms"] = start
                    result["provenance"]["start_ms"] = _proof(place, line, offset, raw, envelope, ["timestamp"])
        version = record.get("version") if place.harness == "claude-code" else (
            (record.get("payload") or {}).get("cli_version") if record.get("type") == "session_meta"
            and isinstance(record.get("payload") or {}, dict) else None)
        if result["harness_version"] is None and isinstance(version, str) and version:
            result["harness_version"] = version
        if record.get("cwd"):
            serialized(record["cwd"])  # Only selected evidence must be finite wire JSON.
            result["header"]["cwd"] = record["cwd"]
            result["provenance"]["cwd"] = _proof(place, line, offset, raw, envelope, ["cwd"])
            break
        if record.get("type") == "session_meta":
            payload = record.get("payload") or {}
            serialized(payload.get("cwd"))
            result["header"]["cwd"] = payload.get("cwd")
            result["provenance"]["cwd"] = _proof(place, line, offset, raw, envelope, ["payload.cwd"])
            break


def _file(source, number, place, adapter, request, envelope):
    physical = Path(source.get("read_path") or source["path"])
    result = {**envelope, "request": request["id"], "object": "header", "file": number,
              "path": source["path"], "harness": place.harness, "harness_version": None,
              "status": "ok", "header": {"session": None, "cwd": None, "start_ms": None},
              "provenance": {}, "error": None}
    try:
        with physical.open("rb") as handle:
            info = os.fstat(handle.fileno())
            if source["identity"] != {"device": info.st_dev, "inode": info.st_ino}:
                raise ProtocolError("header source identity changed")
            if info.st_size < source["size"]:
                raise ProtocolError("header source is shorter than its fixed span")
            adapter.header(place, handle, size=source["size"], envelope=envelope, result=result)
    except (OSError, UnicodeError, ValueError, AttributeError, RecursionError) as error:
        result.update(status="vanished" if isinstance(error, FileNotFoundError) else
                      "unreadable" if isinstance(error, OSError) else "invalid_source",
                      error={"type": type(error).__name__, "message": str(error)})
    return result


def _request(request):
    _fields(request, {"id", "files", "roots"}, {"id", "files", "roots"})
    if not isinstance(request["roots"], list) or not request["roots"]:
        raise ProtocolError("header requires explicit roots")
    # Reuse held-source validation without introducing a second identity vocabulary.
    validate({**request, "extract": "index"})
    paths = []
    for source in request["files"]:
        _fields(source, {"path", "read_path", "size", "identity"}, {"path", "size", "identity"})
        paths.append(source["path"])
    if len(set(paths)) != len(paths):
        raise ProtocolError("duplicate header source path")
    return request


def run(stdin, stdout, stderr, envelope):
    """One complete ordered batch per JSON line; protocol faults end the command."""
    from . import index_adapters  # The Claude adapter imports this module's selection.
    for line in stdin:
        try:
            request = _request(json.loads(line, parse_constant=_reject_constant, parse_float=_finite_float))
            roots = discover.roots(explicit=[(r["harness"], Path(r["path"])) for r in request["roots"]])
            # Validate every selection before emitting a partial batch.
            places = []
            for source in request["files"]:
                try:
                    place = discover.place_of(Path(source["path"]), roots)
                except ValueError as error:
                    raise ProtocolError(str(error)) from error
                places.append((place, index_adapters.for_source(place, extract=False)))
            for number, (source, (place, adapter)) in enumerate(zip(request["files"], places)):
                stdout.write(serialized(_file(source, number, place, adapter, request, envelope)) + "\n")
                stdout.flush()
            stdout.write(serialized({**envelope, "request": request["id"], "object": "request_end",
                                     "files": len(request["files"])}) + "\n")
            stdout.flush()
        except (ValueError, RecursionError, ProtocolError) as error:
            print("protocol error: " + str(error).replace("\n", " "), file=stderr, flush=True)
            return 2
    return 0

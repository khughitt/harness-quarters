"""Bounded, line-resilient extraction of native Codex meter readings."""
import json
from pathlib import Path

from . import discover
from .index_codex import codex_rate_limits
from .lines import Place, lines, ref, sha256


def _file(source, base, roots):
    path = Path(source["path"])
    try:
        place = discover.place_of(path, roots)
    except ValueError:
        place = Place("codex", "file", None, "explicit", str(path), path)
    yield {**base, "object": "file_start", "key": "file", "path": source["path"]}
    offset, count, malformed = 0, 0, 0
    status = "ok"
    try:
        for line in lines(path, source["size"]):
            start = offset
            offset += len(line.raw)
            if b"rate_limits" not in line.raw:
                continue
            try:
                record = json.loads(line.raw)
            except (ValueError, RecursionError):
                malformed += 1
                continue
            meter = codex_rate_limits(record)
            if meter is None:
                continue
            if meter["status"] == "malformed":
                malformed += 1
                continue
            count += 1
            yield {**base, "object": "meter_reading", "key": f"M{line.number}",
                   "line": line.number, "offset": start, "ref": ref(place, line.number),
                   "sha256": sha256(line), "at_ms": meter["at_ms"],
                   "balance": meter["balance"], "weekly_used_percent": meter["weekly_used_percent"]}
    except (OSError, UnicodeError) as error:
        status = "vanished" if isinstance(error, FileNotFoundError) else "unreadable"
    yield {**base, "object": "file_end", "key": "end", "status": status,
           "count": count, "malformed_lines": malformed}


def objects(request, envelope):
    """Stream a meter scan, retaining one physical line at a time."""
    roots = discover.roots(explicit=[(r["harness"], Path(r["path"])) for r in request.get("roots") or []
                                     if r["harness"] == "codex"])
    base = {**envelope, "request": request["id"]}
    for number, source in enumerate(request["files"]):
        yield from _file(source, {**base, "file": number, "harness": "codex", "harness_version": None}, roots)
    yield {**base, "object": "request_end", "files": len(request["files"])}

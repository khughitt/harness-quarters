"""Bounded held-source index framing, prefix-proved resume and terminal restarts."""
from dataclasses import asdict, replace
import copy
import hashlib
import os
from pathlib import Path

from . import discover, index_events
from .lines import Place
from ._protocol import ProtocolError, validate


def _prefix(handle, limit):
    digest, count, offset, last = hashlib.sha256(), 0, 0, b""
    while offset < limit:
        raw = handle.read(min(65536, limit - offset))
        if not raw:
            raise ProtocolError("short read within index prefix")
        digest.update(raw)
        count += raw.count(b"\n")
        offset += len(raw)
        last = raw[-1:]
    return digest, count, not limit or last == b"\n"


def _binding(source, place, envelope, text):
    return {"decoder": envelope["decoder"], "identity": source["identity"],
            "path": str(place.path), "path_facts": discover.path_facts(place), "text": text}


def _checkpoint(state, digest, binding, *, seed=False):
    return {"next_line": state.pop("next_line", 1), "next_offset": state.pop("next_offset", 0),
            "digest": digest, "index": {**binding, "digest": digest,
            "mode": "restart" if seed else "resume", "native": state}}


def _compatible(old, binding):
    index = old["index"]
    return (all(index.get(k) == v for k, v in binding.items())
            and index.get("digest") == old["digest"]
            and index.get("mode") in {"resume", "restart"}
            and isinstance(index.get("native"), dict))


def _file(source, number, roots, request, envelope):
    logical = Path(source["path"])
    physical = Path(source.get("read_path") or source["path"])
    try:
        place = discover.place_of(logical, roots)
    except ValueError:
        place = Place("claude-code", "file", None, "explicit", str(logical), logical)
    if place.harness != "claude-code":
        raise ProtocolError("index extraction currently supports Claude only")
    place = replace(place, read_path=physical)
    binding = _binding(source, place, envelope, request.get("text", False))
    base = {**envelope, "request": request["id"], "file": number,
            "harness": place.harness, "harness_version": None}
    location = asdict(place)
    location.pop("path")
    location.pop("read_path")
    start = {**base, "object": "file_start", "key": "file", "path": str(logical),
             "place": location, "filename_identity": None,
             "path_facts": discover.path_facts(place), "replaces": "all"}
    try:
        handle = physical.open("rb")
    except (OSError, UnicodeError) as error:
        yield start
        yield {**base, "object": "coverage", "key": "coverage", "records": [], "fields": [],
               "malformed": 0, "partial_tail": False}
        yield {**base, "object": "file_end", "key": "end", "count": 1, "offset": 0,
               "state": None, "restart": None,
               "status": "vanished" if isinstance(error, FileNotFoundError) else "unreadable"}
        return
    with handle:
        info = os.fstat(handle.fileno())
        if source["identity"] != {"device": info.st_dev, "inode": info.st_ino}:
            raise ProtocolError("index source identity changed")
        if info.st_size < source["size"]:
            raise ProtocolError("index source is shorter than its fixed span")
        old = source.get("state")
        digest, state = hashlib.sha256(), {"next_line": 1, "next_offset": 0}
        if old is not None and old["next_offset"] <= source["size"] and _compatible(old, binding):
            prior, lines, boundary = _prefix(handle, old["next_offset"])
            if boundary and lines + 1 == old["next_line"] and prior.hexdigest() == old["digest"]:
                state = copy.deepcopy(old["index"]["native"])
                state.update(next_line=old["next_line"], next_offset=old["next_offset"])
                digest = prior
                if old["index"]["mode"] == "resume":
                    start["replaces"] = {"from_line": old["next_line"]}
        handle.seek(state["next_offset"])
        yield start

        def physical_lines():
            offset = state["next_offset"]
            while offset < source["size"]:
                raw = handle.readline(source["size"] - offset)
                if not raw:
                    raise ProtocolError("short read within index fixed span")
                if raw.endswith(b"\n"):
                    digest.update(raw)
                yield offset, raw
                offset += len(raw)

        count, restart = 0, None
        try:
            for value in index_events.extract(physical_lines(), state, place=place, text=request.get("text", False)):
                for provenance in value.get("provenance", {}).values():
                    provenance["revision"] = envelope["decoder"]["revision"]
                count += 1
                yield {**base, **value, "harness_version": value.get("identity", {}).get("version")}
        except index_events.Restart as signal:
            if not isinstance(signal.reason, str) or not signal.reason or not isinstance(signal.seed, dict):
                raise ProtocolError("invalid native restart signal") from signal
            seed = copy.deepcopy(signal.seed)
            seed.update(next_line=1, next_offset=0)
            restart = {"reason": signal.reason,
                       "seed": _checkpoint(seed, hashlib.sha256(b"").hexdigest(), binding, seed=True)}
        offset = state["next_offset"]
        checkpoint = None if restart else _checkpoint(state, digest.hexdigest(), binding)
        yield {**base, "object": "file_end", "key": "end", "status": "ok", "restart": restart,
               "offset": offset, "state": checkpoint, "count": count}


def objects(request: dict, envelope: dict):
    """Validate then frame files independently; retain only the current file's state."""
    validate(request)
    if request.get("extract") != "index":
        raise ProtocolError("index stream requires extract:index")
    roots = discover.roots(explicit=[(r["harness"], Path(r["path"])) for r in request.get("roots") or []])
    for number, source in enumerate(request["files"]):
        yield from _file(source, number, roots, request, envelope)
    yield {**envelope, "request": request["id"], "object": "request_end", "files": len(request["files"])}

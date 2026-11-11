"""Framed whole-prefix decoding and transport-independent replay checkpoints."""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import re

from . import copies, discover, records
from .lines import Place, UnknownFormat, decode, detect_format, lines, ref, sha256
from .links import native_links


class ProtocolError(Exception):
    """The request, rather than a source file, violates the wire contract."""


def serialized(value, *, canonical=False):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=canonical, allow_nan=False)


def _fields(value, allowed, required=()):
    if not isinstance(value, dict) or value.keys() - set(allowed) or set(required) - value.keys():
        raise ProtocolError("invalid object fields")


def _integer(value, minimum):
    if type(value) is not int or value < minimum:
        raise ProtocolError("expected an integer in range")


def _path(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ProtocolError("expected a nonempty path string")


def validate(value):
    """Reject the complete request before any response for it is emitted."""
    _fields(value, {"id", "files", "roots", "context", "cross_file", "text", "raw"}, {"id", "files"})
    if type(value["id"]) is not int:
        raise ProtocolError("id must be an integer")
    if not isinstance(value["files"], list):
        raise ProtocolError("files must be an array")
    for file in value["files"]:
        _fields(file, {"path", "read_path", "size", "state"}, {"path", "size"})
        _path(file["path"])
        if file.get("read_path") is not None:
            _path(file["read_path"])
        _integer(file["size"], 0)
        state = file.get("state")
        if state is not None:
            _fields(state, {"next_line", "next_offset", "digest"}, {"next_line", "next_offset", "digest"})
            _integer(state["next_line"], 1)
            _integer(state["next_offset"], 0)
            if not isinstance(state["digest"], str) or re.fullmatch("[0-9a-f]{64}", state["digest"]) is None:
                raise ProtocolError("invalid checkpoint digest")
    roots = value.get("roots")
    if roots is not None:
        if not isinstance(roots, list):
            raise ProtocolError("roots must be an array or null")
        for root in roots:
            _fields(root, {"harness", "path"}, {"harness", "path"})
            if root["harness"] not in ("claude-code", "codex"):
                raise ProtocolError("unsupported root harness")
            _path(root["path"])
    if not isinstance(value.get("context", []), list):
        raise ProtocolError("context must be an array")
    for path in value.get("context", []):
        _path(path)
    for key in ("cross_file", "text", "raw"):
        if type(value.get(key, False)) is not bool:
            raise ProtocolError(f"{key} must be boolean")
    return value


@dataclass
class _File:
    source: dict
    place: Place
    read: records.FileRead
    status: str
    positions: dict
    state: dict
    unresolved: list
    harness_version: str | None


def _read(source, roots, inherited):
    logical = Path(source["path"])
    physical = Path(source.get("read_path") or source["path"])
    try:
        place = discover.place_of(logical, roots)
    except ValueError:
        place = Place("unknown", "file", None, "explicit", str(logical), logical)
    place = replace(place, read_path=physical)
    status, fmt = "ok", None
    positions, next_line, next_offset = {}, 1, 0
    unresolved = []
    version = None

    def lookup(thread):
        found = inherited.get(thread)
        if found is None and thread not in unresolved:
            unresolved.append(thread)
        return found

    try:
        size = min(source["size"], physical.stat().st_size)
        with physical.open("rb") as handle:
            data = handle.read(size)
        size = len(data)
        try:
            fmt = detect_format(data, size)
        except UnknownFormat:
            status = "unknown_format"
        if fmt is not None:
            place = replace(place, harness="codex" if fmt == "codex" else "claude-code")
            reader = {"claude": records.claude_read, "sdk": records.sdk_read, "codex": records.codex_read}[fmt]
            read = reader(place, size, lookup, data=data) if fmt == "codex" else reader(place, size, data=data)
        else:
            read = records.FileRead(place, [], [])
        offset = 0
        for line in lines(data, size):
            if fmt == "claude" and version is None and line.complete:
                native = decode(line)
                candidate = native.get("version") if native else None
                if isinstance(candidate, str) and candidate:
                    version = candidate
            end = offset + len(line.raw)
            positions[line.number] = {"offset": offset, "end": end, "sha256": sha256(line),
                                      "raw": line.raw.decode("utf-8", errors="surrogateescape") if source.get("_raw") else None}
            if line.complete:
                next_line, next_offset = line.number + 1, end
            else:
                next_line, next_offset = line.number, offset
            offset = end
        if fmt is None:
            # Unknown syntax stays unknown; only malformed/truncated physical lines are unparsed.
            read.unparsed = [{"_line": line.number,
                              "reason": "malformed" if line.complete else "truncated"}
                             for line in lines(data, size)
                             if not line.complete or decode(line) is None]
    except (OSError, UnicodeError) as error:
        status = "vanished" if isinstance(error, FileNotFoundError) else "unreadable"
        read = records.FileRead(place, [], [])
        positions, next_line, next_offset = {}, 1, 0
    state = {"next_line": next_line, "next_offset": next_offset, "digest": hashlib.sha256(b"").hexdigest()}
    return _File(source, place, read, status, positions, state, unresolved,
                 version if fmt == "claude" else read.header.get("cli_version"))


def _public(value: dict, text: bool) -> dict:
    """Project reader fields explicitly; native metadata keys are data, not field names."""
    out = {k: v for k, v in value.items() if not k.startswith("_")}
    if not text:
        for key in ("text", "turn_end_message", "prompt_source"):
            out.pop(key, None)
        for key in ("call", "execution"):
            if key in out:
                out[key] = {k: v for k, v in out[key].items() if k != "command"}
    return out


def _objects(file, text, raw, copy_scope, *, lexical_keys=False):
    grouped = {}
    for record in file.read.records:
        grouped.setdefault(record["line"], []).append(record)
    unparsed = {r["_line"]: r for r in file.read.unparsed}
    for number in sorted(grouped.keys() | unparsed.keys()):
        position = file.positions[number]
        for record in sorted(grouped.get(number, []),
                             key=lambda r: str(r.get("block", "")) if lexical_keys else r.get("block", -1)):
            value = _public(record, text)
            key = f"L{number}" + (f"#{record['block']}" if "block" in record else "")
            value.update(object="record", key=key, offset=position["offset"], end=position["end"])
            if "copy" in record:
                value["copy_scope"] = copy_scope
            if raw:
                value["raw"] = position["raw"]
            yield value
        if number in unparsed:
            problem = unparsed[number]
            value = {"object": "unparsed", "key": f"L{number}", "ref": ref(file.place, number),
                     "sha256": position["sha256"], "line": number, "offset": position["offset"],
                     "end": position["end"], "reason": problem["reason"],
                     "provisional": problem["reason"] == "truncated"}
            if raw:
                value["raw"] = position["raw"]
            yield value


def _emit_file(file, index, envelope, request):
    text, raw = request.get("text", False), request.get("raw", False)
    scope = sorted({f["path"] for f in request["files"]}) if request.get("cross_file") else [file.source["path"]]
    old = file.source.get("state")
    digest, prior = hashlib.sha256(), hashlib.sha256()
    for value in _objects(file, text, raw, scope, lexical_keys=True):
        if value.get("provisional"):
            continue
        encoded = (serialized(value, canonical=True) + "\n").encode("ascii")
        if value["line"] < file.state["next_line"]:
            digest.update(encoded)
        if old is not None and value["line"] < old["next_line"]:
            prior.update(encoded)
    file.state["digest"] = digest.hexdigest()
    valid = old is not None and old["next_line"] <= file.state["next_line"] \
        and old["digest"] == prior.hexdigest()
    if valid:
        boundary = file.positions.get(old["next_line"], {}).get("offset", file.state["next_offset"])
        valid = boundary == old["next_offset"]
    replacement = {"from_line": old["next_line"]} if valid else "all"
    base = {**envelope, "file": index}
    location = asdict(file.place)
    location.pop("path")
    location.pop("read_path")
    yield {**base, "object": "file_start", "key": "file", "path": file.source["path"],
           "harness": file.place.harness, "harness_version": file.harness_version,
           "place": location, "filename_identity": discover.filename_identity(file.place.harness, file.place.path),
           "replaces": replacement}
    count = 0
    for value in _objects(file, text, raw, scope):
        if not valid or value["line"] >= old["next_line"]:
            count += 1
            yield {**base, **value}
    count += 1
    linked = native_links(file.read) if file.status == "ok" else []
    for link in linked:
        if "copy" in link:
            link["copy_scope"] = scope
    yield {**base, "object": "session", "key": "session", "header": _public(file.read.header, text),
           "links": linked, "unresolved_forks": file.unresolved}
    yield {**base, "object": "file_end", "key": "end", "status": file.status,
           "offset": file.state["next_offset"], "state": file.state, "count": count}


def objects(request, envelope):
    """Yield one request, buffering all reads only when copy marking requires it."""
    explicit = request.get("roots")
    roots = discover.roots(explicit=None if explicit is None else [(r["harness"], Path(r["path"])) for r in explicit])
    inherited = {}
    # Context is evidence only: never emitted and never included in copy scope.
    for path in request.get("context", []):
        try:
            context = _read({"path": path, "size": Path(path).stat().st_size}, roots, {})
        except (OSError, UnicodeError):
            continue
        if context.place.harness == "codex" and context.status == "ok" and context.read.header.get("session"):
            inherited.setdefault(context.read.header["session"], set()).update(context.read.header["turn_ids"])
        del context
    sources = [{**f, "_raw": request.get("raw", False)} for f in request["files"]]
    base = {**envelope, "request": request["id"]}
    if request.get("cross_file"):
        files = [_read(source, roots, inherited) for source in sources]

        def priority(read):
            root = discover._root_of(read.place.path, roots)
            return (roots.index(root) if root is not None else 0, read.place.relpath)

        reads = sorted([f.read for f in files if f.status == "ok"], key=priority)
        copies.mark_resume_copies(reads)
        copies.mark_duplicate_files(reads)
        for i, file in enumerate(files):
            yield from _emit_file(file, i, base, request)
    else:
        for i, source in enumerate(sources):
            yield from _emit_file(_read(source, roots, inherited), i, base, request)
    yield {**base, "object": "request_end", "files": len(sources)}


def run(stdin, stdout, stderr, envelope):
    for line in stdin:
        try:
            request = validate(json.loads(line, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid JSON constant"))))
        except (ValueError, RecursionError, ProtocolError) as error:
            print("protocol error: " + str(error).replace("\n", " "), file=stderr, flush=True)
            return 2
        for value in objects(request, envelope):
            stdout.write(serialized(value) + "\n")
            stdout.flush()
    return 0

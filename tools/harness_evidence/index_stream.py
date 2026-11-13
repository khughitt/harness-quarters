"""Bounded held-source index framing, prefix-proved resume and terminal restarts."""
from dataclasses import asdict, replace
from collections.abc import Callable
import copy
import hashlib
import os
from pathlib import Path

from . import discover, index_events
from .lines import Place
from ._protocol import ProtocolError, validate


def _factor_provenance(event: dict, defaults: dict) -> dict:
    """Audit complete native proofs before encoding exact sparse replacements."""
    proofs = event.get("provenance")
    if not isinstance(proofs, dict) or proofs.keys() != defaults.keys():
        raise ProtocolError("index provenance fields differ from declarations")
    required = {"native_paths", "coverage_keys", "basis", "rule", "ref", "revision"}
    sparse = {}
    for field, proof in proofs.items():
        if (not isinstance(proof, dict) or not required <= proof.keys()
                or proof.keys() - required - {"source"}):
            raise ProtocolError("index provenance attributes are missing or unknown")
        for name in ("native_paths", "coverage_keys"):
            value = proof[name]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ProtocolError("index provenance arrays must contain strings")
        if (not isinstance(proof["basis"], str)
                or proof["basis"] not in {"native", "convention", "heuristic"}
                or not isinstance(proof["rule"], str) or not proof["rule"]
                or not isinstance(proof["ref"], str) or not proof["ref"]
                or not isinstance(proof["revision"], str)
                or proof["revision"] != event["decoder"]["revision"]):
            raise ProtocolError("index provenance basis, rule, ref or revision is invalid")
        default = defaults[field]
        if ("source" in proof and not isinstance(proof["source"], str)
                or "source" in default and "source" not in proof):
            raise ProtocolError("index provenance source is invalid or cannot be deleted")
        changes = {}
        for name, value in proof.items():
            if name == "revision":
                continue
            inherited = event["ref"] if name == "ref" else default.get(name)
            if name not in default and name != "ref" or value != inherited:
                changes[name] = list(value) if isinstance(value, list) else value
        if changes:
            sparse[field] = changes
    return sparse


def _plain_declaration(proof):
    """Declarations contain only built-in strings and string arrays."""
    if type(proof) is not dict:
        return False
    for key, value in proof.items():
        if type(key) is not str:
            return False
        if type(value) is str:
            continue
        if type(value) is not list:
            return False
        for item in value:
            if type(item) is not str:
                return False
    return True


def _provenance_encoder(defaults: dict) -> Callable[[dict], dict]:
    """Validate owned declarations once, then audit every supplied resolved change."""
    attributes = {"native_paths", "coverage_keys", "basis", "rule"}
    if (type(defaults) is not dict or not all(type(field) is str for field in defaults)
            or defaults.keys() != index_events.PROVENANCE.keys()):
        raise ProtocolError("index provenance declaration fields are missing or unknown")
    for proof in defaults.values():
        if (not _plain_declaration(proof) or not attributes <= proof.keys()
                or proof.keys() - attributes - {"source"}):
            raise ProtocolError("index provenance declaration attributes are missing or unknown")
    defaults = copy.deepcopy(defaults)
    prototypes = {field: {**proof, "ref": "checked", "revision": "checked"}
                  for field, proof in defaults.items()}
    _factor_provenance({"provenance": prototypes, "ref": "checked",
                        "decoder": {"revision": "checked"}}, defaults)
    allowed = attributes | {"source", "ref"}

    def encode(event: dict) -> dict:
        if type(event) is not dict:
            raise ProtocolError("index provenance event must be an object")
        changes, reference, decoder = event.get("provenance"), event.get("ref"), event.get("decoder")
        if (type(changes) is not dict or not isinstance(reference, str) or not reference
                or type(decoder) is not dict or not isinstance(decoder.get("revision"), str)):
            raise ProtocolError("index provenance changes or envelope is invalid")
        sparse = {}
        for field, change in changes.items():
            if type(field) is not str or field not in defaults:
                raise ProtocolError("index provenance change field is unknown")
            if (type(change) is not dict or not all(type(name) is str for name in change)
                    or change.keys() - allowed):
                raise ProtocolError("index provenance change attributes are invalid or unknown")
            proof = {**defaults[field], "ref": reference, "revision": decoder["revision"], **change}
            audited = _factor_provenance({**event, "provenance": {field: proof}},
                                         {field: defaults[field]})
            sparse.update(audited)
        return sparse
    return encode


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
    defaults = index_events.provenance_defaults()
    encode_provenance = _provenance_encoder(defaults)
    start = {**base, "provenance_format": "defaults/1",
             "provenance_defaults": copy.deepcopy(defaults),
             "object": "file_start", "key": "file", "path": str(logical),
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
                remaining = source["size"] - offset
                raw = handle.readline(remaining)
                if not raw or not raw.endswith(b"\n") and len(raw) < remaining:
                    raise ProtocolError("short read within index fixed span")
                if raw.endswith(b"\n"):
                    digest.update(raw)
                yield offset, raw
                offset += len(raw)

        count, restart = 0, None
        try:
            for value in index_events.extract(physical_lines(), state, place=place, text=request.get("text", False)):
                event = {**base, **value, "harness_version": value.get("identity", {}).get("version")}
                if event["object"] == "index_event":
                    event["provenance"] = encode_provenance(event)
                count += 1
                yield event
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

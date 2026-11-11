"""Package-local capability view; explicit checkout builds use catalogued samples only.

Field names are dotted decoded paths (header.* and links[].* for session evidence).
Native paths are dotted JSON keys, with [] visiting array items. Transport fields
and values derived only from filenames/defaults are not native field evidence.
"""
import hashlib
import json
from pathlib import Path
import tomllib

from . import DECODER_VERSION, SCHEMA

EVIDENCE_RULE = ("synthetic samples establish decoder conformance; observed samples or probes "
                 "establish emission; absent from a sample means unobserved")
ARTIFACT = Path(__file__).with_name("capabilities.json")

# Only paths actually consumed by the readers: retained raw metadata is not a capability.
DECLARED: dict[str, dict[str, list[str]]] = {
    "claude-code": {
        "at": ["timestamp"],
        "session": ["sessionId", "session_id", "agentId"],
        "agent": ["agentId"],
        "kind": ["type", "subtype", "attachment.type"],
        "block_type": ["message.content[].type"],
        "text": ["message.content", "message.content[].text", "message.content[].thinking",
                 "message.content[].input", "message.content[].content", "content", "attachment.prompt"],
        "message_id": ["message.id"],
        "model.value": ["message.model", "toolUseResult.resolvedModel"],
        "stop_reason": ["message.stop_reason"],
        "stop_class": ["message.stop_reason"],
        "synthetic": ["message.model"],
        "encrypted": ["message.content[].type"],
        "call.id": ["message.content[].id", "message.content[].tool_use_id"],
        "call.tool": ["message.content[].name"],
        "call.command": ["message.content[].input.command"],
        "call.is_error": ["message.content[].is_error"],
        "origin_kind": ["origin.kind", "attachment.origin.kind"],
        "origin.native_kind": ["origin.kind", "attachment.origin.kind"],
        "origin.flags": ["isMeta", "isCompactSummary"],
        "origin.markers": ["message.content", "content", "attachment.prompt"],
        "origin.unrecognized_tag.lead": ["message.content", "content", "attachment.prompt"],
        "origin.unrecognized_tag.joined": ["message.content", "content", "attachment.prompt"],
        "prompt_source": ["promptSource"],
        "queued": ["attachment.type"],
        "flags": ["isMeta", "isCompactSummary", "type", "subtype"],
        "copy": ["type"],
        "copy_basis": ["type"],
        "copy_rule": ["type"],
        "readable_text": ["type", "message.content[].type"],
        "waits_for_user": ["message.content[].name"],
        "header.session": ["sessionId", "session_id", "agentId"],
        "header.agent": ["agentId"],
        "header.cwd": ["cwd"],
        "header.entrypoint": ["entrypoint"],
        "header.first_at": ["timestamp"],
        "header.last_at": ["timestamp"],
        "header.subagent": ["isSidechain"],
        "header.subagent_basis": ["isSidechain"],
        "header.forked": ["type"],
        "header.uuids": ["uuid"],
        "header.markers": ["subtype"],
        "header.models[].value": ["message.model", "requestedModel",
                                  "toolUseResult.resolvedModel", "message.content[].input.model"],
        "dispatch.call": ["parent_tool_use_id"],
        "links[].target": ["parent_tool_use_id", "toolUseResult.agentId"],
    },
    "codex": {
        "at": ["timestamp"],
        "session": ["payload.id"],
        "kind": ["type", "payload.type", "payload.item.type"],
        "block_type": ["payload.content[].type", "payload.type"],
        "text": ["payload.content", "payload.arguments", "payload.input", "payload.output",
                 "payload.summary", "payload.item.content"],
        "message_id": ["payload.id", "payload.item.id"],
        "model.value": ["payload.model", "payload.base_instructions.provenance.model"],
        "phase": ["payload.phase", "payload.item.phase"],
        "answer_phase": ["payload.phase"],
        "encrypted": ["payload.content[].type"],
        "call.id": ["payload.call_id", "payload.id"],
        "call.tool": ["payload.name", "payload.type"],
        "call.command": ["payload.arguments"],
        "call.is_error": ["payload.output"],
        "origin.markers": ["payload.content"],
        "origin.unrecognized_tag.lead": ["payload.content"],
        "origin.unrecognized_tag.joined": ["payload.content"],
        "flags": ["type", "payload.type", "payload.role", "payload.item.questions"],
        "turn_id": ["payload.turn_id"],
        "turn_end_message": ["payload.last_agent_message"],
        "abort_reason": ["payload.reason"],
        "readable_text": ["payload.role", "payload.type"],
        "waits_for_user": ["payload.name"],
        "copy": ["type", "payload.type"],
        "copy_basis": ["type", "payload.type"],
        "copy_rule": ["type", "payload.type"],
        "original": ["payload.item.id"],
        "header.session": ["payload.id"],
        "header.parent": ["payload.parent_thread_id", "payload.source.subagent.thread_spawn.parent_thread_id"],
        "header.agent_path": ["payload.source.subagent.thread_spawn.agent_path"],
        "header.depth": ["payload.source.subagent.thread_spawn.depth"],
        "header.inherited_id": ["payload.id"],
        "header.child": ["payload.parent_thread_id", "payload.source.subagent.thread_spawn.parent_thread_id",
                         "payload.thread_source"],
        "header.child_basis": ["payload.parent_thread_id", "payload.source.subagent.thread_spawn.parent_thread_id",
                               "payload.thread_source"],
        "header.forked": ["type"],
        "header.cwd": ["payload.cwd"],
        "header.entrypoint": ["payload.originator"],
        "header.cli_version": ["payload.cli_version"],
        "header.first_at": ["timestamp"],
        "header.last_at": ["timestamp"],
        "header.turn_ids": ["payload.turn_id"],
        "header.own_turn_ids": ["payload.turn_id"],
        "header.models[].value": ["payload.model", "payload.base_instructions.provenance.model",
                                  "payload.arguments"],
        "links[].target": ["payload.parent_thread_id", "payload.source.subagent.thread_spawn.parent_thread_id",
                           "payload.item.agent_thread_id"],
        "links[].call.id": ["payload.item.id"],
    },
}


def _values(value, path):
    if not path:
        return [] if value is None else [value]
    key, _, rest = path.partition(".")
    many = key.endswith("[]")
    child = value.get(key[:-2] if many else key) if isinstance(value, dict) else None
    if many:
        return [v for item in (child if isinstance(child, list) else []) for v in _values(item, rest)]
    return _values(child, rest)


def _seen(decoded, native, fields):
    def source(field, row, path):
        values = _values(row, path)
        if (field == "text" or field.startswith("origin.")) and \
                (path.endswith("content") or path == "payload.output"):
            # A content container alone supplies no classifier text (e.g. images).
            values = [value.get("content") if isinstance(value, dict) else value for value in values]
            return any(isinstance(value, str) or isinstance(value, list) and any(
                isinstance(block, dict) and isinstance(block.get("text"), str) for block in value)
                       for value in values)
        return bool(values)

    return {field for field, paths in fields.items()
            if any(value != [] and value != {} for value in _values(decoded, field))
            and any(source(field, row, path) for row in native for path in paths)}


def build(catalogue: Path) -> dict:
    """Decode each catalogued byte snapshot; no links may read ancillary store files."""
    from . import records
    from .lines import Place, UnknownFormat, decode, detect_format, lines
    from .links import native_links

    raw_catalogue = catalogue.read_bytes()
    samples = tomllib.loads(raw_catalogue.decode("utf-8"))["sample"]
    harnesses = {slug: {"record_kinds": set(), "fields": {
        field: {"provenance": sorted(paths), "coverage_keys": []} for field, paths in fields.items()
    }, "labels": {}, "versions": {}, "exceptions": []} for slug, fields in DECLARED.items()}
    hashes = {}
    for sample in samples:
        name, slug, version, provenance = (sample[key] for key in ("path", "harness", "version", "provenance"))
        path = catalogue.parent / name
        if Path(name).is_absolute() or not path.resolve().is_relative_to(catalogue.parent.resolve()):
            raise ValueError("sample path must remain within the catalogue directory")
        if name in hashes:
            raise ValueError("duplicate sample path")
        if provenance not in ("synthetic", "observed"):
            raise ValueError("sample provenance must be synthetic or observed")
        harness = harnesses[slug]
        evidence = harness["versions"].setdefault(version, {
            "synthetic": [], "observed": [], "fields_seen": {"synthetic": set(), "observed": set()}})
        data = path.read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        evidence[provenance].append(name)
        try:
            fmt = detect_format(data, len(data))
        except UnknownFormat:
            continue
        if ("codex" if fmt == "codex" else "claude-code") != slug:
            raise ValueError("sample harness disagrees with decoded format")
        # Explicit place prevents metadata sidecars and sibling transcript discovery.
        place = Place(slug, "file", None, "explicit", name, path)
        reader = {"claude": records.claude_read, "sdk": records.sdk_read, "codex": records.codex_read}[fmt]
        read = reader(place, len(data), lambda _: None, data=data) if fmt == "codex" \
            else reader(place, len(data), data=data)
        native = {line.number: row for line in lines(data, len(data))
                  if line.complete and (row := decode(line)) is not None}
        fields = DECLARED[slug]
        seen = evidence["fields_seen"][provenance]
        for record in read.records:
            if record["kind"] is not None:
                harness["record_kinds"].add(record["kind"])
            harness["labels"].setdefault(record["role"], set()).add(record["basis"])
            seen.update(_seen(record, [native[record["line"]]], fields))
        seen.update(_seen({"links": native_links(read)}, list(native.values()), fields))
        first_meta = next((row for row in native.values() if row.get("type") == "session_meta"), {})
        creation = {"session", "parent", "agent_path", "depth", "child", "child_basis", "cwd",
                    "entrypoint", "cli_version"}
        for field, paths in fields.items():
            if not field.startswith("header."):
                continue
            name = field.removeprefix("header.")
            # These false values describe an absent marker, not a native false field.
            if name in {"forked", "markers"} and not read.header.get(name):
                continue
            source = [first_meta] if fmt == "codex" and name in creation else list(native.values())
            seen.update(_seen({"header": read.header}, source, {field: paths}))
    for harness in harnesses.values():
        harness["record_kinds"] = sorted(harness["record_kinds"])
        harness["labels"] = {role: sorted(bases) for role, bases in harness["labels"].items()}
        for evidence in harness["versions"].values():
            for provenance in ("synthetic", "observed"):
                evidence[provenance].sort()
                evidence["fields_seen"][provenance] = sorted(evidence["fields_seen"][provenance])
    return {"schema": SCHEMA, "decoder_version": DECODER_VERSION, "built_from": {
        "catalogue_sha256": hashlib.sha256(raw_catalogue).hexdigest(), "samples": hashes},
        "evidence_rule": EVIDENCE_RULE, "harnesses": harnesses}


def build_artifact() -> None:
    """Rebuild only in the source checkout; a pinned package never needs fixtures."""
    root = ARTIFACT.parent.parent.parent
    catalogue = root / "tools/fixtures/session-logs/CATALOGUE.toml"
    if not (root / ".git").exists() or not (root / "tools/hq").is_file() or not catalogue.is_file():
        raise ValueError("capabilities --build requires an hq checkout with its catalogue")
    ARTIFACT.write_text(json.dumps(build(catalogue), sort_keys=True, indent=1) + "\n", encoding="utf-8")


def view(decoder: dict) -> dict:
    """Attach identity to a served copy, never to the deterministic build product."""
    value = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if value["schema"] != SCHEMA or value["decoder_version"] != DECODER_VERSION:
        raise ValueError("capabilities artifact does not match the running decoder")
    return {**value, "decoder": decoder}


def table(value: dict) -> str:
    """Render the entire view as path/value rows, retaining evidence provenance."""
    rows = ["Capability\tEvidence", "Unlisted versions\tuntested; absent fields remain unobserved"]

    def visit(item, path):
        if isinstance(item, dict) and item:
            for key in sorted(item):
                visit(item[key], f"{path}.{key}" if path else key)
        else:
            rows.append(path + "\t" + json.dumps(item, sort_keys=True))

    visit(value, "")
    return "\n".join(rows)

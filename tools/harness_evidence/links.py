"""Native link evidence relocated from obs session_logs/_sessions.py.
Source revision: fe61869f0041eff423ed495d10845ef3cf3d5638.
"""
import json
from pathlib import Path, PurePosixPath

from .lines import Place, ref
from .records import FileRead


def _meta_path(read: FileRead) -> tuple[Path, str] | None:
    """A Claude child's metadata beside its actual source, with its logical ref path."""
    if read.place.harness != "claude-code" or not read.header.get("subagent") \
            or read.place.store == "explicit":
        return None
    stem = PurePosixPath(read.place.relpath).stem
    relpath = str(PurePosixPath(read.place.relpath).with_name(f"{stem}.meta.json"))
    source = read.place.read_path if read.place.read_path is not None else read.place.path
    return source.with_name(f"{stem}.meta.json"), relpath


def _meta(read: FileRead) -> tuple[dict, str] | None:
    """The child's `.meta.json` object and its ref, when present and an object; it is never
    required."""
    located = _meta_path(read)
    if located is None:
        return None
    path, relpath = located
    try:
        value = json.loads(path.read_bytes())
    except (OSError, ValueError, RecursionError):
        return None
    if not isinstance(value, dict):
        return None
    place = read.place
    return value, ref(Place(place.harness, place.home, place.profile, place.store, relpath, path))


def _str(value) -> str | None:
    return value if isinstance(value, str) and value else None


def requested_model(read: FileRead) -> dict | None:
    """Separately observed child metadata, added only after transcript copy settlement."""
    meta = _meta(read)
    value = _str(meta[0].get("model")) if meta else None
    return {"value": value, "basis": "requested", "ref": meta[1]} if value else None


def _link(kind: str, target: str, rule: str, at: str | None, call: dict | None = None,
          *sources: dict) -> dict:
    """One link; `call` only when the link goes through a dispatching call, and
    `copy: ambiguous` when a record it comes from lies in an ambiguous range (R27)."""
    out = {"kind": kind, "target": target,
           "basis": {"native_metadata": "native", "path": "convention"}[rule], "rule": rule, "ref": at}
    if call is not None:
        out["call"] = call
    ambiguous = next((source for source in sources if source.get("copy") == "ambiguous"), None)
    if ambiguous is not None:
        out["copy"] = "ambiguous"
        out.update(copy_basis=ambiguous["copy_basis"], copy_rule=ambiguous["copy_rule"])
    return out


def _own(record: dict) -> bool:
    """A record that may record a link: not a known copy (an ambiguous one may, R27)."""
    return record.get("copy") in (None, "ambiguous")


def _codex_links(read: FileRead) -> list[dict]:
    links = []
    parent = _str(read.header.get("parent"))
    first = next((r for r in read.records if r["kind"] == "session_meta"), None)
    if parent and first is not None:
        links.append(_link("child_to_parent", parent, "native_metadata", first["ref"], None, first))
    spawns = {}  # binds a SubAgentActivity item to the spawn call it names
    for record in read.records:
        call = record.get("call")
        if record["role"] == "tool_call" and call and call.get("tool") == "spawn_agent" \
                and isinstance(call.get("id"), str) and _own(record):
            spawns.setdefault(call["id"], record)
    bound = set()
    for record in read.records:
        binding = record.get("_subagent")
        if not binding or not _own(record):
            continue
        call, thread = binding.get("call"), _str(binding.get("thread"))
        if thread is None or call not in spawns or (call, thread) in bound:
            continue
        bound.add((call, thread))
        spawn = spawns[call]
        links.append(_link("dispatch_binding", thread, "native_metadata", record["ref"],
                           {"id": call, "ref": spawn["ref"]}, record, spawn))
    return links


def _claude_links(read: FileRead) -> list[dict]:
    links, place = [], read.place
    launched = set()
    for record in read.records:
        if not _own(record):
            continue
        agent = record.get("_launched_agent")
        if agent and (agent, record["line"]) not in launched:
            launched.add((agent, record["line"]))
            call = record.get("call")
            links.append(_link("parent_to_child", f"agent-{agent}", "native_metadata",
                               ref(place, record["line"]),
                               {"id": call.get("id"), "ref": call.get("peer")} if call else None,
                               record))
        if record.get("_continued_in"):
            links.append(_link("continued_in", record["_continued_in"], "native_metadata",
                               record["ref"], None, record))
    relpath = PurePosixPath(place.relpath)
    if read.header.get("subagent") and relpath.parent.name == "subagents" \
            and _str(read.header.get("parent")):
        meta = _meta(read)
        tool_use = _str(meta[0].get("toolUseId")) if meta else None
        links.append(_link("child_to_parent", read.header["parent"], "path", ref(place),
                           {"id": tool_use, "ref": None} if tool_use else None))
    elif not read.header.get("subagent") and place.store in ("live", "archived"):
        children = place.path.parent / relpath.stem / "subagents"
        for child in sorted(children.glob("agent-*.jsonl")):
            child_rel = str(relpath.parent / relpath.stem / "subagents" / child.name)
            links.append(_link("parent_to_child", child.stem, "path",
                               ref(Place(place.harness, place.home, place.profile, place.store,
                                         child_rel, child))))
    return links


def _sdk_links(read: FileRead) -> list[dict]:
    """An SDK event's `parent_tool_use_id` names a dispatching call, never a session (SL9):
    one link per call, at its first event."""
    links, seen = [], set()
    for record in read.records:
        call = (record.get("dispatch") or {}).get("call")
        if call and call not in seen:
            seen.add(call)
            links.append(_link("sdk_dispatch", call, "native_metadata",
                               ref(read.place, record["line"])))
    return links


def native_links(read: FileRead) -> list[dict]:
    """The links `read` records, in file order, then the path links:
    - Codex `child_to_parent` from the first `session_meta`'s parent (never its
      `session_id`), and a `dispatch_binding` for each `SubAgentActivity` item whose `id` is
      a spawn call's `call_id` (`ref` the item, `call` the spawn call);
    - Claude `parent_to_child` from a launch result's `toolUseResult.agentId` (`ref` the
      result's line, `call` its dispatching call) and, by `path`, from each
      `<session>/subagents/agent-*.jsonl` beside the file; a child's `child_to_parent` by
      `path`, its `call` from `.meta.json` `toolUseId` when present; `continued_in` from a
      `continued-in` record;
    - SDK `sdk_dispatch`, whose target is a call id.
    Never a link: `parentUuid`, `parent_turn_id`, a Codex child's `session_id`, a parent id
    in tool output. Known copies record no link of this file; a link from a record in an
    ambiguous range is kept and marked `copy: ambiguous` (R27)."""
    if any("dispatch" in r for r in read.records):
        return _sdk_links(read)
    if read.place.harness == "codex":
        return _codex_links(read)
    if read.place.harness == "claude-code":
        return _claude_links(read)
    return []

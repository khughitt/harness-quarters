"""Read-only native transcript discovery and filename-claimed identity."""
from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath
import re
import stat

from . import homes
from .lines import Place, ref

NAMING_RULE = ("home: the root's parent directory name without its leading dot; store: "
               "archived for an archived_sessions root, else live; profile: work when the "
               "home name ends in -work, else personal")
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
# The thread a rollout's stem names (group 1): its first UUID, also in a Codex 0.165+
# continuation segment (`rollout-<ts>-<thread>_<segment>`, segment in group 2), whose
# session_meta records the thread.
ROLLOUT_ID = re.compile(rf"-({_UUID})(?:_({_UUID}))?$")
ERROR_SAMPLE = 3


@dataclass(frozen=True)
class Root:
    harness: str
    home: str
    profile: str
    store: str
    path: Path


def roots(user_home: Path | None = None,
          explicit: list[tuple[str, Path]] | None = None) -> list[Root]:
    """Explicit roots replace every default; otherwise use supported harness homes."""
    if explicit is None:
        user_home = Path.home() if user_home is None else user_home
        explicit = [(homes.SLUG[home.harness], path)
                    for harness in ("claude", "codex", "agy")
                    for home in homes.homes(user_home, harness)
                    for _store, path in homes.stores(home)]
    found = []
    for harness, path in explicit:
        if harness not in ("claude-code", "codex", "agy"):
            raise ValueError(f"unsupported discovery harness: {harness}")
        if harness == "agy" and path.name != "brain":
            # Conversation ids and the summaries database are found from brain/<id>/...
            raise ValueError(f"agy root must be a brain directory: {path}")
        name = path.parent.name
        # agy's home directory is antigravity-cli; its refs name the harness instead.
        home = "agy" if harness == "agy" else name[1:] if name.startswith(".") else name
        found.append(Root(harness, home, "work" if home.endswith("-work") else "personal",
                          "archived" if path.name == "archived_sessions" else "live", path))
    return found


def _root_of(path: Path, roots: list[Root]) -> Root | None:
    parts = path.parts  # a parts prefix: Path.is_relative_to is slow over every index row
    held = [root for root in roots if parts[:len(root.path.parts)] == root.path.parts]
    return max(held, key=lambda root: len(root.path.parts)) if held else None


@dataclass
class Listing:
    roots: list[dict]
    files: list[Path]
    aliases: list[Path]
    skipped_by_mtime: int
    file_errors: dict[Path, OSError]


# agy keeps each conversation's transcripts in brain/<id>/.system_generated/logs. Its
# chunks/ subdirectories hold byte segments of the same files and are not listed.
AGY_FULL, AGY_MIRROR = "transcript_full.jsonl", "transcript.jsonl"
_AGY_DIRS = {1: ".system_generated", 2: "logs"}


def _matches(root: Root, depth: int, dirnames: list[str]) -> bool:
    """Whether files at this depth match the index's patterns (`stores.paths`), pruning
    Claude directories no pattern reaches: `*/*.jsonl`, `*/*/subagents/*.jsonl`; Codex
    `**/*.jsonl`; agy `*/.system_generated/logs/transcript{_full,}.jsonl`."""
    if root.harness == "agy":
        dirnames[:] = [name for name in dirnames if depth == 0 or _AGY_DIRS.get(depth) == name]
        return depth == 3
    if root.harness != "claude-code":
        return True
    if depth == 2:
        dirnames[:] = [name for name in dirnames if name == "subagents"]
    elif depth >= 3:
        dirnames[:] = []
    return depth in (1, 3)


def root_state(root: Root) -> tuple[str, OSError | None]:
    """`absent` only when the root is not there; any other failure to reach it (a mode-0
    parent, a file in its place) is `unreadable`."""
    try:
        info = os.stat(root.path)
    except FileNotFoundError:
        return "absent", None
    except OSError as error:
        return "unreadable", error
    if not stat.S_ISDIR(info.st_mode):
        return "unreadable", NotADirectoryError(f"{root.path} is not a directory")
    return "searched", None


def list_files(roots: list[Root], since_ms: int | None) -> Listing:
    """Every selected root listed before any file is read. Symlinked transcripts are
    aliases, never files. Claude roots follow directory links as the index's glob does (the
    depth limit rules out loops); Codex roots do not. With `since_ms`, a file whose mtime is
    older is skipped and counted. An unreadable root records how many listing errors
    it met, the first few, and whether its listing was `partial` or `failed`.
    Enumerated names with unavailable metadata remain selected even with `since_ms`;
    their mtime is unknown and file_errors retains the failed observation."""
    entries, files, aliases, skipped = [], [], [], 0
    file_errors = {}
    for root in roots:
        entry = {"harness": root.harness, "home": root.home, "profile": root.profile,
                 "store": root.store, "state": "searched", "files": 0, "bytes": 0}
        entries.append(entry)
        state, failure = root_state(root)
        if state != "searched":
            entry["state"] = state
            if failure is not None:
                entry.update(errors=1, first_errors=[str(failure)], listing="failed")
            continue
        errors: list[OSError] = []
        found, links = [], []
        for dirpath, dirnames, filenames in os.walk(root.path, onerror=errors.append,
                                                    followlinks=root.harness == "claude-code"):
            depth = len(Path(dirpath).relative_to(root.path).parts)
            names = filenames + dirnames  # Keep matching paths before traversal pruning.
            if not _matches(root, depth, dirnames):
                continue
            for name in names:
                if name.endswith(".jsonl") and (root.harness != "agy" or name in (AGY_FULL, AGY_MIRROR)):
                    path = Path(dirpath) / name
                    try:  # a directory readable but not searchable lists names it cannot stat
                        (links if stat.S_ISLNK(path.lstat().st_mode) else found).append(path)
                    except OSError as error:
                        found.append(path)
                        file_errors[path] = error
                        if not isinstance(error, FileNotFoundError):
                            errors.append(error)
        for path in sorted(found):
            if path in file_errors:
                files.append(path)
                entry["files"] += 1
                continue
            try:
                info = path.stat()
            except OSError as error:
                file_errors[path] = error
                files.append(path)
                entry["files"] += 1
                if not isinstance(error, FileNotFoundError):
                    errors.append(error)
                continue
            if since_ms is not None and info.st_mtime_ns // 1_000_000 < since_ms:
                skipped += 1
                continue
            files.append(path)
            entry["files"] += 1
            entry["bytes"] += info.st_size
        if errors:
            top = any(Path(error.filename or "") == root.path for error in errors)
            entry.update(state="unreadable", errors=len(errors),
                         first_errors=[str(error) for error in errors[:ERROR_SAMPLE]],
                         listing="failed" if top else "partial")
        aliases.extend(sorted(links))
    return Listing(entries, files, aliases, skipped, file_errors)


def place_of(path: Path, roots: list[Root], store: str | None = None) -> Place:
    """The logical place of a path under a root, whether or not the file exists; the ref
    path is relative to the home directory (the root's parent)."""
    root = _root_of(path, roots)
    if root is None:
        raise ValueError(f"{path} is under no store root")
    return Place(root.harness, root.home, root.profile, store or root.store,
                 path.relative_to(root.path.parent).as_posix(), path)


def filename_identity(harness: str, path: Path) -> dict | None:
    """Identity claimed by a Codex rollout name or an agy brain directory, independent of
    recorded identity."""
    if harness == "agy":
        if path.name not in (AGY_FULL, AGY_MIRROR) or path.parent.parent.name != ".system_generated":
            return None
        return {"conversation": path.parent.parent.parent.name, "basis": "convention"}
    if harness != "codex" or path.suffix != ".jsonl" or not path.name.startswith("rollout-"):
        return None
    match = ROLLOUT_ID.search(path.stem)
    if match is None:
        return None
    return {"thread": match.group(1), "segment": match.group(2), "basis": "convention"}


def copy_label(harness: str, path: Path) -> dict | None:
    """agy's transcript.jsonl is an export-truncated mirror of transcript_full.jsonl; `full`
    names that file when it exists and is null otherwise (the mirror itself is never decoded)."""
    if harness != "agy" or path.name != AGY_MIRROR:
        return None
    full = path.with_name(AGY_FULL)
    return {"label": "truncated_mirror", "basis": "convention", "full": str(full) if full.exists() else None}


def path_facts(place: Place) -> dict | None:
    """Claude naming claims from the logical path, independently of source bytes."""
    if place.harness != "claude-code":
        return None
    session = PurePosixPath(place.relpath).stem
    subagent = place.path.parent.name == "subagents"
    return {"session": session, "agent": session[len("agent-"):] if session.startswith("agent-") else None,
            "parent": place.path.parent.parent.name if subagent else None, "subagent": subagent,
            "resume_group": None if subagent else str(PurePosixPath(place.relpath).parent),
            "basis": "convention", "rule": "claude_path_layout", "ref": ref(place)}


def filename_lookup(harness: str, path: Path, *, root: Root | None = None) -> dict | None:
    """Exact possible native name-lookup IDs, separate from recorded identities."""
    if harness == "claude-code":
        if root is None or not path.name.endswith(".jsonl"):
            return None
        parts = path.relative_to(root.path).parts
        stem = path.name[:-len(".jsonl")]
        candidates = set()
        if len(parts) == 2:
            candidates.add(stem)
        elif len(parts) == 4 and parts[2] == "subagents" and stem.startswith("agent-"):
            candidates.update((parts[1], stem))
            agent = stem[len("agent-"):]
            if not agent.startswith("agent-"):
                candidates.add(agent)
        return {"session_ids": sorted(candidates - {""}), "basis": "convention", "rule": "claude_name_lookup"}
    if harness != "codex" or path.suffix != ".jsonl" or not path.name.startswith("rollout-"):
        return None
    body = path.stem[len("rollout-"):]
    candidates = {body[i + 1:] for i, char in enumerate(body) if char == "-" and body[i + 1:]}
    match = ROLLOUT_ID.search(path.stem)
    # The old rollout-*-<id>* glob needs a separator after the rollout- prefix.
    if match is not None and match.start() >= len("rollout-"):
        candidates.add(match.group(1))
    return {"session_ids": sorted(candidates), "basis": "convention", "rule": "rollout_name_lookup"}

"""Copy evidence relocated from obs session_logs/_sessions.py.
Source revision: fe61869f0041eff423ed495d10845ef3cf3d5638.
Read-only: changes only normalized in-memory records.
"""
from collections import defaultdict
from datetime import datetime, timezone
import itertools
from pathlib import PurePosixPath
import re

from harness_evidence.lines import Place, ref
from harness_evidence.records import FileRead, pair_calls

_KNOWN = frozenset({"resume_history", "duplicate_file"})
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_ROLLOUT_ID = re.compile(rf"-({_UUID})(?:_({_UUID}))?$")


def _when(at) -> datetime | None:
    if not isinstance(at, str) or not at:
        return None
    try:
        when = datetime.fromisoformat(at)
    except ValueError:
        return None
    return when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)


def _by_line(read: FileRead) -> dict[int, list[dict]]:
    lines = defaultdict(list)
    for record in read.records:
        lines[record["line"]].append(record)
    return lines


def _original_ref(original: FileRead, refs: set[str], line: int, block: int | None) -> str:
    """The original's ref for a copied record: the same block when the original has it, else
    the line."""
    candidate = ref(original.place, line, block)
    return candidate if candidate in refs else ref(original.place, line)


def _settle(read: FileRead, copied: set[int]) -> None:
    """After lines of `read` were marked: a known copy (`resume_history`, `duplicate_file`)
    keeps no model, and the header lists none from it: each model's ref moves to its first
    line that is still the file's own, or the model goes. `copied` holds only known-copy
    lines; an `ambiguous` line keeps its model (R24). Calls pair again either way, so known
    copies take no part and ambiguous records pair within the file."""
    for record in read.records:
        if record["line"] in copied and record.get("copy") in _KNOWN:
            record.pop("model", None)
    if copied:
        refs = read.header["_model_refs"]
        kept = []
        for model in read.header.get("models", []):
            key = (model["value"], model["basis"])
            refs[key] = [(at, line) for at, line in refs[key] if line not in copied]
            if refs[key]:
                kept.append({**model, "ref": refs[key][0][0]})
        read.header["models"] = kept
    pair_calls(read.records)


# ---------------------------------------------------------------------------------------
# resume_history
# ---------------------------------------------------------------------------------------

def _named(read: FileRead, other: FileRead) -> bool:
    """Whether a `continued-in` record of `read` names `other`'s session."""
    return any(r.get("_continued_in") == other.header.get("session") and "copy" not in r
               for r in read.records)


def _timed_turns(read: FileRead) -> dict[int, datetime]:
    """Each user or assistant line with a timestamp, by line."""
    out = {}
    for record in read.records:
        when = _when(record.get("at"))
        if record.get("kind") in ("user", "assistant") and when is not None:
            out[record["line"]] = when
    return out


def _later(read: FileRead, shared_lines: set[int], other: FileRead, timed: dict) -> bool:
    """Test for the later file: whether `read`'s first unshared user or assistant record is later
    than every user or assistant record of `other`. A file with no unshared timed record
    cannot meet it (R26), nor can one compared with a file that has no timed record."""
    mine = timed[id(read)]
    unshared = [line for line in sorted(mine) if line not in shared_lines]
    theirs = timed[id(other)]
    if not unshared or not theirs:
        return False
    return mine[unshared[0]] > max(theirs.values())


def _direction(a: FileRead, b: FileRead, shared: set[str], timed: dict) -> tuple[FileRead, FileRead, str] | None:
    """(copy, original) by the native link, then timing; None for a tie (`ambiguous`)."""
    a_names_b, b_names_a = _named(a, b), _named(b, a)
    if a_names_b != b_names_a:
        return (b, a, "continued_in") if a_names_b else (a, b, "continued_in")
    a_later = _later(a, {a.header["uuids"][u] for u in shared}, b, timed)
    b_later = _later(b, {b.header["uuids"][u] for u in shared}, a, timed)
    if a_later == b_later:  # neither or both meet the timing test: a tie
        return None
    return (a, b, "timestamp_order") if a_later else (b, a, "timestamp_order")


def mark_resume_copies(reads: list[FileRead]) -> None:
    """Mark `resume_history` in Claude main files that share record `uuid`s within one
    project directory. Which file holds the copy: a `continued-in` record naming the other
    file's session, else the timing rule (a file with no unshared record cannot meet it),
    else, when neither or both files meet it, both files' shared records are `ambiguous`
    and neither collapses. A copy's `original` is the original's ref (followed through a
    chain of resumes). Records already holding another copy kind keep it. Only the files
    given are compared: an original outside them is not recognized."""
    groups = defaultdict(list)
    for read in reads:
        if read.place.harness == "claude-code" and "uuids" in read.header \
                and not read.header.get("subagent") and read.header.get("session"):
            groups[(read.place.home, PurePosixPath(read.place.relpath).parent)].append(read)
    decided, ties = [], []
    for group in groups.values():
        holders = defaultdict(list)
        for n, read in enumerate(group):
            for uuid in read.header["uuids"]:
                holders[uuid].append(n)
        shared_by_pair = defaultdict(set)
        for uuid, owners in holders.items():
            for pair in itertools.combinations(owners, 2):
                shared_by_pair[pair].add(uuid)
        timed = {id(read): _timed_turns(read) for read in group}
        for (first, second), shared in sorted(shared_by_pair.items()):
            a, b = group[first], group[second]
            direction = _direction(a, b, shared, timed)
            if direction is None:
                ties.append((a, b, shared))
            else:
                decided.append((*direction, shared))
    copied: dict[int, set[int]] = defaultdict(set)  # id(read) -> known-copy lines
    touched: set[int] = set()  # id(read) of every file with a line marked
    lines_of = {id(read): _by_line(read) for read in reads}
    marked: list[dict] = []
    for copy, original, rule, shared in decided:
        refs = {r["ref"] for r in original.records}
        for uuid in shared:
            line, source = copy.header["uuids"][uuid], original.header["uuids"][uuid]
            for record in lines_of[id(copy)][line]:
                if record.get("copy") not in (None, "ambiguous"):
                    continue
                record["copy"] = "resume_history"
                record.update(copy_basis="native" if rule == "continued_in" else "heuristic", copy_rule=rule)
                record["original"] = _original_ref(original, refs, source, record.get("block"))
                marked.append(record)
                copied[id(copy)].add(line)
                touched.add(id(copy))
    for a, b, shared in ties:
        for read in (a, b):
            for uuid in shared:
                line = read.header["uuids"][uuid]
                for record in lines_of[id(read)][line]:
                    if "copy" not in record:
                        record["copy"] = "ambiguous"
                        record.update(copy_basis="heuristic", copy_rule="timing_ambiguity")
                        touched.add(id(read))
    # A resume of a resume: point at the first holder, never at another copy.
    every = {r["ref"]: r for read in reads for r in read.records}
    for record in marked:
        seen = {record["ref"]}
        target = every.get(record["original"])
        while target is not None and target.get("copy") == "resume_history" \
                and target.get("original") and target["original"] not in seen:
            seen.add(target["ref"])
            record["original"] = target["original"]
            target = every.get(record["original"])
    for read in reads:
        if id(read) in touched:
            _settle(read, copied.get(id(read), set()))


# ---------------------------------------------------------------------------------------
# duplicate_file and divergent
# ---------------------------------------------------------------------------------------

def _signature(read: FileRead) -> dict[int, object]:
    """Each physical line's content as read: a record line's hash, an unparsed line's text."""
    out: dict[int, object] = {r["line"]: r["sha256"] for r in read.records}
    for unparsed in read.unparsed:
        out[unparsed["_line"]] = ("unparsed", unparsed["_raw"])
    return out


def _archived(place: Place) -> bool:
    return place.store == "archived" or place.relpath.startswith("archived_sessions/")


def _segment(place: Place) -> str | None:
    """A Codex continuation segment's UUID (`rollout-<ts>-<thread>_<segment>`), else None. A
    thread's base and its segments are ordered parts of it, never copies of one another; a
    copy of one part keeps its file name, so the name, not the path, tells them apart."""
    if place.harness != "codex":
        return None
    match = _ROLLOUT_ID.search(PurePosixPath(place.relpath).stem)
    return match.group(2) if match else None


def mark_duplicate_files(reads: list[FileRead]) -> None:
    """Mark `duplicate_file`: files of one harness, identity and Codex segment are grouped;
    the earliest root's file (`sessions/` before `archived_sessions/`, else the order given,
    which is root order) is the original. A later file's line that repeats the original's
    line at the same number becomes a `duplicate_file` copy of it, whatever copy kind it
    held. Every file of a group whose lines differ from another's gets header
    `divergent: true`."""
    groups = defaultdict(list)
    for read in reads:
        if read.place.store != "explicit" and read.header.get("session"):
            groups[(read.place.harness, read.header["session"], _segment(read.place))].append(read)
    for group in groups.values():
        if len(group) < 2:
            continue
        group = sorted(group, key=lambda read: _archived(read.place))  # stable: root order
        original, others = group[0], group[1:]
        signatures = [_signature(read) for read in group]
        for read, signature in zip(group, signatures):
            if any(other != signature for other in signatures):
                read.header["divergent"] = True
        source, refs = signatures[0], {r["ref"] for r in original.records}
        for read, signature in zip(others, signatures[1:]):
            copied = set()
            for record in read.records:
                line = record["line"]
                if source.get(line) == signature[line]:
                    record["copy"] = "duplicate_file"
                    record.update(copy_basis="convention", copy_rule="identity_line_match")
                    record["original"] = _original_ref(original, refs, line, record.get("block"))
                    copied.add(line)
            if copied:
                _settle(read, copied)

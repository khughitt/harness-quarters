"""Native associations relocated from OBS 1e0afad1; no consumer command roles.

Shell runs in Codex code-mode rollouts: scripts, yielded cells and exec sessions.

A top-level record (a call, a script's own output, a `wait` output) is timestamped when it
happens. A result produced by an operation inside a script is not: it happened somewhere
between the script's call C and the record D that delivered it, so bounds use only C, D and
the operation's own `wall_time_seconds`. Results are paired with the script's operations by
position, across every delivery of the script's output. No command text is kept.
"""

import json
import re

from . import _index_codex_outcomes as outcomes

OPERATION = re.compile(r"tools\.(exec_command|shell_command|write_stdin)\(")
STRINGS = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`', re.S)
CONTROL = re.compile(r"\?|&&|\|\||=>|\bPromise\.|\b(?:if|else|for|while|do|switch|try|catch|"
                     r"finally|function|return|break|continue)\b")
COMMENT = re.compile(r"//[^\n]*")
TEXT_AWAIT = re.compile(r"^text\(\s*await\s+tools\.\w+\(.*\)\s*\)$", re.S)
BOUND = re.compile(r"^(?:const|let|var)\s+(\w+)\s*=\s*await\s+tools\.\w+\(.*\)$", re.S)
BARE_AWAIT = re.compile(r"^await\s+tools\.\w+\(.*\)$", re.S)
TEXT_CALL = re.compile(r"^text\((.*)\)$", re.S)
# `text(<expr>)` (no `await`) stays plain only when <expr> is a name bound earlier by
# `const|let|var <name> = await tools.…`, `JSON.stringify(<such a name>[, …])`, or a
# static string literal: anything else (member access, concatenation, a dynamic
# template, another call) could print raw command output rather than a result object.
STRINGIFY = re.compile(r"^JSON\.stringify\(\s*(\w+)\s*(?:,.*)?\)$", re.S)
# The literal must be the whole property value: `'sleep 120; ' + bench` is not a wait.
CMD = re.compile(r'["\']?(?:cmd|command)["\']?\s*:\s*'
                 r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|`(?:[^`\\]|\\.)*`)(?=\s*[,}])', re.S)
SESSION_ARG = re.compile(r'["\']?session_id["\']?\s*:\s*(\d+)')
RUNNING = re.compile(r"Script running with cell ID (\S+)")
# Recognised only as the harness's own error block for the waited cell: the
# `Script error:` / `exec cell <C> not found` pair immediately after the harness's own
# `Script failed` / `Wall time …` / `Output:` header, before any other text — never a
# copy of the same words printed later, deep in a known cell's own output.
NOT_FOUND = re.compile(r"\AScript failed\nWall time [^\n]*\nOutput:\n+"
                       r"Script error:\nexec cell (\S+) not found(?=\n|\Z)")
DECODER = json.JSONDecoder()
COUNTERS = ("unattributed_scripts", "unmatched_poll", "session_reused", "unmatched_wait")
WINDOW_SLACK_MS = 1000


def _string_end(script, start, failed):
    """End of a complete literal, remembering failed scans for each delimiter."""
    quote = script[start]
    if quote not in "\"'`" or start < failed.get(quote, 0):
        return None
    end = start + 1
    while end < len(script):
        if script[end] == "\\":
            end += 2
        elif script[end] == quote:
            return end + 1
        elif script[end] == "\n" and quote != "`":
            break
        else:
            end += 1
    # Later copies of this delimiter before the boundary were escaped, so also fail.
    failed[quote] = end
    return None


def _code(script):
    """The script with string contents and `//` comments blanked, positions unchanged.

    Validation and operation discovery both read this, so an operation inside a comment
    is never an operation.
    """
    parts, failed = [], {}
    i = copied = 0
    while i < len(script):
        end = _string_end(script, i, failed)
        if end is None:
            i += 1
            continue
        parts.append(script[copied:i + 1] + " " * (end - i - 2) + script[end - 1])
        copied = i = end
    parts.append(script[copied:])
    blank = "".join(parts)
    return COMMENT.sub(lambda m: " " * len(m.group()), blank)


def _argument(script, open_paren):
    """The text between the call's parentheses, string literals respected."""
    depth, i = 0, open_paren
    failed = {}
    while i < len(script):
        end = _string_end(script, i, failed)
        if end is not None:
            i = end
            continue
        if script[i] == "(":
            depth += 1
        elif script[i] == ")":
            depth -= 1
            if depth == 0:
                return script[open_paren + 1:i]
        i += 1
    return script[open_paren + 1:]


def _statements(code):
    """Top-level statement spans of a string-blanked script, split on `;` and newlines."""
    spans, depth, start = [], 0, 0
    for i, ch in enumerate(code):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch in ";\n" and depth == 0:
            spans.append((start, i))
            start = i + 1
    spans.append((start, len(code)))
    return spans


def _trimmed(text, start, end):
    """`(start, end)` narrowed to its non-whitespace content, or None when it is blank."""
    piece = text[start:end]
    stripped = piece.strip()
    if not stripped:
        return None
    lead = len(piece) - len(piece.lstrip())
    trail = len(piece) - len(piece.rstrip())
    return start + lead, end - trail


def _plain(script, code):
    """Whether a blanked script is a sequence of plain statements.

    Structure (is this `text(await tools.…)`, a bound `const … = await tools.…`, or a
    bare `await tools.…`?) is read from the blanked code, so an operation name inside a
    string literal is never mistaken for one. A `text(<expr>)` statement without `await`
    is read from the unblanked script instead, since only there can <expr> be told apart
    from a member access or a concatenation that would print raw command output.
    """
    if CONTROL.search(code):
        return False
    bound = set()
    for start, end in _statements(code):
        span = _trimmed(code, start, end)
        if span is None:
            continue
        s, e = span
        blanked = code[s:e]
        if TEXT_AWAIT.fullmatch(blanked) or BARE_AWAIT.fullmatch(blanked):
            continue
        bound_match = BOUND.fullmatch(blanked)
        if bound_match:
            bound.add(bound_match.group(1))
            continue
        text_call = TEXT_CALL.fullmatch(script[s:e])
        if text_call is None:
            return False
        arg = text_call.group(1).strip()
        if arg in bound:
            continue
        stringify = STRINGIFY.fullmatch(arg)
        if stringify is not None and stringify.group(1) in bound:
            continue
        literal = STRINGS.fullmatch(arg)
        if literal is not None and not (arg[:1] == "`" and "${" in arg):
            continue
        return False
    return True


def _js_string(literal):
    """A JS string literal's value; None for a dynamic template or an unreadable escape."""
    quote, body = literal[0], literal[1:-1]
    if quote == "`" and "${" in body:
        return None
    out, i = [], 0
    while i < len(body):
        if body[i] == "\\" and i + 1 < len(body):
            following = body[i + 1]
            out.append(following if following in "'`" else "\\" + following)
            i += 2
            continue
        out.append('\\"' if body[i] == '"' else body[i])
        i += 1
    try:
        return json.loads('"' + "".join(out) + '"', strict=False)
    except json.JSONDecodeError:
        return None


def operations(script):
    """The script's shell operations in source order, or None when its printed results
    cannot be paired with them by position."""
    code = _code(script)
    if not _plain(script, code):
        return None
    found = list(OPERATION.finditer(code))
    if len(found) > 1 and any(not code[:m.start()].rstrip().endswith("text(await")
                              for m in found):
        return None
    ops = []
    for match in found:
        argument = _argument(script, match.end() - 1)
        if match.group(1) == "write_stdin":
            # Search the raw argument (a quoted key like `"session_id"` is itself a
            # string literal, blanked away in `code`), but accept only a match whose
            # digits are still there, unblanked, at the same offsets in the blanked
            # slice: a raw `chars` payload that itself reads `session_id: 7` blanks to
            # spaces there and is never mistaken for the call's own argument.
            blanked = _argument(code, match.end() - 1)
            session = next((candidate for candidate in SESSION_ARG.finditer(argument)
                            if blanked[candidate.start(1):candidate.end(1)]
                            == candidate.group(1)), None)
            if session is None:
                return None
            ops.append({"op": "poll", "command": None, "session_id": session.group(1)})
            continue
        command = CMD.search(argument)
        ops.append({"op": "launch", "command": _js_string(command.group(1)) if command else None, "session_id": None})
    return ops


def output_text(output):
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "\n".join(block.get("text", "") for block in output if isinstance(block, dict))
    return ""


def results(text):
    """Result objects the script printed, in order, read with the JSON decoder.

    Every `{` is tried; a decoded object is skipped whole, so text inside a result's
    `output` is never read as another result. Property order does not matter.
    """
    found, i = [], 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return found
        try:
            value, end = DECODER.raw_decode(text, i)
        except json.JSONDecodeError:
            i += 1
            continue
        if isinstance(value, dict) and "chunk_id" in value:
            session, exit_code = value.get("session_id"), value.get("exit_code")
            wall = value.get("wall_time_seconds")
            found.append({
                "session": str(session) if type(session) is int else None,
                "exit_code": exit_code if type(exit_code) is int else None,
                "wall_ms": round(wall * 1000) if type(wall) in (int, float) else 0})
        i = end


def _counters(state):
    return state.setdefault("run_diagnostics", dict.fromkeys(COUNTERS, 0))


def _status(text):
    """A script output's status: `Script failed`/`terminated`/`completed`, or an abort."""
    if text.startswith("Script failed"):
        return "failed"
    if text.startswith("Script terminated"):
        return "terminated"
    if text.startswith("aborted by user"):
        return "aborted"
    return "completed"


def _row(run, end_lo_ms, end_ms, basis, status, exit_code):
    return {"session_id": run["session_id"], "run_id": run["run_id"],
            "call_id": run["call_id"], "start_ms": run["start_ms"],
            "start_hi_ms": run["start_hi_ms"], "end_lo_ms": end_lo_ms, "end_ms": end_ms,
            "mode": run["mode"], "end_basis": basis, "operation_seq": run["operation_seq"], "status": status,
            "exit_code": exit_code}


def _function_command(value):
    try:
        arguments = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return None
    command = arguments.get("cmd", arguments.get("command")) if isinstance(arguments, dict) else None
    return " ".join(command) if isinstance(command, list) else command


def _function_session(value):
    try:
        session = json.loads(value).get("session_id")
    except (TypeError, AttributeError, json.JSONDecodeError):
        return None
    return str(session) if type(session) is int else None


def on_call(state, session_id, call_id, name, value, at_ms):
    """Remember what a call's output will need; nothing is emitted yet."""
    calls = state.setdefault("run_calls", {})
    if name == "exec":
        text = str(value)
        ops = operations(text)
        calls[call_id] = {"kind": "exec", "session_id": session_id, "at_ms": at_ms, "ops": None if ops is None else [{"op": op["op"], "session": op["session_id"]} for op in ops],
                          "sessionish": "write_stdin" in text or "session_id" in text}
    elif name in ("exec_command", "shell_command"):
        calls[call_id] = {"kind": "command", "session_id": session_id, "at_ms": at_ms,
                          "operation_seq": None}
    elif name == "wait":
        try:
            cell = json.loads(value).get("cell_id")
        except (TypeError, AttributeError, json.JSONDecodeError):
            cell = None
        if cell is not None:
            calls[call_id] = {"kind": "wait", "cell": str(cell)}
    elif name == "write_stdin":
        session = _function_session(value)
        if session is not None:
            calls[call_id] = {"kind": "stdin", "session": session}


def origin_of(state, call_id):
    """The exec call an open call stands for: an exec itself, or a wait on
    a known cell; None for any other call."""
    call = state.setdefault("run_calls", {}).get(call_id)
    if call is None:
        return None
    if call["kind"] == "exec":
        return call_id
    if call["kind"] == "wait":
        origin = state.setdefault("run_cells", {}).get(call["cell"])
        return origin["call_id"] if origin is not None else None
    return None


def note_item(state, origin_call_id, info):
    """Keep a positional item on its script, for a session launch printed later."""
    call = state.setdefault("run_calls", {}).get(origin_call_id)
    if call is not None and call["kind"] == "exec":
        call.setdefault("items", []).append(info)
        return
    for origin in state.setdefault("run_cells", {}).values():
        if origin["call_id"] == origin_call_id:
            origin.setdefault("items", []).append(info)
            return


def origin_start(state, origin_call_id):
    """When the script an item was attributed to was called: the bound an untimed item
    ran within."""
    call = state.setdefault("run_calls", {}).get(origin_call_id)
    if call is not None and call["kind"] == "exec":
        return call["at_ms"]
    for origin in state.setdefault("run_cells", {}).values():
        if origin["call_id"] == origin_call_id:
            return origin["start_ms"]
    return None


def join_item(state, info):
    """The rows for an item that reports a launched session's end: the
    launch whose session id is the item's process id, whose start window holds the
    item's start, and that no item has joined yet. None when none fits."""
    if not info["timed"]:
        return None
    sessions = state.setdefault("run_sessions", {})
    run = sessions.get(info["process_id"])
    if run is None or run["closed"] or not _fits(run, info["started_ms"]):
        past = state.setdefault("past_launches", [])
        run = next((run for run in reversed(past)
                    if run.get("session") == info["process_id"] and not run["closed"]
                    and _fits(run, info["started_ms"])), None)
        if run is None:
            return None
        past.remove(run)
    return [_exact_run(run, info["started_ms"], info["completed_ms"], info["exit_code"], "item"),
            outcomes.command(run["session_id"], run["run_id"], run["call_id"],
                                       info["started_ms"], info["completed_ms"], "exact",
                                       info["exit_code"], "item", "process_id")]


def _origin(call, call_id, run_id, mode):
    """A script run that also carries what pairing needs across deliveries."""
    return {"session_id": call["session_id"], "call_id": call_id, "run_id": run_id,
            "start_ms": call["at_ms"], "start_hi_ms": call["at_ms"], "mode": mode,
            "operation_seq": None, "ops": call["ops"], "sessionish": call["sessionish"],
            "paired": 0, "unattributed": False, "saw_session": False,
            "items": call.get("items", [])}


def _fits(run, started_ms):
    return run["start_ms"] - WINDOW_SLACK_MS <= started_ms <= run["start_hi_ms"] + WINDOW_SLACK_MS


def _finished_launch(state, origin, result, delivered_ms, outcome):
    """A command that ran to completion inside the script. Its exit feeds the
    call's own outcome while the call is open; a file that reports items takes no result
    rows, because an unattributed item may be the same command."""
    if outcome is not None:
        outcomes.add_exit(outcome, result["exit_code"])
    if state.get("command_items_seen"):
        return []
    return [outcomes.command(origin["session_id"],
                                       f"{origin['call_id']}#r{origin['paired'] - 1}",
                                       origin["call_id"], origin["start_ms"], delivered_ms,
                                       "bounds", result["exit_code"], "result", "position")]


def _join_early_item(origin, run):
    """An item that reported this session's end before the launch was printed:
    the run closes exactly; the item already has its command row."""
    for item in origin.get("items", []):
        if (item["timed"] and item["process_id"] == run["session"]
                and _fits(run, item["started_ms"])):
            origin["items"].remove(item)
            return [_exact_run(run, item["started_ms"], item["completed_ms"],
                               item["exit_code"], "item")]
    return []


def keep_loose(state, info, counter):
    """An item that fit no launch and no open call: kept, bounded, for a launch result
    delivered later that names its session (a buffered cell's launch)."""
    loose = state.setdefault("loose_items", [])
    loose.append({**info, "counter": counter})
    del loose[:-outcomes.RECENT]


def _join_loose_item(state, run):
    """The launch just delivered was ended by an item that arrived while nothing was open:
    the run closes exactly and the item's row gains its call."""
    loose = state.setdefault("loose_items", [])
    for item in loose:
        if item["process_id"] == run["session"] and _fits(run, item["started_ms"]):
            loose.remove(item)
            outcomes.diagnostics(state)[item["counter"]] -= 1
            return [_exact_run(run, item["started_ms"], item["completed_ms"],
                               item["exit_code"], "item"),
                    outcomes.command(run["session_id"], item["id"], run["call_id"],
                                               item["started_ms"], item["completed_ms"],
                                               "exact", item["exit_code"], "item",
                                               "process_id")]
    return []


def _deliver(state, origin, text, delivered_ms, outcome=None):
    """Pair newly delivered results with the next unpaired operations."""
    ops, rows = origin["ops"], []
    sessions, counters = state.setdefault("run_sessions", {}), _counters(state)
    for result in results(text):
        origin["saw_session"] = origin["saw_session"] or result["session"] is not None
        if ops is None or origin["paired"] >= len(ops):
            origin["unattributed"] = True
            continue
        op = ops[origin["paired"]]
        origin["paired"] += 1
        if op["op"] == "launch":
            if result["exit_code"] is not None:
                rows.extend(_finished_launch(state, origin, result, delivered_ms, outcome))
                continue
            if result["session"] is None:
                continue
            previous = sessions.get(result["session"])
            if previous is not None and not previous["closed"]:
                counters["session_reused"] += 1
                _remember(state, previous)
            run = {"session_id": origin["session_id"], "call_id": origin["call_id"],
                   "run_id": f"{origin['call_id']}#s{result['session']}",
                   "start_ms": origin["start_ms"],
                   "start_hi_ms": delivered_ms - result["wall_ms"],
                   "end_lo_ms": origin["start_ms"] + result["wall_ms"], "mode": "exec_session",
                   "operation_seq": origin["paired"] - 1,
                   "session": result["session"], "closed": None}
            sessions[result["session"]] = run
            rows.append(_row(run, None, None, None, None, None))
            rows.extend(_join_early_item(origin, run) or _join_loose_item(state, run))
            continue
        run = sessions.get(op["session"])
        if run is None:
            counters["unmatched_poll"] += 1
            continue
        if result["exit_code"] is None:
            if not run["closed"]:
                run["end_lo_ms"] = max(run["end_lo_ms"], origin["start_ms"] + result["wall_ms"])
            continue
        del sessions[op["session"]]
        if run["closed"]:
            continue
        rows.extend(_close_by_poll(state, run, run["end_lo_ms"], delivered_ms,
                                   result["exit_code"], "poll"))
    return rows


def _finish(state, origin):
    """At the script's completion, count it once if its sessions could not be followed."""
    short = origin["ops"] is not None and origin["paired"] < len(origin["ops"])
    if (origin["unattributed"] or short or origin["ops"] is None) and \
            (origin["sessionish"] or origin["saw_session"]):
        _counters(state)["unattributed_scripts"] += 1


def on_exec_end(state, call_id, exit_code, start_ms, end_ms):
    """exec_command_end: the rows it gives, and whether this layer took it (a session, or
    a completion held until the call's output). A session's launch is found by its call
    id, open or remembered; a call whose output has not arrived holds the
    completion, since only the output says whether it launched a session; anything else
    is a finished foreground run. Without a duration the event gives only the end."""
    sessions = state.setdefault("command_sessions", {})
    run = next((run for run in sessions.values() if run["call_id"] == call_id), None)
    if run is None:
        past = state.setdefault("past_launches", [])
        run = next((run for run in past if run["call_id"] == call_id), None)
        if run is None:
            held = _hold(state, call_id, "exec_end", exit_code, start_ms, end_ms)
            if held is not None:
                return held, True
            return _foreground_exec_end(state, call_id, exit_code), False
        past.remove(run)
    elif run["closed"]:
        return [], True
    if start_ms is None:
        run["closed"] = "exec_end"
        return [_row(run, end_ms, end_ms, "exec_end", "exited", exit_code),
                outcomes.command(run["session_id"], run["run_id"], call_id,
                                           run["start_ms"], end_ms, "bounds", exit_code,
                                           "exec_end", "call_id")], True
    return [_exact_run(run, start_ms, end_ms, exit_code, "exec_end"),
            outcomes.command(run["session_id"], run["run_id"], call_id, start_ms,
                                       end_ms, "exact", exit_code, "exec_end", "call_id")], True


# A kept foreground run, for an exec_command_end after its output: every rollout keeps up
# to RECENT of them between index runs, so only what its row needs, in this order.
KEPT = ("session_id", "call_id", "start_ms", "end_ms", "operation_seq", "status", "exit_code")


def _kept_run_row(entry):
    kept = dict(zip(KEPT, entry, strict=True))
    run = {"session_id": kept["session_id"], "call_id": kept["call_id"],
           "run_id": kept["call_id"], "start_ms": kept["start_ms"],
           "start_hi_ms": kept["start_ms"], "mode": "foreground", "operation_seq": kept["operation_seq"]}
    return _row(run, kept["end_ms"], kept["end_ms"], "result", kept["status"],
                kept["exit_code"])


def _foreground_exec_end(state, call_id, exit_code):
    position = KEPT.index("call_id")
    entry = next((entry for entry in state.setdefault("recent_runs", [])
                  if entry[position] == call_id), None)
    if entry is None:
        return []
    entry[KEPT.index("status")] = "exited"
    entry[KEPT.index("exit_code")] = exit_code
    return [_kept_run_row(entry)]


def _foreground_run(state, call, call_id, status, at_ms, outcome):
    """A direct command's run and command row, closed at its output. A completion held
    from an item or exec_command_end wins over the header."""
    held = call.get("held")
    exit_code = held["exit_code"] if held is not None else status["exit_code"]
    rows = []
    if held is not None:
        # Its command row was written when the completion arrived (_hold).
        if outcome is not None:
            outcomes.add_exit(outcome, exit_code)
    elif exit_code is not None:
        rows.append(outcomes.command(call["session_id"], call_id, call_id,
                                               call["at_ms"], at_ms, "bounds", exit_code,
                                               "header", "call_id"))
    run = {"session_id": call["session_id"], "call_id": call_id, "run_id": call_id,
           "start_ms": call["at_ms"], "start_hi_ms": call["at_ms"], "mode": "foreground",
           "operation_seq": call["operation_seq"]}
    row = _row(run, at_ms, at_ms, "result", "completed" if exit_code is None else "exited",
               exit_code)
    recent = state.setdefault("recent_runs", [])
    recent.append([call["session_id"], call_id, call["at_ms"], at_ms, call["operation_seq"],
                   row["status"], exit_code])
    del recent[:-outcomes.RECENT]
    return [row, *rows]


RANK = {"item": 2, "exec_end": 1}


def _hold(state, call_id, source, exit_code, start_ms, end_ms):
    """A direct call's completion that arrived before its output: its command row is
    written now, under the call id, so it survives a call that never gets an output; the
    completion is kept for the output to say whether the run was foreground or a session.
    None when the output has already arrived. The stronger report wins."""
    call = state.setdefault("run_calls", {}).get(call_id)
    if call is None or call["kind"] != "command":
        return None
    held = call.get("held")
    if held is not None and RANK[source] < RANK[held["source"]]:
        return []
    timing = "exact" if start_ms is not None else "bounds"
    call["held"] = {"source": source, "exit_code": exit_code, "timing": timing,
                    "start_ms": start_ms if start_ms is not None else call["at_ms"],
                    "end_ms": end_ms}
    return [_held_row(call, call_id, call_id, call["held"])]


def _held_row(call, command_id, call_id, held):
    return outcomes.command(call["session_id"], command_id, call_id,
                                      held["start_ms"], held["end_ms"], held["timing"],
                                      held["exit_code"], held["source"], "call_id")


def _close_direct(run, held, command=True):
    """A direct session closed by its own item or exec_command_end; `command`
    False when the command row was already written under the call id (_hold)."""
    if held["timing"] == "exact":
        row = _exact_run(run, held["start_ms"], held["end_ms"], held["exit_code"], held["source"])
    else:
        run["closed"] = held["source"]
        row = _row(run, held["end_ms"], held["end_ms"], held["source"], "exited",
                   held["exit_code"])
    if not command:
        return [row]
    return [row, _held_row(run, run["run_id"], run["call_id"], held)]


def join_direct_item(state, info, session_id):
    """An item whose id is a direct call's id (never positional). Returns the rows
    and what the item named: "session" (it closed the call's session), "held" (the
    call's output has not arrived), or "foreground" (a finished call; the caller marks
    the call row)."""
    call_id = info["id"]
    start_ms = info["started_ms"]
    sessions = state.setdefault("command_sessions", {})
    past = state.setdefault("past_launches", [])
    run = next((run for run in [*sessions.values(), *past] if run["call_id"] == call_id), None)
    if run is not None:
        if run["closed"] == "item":
            return [], "session"
        if run in past:
            past.remove(run)
        held = {"source": "item", "exit_code": info["exit_code"],
                "timing": "exact" if info["timed"] else "bounds",
                "start_ms": start_ms if info["timed"] else run["start_ms"],
                "end_ms": info["completed_ms"]}
        return _close_direct(run, held), "session"
    held = _hold(state, call_id, "item", info["exit_code"], start_ms, info["completed_ms"])
    if held is not None:
        return held, "held"
    rows = _foreground_exec_end(state, call_id, info["exit_code"])
    start = start_ms if info["timed"] else (rows[0]["start_ms"] if rows else None)
    timing = "exact" if info["timed"] else ("bounds" if start is not None else "end_only")
    rows.append(outcomes.command(session_id, call_id, call_id, start,
                                           info["completed_ms"], timing, info["exit_code"],
                                           "item", "call_id"))
    return rows, "foreground"


def _exact_run(run, start_ms, end_ms, exit_code, basis):
    """The run closed with the exact times an item or exec_command_end reported."""
    run.update(start_ms=start_ms, start_hi_ms=start_ms, closed=basis)
    return _row(run, end_ms, end_ms, basis, "exited", exit_code)


def _remember(state, run):
    """A launch that left its session map without an exact report, kept until an item or
    exec_command_end joins it. No count limit: dropping one would
    let its late exact report write a second row. Joined launches leave the list."""
    state.setdefault("past_launches", []).append(run)


def _close_by_poll(state, run, end_lo_ms, end_ms, exit_code, source):
    """A session a poll saw exit: bounds only, until an exact report replaces them."""
    _remember(state, run)
    return [_row(run, end_lo_ms, end_ms, "exit_poll", "exited", exit_code),
            outcomes.command(run["session_id"], run["run_id"], run["call_id"],
                                       run["start_ms"], end_ms, "bounds", exit_code, source,
                                       "session")]


def on_output(state, call_id, output, at_ms, outcome=None):
    """The native run and command facts a call's output opens, updates or closes."""
    call = state.setdefault("run_calls", {}).pop(call_id, None)
    if call is None:
        return []
    text = output_text(output)
    if call["kind"] == "command":
        status = outcomes.harness_status(text)
        if status["session"] is None:
            return _foreground_run(state, call, call_id, status, at_ms, outcome)
        sessions = state.setdefault("command_sessions", {})
        previous = sessions.get(status["session"])
        if previous is not None and not previous["closed"]:
            _counters(state)["session_reused"] += 1
            _remember(state, previous)
        run = {"session_id": call["session_id"], "call_id": call_id,
               "run_id": f"{call_id}#s{status['session']}", "start_ms": call["at_ms"],
               "start_hi_ms": call["at_ms"], "end_lo_ms": at_ms, "mode": "exec_session",
               "operation_seq": call["operation_seq"], "session": status["session"], "closed": None}
        sessions[status["session"]] = run
        if call.get("held") is not None:
            # It ended before its output said it was running: closed now, and the poll
            # that later reports the same exit writes nothing. Its command row was
            # written under the call id when the completion arrived.
            return _close_direct(run, call["held"], command=False)
        return [_row(run, None, None, None, None, None)]
    if call["kind"] == "stdin":
        sessions = state.setdefault("command_sessions", {})
        run = sessions.get(call["session"])
        if run is None:
            _counters(state)["unmatched_poll"] += 1
            return []
        status = outcomes.harness_status(text)
        if status["exit_code"] is None:
            run["end_lo_ms"] = at_ms
            return []
        del sessions[call["session"]]
        if run["closed"]:
            return []
        return _close_by_poll(state, run, run["end_lo_ms"], at_ms, status["exit_code"], "header")
    if call["kind"] == "exec":
        running = RUNNING.match(text)
        if running:
            cell = running.group(1)
            origin = _origin(call, call_id, f"{call_id}#c{cell}", "exec_cell")
            origin["end_lo_ms"] = at_ms
            state.setdefault("run_cells", {})[cell] = origin
            return [_row(origin, None, None, None, None, None),
                    *_deliver(state, origin, text, at_ms, outcome)]
        origin = _origin(call, call_id, call_id, "foreground")
        status = _status(text)
        rows = [_row(origin, at_ms, at_ms, "result", status, None),
                *_deliver(state, origin, text, at_ms, outcome)]
        _finish(state, origin)
        return rows
    cells = state.setdefault("run_cells", {})
    origin = cells.get(call["cell"])
    not_found = NOT_FOUND.search(text)
    if origin is None or (not_found is not None and not_found.group(1) == call["cell"]):
        _counters(state)["unmatched_wait"] += 1
        return []
    if text.startswith("Script running"):
        origin["end_lo_ms"] = at_ms
        return _deliver(state, origin, text, at_ms)
    if not text.startswith(("Script completed", "Script failed", "Script terminated")):
        # An abort, or any other output that is not one of the script's own literal
        # end headers: the script has not ended, so the cell stays open for a later
        # wait to close, and only the output's own results pair.
        origin["end_lo_ms"] = at_ms
        return _deliver(state, origin, text, at_ms)
    del cells[call["cell"]]
    rows = [_row(origin, origin["end_lo_ms"], at_ms, "cell_wait", _status(text), None),
            *_deliver(state, origin, text, at_ms)]
    _finish(state, origin)
    return rows

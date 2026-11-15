"""Codex command, outcome and write associations, relocated from OBS 1e0afad1.

No command text is kept in state. Operation indices replace consumer lifecycle data.
"""
import json
import posixpath
import re
from . import index_codex_runs as runs, _index_codex_outcomes as outcomes
from .index_codex_coverage import applied
from .index_events import _size

PATCH_PATH = re.compile(r"\*\*\* (?:(?:Update|Add|Delete) File|Move to): (.+?)(?=\\n|\n|[\"'`]|$)")
CODEX_SHELL = ("exec_command", "shell_command", "shell")
# Where an object key can start in a blanked script: after `{` or `,`.
KEY_START = re.compile(r"[{,]\s*")
KEY_COLON = re.compile(r"\s*:\s*")
# A literal is a property's whole value only when the property ends right after it, as
# `runs.CMD` requires: `"/w/" + "x"` or `"/w".trim()` is an expression.
VALUE_END = re.compile(r"\s*[,}]")
# Codex tools that run no shell command.
CODEX_INERT = frozenset({"wait", "wait_agent", "spawn_agent", "send_message", "followup_task",
                         "list_agents", "request_user_input", "request_user_input_async",
                         "update_plan", "view_image", "web_search", "apply_patch"})


def codex_patch_paths(name, value):
    text = str(value)
    if name != "apply_patch" and not (name == "exec" and "tools.apply_patch(" in text):
        return []
    paths = [match.group(1).strip() for match in PATCH_PATH.finditer(text)]
    return paths or [None]


def codex_commands(name, value):
    text = str(value)
    if name in CODEX_SHELL:
        command = runs._function_command(text)
        if command is None and name == "shell" and not text.lstrip().startswith("{"):
            command = text
        return [command]
    if name == "exec":
        code = runs._code(text)
        if not runs._plain(text, code):
            return [None]
        commands = []
        for match in runs.OPERATION.finditer(code):
            if match.group(1) == "write_stdin":
                commands.append(None)
                continue
            found = runs.CMD.search(runs._argument(text, match.end() - 1))
            commands.append(runs._js_string(found.group(1)) if found else None)
        return commands
    if name in CODEX_INERT:
        return []
    return [None]


def _joined(cwd, workdir):
    """The directory a command ran in: its workdir against the directory current at the
    call; None when either is needed and not known."""
    if posixpath.isabs(workdir):
        return workdir
    return posixpath.join(cwd, workdir) if cwd else None


def _workdirs(text):
    """Each `workdir` key of the object literals in a script or an operation's argument,
    read from the script itself (a quoted key is blanked in the code): the key's value
    when that whole value is one string literal, else None. String contents never hold
    a key."""
    code, out = runs._code(text), []
    for start in KEY_START.finditer(code):
        at = start.end()
        if code.startswith("workdir", at):
            after = at + len("workdir")
        elif text[at:at + 1] in ("'", '"') and text[at + 1:at + 9] == "workdir" + text[at]:
            after = at + 9
        else:
            continue
        colon = KEY_COLON.match(code, after)
        if colon is None:
            continue
        literal = runs.STRINGS.match(text, colon.end())
        whole = literal is not None and VALUE_END.match(code, literal.end()) is not None
        out.append(runs._js_string(literal.group()) if whole else None)
    return out


def codex_directories(name, value, cwd):
    """The directory current for each command `codex_commands` reads from a call, in the
    same order: the command's own `workdir`, else the turn's directory `cwd`. An unreadable workdir (empty, not a string, not a whole
    string literal, or in a script whose commands cannot be read) leaves
    the directory unknown (None) rather than the turn's."""
    text = str(value)
    if name in CODEX_SHELL:
        arguments = codex_arguments(name, value)
        if arguments is None or "workdir" not in arguments:
            return [cwd]
        workdir = arguments["workdir"]
        return [_joined(cwd, workdir) if isinstance(workdir, str) and workdir else None]
    if name != "exec":
        return [cwd] * len(codex_commands(name, value))
    code = runs._code(text)
    if not runs._plain(text, code):
        return [None if _workdirs(text) else cwd]
    out = []
    for match in runs.OPERATION.finditer(code):
        found = [] if match.group(1) == "write_stdin" \
            else _workdirs(runs._argument(text, match.end() - 1))
        if not found:
            out.append(cwd)
            continue
        workdir = found[0] if len(found) == 1 else None
        out.append(_joined(cwd, workdir) if workdir else None)
    return out


def codex_arguments(name, value):
    """A Codex shell function call's arguments object, or None (another tool, or
    arguments that are not a JSON object)."""
    if name not in CODEX_SHELL:
        return None
    try:
        arguments = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return arguments if isinstance(arguments, dict) else None



# Named events can still arrive after output and usage; preserve the original bound.
UNNAMED = frozenset({'exec', 'wait', 'write_stdin'})
KEPT = ('session_id', 'call_id', 'at_ms', 'error', 'interrupted', 'duration_ms')


def _update(call):
    return {'session_id': call['session_id'], 'call_id': call['call_id'],
            'error': call['outcome']['error'], 'interrupted': call['outcome']['interrupted'],
            'duration_ms': call.get('duration_ms')}


def _retire(state, call):
    if call['tool'] in UNNAMED:
        return
    update = {**_update(call), 'at_ms': call['at_ms']}
    recent = state.setdefault('recent_calls', [])
    recent.append([update[key] for key in KEPT])
    del recent[:-outcomes.RECENT]


def _named_call(state, call_id):
    pending = state.setdefault('pending_tools', {}).get(call_id)
    if pending is not None:
        return pending, None
    entry = next((entry for entry in state.setdefault('recent_calls', [])
                  if entry[1] == call_id), None)
    return None, entry


def _mark(state, call_id, exit_code=None, failed=False):
    pending, entry = _named_call(state, call_id)
    if pending is not None:
        outcomes.add_exit(pending['outcome'], exit_code)
        pending['outcome']['error'] = pending['outcome']['error'] or failed
        return [_update(pending)]
    if entry is None:
        return None
    update = dict(zip(KEPT, entry, strict=True))
    outcome = {'error': update['error'] or failed, 'interrupted': update['interrupted']}
    outcomes.add_exit(outcome, exit_code)
    update.update(outcome)
    entry[:] = [update[key] for key in KEPT]
    update.pop('at_ms')
    return [update]


def _positional_failure(state):
    origins = state.setdefault('open_origins', {})
    if len(set(origins.values())) != 1:
        return []
    origin = next(iter(origins.values()))
    pending = state.setdefault('pending_tools', {}).get(origin)
    if origin in origins and pending is not None:
        pending['outcome']['error'] = True
        return [_update(pending)]
    return []


def _unmatched(state, call_id):
    if call_id in state.setdefault('call_ids', {}):
        outcomes.diagnostics(state)['late_event_unmatched'] += 1
        return []
    return _positional_failure(state)


def _open_origin(state):
    origins = set(state.setdefault('open_origins', {}).values())
    return origins.pop() if len(origins) == 1 else None


def _operation_statuses(entry, output):
    count, text = entry['count'], runs.output_text(output)
    if entry['name'] != 'exec':
        status = outcomes.harness_status(text)
        if status['session'] is not None or status['exit_code'] is None:
            return None
        return ['ok' if status['exit_code'] == 0 else 'failed'] * count
    if runs.RUNNING.match(text):
        return None
    results = runs.results(text)
    if not text.startswith('Script completed') or len(results) != count:
        return ['unknown'] * count
    return ['ok' if result['exit_code'] == 0 else 'failed' if result['exit_code'] is not None
            else 'unknown' for result in results]


def _settle_operations(state, key, statuses):
    state['pending_operations'].pop(key)
    return [{'call_id': key, 'seq': seq, 'status': status} for seq, status in enumerate(statuses)]


def _based(path, base):
    if path is None or posixpath.isabs(path) or not (isinstance(base, str) and posixpath.isabs(base)):
        return path
    return posixpath.normpath(posixpath.join(base, path))


def _writes(session_id, call_id, at_ms, paths, status, seqs=None):
    seqs = range(len(paths)) if seqs is None else seqs
    return [{'session_id': session_id, 'call_id': call_id, 'at_ms': at_ms,
             'seq': seq, 'path': path, 'status': status}
            for seq, path in zip(seqs, paths, strict=True)]


def _patch_rows(key, entry, status):
    seqs = sorted(entry['paths'], key=int)
    return _writes(entry['session_id'], key, entry['at_ms'],
                   [_based(entry['paths'][seq], entry['base']) for seq in seqs], status,
                   seqs=[int(seq) for seq in seqs])


def _resolve_patches(state, session_id, paths):
    pending = state.setdefault('pending_patches', {})
    rows, bases = [], {}
    for path in paths:
        owners = [(key, seq) for key, entry in pending.items()
                  if entry['open'] and entry['session_id'] == session_id
                  for seq, expected in entry['paths'].items() if expected == path]
        if len(owners) != 1:
            continue
        key, seq = owners[0]
        entry = pending[key]
        entry['paths'].pop(seq)
        bases[path] = entry['base']
        rows += _writes(entry['session_id'], key, entry['at_ms'],
                        [_based(path, entry['base'])], 'resolved', seqs=[int(seq)])
        if not entry['paths']:
            pending.pop(key)
    return rows, bases


def _add(execution, facts):
    for fact in facts:
        group = ('runs' if 'run_id' in fact else 'commands' if 'command_id' in fact else
                 'writes' if 'path' in fact else 'operations' if 'seq' in fact else 'call_updates')
        execution[group].append(fact)


def on_call(state, event, call, value):
    session_id, call_id, at_ms = event['identity']['session'], call['id'], event['at_ms']
    name = call['native_name']
    state.setdefault('pending_tools', {})[call_id] = {
        'session_id': session_id, 'call_id': call_id, 'at_ms': at_ms, 'tool': name,
        'usage_id': None, 'result_seen': False, 'outcome': outcomes.new_outcome()}
    state.setdefault('call_ids', {})[call_id] = 1
    if call['commands']:
        state.setdefault('pending_operations', {})[call_id] = {'name': name, 'count': len(call['commands'])}
        event['execution']['operations'] += [{'call_id': call_id, 'seq': seq, 'status': 'unknown'}
                                              for seq in range(len(call['commands']))]
    if call['patch_paths']:
        entry = {'session_id': session_id, 'at_ms': at_ms, 'open': True,
                 'base': state.get('turn_cwd'),
                 'paths': {str(seq): path for seq, path in enumerate(call['patch_paths'])}}
        state.setdefault('pending_patches', {})[call_id] = entry
        event['execution']['writes'] += _patch_rows(call_id, entry, 'unknown')
    runs.on_call(state, session_id, call_id, name, value, at_ms)
    origin = runs.origin_of(state, call_id)
    if origin is not None:
        state.setdefault('open_origins', {})[call_id] = origin
    event['execution']['call_updates'].append(_update(state['pending_tools'][call_id]))


def on_usage(state, response_id):
    pending = state.setdefault('pending_tools', {})
    for call_id, call in list(pending.items()):
        if call['usage_id'] is not None:
            continue
        call['usage_id'] = response_id
        if call['result_seen']:
            _retire(state, pending.pop(call_id))


def on_output(state, event, payload, day):
    session_id, at_ms = event['identity']['session'], event['at_ms']
    applied(state, session_id, day, 'tool_output',
            {'call_id': payload.get('call_id') is not None, 'output': payload.get('output') is not None})
    call_id = payload.get('call_id')
    origin = state.setdefault('open_origins', {}).pop(call_id, None)
    call = state.setdefault('pending_tools', {}).get(call_id)
    output = payload.get('output')
    facts = runs.on_output(state, call_id, output, at_ms, call['outcome'] if call is not None else None)
    own = outcomes.new_outcome()
    if call is not None:
        text = runs.output_text(output)
        status = outcomes.harness_status(text)
        outcomes.apply_output(call['outcome'], call['tool'], status)
        outcomes.apply_output(own, call['tool'], status)
        if call['tool'] == 'wait' and runs.NOT_FOUND.search(text):
            call['outcome']['error'] = own['error'] = True
        operations = state.setdefault('pending_operations', {})
        patches = state.setdefault('pending_patches', {})
        final = not runs.RUNNING.match(text)
        for key in dict.fromkeys(k for k in (origin, call_id) if k is not None):
            if key in patches and final:
                patches[key]['open'] = False
            if key in operations:
                statuses = _operation_statuses(operations[key], output)
                if statuses is not None:
                    event['execution']['operations'] += _settle_operations(state, key, statuses)
        call['result_seen'] = True
        call['duration_ms'] = at_ms - call['at_ms']
        event['execution']['call_updates'].append(_update(call))
        if call['usage_id'] is not None:
            _retire(state, state['pending_tools'].pop(call_id))
    # A result's status belongs to its own call, distinct from associated command exits.
    cut, tokens, size = outcomes.truncation(payload.get('output', ''))
    event['results'].append({'call_id': call_id, 'bytes': _size(payload.get('output', '')),
        'error': own['error'] if call is not None else None,
        'interrupted': own['interrupted'] if call is not None else None,
        'native_duration_ms': None, 'background_id': None, 'agent': None,
        'child_session': None, 'answers': None,
        'truncation': {'kind': cut, 'original_tokens': tokens, 'original_bytes': size}})
    _add(event['execution'], facts)


def _exec_end(state, session, payload, at_ms, day):
    call_id, exit_code = payload.get("call_id"), payload.get("exit_code")
    duration = outcomes.duration_ms(payload.get("duration"))
    applied(state, session["session_id"], day, "exec_end",
                     {"call_id": call_id is not None, "exit_code": exit_code is not None,
                      "duration": duration is not None})
    exit_code = exit_code if type(exit_code) is int else None
    pending = state.setdefault("pending_operations", {}).get(call_id)
    if pending is not None and pending["name"] != "exec" and exit_code is not None:
        yield from _settle_operations(state, call_id,
                                     ["ok" if exit_code == 0 else "failed"] * pending["count"])
    start_ms = at_ms - duration if duration is not None else None
    run_rows, session_run = runs.on_exec_end(state, call_id, exit_code, start_ms, at_ms)
    yield from run_rows
    if session_run:
        return
    pending, entry = _named_call(state, call_id)
    if pending is None and entry is None:
        outcomes.diagnostics(state)["late_event_unmatched"] += 1
        return
    yield from _mark(state, call_id, exit_code=exit_code)
    call_ms = pending["at_ms"] if pending is not None else entry[2]
    yield _exec_end_row(session["session_id"], call_id, call_ms, start_ms, at_ms, exit_code)

def _exec_end_row(session_id, call_id, call_ms, start_ms, end_ms, exit_code):
    """Exact from the event's duration; bounded by the call when it has none."""
    if start_ms is None:
        return outcomes.command(session_id, call_id, call_id, call_ms, end_ms,
                                          "bounds", exit_code, "exec_end", "call_id")
    return outcomes.command(session_id, call_id, call_id, start_ms, end_ms, "exact",
                                      exit_code, "exec_end", "call_id")

def _item(state, session, payload, at_ms, day):
    item = payload.get("item") or {}
    kind = item.get("type")
    session_id = session["session_id"]
    if kind in ("FileChange", "McpToolCall"):
        applied(state, session_id, day, "tool_item",
                         {"status": item.get("status") is not None})
        if outcomes.item_failed(item):
            yield from _positional_failure(state)
        if kind == "FileChange":
            paths = sorted(item.get("changes") or {})
            status = {"completed": "ok", "failed": "failed",
                      "declined": "failed"}.get(item.get("status"), "unknown")
            # Settled against the raw header paths; a path that settles a patch is located
            # against that patch's directory, any other against the turn's.
            settled, bases = _resolve_patches(state, session_id, paths) if status != "unknown" else ([], {})
            yield from _writes(
                session_id, item.get("id"), at_ms,
                [_based(path, bases[path] if path in bases else state.get("turn_cwd")) for path in paths],
                status)
            yield from settled
        return
    if kind != "CommandExecution":
        return
    started, completed = payload.get("started_at_ms"), payload.get("completed_at_ms")
    exit_code, process_id = item.get("exit_code"), item.get("process_id")
    applied(state, session_id, day, "command_item",
                     {"id": item.get("id") is not None, "exit_code": exit_code is not None,
                      "process_id": process_id is not None, "started_at_ms": started is not None,
                      "completed_at_ms": completed is not None})
    state["command_items_seen"] = True
    timed = type(started) is int and type(completed) is int
    info = {"id": item.get("id"), "process_id": None if process_id is None else str(process_id),
            "timed": timed, "started_ms": started if timed else None,
            "completed_ms": completed if timed else at_ms,
            "exit_code": exit_code if type(exit_code) is int else None}
    if info["id"] in state.setdefault("call_ids", {}):
        # A direct call's own item: joined by id, never by position.
        rows, named = runs.join_direct_item(state, info, session_id)
        yield from rows
        if named == "foreground":
            yield from _mark(state, info["id"], exit_code=info["exit_code"]) or []
        return
    rows = runs.join_item(state, info) if timed else None
    if rows is not None:
        yield from rows
        return
    origins = state.setdefault("open_origins", {})
    origin = _open_origin(state)
    if origin is None:
        counter = "commands_ambiguous" if origins else "commands_unattributed"
        outcomes.diagnostics(state)[counter] += 1
        if timed and info["process_id"] is not None:
            runs.keep_loose(state, info, counter)
        yield outcomes.command(session_id, info["id"], None, info["started_ms"],
                                         info["completed_ms"], "exact" if timed else "end_only",
                                         info["exit_code"], "item", "none")
        return
    pending = state.setdefault("pending_tools", {}).get(origin)
    if origin in origins and pending is not None:
        outcomes.add_exit(pending["outcome"], info["exit_code"])
        yield _update(pending)
    runs.note_item(state, origin, info)
    start_ms, timing = info["started_ms"], "exact"
    if not timed:
        start_ms = runs.origin_start(state, origin)
        timing = "bounds" if start_ms is not None else "end_only"
    yield outcomes.command(session_id, info["id"], origin, start_ms,
                                     info["completed_ms"], timing, info["exit_code"],
                                     "item", "position")

def _patch_end(state, session, payload, day):
    call_id, success = payload.get("call_id"), payload.get("success")
    applied(state, session["session_id"], day, "patch_end",
                     {"call_id": call_id is not None, "success": success is not None})
    # A missing outcome is not a negative one: the paths stay pending.
    entry = state.setdefault("pending_patches", {}).pop(call_id, None) if type(success) is bool else None
    if entry is not None:
        yield from _patch_rows(call_id, entry, "ok" if success else "failed")
    if success is not False:
        return
    rows = _mark(state, call_id, failed=True)
    if rows is None:
        yield from _unmatched(state, call_id)
        return
    yield from rows

def _mcp_end(state, session, payload, day):
    call_id, result = payload.get("call_id"), payload.get("result")
    applied(state, session["session_id"], day, "mcp_end",
                     {"call_id": call_id is not None, "result": result is not None})
    if not outcomes.mcp_end_failed(result):
        return
    rows = _mark(state, call_id, failed=True)
    if rows is None:
        yield from _unmatched(state, call_id)
        return
    yield from rows


def on_event(state, event, payload, day):
    session = {'session_id': event['identity']['session']}
    kind = payload.get('type')
    if kind == 'turn_aborted':
        state['open_origins'] = {}
    elif kind == 'exec_command_end':
        _add(event['execution'], _exec_end(state, session, payload, event['at_ms'], day))
    elif kind == 'item_completed':
        _add(event['execution'], _item(state, session, payload, event['at_ms'], day))
    elif kind == 'patch_apply_end':
        _add(event['execution'], _patch_end(state, session, payload, day))
    elif kind == 'mcp_tool_call_end':
        _add(event['execution'], _mcp_end(state, session, payload, day))

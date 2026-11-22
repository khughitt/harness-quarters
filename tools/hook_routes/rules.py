"""Check the live and proposed policy paths independently."""
from dataclasses import dataclass
from pathlib import Path
import re
import shlex

from .table import Finding, RouteState, Table

__all__ = ["PolicyRoute", "route_status", "validate"]

_NOTIFICATION_MATCHERS = {"idle_prompt", "permission_prompt"}
_HOME_PREFIXES = ("~/", "@HOME@/", "$HOME/", "${HOME}/")
_AGY_BRIDGE = "d/hq/harnesses/agy/hook"
_RELAY_BUILTINS = {"relay-hooks", "relay-provenance"}


@dataclass(frozen=True)
class PolicyRoute:
    policy: str
    home: str
    event: str
    matcher: str | None
    state: RouteState | None
    next: RouteState | None
    moving: bool


def _where(home, binding, index):
    return f"{home}:{binding.event}[{index}]"


def _home_relative(token):
    for prefix in (*_HOME_PREFIXES, str(Path.home()) + "/"):
        if token.startswith(prefix):
            return token[len(prefix):]
    return token


def _fixed_tool(home, binding):
    if (home.harness in ("claude-code", "codex")
            and binding.event in ("PreToolUse", "PostToolUse", "PostToolUseFailure")
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", binding.matcher or "")):
        return binding.matcher
    return None


def _admitted(entry, home, binding, line):
    tool = _fixed_tool(home, binding)
    return (
        (entry.harnesses is None or home.harness in entry.harnesses)
        and (entry.nativeEvents is None or (line.relay_event or binding.event) in entry.nativeEvents)
        and (entry.kinds is None or line.relay_kind is None or line.relay_kind in entry.kinds)
        and (entry.tools is None or tool is None or tool in entry.tools)
    )


def _selected_entries(table, files, home, binding, line):
    if line.subscriber_file is None:
        return ()
    return tuple(
        entry for entry in files[line.subscriber_file].subscribers
        if _admitted(entry, home, binding, line)
        and (line.relay_kind is not None or entry.nativeEvents is not None or entry.kinds is None
             or table.subscribers[entry.name].policy in line.policies)
    )


def _declared_policies(table, line, entries):
    return dict.fromkeys((*line.policies, *(table.subscribers[entry.name].policy for entry in entries)))


def _overlap(event, left, right):
    if event == "Notification" and {left, right} == _NOTIFICATION_MATCHERS:
        return False
    return True


def _state_problem(state, kind, *, records):
    if state is None:
        return "a runnable policy needs a declared state"
    if state.kind == "native" and kind == "native" and _text(state.owner) and _text(state.reason):
        return None
    if state.kind == "existing" and kind == "relay" and _text(state.owner) and _text(state.grant):
        return None
    if state.kind == kind == "relay" and (not records or state.records and all(map(_text, state.records))):
        return None
    if state.kind == kind == "bridge" and _text(state.evidence):
        return None
    return f"{state.kind} state on a {kind} line needs its owner and reason, owner and grant, records or bridge evidence"


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _configuration(table, *, target):
    files = table.subscriber_files
    if target:
        files = files | table.target_files
    for name, home, index, binding in table.bindings():
        lines = binding.target if target else binding.lines
        for line in lines:
            yield name, home, index, binding, line, files


def route_status(table: Table) -> list[PolicyRoute]:
    def collect(target):
        routes = {}
        for name, home, _, binding, line, files in _configuration(table, target=target):
            entries = _selected_entries(table, files, home, binding, line)
            for policy in _declared_policies(table, line, entries):
                key = (policy, name, binding.event, binding.matcher)
                routes[key] = (table.policy_state(policy, line), binding.next is not None)
        return routes

    live, target = collect(False), collect(True)
    status = []
    for key in dict.fromkeys((*live, *target)):
        state, leaves_binding = live.get(key, (None, False))
        next_state, enters_binding = target.get(key, (None, False))
        moving = leaves_binding or enters_binding
        status.append(PolicyRoute(*key, state, next_state if moving else None, moving))
    return status


def _repository_tokens(table, line, home):
    args = []
    if line.command is not None:
        command = shlex.split(line.command)
        # hq owns the agy transport; the restriction still applies to its delegates.
        if line.kind == "bridge" and home.harness == "agy" and command and _home_relative(command[0]) == _AGY_BRIDGE:
            command = command[1:]
        args.extend(command)
    for argv in line.delegates:
        args.extend(argv)
    if line.kind == "relay":
        runtime = table.runtimes[line.runtime]
        args.extend((runtime.command, runtime.script))
    return [arg for arg in args if _home_relative(arg).startswith("d/")]


def _owns_repository_path(state):
    return state is not None and state.kind in ("native", "existing") and _text(state.owner)


def _check_subscriber_paths(table, *, target):
    if target:
        files = table.subscriber_files | table.target_files
        used = {table.reconciliation_next or table.reconciliation_file}
    else:
        files = table.subscriber_files
        used = set(files)

    authorities = {}
    for _, home, _, binding, line, _ in _configuration(table, target=target):
        source = line.subscriber_file
        if source is None:
            continue
        used.add(source)
        entries = _selected_entries(table, files, home, binding, line)
        for policy in _declared_policies(table, line, entries):
            key = source, policy
            authorities[key] = authorities.get(key, True) and _owns_repository_path(table.policy_state(policy, line))

    # Every entry is emitted, including those outside all selectors of a binding.
    for source in sorted(used):
        for entry in files[source].subscribers:
            subscriber = table.subscribers[entry.name]
            path = next((arg for arg in subscriber.argv if _home_relative(arg).startswith("d/")), None)
            if path is None:
                continue
            policy = subscriber.policy
            if not authorities.get((source, policy), _owns_repository_path(table.states.get(policy))):
                yield Finding("repository-path", f"{source}:{entry.name}",
                              f"subscriber repository path needs an owned native or existing policy: {path}")


def _check_configuration(table, *, target, records):
    findings = []
    paths = {}
    mode = "next" if target else "state"
    for name, home, index, binding, line, files in _configuration(table, target=target):
        entries = _selected_entries(table, files, home, binding, line)
        subscriber_policies = {table.subscribers[entry.name].policy for entry in entries}
        for policy in _declared_policies(table, line, entries):
            where = f"{_where(name, binding, index)}:{policy}:{mode}"
            state = table.policy_state(policy, line)
            problem = _state_problem(state, line.kind, records=records)
            if problem is not None:
                findings.append(Finding("route-state", where, problem))
            elif line.kind == "relay" and policy not in _RELAY_BUILTINS and policy not in subscriber_policies:
                findings.append(Finding("route-selection", where, "relay route needs a subscriber on this binding"))
            # A grandfathered path is permitted only if it has a named owner.
            if state is not None and state.kind not in ("native", "existing"):
                args = _repository_tokens(table, line, home)
                if args:
                    findings.append(Finding("repository-path", where, f"repository path in {state.kind} route: {args[0]}"))
            key = (name, binding.event, policy)
            prior = paths.setdefault(key, [])
            if any(_overlap(binding.event, matcher, binding.matcher) for matcher in prior):
                findings.append(Finding("duplicate-route", where, "policy can run on more than one path"))
            prior.append(binding.matcher)
    return findings


def _reconcile_observers(table, source):
    return {
        entry.name for entry in source.subscribers
        if table.subscribers[entry.name].role == "observer" and "reconcile" in (entry.kinds or ())
    }


def _check_reconciliation(table, removals):
    files = table.subscriber_files | table.target_files
    current_name = table.reconciliation_file
    current = _reconcile_observers(table, table.subscriber_files[current_name])

    def required(target):
        names = {line.subscriber_file for _, _, _, _, line, _ in _configuration(table, target=target)}
        return current.union(*(_reconcile_observers(table, files[name]) for name in names - {None}))

    live_missing = required(False) - current
    if live_missing:
        yield Finding("reconciliation", current_name,
                      f"missing reconcile observers: {', '.join(sorted(live_missing))}")
    target_name = table.reconciliation_next or current_name
    target_missing = required(True) - removals - _reconcile_observers(table, files[target_name])
    if target_name == current_name:
        target_missing -= live_missing
    if target_missing:
        yield Finding("reconciliation", target_name,
                      f"missing reconcile observers in target: {', '.join(sorted(target_missing))}")


def _check_removals(table, removals):
    files = table.subscriber_files | table.target_files
    for name, home, index, binding in table.bindings():
        current_entries = {
            entry.name
            for line in binding.lines if line.subscriber_file is not None
            for entry in table.subscriber_files[line.subscriber_file].subscribers
        }
        for line in binding.target:
            if line.subscriber_file is None:
                continue
            retained = {entry.name for entry in files[line.subscriber_file].subscribers} & removals
            for entry in sorted(retained):
                where = _where(name, binding, index)
                detail = "move this binding off its containing file" if entry in current_entries else "drop it from the target composition"
                yield Finding("retirement-reference", where, f"{entry}: {detail}")
    target_name = table.reconciliation_next or table.reconciliation_file
    for entry in files[target_name].subscribers:
        if entry.name in removals:
            yield Finding("retirement-reference", target_name, f"{entry.name} is still present in reconciliation")


def _coverage_key(name, binding):
    return name, binding.event, None if binding.matcher == "*" else binding.matcher


def _includes_filter(allowed, required):
    return allowed is None or (required is not None and set(required).issubset(allowed))


def _preserves_selection(line, entry, target_line, target_entry, binding, tool):
    if (target_line.relay_event or binding.event) != (line.relay_event or binding.event):
        return False
    if line.relay_kind is not None and target_line.relay_kind not in (None, line.relay_kind):
        return False
    kinds = (line.relay_kind,) if line.relay_kind is not None else entry.kinds
    tools = (tool,) if tool is not None else entry.tools
    return _includes_filter(target_entry.kinds, kinds) and _includes_filter(target_entry.tools, tools)


def _check_cutover_coverage(table, removals):
    target_policies = {}
    target_entries = {}
    for name, home, _, binding, line, files in _configuration(table, target=True):
        key = _coverage_key(name, binding)
        entries = _selected_entries(table, files, home, binding, line)
        target_policies.setdefault(key, set()).update(_declared_policies(table, line, entries))
        target_entries.setdefault(key, []).extend((line, entry) for entry in entries)

    for name, home, index, binding, line, files in _configuration(table, target=False):
        if binding.next is None:
            continue
        key = _coverage_key(name, binding)
        where = _where(name, binding, index)
        entries = _selected_entries(table, files, home, binding, line)
        for policy in _declared_policies(table, line, entries):
            if policy in target_policies.get(key, ()):
                continue
            retired = {entry.name for entry in entries if table.subscribers[entry.name].policy == policy}
            if retired and retired <= removals and policy not in _RELAY_BUILTINS:
                continue
            yield Finding("missing-route", f"{where}:{policy}:next", "live policy needs a target path on this binding's event and matcher")

        tool = _fixed_tool(home, binding)
        for entry in entries:
            if entry.name in removals:
                continue
            if not any(entry.name == other.name and _preserves_selection(line, entry, next_line, other, binding, tool)
                       for next_line, other in target_entries.get(key, ())):
                yield Finding("cutover-composition", where,
                              f"target must retain the applicable selector for {entry.name}")


def validate(table: Table, *, records: bool = True) -> list[Finding]:
    findings = []
    for name in sorted(table.subscriber_files.keys() & table.target_files.keys()):
        findings.append(Finding("cutover-scope", name, "target file would replace a live subscriber file"))
    if findings:
        return findings

    removals = set()
    for removal in table.removals:
        if not _text(removal.owner) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*-[a-f0-9]{6}", removal.owner):
            findings.append(Finding("removal-owner", removal.subscriber, "removal needs an authorizing owner task"))
        elif removal.subscriber not in table.subscribers:
            findings.append(Finding("removal-subscriber", removal.subscriber, "removal needs a declared subscriber"))
        elif removal.subscriber in removals:
            findings.append(Finding("removal-subscriber", removal.subscriber, "subscriber is listed for removal twice"))
        else:
            removals.add(removal.subscriber)

    current = _check_configuration(table, target=False, records=records)
    findings.extend(current)
    findings.extend(_check_subscriber_paths(table, target=False))
    has_moves = any(binding.next is not None for _, _, _, binding in table.bindings())
    if has_moves:
        # A defect inherited by the target is already reported against state.
        existing = {(finding.code, finding.where.removesuffix(":state"), finding.message) for finding in current}
        for finding in _check_configuration(table, target=True, records=records):
            if (finding.code, finding.where.removesuffix(":next"), finding.message) not in existing:
                findings.append(finding)
        findings.extend(_check_cutover_coverage(table, removals))
    if has_moves or table.reconciliation_next is not None:
        findings.extend(finding for finding in _check_subscriber_paths(table, target=True) if finding not in findings)
    findings.extend(_check_reconciliation(table, removals))
    findings.extend(_check_removals(table, removals))
    return findings

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


def _admitted(entry, home, binding):
    return (
        (entry.harnesses is None or home.harness in entry.harnesses)
        and (entry.nativeEvents is None or binding.event in entry.nativeEvents)
    )


def _declared_policies(table, files, home, binding, line):
    policies = dict.fromkeys(line.policies)
    if line.subscriber_file is not None:
        for entry in files[line.subscriber_file].subscribers:
            # Kind-only selectors require relay's projection. Native event selectors
            # give the table enough information to check the possible path directly.
            if _admitted(entry, home, binding) and (entry.nativeEvents is not None or entry.kinds is None):
                policies[table.subscribers[entry.name].policy] = None
    return policies


def _overlap(event, left, right):
    if event == "Notification" and {left, right} == _NOTIFICATION_MATCHERS:
        return False
    return True


def _check_state(state, kind, where, findings, *, records):
    if state is None:
        findings.append(Finding("route-state", where, "a runnable policy needs a declared state"))
    elif state.kind == "native" and kind == "native" and _text(state.owner) and _text(state.reason):
        return
    elif state.kind == "existing" and kind == "relay" and _text(state.owner) and _text(state.grant):
        return
    elif state.kind == kind == "relay" and (not records or state.records and all(map(_text, state.records))):
        return
    elif state.kind == kind == "bridge" and _text(state.evidence):
        return
    else:
        findings.append(Finding(
            "route-state", where,
            f"{state.kind} state on a {kind} line needs its owner and reason, owner and grant, records or bridge evidence",
        ))


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
            for policy in _declared_policies(table, files, home, binding, line):
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


def _repository_tokens(table, files, line, policy, home, binding):
    args = []
    if line.command is not None:
        command = shlex.split(line.command)
        # hq owns the agy transport; the restriction still applies to its delegates.
        if line.kind == "bridge" and home.harness == "agy" and command and _home_relative(command[0]) == _AGY_BRIDGE:
            command = command[1:]
        args.extend(command)
    for argv in line.delegates:
        args.extend(argv)
    if line.subscriber_file is not None:
        source = files[line.subscriber_file]
        for entry in source.subscribers:
            subscriber = table.subscribers[entry.name]
            if subscriber.policy == policy and _admitted(entry, home, binding):
                args.extend(subscriber.argv)
    return [arg for arg in args if _home_relative(arg).startswith("d/")]


def _check_configuration(table, *, target, records):
    findings = []
    paths = {}
    mode = "next" if target else "state"
    for name, home, index, binding, line, files in _configuration(table, target=target):
        for policy in _declared_policies(table, files, home, binding, line):
            where = f"{_where(name, binding, index)}:{policy}:{mode}"
            state = table.policy_state(policy, line)
            _check_state(state, line.kind, where, findings, records=records)
            if state is not None and state.kind == line.kind == "relay" and policy not in _RELAY_BUILTINS:
                if not any(table.subscribers[entry.name].policy == policy and _admitted(entry, home, binding)
                           for entry in files[line.subscriber_file].subscribers):
                    findings.append(Finding("route-selection", where, "relay route needs a subscriber on this binding"))
            # A grandfathered path is permitted only if it has a named owner.
            if state is not None and state.kind not in ("native", "existing"):
                args = _repository_tokens(table, files, line, policy, home, binding)
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
    # A pointer changed directly in state still has to keep the observers declared
    # by its live compositions. Rollback-only compositions can hold retired entries.
    live_names = {line.subscriber_file for _, _, _, _, line, _ in _configuration(table, target=False)}
    required = current.union(*(_reconcile_observers(table, table.subscriber_files[name])
                               for name in live_names - {None}))
    if required - current:
        yield Finding("reconciliation", current_name,
                      f"missing reconcile observers: {', '.join(sorted(required - current))}")
    if table.reconciliation_next is not None:
        target = _reconcile_observers(table, files[table.reconciliation_next])
        missing = required - removals - target
        if missing:
            yield Finding("reconciliation", table.reconciliation_next,
                          f"missing reconcile observers: {', '.join(sorted(missing))}")


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


def _check_compositions(table, removals):
    files = table.subscriber_files | table.target_files
    for name, home, index, binding in table.bindings():
        if binding.next is None:
            continue
        # Routes can move between two groups of the same event and matcher.
        related = [item for item in home.bindings if (item.event, item.matcher) == (binding.event, binding.matcher)]
        target_entries = {
            entry.name
            for other in related for line in other.target if line.subscriber_file is not None
            for entry in files[line.subscriber_file].subscribers if _admitted(entry, home, other)
        }
        required = {
            entry.name
            for line in binding.lines if line.subscriber_file is not None
            for entry in table.subscriber_files[line.subscriber_file].subscribers
            if _admitted(entry, home, binding)
            and (entry.nativeEvents is not None or entry.kinds is None or table.subscribers[entry.name].policy in line.policies)
        }
        missing = required - target_entries - removals
        if missing:
            yield Finding("cutover-composition", _where(name, binding, index),
                          f"cutover drops subscribers without a removal: {', '.join(sorted(missing))}")


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
    if any(binding.next is not None for _, _, _, binding in table.bindings()):
        # A defect inherited by the target is already reported against state.
        existing = {(finding.code, finding.where.removesuffix(":state"), finding.message) for finding in current}
        for finding in _check_configuration(table, target=True, records=records):
            if (finding.code, finding.where.removesuffix(":next"), finding.message) not in existing:
                findings.append(finding)
    findings.extend(_check_reconciliation(table, removals))
    findings.extend(_check_removals(table, removals))
    findings.extend(_check_compositions(table, removals))
    return findings

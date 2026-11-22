"""Compare qualification records with a binding and its actual relay composition."""
from hashlib import sha256
import json
from pathlib import Path
import sys

from .relay_runtime import budget_payload, call, package_for
from .render import subscriber_address, subscriber_bytes
from .rules import RELAY_BUILTINS, fixed_tool, selected_entries
from .table import Finding

__all__ = ["check_binding", "qualification_findings"]

_MODES = ("interactive", "non-interactive")


def _records(directory, filenames):
    if not filenames:
        raise ValueError("relay route needs qualification records")
    for name in filenames:
        path = directory / name
        if Path(name).name != name or not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f"record outside qualification directory: {name}")
        text = path.read_text()
        yield name, text, json.loads(text)


def _evidence(table, line, entries):
    policies = dict.fromkeys((*line.policies, *(table.subscribers[e.name].policy for e in entries)))
    return {policy: state.records for policy in policies
            if (state := table.policy_state(policy, line)) and state.kind == "relay"}


def _line_findings(table, home, binding, line, files, records_dir, render_home, versions, where):
    source = files[line.subscriber_file]
    # An undeclared implicit policy may be selected by the actual adapter. Include
    # every file entry here before deciding whether a runtime check is needed.
    possible = _evidence(table, line, source.subscribers)
    if not possible:
        return
    data = subscriber_bytes(table, source, render_home)
    package = package_for(table, line.runtime, render_home)
    payload = budget_payload(home, binding, line, data, tool=fixed_tool(home, binding))
    actual = call(package, "budget", payload)
    selected = [e for e in source.subscribers if e.name in actual["subscribers"]]
    evidence = _evidence(table, line, selected)
    expected = selected_entries(table, files, home, binding, line)
    if not evidence and not _evidence(table, line, expected):
        return
    if line.relay_kind is not None and line.relay_kind != actual["kind"]:
        raise ValueError(f"declared relay_kind {line.relay_kind} differs from pinned relay's {actual['kind']}")
    if set(actual["subscribers"]) != {e.name for e in expected}:
        raise ValueError(f"declared selector coverage differs from pinned relay's {actual['subscribers']}")
    selected_policies = {table.subscribers[e.name].policy for e in selected}
    missing = set(line.policies) - selected_policies - RELAY_BUILTINS
    if missing:
        raise ValueError(f"no selected subscriber for {', '.join(sorted(missing))}")

    if payload["event"] not in (binding.event, f"{binding.event}:{binding.matcher}"):
        raise ValueError(f"{payload['event']} does not name the rendered event and matcher")
    digest = sha256(data).hexdigest()
    expected_address = f"{line.runtime}-{digest[:12]}/relay/subscribers.json"
    if subscriber_address(source, data, render_home) != expected_address:
        raise ValueError(f"qualified relay binding needs its digest-addressed file {expected_address}")

    for policy, filenames in evidence.items():
        covered = {}
        for name, text, record in _records(records_dir, filenames):
            version, mode = record["version"], record["sessionMode"]
            if mode not in _MODES:
                raise ValueError(f"{name}: unexpected session mode {mode}")
            target = dict(harness=home.harness, version=version, mode=mode, platform=sys.platform,
                          relayCommit=table.runtimes[line.runtime].commit, configDigest=digest)
            try:
                call(package, "qualify", dict(payload, record=text, target=target))
            except ValueError as error:
                raise ValueError(f"{name}: {error}") from error
            covered.setdefault(version, set()).add(mode)
        required = covered.keys() if versions is None else [versions.get(home.harness, "unknown")]
        for version in required:
            absent = [mode for mode in _MODES if mode not in covered.get(version, ())]
            if absent:
                yield Finding("qualification", f"{where}:{policy}",
                              f"{home.harness} {version} missing qualification for {', '.join(absent)}")


def check_binding(table, binding, records_dir: Path, *, home=None, target=None, versions=None) -> list[Finding]:
    render_home = Path.home() if home is None else home
    name, settings, index, _ = next(row for row in table.bindings() if row[3] is binding)
    variants = []
    if target is not True:
        variants.append(("state", binding.lines))
    if target is True or (target is None and binding.next is not None):
        variants.append(("next", binding.target))
    findings = []
    for which, lines in variants:
        files = table.subscriber_files if which == "state" else table.subscriber_files | table.target_files
        for line in lines:
            if line.kind != "relay":
                continue
            where = f"{name}:{binding.event}[{index}]:{which}"
            try:
                findings.extend(_line_findings(table, settings, binding, line, files, records_dir,
                                                render_home, versions, where))
            except (OSError, ValueError, KeyError, TypeError) as error:
                findings.append(Finding("qualification", where, str(error)))
    return findings


def qualification_findings(table, *, home=None, target=None, versions=None):
    directory = table.root / "harnesses/qualification"
    return [finding for _, _, _, binding in table.bindings()
            for finding in check_binding(table, binding, directory, home=home, target=target, versions=versions)]

"""Encode hook bindings in each harness's tracked settings format."""
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import shlex

from .rules import validate
from .table import Finding, SubscriberFile, Table, expand_path, load_candidate

__all__ = ["render_live", "render_next", "render_candidate", "splice_claude_hooks", "check_live",
           "subscriber_bytes", "subscriber_address", "claude_hooks"]


def _space(text, index):
    while index < len(text) and text[index] in " \r\n\t":
        index += 1
    return index


def _claude_hooks_span(text):
    decoder = json.JSONDecoder()
    opening = _space(text, 0)
    if text[opening:opening + 1] != "{":
        raise ValueError("Claude settings must be a JSON object")
    index = _space(text, opening + 1)
    span = None
    while text[index:index + 1] != "}":
        key, separator = decoder.raw_decode(text, index)
        colon = _space(text, separator)
        if not isinstance(key, str) or text[colon:colon + 1] != ":":
            raise ValueError("expected a JSON object member")
        start = _space(text, colon + 1)
        _, end = decoder.raw_decode(text, start)
        if key == "hooks":
            if span is not None:
                raise ValueError("duplicate top-level hooks member")
            line_start = text.rfind("\n", 0, index) + 1
            prefix = text[line_start:index]
            indent = prefix[:len(prefix) - len(prefix.lstrip(" \t"))]
            span = start, end, indent
        index = _space(text, end)
        if text[index:index + 1] != ",":
            break
        index = _space(text, index + 1)
        if text[index:index + 1] == "}":
            raise ValueError("unexpected trailing comma in Claude settings")
    if text[index:index + 1] != "}" or _space(text, index + 1) != len(text):
        raise ValueError("expected the end of the Claude settings object")
    if span is None:
        raise ValueError("missing top-level hooks member")
    return span


def claude_hooks(data: bytes):
    text = data.decode("utf-8")
    start, end, _ = _claude_hooks_span(text)
    return json.loads(text[start:end])


def splice_claude_hooks(text: str, hooks: dict) -> str:
    start, end, indent = _claude_hooks_span(text)
    value = json.dumps(hooks, indent=2, ensure_ascii=False).replace("\n", "\n" + indent)
    return text[:start] + value + text[end:]


def _json_file(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _quote(value):
    # The current relay images enclose even uncomplicated paths in single quotes.
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _command(table, binding, line, harness, home):
    if line.kind == "bridge" and binding.event == "Stop":
        [launcher] = shlex.split(line.command)
        [guard] = line.delegates
        package = table.runtimes[line.runtime].package_dir(home)
        # Keep ~/ relative to the eventual shell's home, as in the native bridge.
        launcher = ("~/" + shlex.quote(launcher[2:]) if launcher.startswith("~/") else shlex.quote(launcher))
        return launcher + " " + shlex.join(["Stop", "--runtime", str(package), "--guard", shlex.join(guard)])
    if line.kind in ("native", "bridge"):
        return line.command
    command, script = table.runtimes[line.runtime].argv(home)
    subscribers = table.subscriber_files[line.subscriber_file]
    event = binding.event if line.relay_event is None else line.relay_event
    return (
        f"{_quote(command)} {_quote(script)}"
        f" hook --harness {harness} --outer-ms {line.outer_ms}"
        f" --subscribers {_quote(expand_path(subscribers.path, home))} {event}"
    )


def _hooks(table, settings, home):
    agy = settings.harness == "agy"
    events = {"enabled": True} if agy else {}
    for binding in settings.bindings:
        if not binding.lines:
            continue
        hooks = []
        for line in binding.lines:
            hook = {"type": "command", "command": _command(table, binding, line, settings.harness, home)}
            if line.timeout is not None:
                hook["timeout"] = line.timeout
            hooks.append(hook)
        groups = events.setdefault(binding.event, [])
        if agy and binding.event not in ("PreToolUse", "PostToolUse"):
            groups.extend(hooks)
        else:
            group = {} if binding.matcher is None else {"matcher": binding.matcher}
            groups.append({**group, "hooks": hooks})
    return events


def subscriber_bytes(table, source, home=None):
    subscribers = []
    for entry in source.subscribers:
        name = entry.name
        subscriber = table.subscribers[name]
        result = {"name": name, "role": subscriber.role}
        if subscriber.registry is not None:
            result["registry"] = subscriber.registry
        for key in ("harnesses", "kinds", "tools", "nativeEvents"):
            value = getattr(entry, key)
            if value is not None:
                result[key] = value
        if subscriber.privateFields:
            result["privateFields"] = subscriber.privateFields
        argv = [f"@HOME@/{arg[2:]}" if arg.startswith("~/") else arg for arg in subscriber.argv]
        if home is not None:
            argv = [arg.replace("@HOME@", str(home)) for arg in argv]
        result["argv"] = argv
        result["timeoutMs"] = subscriber.timeoutMs
        subscribers.append(result)
    return _json_file({"schema": 2, "subscribers": subscribers})


def subscriber_address(source, data, home):
    if isinstance(source, SubscriberFile):
        return Path(expand_path(source.path, home)).relative_to(home / ".config/relay").as_posix()
    return f"{source.runtime}-{sha256(data).hexdigest()[:12]}/relay/subscribers.json"


def _settings(table, home):
    files = {}
    for settings in table.homes.values():
        hooks = _hooks(table, settings, home)
        if settings.harness == "claude-code":
            path = table.root / settings.path
            try:
                data = splice_claude_hooks(path.read_bytes().decode("utf-8"), hooks).encode("utf-8")
            except ValueError as error:
                raise ValueError(f"{settings.path}: {error}") from error
        else:
            data = _json_file({"hq" if settings.harness == "agy" else "hooks": hooks})
        files[settings.path] = data
    return files


def render_live(table: Table, home: Path) -> dict[str, bytes]:
    files = _settings(table, home)
    for source in table.subscriber_files.values():
        files[source.output] = subscriber_bytes(table, source)
    return files


def _render_target(table, home, *, records):
    findings = validate(table, home=home, records=records)
    if findings:
        details = "\n".join(f"{item.where}: {item.code}: {item.message}" for item in findings)
        raise ValueError(details)

    source_names = {
        line.subscriber_file
        for _, _, _, binding in table.bindings() for line in binding.target
        if line.subscriber_file in table.target_files
    }
    if table.reconciliation_next in table.target_files:
        source_names.add(table.reconciliation_next)
    targets = {}
    files = {}
    for name in sorted(source_names):
        source = table.target_files[name]
        data = subscriber_bytes(table, source, home)
        address = subscriber_address(source, data, home)
        if address in files and files[address] != data:
            raise ValueError(f"digest address collision: {address}")
        targets[name] = SubscriberFile(f"~/.config/relay/{address}", address, source.subscribers)
        files[address] = data
    homes = {
        name: replace(settings, bindings=tuple(replace(binding, lines=binding.target) for binding in settings.bindings))
        for name, settings in table.homes.items()
    }
    effective = replace(table, homes=homes, subscriber_files=table.subscriber_files | targets)
    live_templates = {source.output: subscriber_bytes(table, source) for source in table.subscriber_files.values()}
    settings = _settings(effective, home)
    if files.keys() & (live_templates.keys() | settings.keys()):
        raise ValueError("candidate output would replace a tracked output")
    return settings | live_templates | files


def render_next(table: Table, home: Path) -> dict[str, bytes]:
    return _render_target(table, home, records=True)


def render_candidate(table: Table, candidate: Path, home: Path) -> dict[str, bytes]:
    return _render_target(load_candidate(table, candidate), home, records=False)


def check_live(table: Table, home: Path) -> list[Finding]:
    claude_paths = {settings.path for settings in table.homes.values() if settings.harness == "claude-code"}
    findings = []
    missing = object()
    for path, expected in render_live(table, home).items():
        try:
            current = (table.root / path).read_bytes()
        except OSError as error:
            findings.append(Finding("settings-read", path, error.strerror))
            continue
        if path in claude_paths:
            actual_hooks = json.loads(current)["hooks"]
            expected_hooks = json.loads(expected)["hooks"]
            if not isinstance(actual_hooks, dict):
                findings.append(Finding("hook-drift", f"{path}:hooks", "must be a JSON object"))
                continue
            for event in dict.fromkeys((*actual_hooks, *expected_hooks)):
                if actual_hooks.get(event, missing) != expected_hooks.get(event, missing):
                    findings.append(Finding("hook-drift", f"{path}:{event}", "differs from the route table"))
        elif current != expected:
            findings.append(Finding("hook-drift", path, "differs from the route table"))
    return findings

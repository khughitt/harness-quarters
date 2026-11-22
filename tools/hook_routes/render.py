"""Encode hook bindings in each harness's tracked settings format."""
import json
from pathlib import Path

from .table import Finding, Table

__all__ = ["render_live", "splice_claude_hooks", "check_live"]


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


def splice_claude_hooks(text: str, hooks: dict) -> str:
    start, end, indent = _claude_hooks_span(text)
    value = json.dumps(hooks, indent=2, ensure_ascii=False).replace("\n", "\n" + indent)
    return text[:start] + value + text[end:]


def _json_file(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _expand(path, home):
    return str(home / path[2:]) if path.startswith("~/") else path


def _quote(value):
    # The current relay images enclose even uncomplicated paths in single quotes.
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _command(table, binding, line, harness, home):
    if line.runtime is None:
        return line.command
    runtime = table.runtimes[line.runtime]
    subscribers = table.subscriber_files[line.subscriber_file]
    event = binding.event if line.relay_event is None else line.relay_event
    return (
        f"{_quote(_expand(runtime.command, home))} {_quote(_expand(runtime.script, home))}"
        f" hook --harness {harness} --outer-ms {line.outer_ms}"
        f" --subscribers {_quote(_expand(subscribers.path, home))} {event}"
    )


def _hooks(table, settings, home):
    agy = settings.harness == "agy"
    events = {"enabled": True} if agy else {}
    for binding in settings.bindings:
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


def _subscriber_file(table, source):
    subscribers = []
    for entry in source.subscribers:
        name = entry["name"]
        subscriber = table.subscribers[name]
        result = {"name": name, "role": subscriber.role}
        if subscriber.registry is not None:
            result["registry"] = subscriber.registry
        result.update((key, value) for key, value in entry.items() if key != "name")
        if subscriber.privateFields:
            result["privateFields"] = subscriber.privateFields
        result["argv"] = [f"@HOME@/{arg[2:]}" if arg.startswith("~/") else arg for arg in subscriber.argv]
        result["timeoutMs"] = subscriber.timeoutMs
        subscribers.append(result)
    return _json_file({"schema": 2, "subscribers": subscribers})


def render_live(table: Table, home: Path) -> dict[str, bytes]:
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
    for source in table.subscriber_files.values():
        files[source.output] = _subscriber_file(table, source)
    return files


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

"""Read the declared hook routes and their rendering inputs."""
from dataclasses import dataclass
from pathlib import Path
import tomllib

__all__ = ["Binding", "Finding", "Line", "RouteState", "Subscriber", "SubscriberFile", "Table", "load"]

# The home links and legacy relay runtime consume these tracked outputs.
_REQUIRED_HOMES = {
    ("claude-code", "harnesses/claude/settings.json"),
    ("codex", "harnesses/codex/hooks.json"),
    ("codex", "harnesses/codex/work/hooks.json"),
    ("agy", "harnesses/agy/hooks.json"),
}
_REQUIRED_SUBSCRIBER_OUTPUT = "relay/subscribers.template.json"


@dataclass(frozen=True)
class Finding:
    code: str
    where: str
    message: str


@dataclass(frozen=True)
class RouteState:
    state: str
    owner: str
    reason: str | None = None
    grant: str | None = None


@dataclass(frozen=True)
class Subscriber:
    policy: str
    role: str
    argv: tuple[str, ...]
    timeoutMs: int
    registry: str | None = None
    privateFields: tuple[dict, ...] = ()


@dataclass(frozen=True)
class _SubscriberSelection:
    name: str
    harnesses: list[str] | None = None
    kinds: list[str] | None = None
    tools: list[str] | None = None
    nativeEvents: list[str] | None = None


@dataclass(frozen=True)
class SubscriberFile:
    path: str
    output: str
    subscribers: tuple[_SubscriberSelection, ...]


@dataclass(frozen=True)
class Line:
    policies: tuple[str, ...]
    command: str | None = None
    runtime: str | None = None
    subscriber_file: str | None = None
    outer_ms: int | None = None
    timeout: int | None = None
    relay_event: str | None = None


@dataclass(frozen=True)
class Binding:
    event: str
    matcher: str | None
    lines: tuple[Line, ...]


@dataclass(frozen=True)
class _Home:
    harness: str
    path: str
    bindings: tuple[Binding, ...]


@dataclass(frozen=True)
class _Runtime:
    command: str
    script: str
    commit: str


@dataclass(frozen=True)
class Table:
    root: Path
    reconciliation_file: str
    states: dict[str, RouteState]
    subscribers: dict[str, Subscriber]
    subscriber_files: dict[str, SubscriberFile]
    runtimes: dict[str, _Runtime]
    homes: dict[str, _Home]


def _line(policies, **fields):
    return Line(policies=tuple(policies), **fields)


def _binding(event, lines, matcher=None):
    return Binding(event, matcher, tuple(_line(**line) for line in lines))


def _home(harness, path, bindings):
    return _Home(harness, path, tuple(_binding(**binding) for binding in bindings))


def _subscriber(argv, privateFields=(), **fields):
    return Subscriber(argv=tuple(argv), privateFields=tuple(privateFields), **fields)


def _subscriber_file(path, output, subscribers):
    selections = []
    for entry in subscribers:
        if not isinstance(entry, dict):
            raise ValueError(f"{output}: expected a named subscriber selection")
        try:
            selections.append(_SubscriberSelection(**entry))
        except TypeError as error:
            raise ValueError(f"{output}:{entry.get('name', '<unnamed>')}: {error}") from error
    return SubscriberFile(path, output, tuple(selections))


def _named(data, construct):
    return {name: construct(**fields) for name, fields in data.items()}


def _validate(table):
    if table.reconciliation_file not in table.subscriber_files:
        raise ValueError(f"unknown reconciliation file {table.reconciliation_file!r}")
    for name, state in table.states.items():
        if state.state == "native" and state.owner and state.reason:
            continue
        if state.state == "existing" and state.owner and state.grant:
            continue
        raise ValueError(f"states.{name}: expected a native owner and reason or an existing owner and grant")

    homes = {(home.harness, home.path) for home in table.homes.values()}
    subscriber_outputs = [source.output for source in table.subscriber_files.values()]
    missing = [f"{path} ({harness})" for harness, path in sorted(_REQUIRED_HOMES - homes)]
    if _REQUIRED_SUBSCRIBER_OUTPUT not in subscriber_outputs:
        missing.append(_REQUIRED_SUBSCRIBER_OUTPUT)
    if missing:
        raise ValueError("missing required output declarations: " + ", ".join(missing))

    outputs = [home.path for home in table.homes.values()] + subscriber_outputs
    if len(set(outputs)) != len(outputs):
        raise ValueError("hook routes repeat an output path")
    for output in outputs:
        if not (table.root / output).resolve().is_relative_to(table.root.resolve()) or Path(output).is_absolute():
            raise ValueError(f"output path is outside the checkout: {output!r}")

    for name, subscriber in table.subscribers.items():
        if subscriber.policy not in table.states:
            raise ValueError(f"subscribers.{name}: unknown policy {subscriber.policy!r}")
    for name, source in table.subscriber_files.items():
        for entry in source.subscribers:
            if entry.name not in table.subscribers:
                raise ValueError(f"subscriber_files.{name}: unknown subscriber {entry.name!r}")
    for name, home in table.homes.items():
        if home.harness not in ("agy", "claude-code", "codex"):
            raise ValueError(f"homes.{name}: unknown harness {home.harness!r}")
        for binding in home.bindings:
            where = f"homes.{name}:{binding.event}"
            for line in binding.lines:
                if not line.policies:
                    raise ValueError(f"{where}: every line needs a policy")
                for policy in line.policies:
                    if policy not in table.states:
                        raise ValueError(f"{where}: unknown policy {policy!r}")
                if line.runtime is None:
                    if not line.command:
                        raise ValueError(f"{where}: native line needs a command")
                elif (line.command is not None or line.runtime not in table.runtimes
                      or line.subscriber_file not in table.subscriber_files
                      or not (line.outer_ms and line.timeout)):
                    raise ValueError(f"{where}: relay line needs a known runtime and subscriber file, budget and timeout")


def load(path: Path) -> Table:
    with path.open("rb") as source:
        data = tomllib.load(source)
    table = Table(
        root=path.parent.parent,
        reconciliation_file=data["reconciliation_file"],
        states=_named(data["states"], RouteState),
        subscribers=_named(data["subscribers"], _subscriber),
        subscriber_files=_named(data["subscriber_files"], _subscriber_file),
        runtimes=_named(data["runtimes"], _Runtime),
        homes=_named(data["homes"], _home),
    )
    _validate(table)
    return table

"""Read the declared hook routes and their rendering inputs."""
from dataclasses import dataclass, field, replace
from pathlib import Path
import posixpath
import shlex
import tomllib
from typing import Literal

__all__ = [
    "Binding", "Finding", "Line", "Removal", "RollbackBase", "RouteState", "Subscriber",
    "SubscriberFile", "Table", "TargetSubscriberFile", "expand_path", "load", "load_candidate",
]

# The home links and legacy relay runtime consume these tracked outputs.
_REQUIRED_HOMES = {
    ("claude-code", "harnesses/claude/settings.json"),
    ("claude-code", "harnesses/claude/work/settings.json"),
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
    kind: Literal["relay", "bridge", "native", "existing"]
    owner: str | None = None
    reason: str | None = None
    grant: str | None = None
    records: tuple[str, ...] = ()
    evidence: str | None = None
    activation: str | None = None


@dataclass(frozen=True)
class Removal:
    subscriber: str
    owner: str


@dataclass(frozen=True)
class RollbackBase:
    subscriber_files: tuple[str, ...] = ()
    commands: tuple[str, ...] = ()


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
    path: str | None
    output: str
    subscribers: tuple[_SubscriberSelection, ...]
    runtime: str | None = None


@dataclass(frozen=True)
class TargetSubscriberFile:
    runtime: str
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
    states: dict[str, RouteState] = field(default_factory=dict)
    delegates: tuple[tuple[str, ...], ...] = ()
    relay_kind: str | None = None

    @property
    def kind(self) -> str:
        if self.runtime is None:
            return "native"
        return "relay" if self.command is None else "bridge"

    def relay_timeout_problem(self) -> str | None:
        if self.kind == "relay" and not (
                type(self.timeout) is int and type(self.outer_ms) is int
                and 0 < self.outer_ms <= self.timeout * 1000):
            return f"harness timeout {self.timeout}s must cover the positive relay outer budget {self.outer_ms}ms"
        return None


@dataclass(frozen=True)
class Binding:
    event: str
    matcher: str | None
    lines: tuple[Line, ...]
    next: tuple[Line, ...] | None = None

    @property
    def target(self) -> tuple[Line, ...]:
        return self.lines if self.next is None else self.next


@dataclass(frozen=True)
class _Home:
    harness: str
    path: str
    bindings: tuple[Binding, ...]


def expand_path(path: str, home: Path) -> str:
    return str(home / path[2:]) if path.startswith("~/") else path


@dataclass(frozen=True)
class _Runtime:
    command: str
    script: str
    commit: str
    # The subscriber file schema this relay reads.
    subscriber_schema: int = 2

    def argv(self, home: Path) -> tuple[str, str]:
        return expand_path(self.command, home), expand_path(self.script, home)

    def package_dir(self, home: Path) -> Path:
        return Path(expand_path(self.script, home)).parent.parent


@dataclass(frozen=True)
class Table:
    root: Path
    reconciliation_file: str
    states: dict[str, RouteState]
    subscribers: dict[str, Subscriber]
    subscriber_files: dict[str, SubscriberFile]
    runtimes: dict[str, _Runtime]
    homes: dict[str, _Home]
    target_files: dict[str, TargetSubscriberFile] = field(default_factory=dict)
    reconciliation_next: str | None = None
    removals: tuple[Removal, ...] = ()
    rollback_bases: dict[str, RollbackBase] = field(default_factory=dict)
    # Where a schema-3 relay finds subscriber commands, in order.
    search_path: tuple[str, ...] = ()

    def subscriber_schema(self, source) -> int:
        return 2 if source.runtime is None else self.runtimes[source.runtime].subscriber_schema

    def search_directories(self, home: Path) -> list[str]:
        # Textual, as the renderer expands it: a Path would hide what relay refuses.
        return [f"{home}{entry[1:]}" if entry.startswith("~/") else entry for entry in self.search_path]

    def bindings(self):
        for name, home in self.homes.items():
            for index, binding in enumerate(home.bindings):
                yield name, home, index, binding

    def policy_state(self, policy: str, line: Line) -> RouteState | None:
        return line.states.get(policy, self.states.get(policy))


def _state(state, records=(), **fields):
    if not isinstance(records, (list, tuple)) or not all(isinstance(record, str) for record in records):
        raise ValueError("route records must be a list of qualification record names")
    return RouteState(state, records=tuple(records), **fields)


def _line(policies, states=None, delegates=(), **fields):
    if not all(isinstance(argv, list) and argv and all(isinstance(arg, str) for arg in argv) for argv in delegates):
        raise ValueError("bridge delegates must be ordered argv lists")
    return Line(tuple(policies), states=_named(states or {}, _state),
                delegates=tuple(tuple(argv) for argv in delegates), **fields)


def _lines(lines):
    return tuple(_line(**line) for line in lines)


def _binding(event, lines, matcher=None, next=None):
    return Binding(event, matcher, _lines(lines), None if next is None else _lines(next))


def _home(harness, path, bindings):
    return _Home(harness, path, tuple(_binding(**binding) for binding in bindings))


def _subscriber(argv, privateFields=(), **fields):
    return Subscriber(argv=tuple(argv), privateFields=tuple(privateFields), **fields)


def _selections(subscribers, where):
    selections = []
    for entry in subscribers:
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: expected a named subscriber selection")
        try:
            selections.append(_SubscriberSelection(**entry))
        except TypeError as error:
            raise ValueError(f"{where}:{entry.get('name', '<unnamed>')}: {error}") from error
    return tuple(selections)


def _subscriber_file(output, subscribers, *, path=None, runtime=None):
    if (path is None) == (runtime is None):
        raise ValueError(f"{output}: subscriber file needs exactly one of path or runtime")
    return SubscriberFile(path, output, _selections(subscribers, output), runtime)


def _target_file(runtime, subscribers):
    return TargetSubscriberFile(runtime, _selections(subscribers, "target file"))


def _rollback_base(subscriber_files=(), commands=()):
    return RollbackBase(tuple(subscriber_files), tuple(commands))


def _named(data, construct):
    return {name: construct(**fields) for name, fields in data.items()}


def _validate_search_path(table):
    for name, runtime in table.runtimes.items():
        if type(runtime.subscriber_schema) is not int or runtime.subscriber_schema not in (2, 3):
            raise ValueError(f"runtimes.{name}: subscriber_schema must be 2 or 3")
    for entry in table.search_path:
        if not isinstance(entry, str) or not entry.startswith(("/", "~/")):
            raise ValueError(f"search_path: {entry!r} must start with / or ~/")
    # relay's own rules for the list, on the directories this home gives it.
    directories = table.search_directories(Path.home())
    for entry, directory in zip(table.search_path, directories):
        if (posixpath.normpath(directory) != directory or directory.startswith("//")
                or ":" in directory or "\0" in directory):
            raise ValueError(f"search_path: {entry!r} must be a normalized directory without ':'")
    if len(set(directories)) != len(directories):
        raise ValueError("search_path repeats a directory")
    if not table.search_path:
        for name, source in (table.subscriber_files | table.target_files).items():
            if source.runtime in table.runtimes and table.subscriber_schema(source) == 3:
                raise ValueError(f"subscriber_files.{name}: a schema 3 runtime needs a search_path")


def _validate_structure(table, *, required_outputs):
    if table.reconciliation_file not in table.subscriber_files:
        raise ValueError(f"unknown reconciliation file {table.reconciliation_file!r}")
    if (table.reconciliation_next is not None
            and table.reconciliation_next not in table.subscriber_files
            and table.reconciliation_next not in table.target_files):
        raise ValueError(f"unknown target reconciliation file {table.reconciliation_next!r}")

    homes = {(home.harness, home.path) for home in table.homes.values()}
    subscriber_outputs = [source.output for source in table.subscriber_files.values()]
    missing = [f"{path} ({harness})" for harness, path in sorted(_REQUIRED_HOMES - homes)]
    if _REQUIRED_SUBSCRIBER_OUTPUT not in subscriber_outputs:
        missing.append(_REQUIRED_SUBSCRIBER_OUTPUT)
    if required_outputs and missing:
        raise ValueError("missing required output declarations: " + ", ".join(missing))

    outputs = [home.path for home in table.homes.values()] + subscriber_outputs
    if len(set(outputs)) != len(outputs):
        raise ValueError("hook routes repeat an output path")
    for output in outputs:
        if not (table.root / output).resolve().is_relative_to(table.root.resolve()) or Path(output).is_absolute():
            raise ValueError(f"output path is outside the checkout: {output!r}")

    all_policies = set(table.states)
    for name, home, index, binding in table.bindings():
        if home.harness not in ("agy", "claude-code", "codex"):
            raise ValueError(f"homes.{name}: unknown harness {home.harness!r}")
        where = f"homes.{name}:{binding.event}[{index}]"
        for lines, files in (
            (binding.lines, table.subscriber_files),
            (binding.target, table.subscriber_files | table.target_files),
        ):
            for line in lines:
                if not line.policies:
                    raise ValueError(f"{where}: every line needs a policy")
                if line.relay_kind is not None and (line.kind != "relay" or not isinstance(line.relay_kind, str)
                                                   or not line.relay_kind.strip()):
                    raise ValueError(f"{where}: relay_kind must name the expected selector kind for a relay line")
                if set(line.states) - set(line.policies):
                    raise ValueError(f"{where}: state override for a policy absent from the line")
                for policy in line.policies:
                    if policy not in table.states and policy not in line.states:
                        raise ValueError(f"{where}: unknown policy {policy!r}")
                    all_policies.add(policy)
                if line.kind == "native":
                    if not line.command or line.subscriber_file is not None or line.delegates:
                        raise ValueError(f"{where}: native line needs a command")
                elif line.kind == "bridge":
                    if (home.harness != "agy" or binding.event not in ("SessionStart", "Stop")
                            or not line.command or line.runtime not in table.runtimes
                            or not line.delegates or line.subscriber_file is not None):
                        raise ValueError(f"{where}: agy bridge needs a command, ordered delegates and a known runtime")
                    launcher = shlex.split(line.command)
                    if len(launcher) != 1 or not launcher[0]:
                        raise ValueError(f"{where}: bridge command must contain only the launcher")
                    if any(not argv[0] or "/" in argv[0] for argv in line.delegates):
                        raise ValueError(f"{where}: bridge delegates must name commands on PATH")
                    if len(set(line.delegates)) != len(line.delegates):
                        raise ValueError(f"{where}: duplicate delegate command")
                    if binding.event == "Stop" and len(line.delegates) != 1:
                        raise ValueError(f"{where}: Stop bridge requires one guard command on PATH")
                elif (line.runtime not in table.runtimes or line.subscriber_file not in files
                      or line.delegates or not (line.outer_ms and line.timeout)):
                    raise ValueError(f"{where}: relay line needs a known runtime and subscriber file, budget and timeout")
                else:
                    file_runtime = files[line.subscriber_file].runtime
                    if file_runtime is None and table.runtimes[line.runtime].subscriber_schema == 3:
                        raise ValueError(f"{where}: a subscriber file declared by path cannot serve a schema 3 runtime")
                    if file_runtime is not None and line.runtime != file_runtime:
                        raise ValueError(f"{where}: relay runtime differs from its subscriber file runtime")

    for name, subscriber in table.subscribers.items():
        if subscriber.policy not in all_policies:
            raise ValueError(f"subscribers.{name}: unknown policy {subscriber.policy!r}")
    for name, source in (table.subscriber_files | table.target_files).items():
        for entry in source.subscribers:
            if entry.name not in table.subscribers:
                raise ValueError(f"subscriber_files.{name}: unknown subscriber {entry.name!r}")
    for name, source in (table.subscriber_files | table.target_files).items():
        if source.runtime is None:
            continue
        if source.runtime not in table.runtimes:
            raise ValueError(f"target_files.{name}: unknown runtime {source.runtime!r}")
        if Path(source.runtime).name != source.runtime or source.runtime == "..":
            raise ValueError(f"target_files.{name}: runtime version cannot contain a path")
    _validate_search_path(table)
    for name, files in table.rollback_bases.items():
        for source in files.subscriber_files:
            if source not in table.subscriber_files:
                raise ValueError(f"rollback_bases.{name}: unknown subscriber file {source!r}")


def load(path: Path) -> Table:
    with path.open("rb") as source:
        data = tomllib.load(source)
    table = Table(
        root=path.parent.parent,
        reconciliation_file=data["reconciliation_file"],
        states=_named(data["states"], _state),
        subscribers=_named(data["subscribers"], _subscriber),
        subscriber_files=_named(data["subscriber_files"], _subscriber_file),
        runtimes=_named(data["runtimes"], _Runtime),
        homes=_named(data["homes"], _home),
        target_files=_named(data.get("target_files", {}), _target_file),
        reconciliation_next=data.get("reconciliation_next"),
        removals=tuple(Removal(**fields) for fields in data.get("removals", ())),
        rollback_bases=_named(data.get("rollback_bases", {}), _rollback_base),
        search_path=tuple(data.get("search_path", ())),
    )
    _validate_structure(table, required_outputs=True)
    return table


def _candidate_additions(current, definitions, construct, where):
    additions = _named(definitions, construct)
    if current.keys() & additions.keys():
        raise ValueError(f"candidate cannot replace {where}: {', '.join(sorted(current.keys() & additions.keys()))}")
    return current | additions


def load_candidate(table: Table, path: Path) -> Table:
    with path.open("rb") as source:
        data = tomllib.load(source)
    unknown = data.keys() - {"moves", "subscribers", "runtimes", "target_files", "reconciliation_next", "removals"}
    if unknown:
        raise ValueError(f"unknown candidate fields: {', '.join(sorted(unknown))}")

    homes = {
        name: replace(home, bindings=tuple(replace(binding, next=None) for binding in home.bindings))
        for name, home in table.homes.items()
    }
    moved = set()
    for move in data.get("moves", ()):
        name, index = move["home"], move["binding"]
        if move.keys() != {"home", "binding", "lines"}:
            raise ValueError("candidate move requires home, binding and lines")
        home = homes[name]
        if type(index) is not int or not 0 <= index < len(home.bindings):
            raise ValueError(f"candidate binding index is out of range: {name}:{index}")
        if (name, index) in moved:
            raise ValueError(f"candidate moves {name}:{index} twice")
        moved.add((name, index))
        bindings = list(home.bindings)
        bindings[index] = replace(bindings[index], next=_lines(move["lines"]))
        homes[name] = replace(home, bindings=tuple(bindings))

    target_files = _named(data.get("target_files", {}), _target_file)
    removals = tuple(Removal(**fields) for fields in data.get("removals", ()))
    used_subscribers = {
        entry.name
        for source in (*table.subscriber_files.values(), *target_files.values())
        for entry in source.subscribers
    }
    used_subscribers.update(removal.subscriber for removal in removals)
    inherited = {name: subscriber for name, subscriber in table.subscribers.items() if name in used_subscribers}
    proposed = replace(
        table, homes=homes,
        subscribers=_candidate_additions(inherited, data.get("subscribers", {}), _subscriber, "subscribers"),
        runtimes=_candidate_additions(table.runtimes, data.get("runtimes", {}), _Runtime, "runtimes"),
        target_files=target_files,
        reconciliation_next=data.get("reconciliation_next"),
        removals=removals,
    )
    _validate_structure(proposed, required_outputs=False)
    return proposed

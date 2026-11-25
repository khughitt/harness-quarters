"""Inspect this host's commands, relay installations, budgets and deployed files."""
from hashlib import sha256
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from .deploy import review_files
from .qualification import admit_binding, qualification_findings
from .relay_runtime import call, package_for, standalone_package
from .render import subscriber_address, subscriber_bytes
from .rules import validate
from .table import Finding, expand_path

__all__ = ["installed_versions", "run"]

_VERSION = re.compile(r"(?<![\w.-])v?(\d+\.\d+\.\d+(?:[-+][\w.+-]+)?)(?![\w.-])")


def installed_versions(path_env: str) -> dict[str, str]:
    versions = {}
    for harness, name in (("claude-code", "claude"), ("codex", "codex"), ("agy", "agy")):
        command = shutil.which(name, path=path_env)
        if not command:
            continue
        try:
            probe = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=10,
                                   env={"PATH": path_env, "HOME": str(Path.home())})
        except (OSError, subprocess.TimeoutExpired):
            continue
        match = _VERSION.search(probe.stdout)
        if probe.returncode == 0 and match:
            versions[harness] = match[1]
    return versions


def _command_findings(argv, home, path_env, where):
    args = [expand_path(token, home) for token in argv]
    executables = [args[0]]
    # The shipped schema-2 subscribers use env to run an absolute command.
    if args[0] == "env" and len(args) >= 2 and Path(args[1]).is_absolute():
        executables.append(args[1])
        if args[1] == "/usr/bin/python3" and len(args) >= 3 and Path(args[2]).is_absolute():
            script = Path(args[2])
            if not script.is_file() or not os.access(script, os.R_OK):
                yield Finding("missing-command", where, f"cannot read script {script}")
    for name in executables:
        if shutil.which(name, path=path_env) is None:
            yield Finding("missing-command", where, f"cannot execute {name}")


def _first_candidate(name: str, directories: list[str]) -> tuple[Path | None, str | None]:
    """relay's rule for a subscriber command: the first candidate that exists decides."""
    for directory in directories:
        candidate = Path(directory) / name
        try:
            candidate.lstat()
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate, None
        except (FileNotFoundError, NotADirectoryError):
            continue
        except OSError as error:
            return None, f"cannot inspect {candidate}: {error.strerror}"
        return None, f"{candidate} is not an executable regular file"
    return None, None


def _env_interpreter(script: Path) -> str | None:
    """The program an env shebang makes env look up by name."""
    try:
        with script.open("rb") as source:
            line = source.readline(4096)
    except OSError:
        return None  # The command findings report an unreadable command.
    words = line[2:].decode("utf-8", "replace").split() if line.startswith(b"#!") else []
    if not words or Path(words[0]).name != "env":
        return None
    return next((word for word in words[1:] if not word.startswith("-") and "=" not in word), None)


def _listed_findings(argv, home, directories, where):
    """One schema-3 subscriber: relay finds its command, and env its interpreter, only in the list."""
    args = [expand_path(token, home) for token in argv]
    command, problem = _first_candidate(args[0], directories)
    if command is None:
        yield (Finding("missing-command", where, f"cannot execute {args[0]}") if problem is None
               else Finding("unusable-command", where, problem))
        return
    search = os.pathsep.join(directories)
    scripts = [command]
    if args[0] == "env" and len(args) >= 2 and Path(args[1]).is_absolute():
        yield from _command_findings(args, home, search, where)
        scripts.append(Path(args[1]))
    for script in scripts:
        interpreter = _env_interpreter(script)
        if interpreter is not None and shutil.which(interpreter, path=search) is None:
            yield Finding("missing-command", where, f"cannot execute {interpreter}, which {script} runs through env")


def run(table, *, home: Path, path_env: str, next_dir: Path | None) -> list[Finding]:
    findings = validate(table, home=home)
    target = next_dir is not None
    if target:
        try:
            review_files(table, home, next_dir)
        except (OSError, ValueError) as error:
            findings.append(Finding("review-files", str(next_dir), str(error)))

    sources = table.subscriber_files | (table.target_files if target else {})
    reconcile = (table.reconciliation_next if target else None) or table.reconciliation_file
    readers = {reconcile: set()}
    try:
        readers[reconcile].add(standalone_package(table.root, home))
    except (OSError, ValueError, TypeError, KeyError) as error:
        findings.append(Finding("runtime", reconcile, str(error)))
    packages = {}
    for name, settings, index, binding in table.bindings():
        where = f"{name}:{binding.event}[{index}]"
        active = binding.target if target else binding.lines
        # A cutover's retention check depends on the declaration of the live
        # composition it replaces. Verify that selection as well as the target.
        previous = tuple(line for line in binding.lines if line.kind == "relay" and line not in active)
        for line in (*active, *previous):
            commands = [*line.delegates]
            if line.command:
                commands.append(shlex.split(line.command))
            if line.runtime:
                runtime = table.runtimes[line.runtime]
                commands.append(runtime.argv(home))
                if line.runtime not in packages:
                    try:
                        packages[line.runtime] = package_for(table, line.runtime, home)
                    except (OSError, ValueError, TypeError, KeyError) as error:
                        packages[line.runtime] = None
                        findings.append(Finding("runtime", where, str(error)))
            for argv in commands:
                findings.extend(_command_findings(argv, home, path_env, where))
            if line.kind != "relay":
                continue
            if line in active:
                selected = readers.setdefault(line.subscriber_file, set())
                if packages[line.runtime]:
                    selected.add(packages[line.runtime])
            if packages[line.runtime]:
                data = subscriber_bytes(table, sources[line.subscriber_file], home)
                try:
                    admit_binding(table, settings, binding, line, sources, data, packages[line.runtime])
                except (OSError, ValueError) as error:
                    findings.append(Finding("relay-budget", where, str(error)))
    for name, installations in sorted(readers.items()):
        source = sources[name]
        expected = subscriber_bytes(table, source, home)
        address = subscriber_address(source, expected, home)
        path = home / ".config/relay" / address
        for installation in sorted(installations):
            try:
                call(installation, "load", {"path": str(path)})
            except (OSError, ValueError) as error:
                findings.append(Finding("deployed-file", name, str(error)))
        # The public default loader permits an absent file. Every declared file
        # is required here, even an intentionally empty subscriber composition.
        if path.is_file():
            try:
                actual_digest = sha256(path.read_bytes()).hexdigest()
                if actual_digest != sha256(expected).hexdigest():
                    findings.append(Finding("deployed-digest", name, f"{path} has sha256 {actual_digest}"))
            except OSError as error:
                findings.append(Finding("deployed-file", name, str(error)))
        else:
            findings.append(Finding("deployed-file", name, f"missing regular subscriber file {path}"))
        for entry in source.subscribers:
            argv = table.subscribers[entry.name].argv
            where = f"{name}:{entry.name}"
            findings.extend(_command_findings(argv, home, path_env, where) if table.subscriber_schema(source) == 2
                            else _listed_findings(argv, home, table.search_directories(home), where))
    versions = installed_versions(path_env)
    findings.extend(qualification_findings(table, home=home, target=target, versions=versions))
    return findings

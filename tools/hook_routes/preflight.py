"""Inspect this host's commands, relay installations, budgets and deployed files."""
from hashlib import sha256
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from .deploy import review_files
from .qualification import qualification_findings
from .relay_runtime import budget_payload, call, package_for
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


def _command(argv, home, path_env, where):
    name = expand_path(argv[0], home)
    if shutil.which(name, path=path_env) is None:
        return Finding("missing-command", where, f"cannot execute {name}")
    return None


def run(table, *, home: Path, path_env: str, next_dir: Path | None) -> list[Finding]:
    findings = validate(table, home=home)
    target = next_dir is not None
    if target:
        try:
            review_files(table, home, next_dir)
        except (OSError, ValueError) as error:
            findings.append(Finding("review-files", str(next_dir), str(error)))

    sources = table.subscriber_files | (table.target_files if target else {})
    used = {table.reconciliation_file}
    if target and table.reconciliation_next is not None:
        used = {table.reconciliation_next}
    packages = {}
    checked_budgets = set()
    for name, settings, index, binding in table.bindings():
        where = f"{name}:{binding.event}[{index}]"
        for line in binding.target if target else binding.lines:
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
                if finding := _command(argv, home, path_env, where):
                    findings.append(finding)
            if line.kind != "relay":
                continue
            used.add(line.subscriber_file)
            key = (line.runtime, line.subscriber_file, settings.harness, line.relay_event or binding.event,
                   line.outer_ms)
            if packages[line.runtime] and key not in checked_budgets:
                checked_budgets.add(key)
                data = subscriber_bytes(table, sources[line.subscriber_file], home)
                try:
                    call(packages[line.runtime], "budget", budget_payload(settings, binding, line, data))
                except (OSError, ValueError) as error:
                    findings.append(Finding("relay-budget", where, str(error)))
    for name in sorted(used):
        source = sources[name]
        expected = subscriber_bytes(table, source, home)
        address = subscriber_address(source, expected, home)
        path = home / ".config/relay" / address
        try:
            actual_digest = sha256(path.read_bytes()).hexdigest()
            if actual_digest != sha256(expected).hexdigest():
                findings.append(Finding("deployed-digest", name, f"{path} has sha256 {actual_digest}"))
        except OSError as error:
            findings.append(Finding("deployed-file", name, str(error)))
        for entry in source.subscribers:
            argv = table.subscribers[entry.name].argv
            if finding := _command(argv, home, path_env, f"{name}:{entry.name}"):
                findings.append(finding)
    versions = installed_versions(path_env)
    findings.extend(qualification_findings(table, home=home, target=target, versions=versions))
    return findings

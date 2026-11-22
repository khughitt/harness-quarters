"""Find donor callers and show Codex hook trust positions affected by a render."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from typing import Literal

from .table import Table

__all__ = ["Reference", "donor_references", "changed_codex_entries"]

# The home links in links.toml are the paths Codex uses in [hooks.state] keys.
_CODEX_HOME_LINKS = {
    "harnesses/codex/hooks.json": ".codex/hooks.json",
    "harnesses/codex/work/hooks.json": ".codex-work/hooks.json",
}


@dataclass(frozen=True)
class Reference:
    kind: Literal["binding", "subscriber-file", "reconciliation", "bridge-delegate", "rollback-base"]
    where: str


def _expand(token):
    for prefix in ("~/", "@HOME@/", "$HOME/", "${HOME}/"):
        if token.startswith(prefix):
            return str(Path.home() / token[len(prefix):])
    return token


def donor_references(table: Table, donor: str) -> list[Reference]:
    expected = _expand(donor)

    def matches(argv):
        return any(_expand(argument) == expected for argument in argv)

    def matching_entries(name):
        return [
            entry.name for entry in table.subscriber_files[name].subscribers
            if matches(table.subscribers[entry.name].argv)
        ]

    references = []
    for home, _, index, binding in table.bindings():
        for line_index, line in enumerate(binding.lines):
            where = f"{home}:{binding.event}[{index}]:{line_index}"
            native = line.command is not None and matches(shlex.split(line.command))
            if line.runtime is not None:
                runtime = table.runtimes[line.runtime]
                native = native or matches((runtime.command, runtime.script))
            if native:
                references.append(Reference("binding", where))
            for delegate, argv in enumerate(line.delegates):
                if matches(argv):
                    references.append(Reference("bridge-delegate", f"{where}:{delegate}"))
            if line.subscriber_file is not None:
                for entry in matching_entries(line.subscriber_file):
                    references.append(Reference("subscriber-file", f"{where}:{line.subscriber_file}:{entry}"))

    for entry in matching_entries(table.reconciliation_file):
        references.append(Reference("reconciliation", f"{table.reconciliation_file}:{entry}"))

    for name, base in table.rollback_bases.items():
        for index, command in enumerate(base.commands):
            if matches(shlex.split(command)):
                references.append(Reference("rollback-base", f"{name}:command[{index}]"))
        for source in base.subscriber_files:
            for entry in matching_entries(source):
                references.append(Reference("rollback-base", f"{name}:{source}:{entry}"))
    return references


def _entries(data):
    entries = {}
    for event, groups in json.loads(data)["hooks"].items():
        event = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", event).lower()
        for group_index, group in enumerate(groups):
            for hook_index, hook in enumerate(group["hooks"]):
                entries[f"{event}:{group_index}:{hook_index}"] = hook["command"]
    return entries


def changed_codex_entries(repo: Path, base_ref: str, rendered: dict[str, bytes]) -> list[str]:
    changed = []
    env = {
        "PATH": os.environ["PATH"], "HOME": str(Path.home()),
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
    }
    absent = object()
    for path, link in _CODEX_HOME_LINKS.items():
        if path not in rendered:
            raise ValueError(f"rendered settings are missing Codex home {path!r}")
        read = subprocess.run(
            ["git", "cat-file", "blob", f"{base_ref}:{path}"], cwd=repo, env=env, capture_output=True,
        )
        if read.returncode:
            detail = read.stderr.decode(errors="replace").strip()
            raise ValueError(f"cannot read {base_ref}:{path}: {detail}")
        before, after = _entries(read.stdout), _entries(rendered[path])
        for position in dict.fromkeys((*before, *after)):
            if before.get(position, absent) != after.get(position, absent):
                changed.append(f"{Path.home() / link}:{position}")
    return changed

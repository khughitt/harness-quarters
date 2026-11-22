"""Donor references and Codex trust positions are read from the actual wiring."""
from dataclasses import replace
import os
from pathlib import Path
import subprocess

import pytest

from hook_routes.render import render_live
from hook_routes.table import load

TABLE = Path(__file__).resolve().parents[1] / "harnesses/hook-routes.toml"


def _ops_donor(name):
    return f"~/{Path('d', 'ops', 'hooks', name)}"


def test_shared_file_reference_survives_partial_move():
    from hook_routes.references import donor_references

    table = load(TABLE)
    claude = table.homes["claude"]
    relay_pretool = next(binding for binding in claude.bindings
                         if binding.event == "PreToolUse" and binding.lines[0].runtime)
    moved = replace(relay_pretool.lines[0], subscriber_file="no-guard")
    file = table.subscriber_files["shared-v0.5.0"]
    moved_file = replace(file, subscribers=tuple(entry for entry in file.subscribers if entry.name != "ops-guard"))
    bindings = tuple(replace(binding, lines=(moved,)) if binding == relay_pretool else binding
                     for binding in claude.bindings)
    table = replace(table, homes={"claude": replace(claude, bindings=bindings)},
                    subscriber_files={**table.subscriber_files, "no-guard": moved_file})

    refs = donor_references(table, _ops_donor("relay-guard"))

    assert any(ref.kind == "subscriber-file" and "claude:Notification" in ref.where and
               "shared-v0.5.0" in ref.where for ref in refs)
    assert not any(ref.kind == "subscriber-file" and "claude:PreToolUse" in ref.where for ref in refs)


def test_rollback_base_counts_until_dropped():
    from hook_routes.references import donor_references
    from hook_routes.table import RollbackBase

    table = load(TABLE)
    table = replace(table, rollback_bases={"prior": RollbackBase(subscriber_files=("shared-v0.5.0",))})

    assert any(ref.kind == "rollback-base" and "prior" in ref.where
               for ref in donor_references(table, _ops_donor("relay-guard")))
    assert all(ref.kind != "rollback-base" for ref in
               donor_references(replace(table, rollback_bases={}), _ops_donor("relay-guard")))


def test_bridge_references_every_delegate():
    from hook_routes.references import donor_references

    table = load(TABLE)
    agy = table.homes["agy"]
    binding = agy.bindings[0]
    donor = _ops_donor("capture-notice")
    line = replace(binding.lines[0], command="hq-bridge", runtime="v0.5.0",
                   delegates=(("profile",), ("env", donor)))
    agy = replace(agy, bindings=(replace(binding, lines=(line,)),))
    refs = donor_references(replace(table, homes={"agy": agy}), donor)
    assert [(ref.kind, ref.where) for ref in refs] == [("bridge-delegate", "agy:SessionStart[0]:0:1")]


@pytest.mark.parametrize(("donor", "kind", "binding"), [
    ("claim-guard", "binding", "codex:Stop"),
    ("claude-sessionstart", "binding", "claude:SessionStart"),
    ("capture-notice", "binding", "agy:SessionStart"),
    ("claude-posttooluse", "binding", "claude:PostToolUse"),
    ("relay-guard", "subscriber-file", "claude:PreToolUse"),
])
def test_today_ops_references(donor, kind, binding):
    from hook_routes.references import donor_references

    refs = donor_references(load(TABLE), _ops_donor(donor))

    assert any(ref.kind == kind and binding in ref.where for ref in refs)


@pytest.fixture
def codex_base(tmp_path, monkeypatch):
    table = load(TABLE)
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    for key in tuple(os.environ):
        if key.startswith("GIT_"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("HOME", str(home))
    env = {
        "PATH": os.environ["PATH"], "HOME": str(home),
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Fixture", "GIT_AUTHOR_EMAIL": "fixture@example.test",
        "GIT_COMMITTER_NAME": "Fixture", "GIT_COMMITTER_EMAIL": "fixture@example.test",
    }

    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, env=env, check=True, capture_output=True).stdout

    git("init", "--quiet")
    assert Path(os.fsdecode(git("rev-parse", "--show-toplevel").strip())) == repo.resolve()
    git_dir = Path(os.fsdecode(git("rev-parse", "--absolute-git-dir").strip()))
    assert git_dir.is_relative_to(repo.resolve())
    table = replace(table, homes={key: table.homes[key] for key in ("codex", "codex-work")})
    for path, data in render_live(table, home).items():
        dest = repo / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    git("add", ".")
    git("commit", "--quiet", "-m", "fixture: record both homes")
    return table, repo, home


@pytest.mark.parametrize("changed", [("codex",), ("codex-work",), ("codex", "codex-work")])
def test_changed_codex_entries_lists_trust_keys(codex_base, changed):
    from hook_routes.references import changed_codex_entries
    from hook_routes.table import RouteState

    table, repo, home = codex_base
    homes = table.homes.copy()
    for name in changed:
        old = homes[name]
        bindings = list(old.bindings)
        index = next(i for i, binding in enumerate(bindings) if binding.event == "Stop")
        line = replace(bindings[index].lines[0], command="new-codex-stop",
                       states={"claim-guard": RouteState("native", "owner-123456", "fixture")})
        bindings[index] = replace(bindings[index], lines=(line,))
        homes[name] = replace(old, bindings=tuple(bindings))
    rendered = render_live(replace(table, homes=homes), home)

    expected = [f"{home / ('.codex' if name == 'codex' else '.codex-work') / 'hooks.json'}:stop:0:0"
                for name in changed]
    assert changed_codex_entries(repo, "HEAD", rendered) == expected


def test_changed_codex_entries_covers_shifted_and_removed_positions(codex_base):
    from hook_routes.references import changed_codex_entries

    table, repo, home = codex_base
    codex = table.homes["codex"]
    bindings = tuple(binding for binding in codex.bindings
                     if not (binding.event == "Stop" and binding.lines[0].policies == ("claim-guard",)))
    table = replace(table, homes={**table.homes, "codex": replace(codex, bindings=bindings)})
    rendered = render_live(table, home)

    assert changed_codex_entries(repo, "HEAD", rendered) == [
        f"{home / '.codex/hooks.json'}:stop:{position}:0" for position in range(4)
    ]

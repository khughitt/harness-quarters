"""tack-link converges home links from links.toml and never overwrites data."""
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOL = Path(__file__).with_name("tack-link")


def load_tack_link():
    """Import tools/tack-link as a module, for unit-testing apply() directly.

    The file has no .py suffix, so the loader must be given explicitly."""
    loader = importlib.machinery.SourceFileLoader("tack_link", str(TOOL))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


MANIFEST = '''
[required]
"~/.agents" = "agents"
"~/.local/bin/refresh" = "hooks/refresh"

[harness.claude]
home = "~/.claude"
[harness.claude.links]
"CLAUDE.md" = "AGENTS.md"
"skills/flow" = "agents/skills/flow"

[harness.codex]
home = "~/.codex"
[harness.codex.links]
"AGENTS.md" = "AGENTS.md"
'''


def run(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


@pytest.fixture
def world(tmp_path):
    """A checkout with the tool and targets, and an empty HOME with a Claude home only."""
    root = tmp_path / "checkout"
    (root / "tools").mkdir(parents=True)
    shutil.copy2(TOOL, root / "tools" / "tack-link")
    (root / "links.toml").write_text(MANIFEST)
    (root / "agents" / "skills" / "flow").mkdir(parents=True)
    (root / "hooks").mkdir()
    (root / "hooks" / "refresh").write_text("#!/bin/sh\n")
    (root / "AGENTS.md").write_text("# rules\n")
    run("init", "-q", str(root))
    run("-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    run("-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    return root, home


def link(root, home, *args, tool=None):
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run([str(tool or root / "tools" / "tack-link"), *args], env=env,
                          text=True, capture_output=True)


def states(result):
    return {line.split("\t")[1]: line.split("\t")[0] for line in result.stdout.splitlines()}


def test_new_host_gets_required_links_and_installed_harnesses_only(world):
    root, home = world
    result = link(root, home)
    assert result.returncode == 0, result.stderr
    assert states(result) == {
        "~/.agents": "create", "~/.local/bin/refresh": "create",
        "~/.claude/CLAUDE.md": "create", "~/.claude/skills/flow": "create",
        "~/.codex": "skipped"}
    assert not (home / ".agents").exists()          # report mode writes nothing

    applied = link(root, home, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert (home / ".agents").resolve() == (root / "agents").resolve()
    assert (home / ".local/bin/refresh").resolve() == (root / "hooks/refresh").resolve()
    assert (home / ".claude/skills/flow").resolve() == (root / "agents/skills/flow").resolve()
    assert link(root, home, "--check").returncode == 0


def test_link_through_another_spelling_is_ok(world, tmp_path):
    root, home = world
    alias = tmp_path / "d"
    alias.symlink_to(root.parent)
    (home / ".agents").symlink_to(alias / "checkout" / "agents")
    assert states(link(root, home))["~/.agents"] == "ok"


def test_dangling_agents_link_is_repointed(world, tmp_path):
    root, home = world
    (home / ".agents").symlink_to(tmp_path / "moved-away" / "agents")
    result = link(root, home, "--apply")
    assert states(result)["~/.agents"] == "repoint"
    assert (home / ".agents").resolve() == (root / "agents").resolve()


def test_real_file_is_refused_and_nothing_is_written(world):
    root, home = world
    (home / ".claude" / "CLAUDE.md").write_text("mine\n")
    result = link(root, home, "--apply")
    assert result.returncode == 1
    assert states(result)["~/.claude/CLAUDE.md"] == "refuse"
    assert (home / ".claude" / "CLAUDE.md").read_text() == "mine\n"
    assert not (home / ".agents").exists()


def test_symlinked_harness_home_is_skipped(world, tmp_path):
    root, home = world
    (tmp_path / "elsewhere").mkdir()
    (home / ".codex").symlink_to(tmp_path / "elsewhere")
    assert states(link(root, home))["~/.codex"] == "skipped"


def test_check_fails_on_drift(world):
    root, home = world
    assert link(root, home, "--check").returncode == 1


def test_nested_entry_is_rejected(world):
    root, home = world
    (root / "links.toml").write_text(MANIFEST + '\n[harness.agents]\nhome = "~/.agents"\n'
                                     '[harness.agents.links]\n"x" = "AGENTS.md"\n')
    result = link(root, home)
    assert result.returncode == 2
    assert "lies under" in result.stderr


def test_real_manifest_validates_in_a_fresh_clone(tmp_path):
    """The committed links.toml resolves every target in a clone, with Claude alone installed."""
    repo = Path(__file__).resolve().parent.parent
    clone = tmp_path / "clone"
    run("clone", "-q", str(repo), str(clone))
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    result = link(clone, home)
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert "refuse" not in result.stdout


def test_missing_target_is_rejected(world):
    root, home = world
    (root / "links.toml").write_text('[required]\n"~/.x" = "nope"\n')
    result = link(root, home)
    assert result.returncode == 2
    assert "nope" in result.stderr
    assert "just setup" not in result.stderr


def test_apply_refuses_when_a_real_file_appears_after_planning(world):
    """A TOCTOU safety net: apply() re-checks each link path immediately before the
    os.replace that would otherwise clobber a real file planted after plan() ran."""
    root, home = world
    module = load_tack_link()
    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(home)
    try:
        entries, homes = module.load(root)
        rows = module.plan(entries, homes)          # planned while home/.agents is absent
        (home / ".agents").write_text("mine\n")      # a real file appears before apply runs
        with pytest.raises(module.ApplyRefused):
            module.apply(rows)
    finally:
        if old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = old_home
    assert (home / ".agents").read_text() == "mine\n"


def test_refuses_from_a_worktree(world, tmp_path):
    root, home = world
    wt = tmp_path / "wt"
    run("-C", str(root), "worktree", "add", "-q", str(wt))
    result = link(root, home, tool=wt / "tools" / "tack-link")
    assert result.returncode == 2
    assert "not a worktree" in result.stderr


def test_missing_target_in_an_absent_home_is_not_checked(world):
    root, home = world
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    result = link(root, home)
    assert result.returncode == 0, result.stderr
    assert states(result)["~/.work"] == "skipped"


def test_missing_target_in_a_symlinked_home_is_not_checked(world, tmp_path):
    root, home = world
    (tmp_path / "elsewhere").mkdir()
    (home / ".work").symlink_to(tmp_path / "elsewhere")
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    assert link(root, home).returncode == 0


def test_missing_local_target_in_an_active_home_names_the_remedy(world):
    root, home = world
    (home / ".work").mkdir()
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    result = link(root, home, "--apply")
    assert result.returncode == 2
    assert "local/work.json" in result.stderr
    assert "another host's `local/`" in result.stderr and "just setup" in result.stderr
    assert not (home / ".work" / "settings.json").exists()
    assert not (home / ".agents").exists()          # nothing is written on this error


def test_local_target_resolves_like_any_other(world):
    root, home = world
    (home / ".work").mkdir()
    (root / "local").mkdir()
    (root / "local" / "work.json").write_text("{}\n")
    (root / "links.toml").write_text(MANIFEST + '\n[harness.work]\nhome = "~/.work"\n'
                                     '[harness.work.links]\n"settings.json" = "local/work.json"\n')
    assert link(root, home, "--apply").returncode == 0
    assert (home / ".work" / "settings.json").resolve() == (root / "local" / "work.json").resolve()


def fresh_clone(tmp_path):
    repo = Path(__file__).resolve().parent.parent
    clone = tmp_path / "clone"
    run("clone", "-q", str(repo), str(clone))
    return clone


def just_setup(clone):
    assert shutil.which("just"), "just is required for the setup tests"
    return subprocess.run(["just", "setup"], cwd=clone, text=True, capture_output=True)


def test_real_manifest_with_codex_needs_setup_first(tmp_path):
    clone = fresh_clone(tmp_path)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir()
    before = link(clone, home)
    assert before.returncode == 2
    assert "local/codex/rules" in before.stderr and "just setup" in before.stderr
    assert just_setup(clone).returncode == 0
    after = link(clone, home)
    assert after.returncode == 0, after.stderr
    assert states(after)["~/.codex/rules"] == "create"


def test_real_manifest_work_home_without_local_names_the_file(tmp_path):
    clone = fresh_clone(tmp_path)
    home = tmp_path / "home"
    (home / ".claude-work").mkdir(parents=True)
    assert just_setup(clone).returncode == 0
    result = link(clone, home)
    assert result.returncode == 2
    assert "local/claude/settings.work.json" in result.stderr


def test_setup_is_idempotent_and_creates_only_the_rules_directory(tmp_path):
    clone = fresh_clone(tmp_path)
    assert just_setup(clone).returncode == 0
    second = just_setup(clone)
    assert second.returncode == 0, second.stderr
    assert sorted(p.relative_to(clone / "local").as_posix()
                  for p in (clone / "local").rglob("*")) == ["codex", "codex/rules"]
    config = lambda key: run("-C", str(clone), "config", key).stdout.strip()
    assert config("core.hooksPath") == ".githooks"
    assert config("filter.harness-state.clean") == ".githooks/harness-state-clean %f"
    assert run("-C", str(clone), "status", "--porcelain", "--", "local").stdout == ""   # ignored

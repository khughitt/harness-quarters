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
    env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
           "XDG_STATE_HOME": str(home / ".local/state")}
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
    """The manifest resolves every target after the clone's skill sources are hydrated and
    the projects it names are staged and registered in the isolated registry."""
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    clone = fresh_clone(tmp_path, home)
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


def fresh_clone(tmp_path, home):
    """A clone of this checkout with the working manifest and tool. Every `<project>:`
    target the manifest names gets a sibling under tmp_path holding those targets, copied
    from the live project's registered root, and registered in `home`'s isolated registry:
    the real manifest then resolves there as it does on a host."""
    repo = Path(__file__).resolve().parent.parent
    clone = tmp_path / "clone"
    run("clone", "-q", str(repo), str(clone))
    stage_project_targets(repo / "links.toml", tmp_path, home)
    # Exercise the working manifest and tool, including changes not committed yet.
    shutil.copy2(repo / "links.toml", clone / "links.toml")
    shutil.copy2(TOOL, clone / "tools/tack-link")
    # A public clone needs the submodule and sibling skill checkouts. Use the local
    # sources in these fixtures so the tests require neither network nor live writes.
    main = Path(run("-C", str(repo), "worktree", "list", "--porcelain").stdout.splitlines()[0][9:])
    for path in (clone / "agents/skills").iterdir():
        if path.is_symlink():
            shutil.copytree((main / "agents/skills" / path.name).resolve(), path.resolve(),
                            dirs_exist_ok=True)
    return clone


def stage_project_targets(manifest, tmp_path, home):
    """For each `<prefix>:<path>` target in the manifest, copy that path from the project's
    live registered root into tmp_path/<prefix> and register it in home's registry."""
    import json, re, tomllib
    live = json.loads(subprocess.run(["tasks", "projects", "--paths", "--json"], text=True,
                                     capture_output=True, check=True).stdout)
    roots = {p["prefix"]: Path(p["root"]) for p in live["projects"]}
    data = tomllib.loads(manifest.read_text())
    targets = list(data.get("required", {}).values())  # [directories] values are former link targets, never project targets
    for table in data.get("harness", {}).values():
        targets += list(table.get("links", {}).values())
    staged = set()
    for target in targets:
        m = re.fullmatch(r"([a-z][a-z0-9]*):(.+)", target)
        if not m:
            continue
        prefix, rel = m.groups()
        sibling = tmp_path / prefix
        src = roots[prefix] / rel
        dst = sibling / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)
        else:
            shutil.copy2(src, dst)
        if prefix not in staged:
            (sibling / "tasks").mkdir(exist_ok=True)
            register(sibling, home, prefix)
            staged.add(prefix)


def just_setup(clone):
    assert shutil.which("just"), "just is required for the setup tests"
    return subprocess.run(["just", "setup"], cwd=clone, text=True, capture_output=True)


def test_real_manifest_with_codex_needs_setup_first(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir()
    clone = fresh_clone(tmp_path, home)
    before = link(clone, home)
    assert before.returncode == 2
    assert "local/codex/rules" in before.stderr and "just setup" in before.stderr
    assert just_setup(clone).returncode == 0
    after = link(clone, home)
    assert after.returncode == 0, after.stderr
    assert states(after)["~/.codex/rules"] == "create"


def test_real_manifest_work_home_without_local_names_the_file(tmp_path):
    home = tmp_path / "home"
    (home / ".claude-work").mkdir(parents=True)
    clone = fresh_clone(tmp_path, home)
    assert just_setup(clone).returncode == 0
    result = link(clone, home)
    assert result.returncode == 2
    assert "local/claude/settings.work.json" in result.stderr


def test_setup_is_idempotent_and_creates_only_the_rules_directory(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    clone = fresh_clone(tmp_path, home)
    assert just_setup(clone).returncode == 0
    second = just_setup(clone)
    assert second.returncode == 0, second.stderr
    assert sorted(p.relative_to(clone / "local").as_posix()
                  for p in (clone / "local").rglob("*")) == ["codex", "codex/rules"]
    config = lambda key: run("-C", str(clone), "config", key).stdout.strip()
    assert config("core.hooksPath") == ".githooks"
    assert config("filter.harness-state.clean") == ".githooks/harness-state-clean %f"
    assert run("-C", str(clone), "status", "--porcelain", "--", "local").stdout == ""   # ignored


DIRECTORIES = '''
[directories]
"~/.agents/skills" = "agents/skills"
"~/.agents" = "agents"
[required]
"~/.agents/skills/flow" = "agents/skills/flow"
'''


def register(root, home, prefix):
    env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
           "XDG_STATE_HOME": str(home / ".local/state")}
    result = subprocess.run(["tasks", "init", "--prefix", prefix], cwd=root, env=env,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("format", ["json", "pretty"])
def test_registry_target_uses_registered_path(world, tmp_path, monkeypatch, format):
    root, home = world
    sibling = tmp_path / "non-sibling-location"
    sibling.mkdir()
    (sibling / "rules.md").write_text("rules\n")
    register(sibling, home, "peer")
    monkeypatch.setenv("TASKS_FORMAT", format)
    (root / "links.toml").write_text('[required]\n"~/.rules" = "peer:rules.md"\n')
    result = link(root, home, "--apply")
    assert result.returncode == 0, result.stderr
    assert (home / ".rules").resolve() == sibling / "rules.md"
    assert link(root, home, "--check").returncode == 0


@pytest.mark.parametrize("target", ["missing:rules.md", "peer:missing.md"])
def test_registry_target_errors_before_any_writes(world, target):
    root, home = world
    register(root, home, "peer")
    (root / "links.toml").write_text(MANIFEST + '\n[harness.extra]\nhome = "~/.claude"\n'
                                     f'[harness.extra.links]\n"rules" = "{target}"\n')
    result = link(root, home, "--apply")
    assert result.returncode == 2
    assert ("not registered" if target.startswith("missing:") else "missing.md") in result.stderr
    assert not (home / ".agents").exists()


def test_registry_target_in_absent_home_is_not_resolved(world):
    root, home = world
    (root / "links.toml").write_text(MANIFEST + '\n[harness.extra]\nhome = "~/.absent"\n'
                                     '[harness.extra.links]\n"rules" = "missing:rules.md"\n')
    result = link(root, home)
    assert result.returncode == 0, result.stderr
    assert states(result)["~/.absent"] == "skipped"


@pytest.mark.parametrize("existing", [False, True])
def test_directories_are_created_before_child_links(world, existing):
    root, home = world
    (root / "links.toml").write_text(DIRECTORIES)
    if existing:
        (home / ".agents").symlink_to(root / "agents")
    result = link(root, home)
    assert result.returncode == 0, result.stderr
    assert states(result)["~/.agents"] == ("convert" if existing else "create")
    assert link(root, home, "--check").returncode == 1
    assert (home / ".agents").is_symlink() == existing
    applied = link(root, home, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert (home / ".agents").is_dir() and not (home / ".agents").is_symlink()
    assert (home / ".agents/skills").is_dir() and not (home / ".agents/skills").is_symlink()
    assert (home / ".agents/skills/flow").is_symlink()
    assert (home / ".agents/skills/flow").resolve() == root / "agents/skills/flow"
    assert not (root / "agents/skills/flow").is_symlink()  # no writes through the old parent
    assert link(root, home, "--check").returncode == 0


@pytest.mark.parametrize("existing", ["file", "foreign", "dangling"])
def test_directory_conversion_refuses_foreign_data(world, tmp_path, existing):
    root, home = world
    (root / "links.toml").write_text(DIRECTORIES)
    path = home / ".agents"
    if existing == "file":
        path.write_text("mine\n")
    else:
        target = tmp_path / "elsewhere"
        if existing == "foreign":
            target.mkdir()
        path.symlink_to(target)
    result = link(root, home, "--apply")
    assert result.returncode == 1, result.stderr
    assert states(result)["~/.agents"] == "refuse"
    assert path.is_symlink() if existing != "file" else path.read_text() == "mine\n"


def test_directory_conversion_rechecks_target_before_unlink(world, tmp_path, monkeypatch):
    root, home = world
    monkeypatch.setenv("HOME", str(home))
    (root / "links.toml").write_text(DIRECTORIES)
    path = home / ".agents"
    path.symlink_to(root / "agents")
    module = load_tack_link()
    entries, homes = module.load(root)
    rows = module.plan(entries, homes)
    path.unlink()
    path.symlink_to(tmp_path / "replacement")
    with pytest.raises(module.ApplyRefused):
        module.apply(rows)
    assert os.readlink(path) == str(tmp_path / "replacement")
    assert not (root / "agents/skills/flow").is_symlink()


@pytest.mark.parametrize("existing", ["owned", "dangling", "absent", "foreign", "file", "directory"])
def test_retired_link_ownership_and_check(world, tmp_path, existing):
    root, home = world
    (root / "links.toml").write_text('[retired]\n"~/.old" = "gone"\n')
    path = home / ".old"
    if existing == "owned":
        (root / "gone").mkdir()
        path.symlink_to(root / "gone")
    elif existing == "dangling":
        path.symlink_to(root / "gone")
    elif existing == "foreign":
        path.symlink_to(tmp_path / "replacement")
    elif existing == "file":
        path.write_text("mine\n")
    elif existing == "directory":
        path.mkdir()
    expected = "remove" if existing in ("owned", "dangling") else (
        "ok" if existing == "absent" else "refuse")
    assert states(link(root, home))["~/.old"] == expected
    assert link(root, home, "--check").returncode == (0 if existing == "absent" else 1)
    result = link(root, home, "--apply")
    assert result.returncode == (1 if expected == "refuse" else 0), result.stderr
    if expected == "refuse":
        assert path.exists() or path.is_symlink()
    else:
        assert not path.exists() and not path.is_symlink()


def test_retirement_rechecks_target_before_unlink(world, tmp_path, monkeypatch):
    root, home = world
    monkeypatch.setenv("HOME", str(home))
    (root / "links.toml").write_text('[retired]\n"~/.old" = "gone"\n')
    path = home / ".old"
    path.symlink_to(root / "gone")
    module = load_tack_link()
    entries, homes = module.load(root)
    rows = module.plan(entries, homes)
    path.unlink()
    path.symlink_to(tmp_path / "replacement")
    with pytest.raises(module.ApplyRefused):
        module.apply(rows)
    assert os.readlink(path) == str(tmp_path / "replacement")


def test_declared_and_retired_overlap_is_rejected(world):
    root, home = world
    (root / "links.toml").write_text(MANIFEST + '\n[retired]\n"~/.agents" = "agents"\n')
    result = link(root, home, "--apply")
    assert result.returncode == 2
    assert "retired" in result.stderr
    assert not (home / ".agents").exists()


def test_retirement_does_not_claim_a_different_link_to_the_same_destination(world):
    root, home = world
    (root / "agents/alias").symlink_to(root / "agents/skills/flow")
    (root / "links.toml").write_text('[retired]\n"~/.old" = "agents/alias"\n')
    path = home / ".old"
    path.symlink_to(root / "agents/skills/flow")
    result = link(root, home, "--apply")
    assert result.returncode == 1
    assert states(result)["~/.old"] == "refuse"
    assert path.is_symlink()


def test_directory_cannot_convert_a_link_into_another_project(world, tmp_path):
    root, home = world
    foreign = tmp_path / "peer"
    (foreign / "agents").mkdir(parents=True)
    register(foreign, home, "peer")
    (root / "links.toml").write_text('[directories]\n"~/.agents" = "peer:agents"\n')
    (home / ".agents").symlink_to(foreign / "agents")
    result = link(root, home, "--apply")
    assert result.returncode == 2
    assert "running checkout" in result.stderr
    assert (home / ".agents").is_symlink()


def test_manifest_declares_every_tracked_agents_entry():
    import tomllib
    repo = Path(__file__).resolve().parent.parent
    data = tomllib.loads((repo / "links.toml").read_text())
    entries = {**data["directories"], **data["required"]}
    for name in run("-C", str(repo), "ls-files", "--", "agents").stdout.splitlines():
        parts = Path(name).parts
        surface = Path(*parts[:3] if parts[1] in ("bin", "skills") else parts[:2])
        assert f"~/.{surface.as_posix()}" in entries


@pytest.mark.parametrize("kind", ["directories", "retired"])
def test_ownership_resolves_symlink_parents_before_dotdot(world, tmp_path, kind):
    root, home = world
    foreign = tmp_path / "foreign"
    (foreign / "child").mkdir(parents=True)
    (foreign / "agents").mkdir()
    (root / "alias").symlink_to(foreign / "child")
    (root / "links.toml").write_text(f'[{kind}]\n"~/.agents" = "agents"\n')
    path = home / ".agents"
    target = root / "alias/../agents"
    path.symlink_to(target)
    assert path.resolve() == foreign / "agents"
    result = link(root, home, "--apply")
    assert result.returncode == 1
    assert states(result)["~/.agents"] == "refuse"
    assert os.readlink(path) == str(target)


@pytest.mark.parametrize("table", ["directories", "required", "retired", "harness"])
def test_managed_paths_reject_parent_traversal(world, table):
    root, home = world
    (home / ".dir").mkdir()
    (home / ".agents").symlink_to(root / "agents")
    extra = (f'\n[{table}]\n"~/.dir/../.agents" = "agents"\n' if table != "harness" else
             '\n[harness.extra]\nhome = "~/.claude"\n[harness.extra.links]\n"../.agents" = "agents"\n')
    base = '[required]\n"~/.agents" = "agents"\n' if table != "required" else ''
    (root / "links.toml").write_text(base + extra)
    result = link(root, home, "--apply")
    assert result.returncode == 2
    assert ".." in result.stderr
    assert (home / ".agents").is_symlink()

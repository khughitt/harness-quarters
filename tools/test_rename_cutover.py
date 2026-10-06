"""rename-cutover saves, guards and restores a rename in a sandbox that shares no live state."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TOOLS = Path(__file__).parent
LINK_TOOL = "tools/harness-links"


def load_cutover():
    """Import tools/rename-cutover as a module, for unit-testing its functions directly.

    The file has no .py suffix, so the loader must be given explicitly."""
    path = TOOLS / "rename-cutover"
    loader = importlib.machinery.SourceFileLoader("rename_cutover", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def task_id(output):
    added = json.loads(output)
    return added.get("id") or added["task"]["id"]


KEPT = ("codex/config.toml", "local/codex/trust.toml")


class Sandbox:
    """A rename in a sandbox that shares no live state. The September shape: checkout
    `ai` (prefix ai) becomes `tack`, retargeting in `repos` (ops, unless a test asks).
    The hq shape (`hq=True`): checkout `tack`, renamed once before from `ai` so the
    registry holds `ai = "tack"`, in the group `agent-layer`, becomes `hq`; its Codex
    trust files are a filtered tracked file and an ignored one, saved with --keep."""

    def __init__(self, tmp, repos=("ops",), hq=False):
        self.tmp = tmp
        self.env = {**os.environ, "HOME": str(tmp / "home"), "XDG_CONFIG_HOME": str(tmp / "cfg"),
                    "XDG_STATE_HOME": str(tmp / "state"), "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self.env.pop("WORK_ROOT", None)
        for d in ("home", "cfg", "state"):
            (tmp / d).mkdir()
        self.sync = tmp / "sync"
        self.hq = hq
        self.old, self.new = ("tack", "hq") if hq else ("ai", "tack")
        self.checkout, self.new_root = self.sync / self.old, self.sync / self.new
        self.repos = [self.sync / name for name in repos]
        self.ops = self.repos[0]
        self.snapshot = tmp / "snap"

    def run(self, *cmd, cwd=None, check=True, env=None):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env or self.env, text=True,
                                capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def repo(self, path, prefix):
        path.mkdir(parents=True)
        self.run("git", "init", "-q", "-b", "main", path)
        self.run("tasks", "init", "--prefix", prefix, cwd=path)

    def commit(self, root, message):
        self.run("git", "add", "-A", cwd=root)
        self.run("git", "commit", "-qm", message, cwd=root)

    def build(self):
        self.repo(self.checkout, "ai")
        (self.checkout / "tools").mkdir()
        for name in ("harness-links", "rename-cutover"):
            shutil.copy2(TOOLS / name, self.checkout / "tools" / name)
        (self.checkout / "agents").mkdir()
        (self.checkout / "agents" / "README").write_text("x\n")
        (self.checkout / "links.toml").write_text('[required]\n"~/.agents" = "agents"\n')
        (self.checkout / ".gitignore").write_text(".worktrees\nlocal/\n")
        tid = task_id(self.run("tasks", "add", "one", "--process", "direct", cwd=self.checkout).stdout)
        self.run("tasks", "add", "two", "--process", "direct", cwd=self.checkout)
        self.run("tasks", "start", tid, cwd=self.checkout)
        self.run("tasks", "park", tid, "next", cwd=self.checkout)
        storage = self.sync.parent / ".dropbox-work" / self.checkout.name / ".worktrees"
        storage.mkdir(parents=True)
        (self.checkout / ".worktrees").symlink_to(f"../../.dropbox-work/{self.checkout.name}/.worktrees")
        self.commit(self.checkout, "init")
        for root in self.repos:
            self.repo(root, root.name)
            self.commit(root, "init")
        if self.hq:
            self.build_hq()
        self.run(self.checkout / "tools" / "harness-links", "--apply")
        return self

    def build_hq(self):
        """The earlier rename, done in place; the group; the two trust files."""
        self.run("tasks", "rename", "ai", "tack", cwd=self.checkout)
        self.commit(self.checkout, "the earlier rename")
        self.run("tasks", "group", "set", "agent-layer", "tack", *(r.name for r in self.repos))
        # The live checkout's filter keeps trust tables out of commits; this one keeps
        # out any line starting with "trust".
        self.run("git", "config", "filter.harness-state.clean", "sed '/^trust/d'", cwd=self.checkout)
        (self.checkout / ".gitattributes").write_text("codex/config*.toml filter=harness-state\n")
        (self.checkout / "codex").mkdir()
        (self.checkout / "codex" / "config.toml").write_text('model = "m"\n')
        self.commit(self.checkout, "a filtered config")
        with (self.checkout / "codex" / "config.toml").open("a") as f:
            f.write(f'trust = "{self.checkout}"\n')
        # git calls a filtered file modified when only its size differs; staging it, as
        # harness-state-refresh does, refreshes the entry and stages nothing new.
        self.run("git", "add", "codex/config.toml", cwd=self.checkout)
        (self.checkout / "local" / "codex").mkdir(parents=True)
        (self.checkout / "local" / "codex" / "trust.toml").write_text(f'"{self.checkout}" = "trusted"\n')
        (self.checkout / "local" / "codex" / "trust.toml").chmod(0o600)
        assert self.run("git", "status", "--porcelain", cwd=self.checkout).stdout == ""

    def cutover(self, *args, check=True):
        tool = self.snapshot / "rename-cutover" if (self.snapshot / "rename-cutover").exists() \
            else self.checkout / "tools" / "rename-cutover"
        return self.run(tool, *args, check=check)

    def save_args(self):
        args = ["save", "--snapshot", self.snapshot, "--checkout", self.checkout,
                "--new-root", self.new_root, "--old", self.old, "--new", self.new,
                "--link-tool", LINK_TOOL]
        if self.hq:
            for rel in KEPT:
                args += ["--keep", rel]
        for root in self.repos:
            args += ["--repo", root]
        return args

    def save(self, check=True):
        return self.cutover(*self.save_args(), check=check)

    def forward(self):
        """The whole cutover up to the runbook's commits: apply, retarget everywhere, link."""
        self.cutover("apply", "--snapshot", self.snapshot)
        for root in self.repos:
            self.cutover("retarget", "--snapshot", self.snapshot, "--repo", root)
        self.cutover("link", "--snapshot", self.snapshot)

    def depend_on_checkout(self, root):
        """A task in `root` that depends on a checkout task, both committed. Returns
        (checkout id, dependent id)."""
        target = task_id(self.run("tasks", "add", "depended on", "--process", "direct",
                                  cwd=self.checkout).stdout)
        self.commit(self.checkout, "a task to depend on")
        dependent = task_id(self.run("tasks", "add", "depends", "--process", "direct", cwd=root).stdout)
        self.run("tasks", "dep", dependent, "--on", target, cwd=root)
        self.commit(root, "depend on the checkout")
        return target, dependent

    def fingerprint(self):
        """Everything rollback must restore, as comparable data."""
        def tree(root):
            return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
                    if p.is_file() and ".git" not in p.parts}
        return {"checkout": tree(self.checkout), **{r.name: tree(r) for r in self.repos},
                "cfg": tree(self.tmp / "cfg" / "tasks"), "state": tree(self.tmp / "state" / "tasks"),
                "worktrees": os.readlink(self.checkout / ".worktrees"),
                "agents": os.path.realpath(self.tmp / "home" / ".agents"),
                "modes": {rel: oct((self.checkout / rel).stat().st_mode) for rel in KEPT
                          if (self.checkout / rel).exists()}}

    def edit_trust(self):
        """What the runbook's step 4 does to the trust files at the new root."""
        with (self.new_root / "codex" / "config.toml").open("a") as f:
            f.write(f'trust = "{self.new_root}"\n')
        trust = self.new_root / "local" / "codex" / "trust.toml"
        with trust.open("a") as f:
            f.write(f'"{self.new_root}" = "trusted"\n')
        trust.chmod(0o644)


@pytest.fixture
def box(tmp_path):
    return Sandbox(tmp_path).build()


@pytest.fixture
def box2(tmp_path):
    """Two retargeted repositories, ops and lore."""
    return Sandbox(tmp_path, repos=("ops", "lore")).build()


@pytest.fixture
def hq(tmp_path):
    """This rename's shape, retargeting in ops, lore and flows."""
    return Sandbox(tmp_path, repos=("ops", "lore", "flows"), hq=True).build()


# --- save ---------------------------------------------------------------------


def test_save_refuses_with_a_live_claim(box):
    tid = task_id(box.run("tasks", "add", "three", "--process", "direct", cwd=box.checkout).stdout)
    box.run("tasks", "start", tid, cwd=box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "live claim" in result.stderr


def test_save_refuses_a_dirty_tree(box):
    (box.ops / "stray").write_text("x\n")
    result = box.save(check=False)
    assert result.returncode == 1
    assert "not clean" in result.stderr


def test_save_refuses_a_dirty_tree_in_any_repository(box2):
    (box2.repos[1] / "stray").write_text("x\n")
    result = box2.save(check=False)
    assert result.returncode == 1
    assert f"{box2.repos[1]} is not clean" in result.stderr


def test_save_refuses_a_snapshot_path_inside_the_checkout(box):
    box.snapshot = box.checkout / "snap"
    result = box.save(check=False)
    assert result.returncode == 1
    assert "lies inside checkout" in result.stderr
    assert not (box.checkout / "snap").exists()


def test_save_resolves_new_roots_parent_through_a_symlink(box, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(box.sync)
    box.new_root = alias / "tack"
    box.save()
    meta = json.loads((box.snapshot / "meta.json").read_text())
    assert meta["new_root"] == str((box.sync / "tack").resolve())


def test_save_refuses_the_checkout_named_as_a_repository(box):
    box.repos.append(box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "never the checkout" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_repository_named_twice(box):
    box.repos.append(box.ops)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "name each --repo once" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_link_tool_that_is_not_there(box):
    args = [str(a) for a in box.save_args()]
    args[args.index("--link-tool") + 1] = "tools/no-such-tool"
    result = box.cutover(*args, check=False)
    assert result.returncode == 1
    assert "no link tool at" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_branch_with_commits_main_lacks(box):
    """Merged after the rename, such a branch would bring old-prefix task files back."""
    box.run("git", "checkout", "-qb", "feature", cwd=box.checkout)
    (box.checkout / "agents" / "more").write_text("y\n")
    box.commit(box.checkout, "unmerged work")
    box.run("git", "checkout", "-q", "main", cwd=box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "feature" in result.stderr
    assert not box.snapshot.exists()


def test_save_accepts_a_branch_main_already_holds(box):
    box.run("git", "branch", "merged", cwd=box.checkout)
    box.save()


def test_save_refuses_a_checkout_off_main(box):
    box.run("git", "checkout", "-qb", "side", cwd=box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "is on refs/heads/side, not main" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_stash(box):
    """A stash popped after the rename could bring old-prefix task files back."""
    (box.checkout / "agents" / "README").write_text("stashed\n")
    box.run("git", "stash", "-q", cwd=box.checkout)
    result = box.save(check=False)
    assert result.returncode == 1
    assert "has stashes" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_dead_claim_in_any_retargeted_repository(box2):
    """`tasks dep` prunes dead claims from the project it writes in, so a dead claim in a
    retargeted repository would be dropped by retarget and then stop the guard. The
    claim is dead the moment it is written: its session's pid does not exist."""
    lore = box2.repos[1]
    tid = task_id(box2.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=lore).stdout)
    ghost = {**box2.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": "999999"}
    box2.run("tasks", "start", tid, cwd=lore, env=ghost)
    box2.commit(lore, "start under a dead session")
    claims = json.loads(box2.run("tasks", "claims").stdout)["claims"]
    assert any(c["id"] == tid and not c["live"] for c in claims), claims
    result = box2.save(check=False)
    assert result.returncode == 1
    assert "a retargeted repository has claims" in result.stderr and tid in result.stderr
    assert not box2.snapshot.exists()


def test_save_refuses_an_old_prefix_that_is_another_project(box):
    """`tasks rename` would rename whatever --old names; rollback could not undo that."""
    box.old = "ops"
    result = box.save(check=False)
    assert result.returncode == 1
    assert "has the prefix 'ai', not --old 'ops'" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_checkout_the_registry_does_not_map(box, tmp_path):
    copy = tmp_path / "elsewhere"
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    registry.write_text(registry.read_text().replace(f'ai = "{box.checkout}"', f'ai = "{copy}"'))
    result = box.save(check=False)
    assert result.returncode == 1
    assert "the registry maps 'ai'" in result.stderr
    assert not box.snapshot.exists()


def test_save_records_every_repository(box2):
    box2.save()
    meta = json.loads((box2.snapshot / "meta.json").read_text())
    assert meta["checkout"]["root"] == str(box2.checkout)
    assert [r["root"] for r in meta["repos"]] == [str(r) for r in box2.repos]
    assert all(r["branch"] == "refs/heads/main" and len(r["head"]) == 40 for r in meta["repos"])
    assert meta["link_tool"] == LINK_TOOL


# --- apply, retarget, link, verify ---------------------------------------------


def test_apply_renames_and_moves_but_neither_retargets_nor_links(box):
    box.depend_on_checkout(box.ops)
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    assert not box.checkout.exists()
    assert any(p.name.startswith("tack-") for p in (box.new_root / "tasks").glob("*.md"))
    registry = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    assert f'tack = "{box.new_root}"' in registry and 'ai = "tack"' in registry
    assert (box.new_root / ".worktrees").resolve() == \
        (box.sync.parent / ".dropbox-work" / "tack" / ".worktrees").resolve()
    assert "retired_prefix" in box.run("tasks", "check", cwd=box.ops).stdout
    assert not os.path.exists(box.tmp / "home" / ".agents")     # still names the old path


def test_the_whole_cutover_retargets_links_and_verifies(box2):
    hexes = {}
    for root in box2.repos:
        target, dependent = box2.depend_on_checkout(root)
        hexes[root] = (target.split("-", 1)[1], dependent)
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    for root in box2.repos:
        result = box2.cutover("retarget", "--snapshot", box2.snapshot, "--repo", root)
        hex_, dependent = hexes[root]
        assert f"retarget: {dependent}: ai-{hex_} -> tack-{hex_}" in result.stdout
        assert box2.run("tasks", "check", cwd=root).stdout == ""
    box2.cutover("link", "--snapshot", box2.snapshot)
    assert os.path.realpath(box2.tmp / "home" / ".agents") == str((box2.new_root / "agents").resolve())
    box2.cutover("verify", "--snapshot", box2.snapshot)


def test_retarget_keeps_every_dependency_and_its_order(box):
    """Two old ids and one other dependency on one task: all three survive, in order."""
    first = task_id(box.run("tasks", "add", "first", "--process", "direct", cwd=box.checkout).stdout)
    second = task_id(box.run("tasks", "add", "second", "--process", "direct", cwd=box.checkout).stdout)
    box.commit(box.checkout, "two tasks to depend on")
    other = task_id(box.run("tasks", "add", "other", "--process", "direct", cwd=box.ops).stdout)
    dependent = task_id(box.run("tasks", "add", "depends", "--process", "direct", cwd=box.ops).stdout)
    for target in (first, other, second):
        box.run("tasks", "dep", dependent, "--on", target, cwd=box.ops)
    box.commit(box.ops, "three dependencies")
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    box.cutover("retarget", "--snapshot", box.snapshot, "--repo", box.ops)
    shown = json.loads(box.run("tasks", "show", dependent, cwd=box.ops).stdout)
    assert shown["task"]["depends"] == [f"tack-{first[3:]}", other, f"tack-{second[3:]}"]
    assert box.run("tasks", "check", cwd=box.ops).stdout == ""


def test_retarget_writes_each_task_once(tmp_path, monkeypatch):
    """No remove-then-add: one `tasks edit` save per task, the list replaced whole."""
    cutover = load_cutover()
    calls = []
    check = {"warnings": [
        {"id": "ops-1", "kind": "retired_prefix",
         "detail": 'depends on ai-a through retired prefix "ai"; it is now tack-a'},
        {"id": "ops-1", "kind": "retired_prefix",
         "detail": 'depends on ai-b through retired prefix "ai"; it is now tack-b'}]}

    def fake_run(*cmd, cwd=None):
        calls.append(cmd)
        if cmd[:2] == ("tasks", "check"):
            return json.dumps(check)
        if cmd[:2] == ("tasks", "show"):
            return json.dumps({"task": {"depends": ["ai-a", "ops-9", "ai-b"]}})
        return ""

    monkeypatch.setattr(cutover, "run", fake_run)
    cutover.retarget_dependencies(tmp_path, "ai")
    writes = [c for c in calls if c[:2] in (("tasks", "edit"), ("tasks", "dep"))]
    assert writes == [("tasks", "edit", "ops-1", "--no-depends", "--depends", "tack-a",
                       "--depends", "ops-9", "--depends", "tack-b")]


def test_verify_fails_while_a_repository_still_names_a_retired_id(box2):
    box2.depend_on_checkout(box2.repos[1])
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    box2.cutover("retarget", "--snapshot", box2.snapshot, "--repo", box2.repos[0])
    box2.cutover("link", "--snapshot", box2.snapshot)
    result = box2.cutover("verify", "--snapshot", box2.snapshot, check=False)
    assert result.returncode == 1
    assert f"tasks check reports findings in {box2.repos[1]}" in result.stderr


def test_retarget_refuses_a_repository_outside_the_snapshot(box):
    """Rollback could not restore it; nothing is written there."""
    outside = box.sync / "relay"
    box.repo(outside, "relay")
    box.commit(outside, "init")
    _, dependent = box.depend_on_checkout(outside)
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    before = (outside / "tasks" / f"{dependent}.md").read_bytes()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", outside, check=False)
    assert result.returncode == 1
    assert "not in the snapshot" in result.stderr and "--forward" in result.stderr
    assert (outside / "tasks" / f"{dependent}.md").read_bytes() == before
    box.cutover("retarget", "--snapshot", box.snapshot, "--repo", outside, "--forward")
    assert box.run("tasks", "check", cwd=outside).stdout == ""


def test_a_forward_retarget_of_a_non_project_records_nothing(box, tmp_path):
    """A mistyped --repo is refused before it can end rollback."""
    box.save()
    box.forward()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", tmp_path / "typo", "--forward",
                         check=False)
    assert result.returncode == 1 and "is not a tasks project" in result.stderr
    assert not (box.snapshot / "forward.json").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)


def test_retarget_refuses_the_renamed_checkout(box):
    """Its own ids were renamed, not retargeted; --forward on it would end rollback for nothing."""
    box.save()
    box.forward()
    for extra in ((), ("--forward",)):
        result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", box.new_root, *extra,
                             check=False)
        assert result.returncode == 1
        assert "is the renamed checkout" in result.stderr and "pass --forward" not in result.stderr
    assert not (box.snapshot / "forward.json").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)


def test_rollback_refuses_after_a_forward_retarget(box):
    """A forward write is one rollback could not undo: it ends rollback, and nothing moves."""
    outside = box.sync / "relay"
    box.repo(outside, "relay")
    box.commit(outside, "init")
    box.depend_on_checkout(outside)
    box.save()
    box.forward()
    box.cutover("retarget", "--snapshot", box.snapshot, "--repo", outside, "--forward")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "ended when retarget --forward" in result.stderr and str(outside) in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_link_refuses_before_apply(box):
    box.save()
    result = box.cutover("link", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "run apply first" in result.stderr


def test_apply_refuses_when_new_root_already_exists(box):
    box.save()
    box.new_root.mkdir()
    result = box.cutover("apply", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert box.checkout.exists()
    assert box.new_root.is_dir() and not (box.new_root / "tasks").exists()


def test_apply_refuses_when_storage_new_parent_already_exists(box):
    box.save()
    (box.sync.parent / ".dropbox-work" / "tack").mkdir(parents=True)
    result = box.cutover("apply", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert box.checkout.exists()
    assert not box.new_root.exists()


def test_the_storage_follows_the_checkout_directory_not_the_prefix(box):
    """work-link names storage after the directory; a new root whose name differs from
    the new prefix moves the storage to the directory's name."""
    box.new_root = box.sync / "renamed"
    box.save()
    meta = json.loads((box.snapshot / "meta.json").read_text())
    assert meta["storage_new"] == str((box.sync.parent / ".dropbox-work" / "renamed" / ".worktrees").resolve())
    box.forward()
    box.cutover("verify", "--snapshot", box.snapshot)


# --- rollback -----------------------------------------------------------------


def test_rollback_before_commit_restores_everything(box2):
    box2.depend_on_checkout(box2.repos[1])
    before = box2.fingerprint()
    box2.save()
    box2.forward()
    assert (box2.new_root / "tasks").is_dir() and not box2.checkout.exists()
    box2.cutover("rollback", "--snapshot", box2.snapshot)
    assert box2.fingerprint() == before
    for root in (box2.checkout, *box2.repos):
        assert box2.run("tasks", "check", cwd=root).stdout == ""
        assert box2.run("git", "status", "--porcelain", cwd=root).stdout == ""


def test_rollback_after_commit_restores_everything(box2):
    for root in box2.repos:
        box2.depend_on_checkout(root)
    before = box2.fingerprint()
    box2.save()
    box2.forward()
    box2.commit(box2.new_root, "rename")
    for root in box2.repos:
        box2.commit(root, "retarget")
    box2.cutover("rollback", "--snapshot", box2.snapshot)
    assert box2.fingerprint() == before
    assert all((box2.snapshot / f"rollback-{r.name}-1.patch").read_text().strip() for r in box2.repos)


def test_rollback_after_partial_apply(box):
    before = box.fingerprint()
    box.save()
    box.run("tasks", "rename", "ai", "tack", cwd=box.checkout)
    os.rename(box.checkout, box.new_root)      # interrupted before storage, init --force, links
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_after_rename_stopped_midway(box):
    """A rename stopped after moving its files leaves rename/ai.toml; rollback accepts
    this rename's own inventory and restores everything."""
    before = box.fingerprint()
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.checkout, env=env, text=True, capture_output=True)
    assert (box.tmp / "state" / "tasks" / "rename" / "ai.toml").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_stops_on_foreign_untracked_file(box):
    """The check runs before move_back: nothing has moved when it stops."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    (box.new_root / "tasks" / "note.md").write_text("mine\n")
    registry_before = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks/note.md" in result.stderr
    assert (box.new_root / "tasks" / "note.md").read_text() == "mine\n"
    assert box.new_root.exists() and not box.checkout.exists()
    assert (box.tmp / "cfg" / "tasks" / "projects.toml").read_text() == registry_before


def test_rollback_stops_on_an_untracked_file_in_any_repository(box2):
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    (box2.repos[1] / "stray").write_text("mine\n")
    result = box2.cutover("rollback", "--snapshot", box2.snapshot, check=False)
    assert result.returncode == 1
    assert f"{box2.repos[1]} has untracked files" in result.stderr
    assert box2.new_root.exists() and not box2.checkout.exists()


def test_rollback_stops_on_a_nested_leftover(box):
    """git ls-files --others must see exactly tasks/<new>-<hex>.md, one level deep."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    nested = box.new_root / "tasks" / "x"
    nested.mkdir()
    (nested / "tack-deadbeef.md").write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks/x/tack-deadbeef.md" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_rollback_stops_when_home_does_not_match_the_snapshot(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    other_home = box.tmp / "other-home"
    other_home.mkdir()
    env = {**box.env, "HOME": str(other_home)}
    result = box.run(box.snapshot / "rename-cutover", "rollback", "--snapshot", box.snapshot,
                     check=False, env=env)
    assert result.returncode == 1
    assert "environment does not match the snapshot" in result.stderr and "home" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_rollback_stops_when_a_repository_changed_branch(box2):
    box2.save()
    box2.cutover("apply", "--snapshot", box2.snapshot)
    box2.run("git", "checkout", "-qb", "other", cwd=box2.repos[1])
    result = box2.cutover("rollback", "--snapshot", box2.snapshot, check=False)
    assert result.returncode == 1
    assert "other" in result.stderr
    assert box2.new_root.exists() and not box2.checkout.exists()


def test_rollback_saves_a_patch_of_edits_since_save(box):
    """git reset --hard is destructive; a tracked edit made after save must survive as a patch."""
    box.save()
    config_file = box.ops / "tasks" / ".config.toml"
    config_file.write_text(config_file.read_text() + "# stray edit\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot)
    patch = box.snapshot / "rollback-ops-1.patch"
    assert "stray edit" in patch.read_text()
    assert f"changes since save kept in {patch}" in result.stderr
    assert box.run("git", "status", "--porcelain", cwd=box.ops).stdout == ""


def test_rollback_refuses_when_the_worktrees_link_is_a_real_file(box):
    """move_back must not delete a real file sitting where the managed symlink goes."""
    box.save()
    link = box.checkout / ".worktrees"
    link.unlink()
    link.write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "not a link" in result.stderr
    assert link.is_file() and not link.is_symlink() and link.read_text() == "mine\n"


def test_rollback_refuses_when_the_worktrees_link_is_a_real_directory(box):
    box.save()
    link = box.checkout / ".worktrees"
    link.unlink()
    link.mkdir()
    (link / "note.txt").write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "not a link" in result.stderr
    assert link.is_dir() and not link.is_symlink() and (link / "note.txt").read_text() == "mine\n"


def test_rollback_tolerates_empty_foreign_claims_files(box):
    """A `tasks` command run elsewhere during the window can create empty
    claims/<prefix>.{toml,lock} files; an empty claims file records no claim."""
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    claims = box.tmp / "state" / "tasks" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / "ops.lock").write_text("")
    (claims / "ops.toml").write_text("")
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


# --- the guard ----------------------------------------------------------------


def test_guard_stops_on_foreign_registry_change(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    registry.write_text(registry.read_text().replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n'))
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "zz" in result.stderr
    assert box.new_root.exists()                      # nothing was moved back


def test_guard_rejects_an_inventory_for_another_root(box):
    """Same prefixes, a root that merely starts with the checkout's path: not ours."""
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.checkout, env=env, text=True, capture_output=True)
    inventory = box.tmp / "state" / "tasks" / "rename" / "ai.toml"
    inventory.write_text(inventory.read_text().replace(f'"{box.checkout}"', f'"{box.checkout}-other"'))
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1 and "inventory" in result.stderr
    assert inventory.exists()                         # the foreign inventory was not deleted


def test_guard_rejects_a_foreign_inventory(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    inventory = box.tmp / "state" / "tasks" / "rename" / "ai.toml"
    inventory.parent.mkdir(parents=True, exist_ok=True)
    inventory.write_text('source = "ai"\ntarget = "tack"\nroot = "/elsewhere"\n')
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1 and "inventory" in result.stderr


def test_guard_stops_on_a_nonempty_foreign_claims_file(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    claims = box.tmp / "state" / "tasks" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / "ops.toml").write_text('[claim]\nid = "ops-000000"\n')
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "claims/ops.toml" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


def test_guard_stops_when_a_claims_file_is_emptied_live(box):
    """Only a file empty on both sides, or empty live with the saved copy absent, is
    tolerated; a saved claim found empty live is a change."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    saved_claims = box.snapshot / "state" / "claims"
    saved_claims.mkdir(parents=True, exist_ok=True)
    (saved_claims / "ops.toml").write_text('[claims.ops-000000]\nowner = "x"\n')
    live_claims = box.tmp / "state" / "tasks" / "claims"
    live_claims.mkdir(parents=True, exist_ok=True)
    (live_claims / "ops.toml").write_text("")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "claims/ops.toml" in result.stderr
    assert box.new_root.exists() and not box.checkout.exists()


# --- move_back and save_reset_patch, directly ----------------------------------


def meta_for(checkout, new_root, storage_old=None, storage_new=None, link=None):
    return {"checkout": {"root": str(checkout)}, "new_root": str(new_root),
            "storage_old": str(storage_old) if storage_old else None,
            "storage_new": str(storage_new) if storage_new else None, "worktrees_link": link}


def test_move_back_stops_when_both_checkout_and_new_root_exist(tmp_path):
    cutover = load_cutover()
    checkout, new_root = tmp_path / "ai", tmp_path / "tack"
    checkout.mkdir()
    new_root.mkdir()
    with pytest.raises(cutover.Stop, match="both"):
        cutover.move_back(meta_for(checkout, new_root))
    assert checkout.is_dir() and new_root.is_dir()


def test_move_back_stops_when_neither_checkout_nor_new_root_exist(tmp_path):
    cutover = load_cutover()
    with pytest.raises(cutover.Stop, match="neither"):
        cutover.move_back(meta_for(tmp_path / "ai", tmp_path / "tack"))


def test_move_back_stops_when_both_storage_dirs_exist(tmp_path):
    cutover = load_cutover()
    checkout = tmp_path / "ai"
    checkout.mkdir()
    storage_old, storage_new = tmp_path / "dw" / "ai" / ".worktrees", tmp_path / "dw" / "tack" / ".worktrees"
    storage_old.mkdir(parents=True)
    storage_new.mkdir(parents=True)
    with pytest.raises(cutover.Stop, match="both"):
        cutover.move_back(meta_for(checkout, tmp_path / "tack", storage_old, storage_new, "../../dw/ai/.worktrees"))
    assert storage_old.parent.is_dir() and storage_new.parent.is_dir()


def test_move_back_stops_when_neither_storage_dir_exists(tmp_path):
    cutover = load_cutover()
    checkout = tmp_path / "ai"
    checkout.mkdir()
    storage_old, storage_new = tmp_path / "dw" / "ai" / ".worktrees", tmp_path / "dw" / "tack" / ".worktrees"
    with pytest.raises(cutover.Stop, match="neither"):
        cutover.move_back(meta_for(checkout, tmp_path / "tack", storage_old, storage_new, "../../dw/ai/.worktrees"))


def test_save_reset_patch_never_overwrites_an_earlier_patch(tmp_path):
    cutover = load_cutover()
    root = tmp_path / "repo"
    root.mkdir()
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "a.txt").write_text("zero\n")
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-qm", "init"], check=True)
    head = subprocess.run([*git, "rev-parse", "HEAD"], check=True, text=True, capture_output=True).stdout.strip()
    snap = tmp_path / "snap"
    snap.mkdir()
    (root / "a.txt").write_text("one\n")
    cutover.save_reset_patch(root, head, snap, "ai")
    first = snap / "rollback-ai-1.patch"
    first_content = first.read_text()
    assert "one" in first_content
    (root / "a.txt").write_text("two\n")
    cutover.save_reset_patch(root, head, snap, "ai")
    assert first.read_text() == first_content
    assert "two" in (snap / "rollback-ai-2.patch").read_text()


# --- the second host ----------------------------------------------------------


def test_second_host_adopts_the_rename(box):
    """A second host, sharing the synced checkout, adopts the first host's rename."""
    second = {**box.env, "XDG_CONFIG_HOME": str(box.tmp / "cfg2"), "XDG_STATE_HOME": str(box.tmp / "state2")}

    def run2(*cmd, cwd):
        return box.run(*cmd, cwd=cwd, env=second).stdout

    run2("tasks", "init", "--prefix", "ai", "--force", cwd=box.checkout)
    tid = task_id(run2("tasks", "add", "on the second host", "--process", "direct", cwd=box.checkout))
    run2("tasks", "start", tid, cwd=box.checkout)
    run2("tasks", "park", tid, "resume here", cwd=box.checkout)
    box.commit(box.checkout, "second host work")

    box.save()
    box.forward()
    box.commit(box.new_root, "rename")

    def first_host():
        return {str(p): p.read_bytes() for d in ("cfg", "state") for p in sorted((box.tmp / d).rglob("*"))
                if p.is_file()}

    first = first_host()
    run2("tasks", "rename", "ai", "tack", "--adopt", cwd=box.new_root)
    registry = (box.tmp / "cfg2" / "tasks" / "projects.toml").read_text()
    assert f'tack = "{box.new_root}"' in registry and 'ai = "tack"' in registry
    hex_ = tid.split("-", 1)[1]
    assert json.loads(run2("tasks", "show", f"ai-{hex_}", cwd=box.new_root))
    parked = json.loads(run2("tasks", "list", "--parked", cwd=box.new_root))
    assert f"tack-{hex_}" in [t["id"] for t in parked["tasks"]]
    assert first_host() == first


# --- this rename's shape: an earlier alias, a group, the trust files ------------


def test_registry_view_reads_the_renames_own_rewrites_as_equal(tmp_path):
    cutover = load_cutover()
    saved, live = tmp_path / "saved.toml", tmp_path / "live.toml"
    saved.write_text('[projects]\nops = "/o"\ntack = "/t"\n[aliases]\nai = "tack"\n'
                     '[groups]\nagent-layer = ["ops", "tack"]\n')
    live.write_text('[projects]\nhq = "/h"\nops = "/o"\n[aliases]\nai = "hq"\ntack = "hq"\n'
                    '[groups]\nagent-layer = ["hq", "ops"]\n')
    assert cutover.registry_view(live, "tack", "hq") == cutover.registry_view(saved, "tack", "hq")


def test_registry_view_reads_the_renamed_projects_locations_as_its_own(tmp_path):
    # tasks moves [locations.<old>] to [locations.<new>] at rename and appends the former
    # root at init --force; another project's locations still count.
    cutover = load_cutover()
    saved, live = tmp_path / "saved.toml", tmp_path / "live.toml"
    base = '[projects]\nops = "/o"\n{p} = "{r}"\n[locations.ops]\nstorage = "/w/ops"\n'
    saved.write_text(base.format(p="tack", r="/t") + '[locations.tack]\nstorage = "/w/tack"\n')
    live.write_text(base.format(p="hq", r="/h") + '[locations.hq]\nstorage = "/w/hq"\n'
                    '[[locations.hq.former]]\nroot = "/t"\nstorage = "/w/tack"\nuntil = "2026-10-06"\n')
    assert cutover.registry_view(live, "tack", "hq") == cutover.registry_view(saved, "tack", "hq")
    live.write_text(live.read_text().replace('storage = "/w/ops"', 'storage = "/w/elsewhere"'))
    changes = cutover.registry_changes(cutover.registry_view(live, "tack", "hq"),
                                       cutover.registry_view(saved, "tack", "hq"))
    assert changes == ["locations.ops"]


@pytest.mark.parametrize("change, named", [
    (lambda t: t.replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n'), "projects.zz"),
    (lambda t: t.replace("[aliases]\n", '[aliases]\nzz = "hq"\n'), "aliases.zz"),
    (lambda t: t.replace('ai = "hq"', 'ai = "ops"'), "aliases.ai"),
    (lambda t: t.replace('"flows", ', ""), "groups.agent-layer"),
    (lambda t: t.replace("[groups]\n", '[groups]\nother = ["ops"]\n'), "groups.other"),
    (lambda t: t + '\n[locations.zz]\nstorage = "/elsewhere"\n', "locations.zz"),
])
def test_the_guard_stops_on_any_other_registry_change(hq, change, named):
    hq.save()
    hq.cutover("apply", "--snapshot", hq.snapshot)
    registry = hq.tmp / "cfg" / "tasks" / "projects.toml"
    text = registry.read_text()
    assert 'ai = "hq"' in text and '"flows", "hq"' in text
    registry.write_text(change(text))
    assert registry.read_text() != text
    result = hq.cutover("rollback", "--snapshot", hq.snapshot, check=False)
    assert result.returncode == 1
    assert "guard: the registry changed" in result.stderr and named in result.stderr
    assert hq.new_root.exists() and not hq.checkout.exists()


def test_this_renames_cutover_and_rollback_before_commit(hq):
    for root in hq.repos:
        hq.depend_on_checkout(root)
    before = hq.fingerprint()
    hq.save()
    hq.forward()
    hq.edit_trust()
    hq.cutover("verify", "--snapshot", hq.snapshot)
    registry = (hq.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    assert 'ai = "hq"' in registry and 'tack = "hq"' in registry
    assert '"hq"' in registry.split("[groups]")[1]
    hq.cutover("rollback", "--snapshot", hq.snapshot)
    assert hq.fingerprint() == before


def test_this_renames_rollback_after_commit_restores_the_trust_files(hq):
    for root in hq.repos:
        hq.depend_on_checkout(root)
    before = hq.fingerprint()
    hq.save()
    hq.forward()
    hq.edit_trust()
    hq.commit(hq.new_root, "rename")
    for root in hq.repos:
        hq.commit(root, "retarget")
    hq.cutover("rollback", "--snapshot", hq.snapshot)
    assert hq.fingerprint() == before
    assert oct((hq.checkout / KEPT[1]).stat().st_mode).endswith("600")


def test_this_renames_second_host_adopts(hq):
    second = {**hq.env, "XDG_CONFIG_HOME": str(hq.tmp / "cfg2"), "XDG_STATE_HOME": str(hq.tmp / "state2")}
    shutil.copytree(hq.tmp / "cfg", hq.tmp / "cfg2")       # the second host's registry, as it was
    (hq.tmp / "state2").mkdir()
    hq.save()
    hq.forward()
    hq.commit(hq.new_root, "rename")
    hq.run("tasks", "rename", "tack", "hq", "--adopt", cwd=hq.new_root, env=second)
    registry = (hq.tmp / "cfg2" / "tasks" / "projects.toml").read_text()
    assert f'hq = "{hq.new_root}"' in registry
    assert 'ai = "hq"' in registry and 'tack = "hq"' in registry
    assert '"hq"' in registry.split("[groups]")[1] and '"tack"' not in registry.split("[groups]")[1]


def test_save_refuses_a_kept_path_that_is_not_a_file(hq):
    args = [str(a) for a in hq.save_args()]
    args[args.index("--keep") + 1] = "codex/absent.toml"
    result = hq.cutover(*args, check=False)
    assert result.returncode == 1
    assert "no regular file" in result.stderr
    assert not hq.snapshot.exists()


@pytest.mark.parametrize("path", ["/etc/hostname", "../outside.toml"])
def test_save_refuses_a_kept_path_outside_the_checkout(hq, path):
    args = [str(a) for a in hq.save_args()]
    args[args.index("--keep") + 1] = path
    result = hq.cutover(*args, check=False)
    assert result.returncode == 1
    assert "name a path inside the checkout" in result.stderr
    assert not hq.snapshot.exists()


def link_away(directory, outside):
    """Replace a directory by a link to `outside`, which holds the same files."""
    shutil.copytree(directory, outside)
    shutil.rmtree(directory)
    directory.symlink_to(outside)


def test_save_refuses_a_kept_path_through_a_linked_directory(hq, tmp_path):
    link_away(hq.checkout / "local" / "codex", tmp_path / "outside")
    result = hq.save(check=False)
    assert result.returncode == 1
    assert "resolves outside the checkout" in result.stderr
    assert not hq.snapshot.exists()


def test_rollback_refuses_a_kept_path_linked_away_since_save(hq, tmp_path):
    """The restore would overwrite a file outside the checkout; nothing moves."""
    hq.save()
    hq.cutover("apply", "--snapshot", hq.snapshot)
    outside = tmp_path / "outside"
    link_away(hq.new_root / "local" / "codex", outside)
    (outside / "trust.toml").write_text("someone else's\n")
    result = hq.cutover("rollback", "--snapshot", hq.snapshot, check=False)
    assert result.returncode == 1
    assert "would be written through a link" in result.stderr
    assert (outside / "trust.toml").read_text() == "someone else's\n"
    assert hq.new_root.exists() and not hq.checkout.exists()


def test_rollback_refuses_a_kept_path_that_became_a_directory(hq):
    """The restore could not write it; rollback stops before anything moves."""
    hq.save()
    hq.cutover("apply", "--snapshot", hq.snapshot)
    trust = hq.new_root / "local" / "codex" / "trust.toml"
    trust.unlink()
    trust.mkdir()
    result = hq.cutover("rollback", "--snapshot", hq.snapshot, check=False)
    assert result.returncode == 1
    assert "is not a regular file" in result.stderr and "Traceback" not in result.stderr
    assert hq.new_root.exists() and not hq.checkout.exists()


def test_check_kept_names_a_mode_that_differs(tmp_path):
    cutover = load_cutover()
    checkout, snap = tmp_path / "c", tmp_path / "s"
    (snap / "kept").mkdir(parents=True)
    checkout.mkdir()
    (checkout / "f").write_text("x\n")
    (snap / "kept" / "0").write_text("x\n")
    (checkout / "f").chmod(0o644)
    with pytest.raises(cutover.Stop, match="mode 644, saved 600"):
        cutover.check_kept(checkout, snap, {"kept": [{"path": "f", "mode": 0o600}]})

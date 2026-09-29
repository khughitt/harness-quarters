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


def load_cutover():
    """Import tools/rename-cutover as a module, for unit-testing its functions directly.

    The file has no .py suffix, so the loader must be given explicitly."""
    path = TOOLS / "rename-cutover"
    loader = importlib.machinery.SourceFileLoader("rename_cutover", str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class Sandbox:
    def __init__(self, tmp):
        self.tmp = tmp
        self.env = {**os.environ, "HOME": str(tmp / "home"), "XDG_CONFIG_HOME": str(tmp / "cfg"),
                    "XDG_STATE_HOME": str(tmp / "state"), "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        self.env.pop("WORK_ROOT", None)
        for d in ("home", "cfg", "state"):
            (tmp / d).mkdir()
        self.sync = tmp / "sync"
        self.ai, self.ops, self.new_root = self.sync / "ai", self.sync / "ops", self.sync / "tack"
        self.snapshot = tmp / "snap"

    def run(self, *cmd, cwd=None, check=True):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=self.env, text=True,
                                capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def repo(self, path, prefix):
        path.mkdir(parents=True)
        self.run("git", "init", "-q", path)
        self.run("tasks", "init", "--prefix", prefix, cwd=path)

    def build(self):
        self.repo(self.ai, "ai")
        (self.ai / "tools").mkdir()
        for name in ("tack-link", "rename-cutover"):
            shutil.copy2(TOOLS / name, self.ai / "tools" / name)
        (self.ai / "agents").mkdir()
        (self.ai / "agents" / "README").write_text("x\n")
        (self.ai / "links.toml").write_text('[required]\n"~/.agents" = "agents"\n')
        (self.ai / ".gitignore").write_text(".worktrees\n")
        first = json.loads(self.run("tasks", "add", "one", "--process", "direct", cwd=self.ai).stdout)
        tid = first.get("id") or first["task"]["id"]
        self.run("tasks", "add", "two", "--process", "direct", cwd=self.ai)
        self.run("tasks", "start", tid, cwd=self.ai)
        self.run("tasks", "park", tid, "next", cwd=self.ai)
        storage = self.sync.parent / ".dropbox-work" / "ai" / ".worktrees"
        storage.mkdir(parents=True)
        (self.ai / ".worktrees").symlink_to("../../.dropbox-work/ai/.worktrees")
        self.run("git", "add", "-A", cwd=self.ai)
        self.run("git", "commit", "-qm", "init", cwd=self.ai)
        self.repo(self.ops, "ops")
        self.run("git", "add", "-A", cwd=self.ops)
        self.run("git", "commit", "-qm", "init", cwd=self.ops)
        self.run(self.ai / "tools" / "tack-link", "--apply")
        return self

    def cutover(self, *args, check=True):
        tool = self.snapshot / "rename-cutover" if (self.snapshot / "rename-cutover").exists() \
            else self.ai / "tools" / "rename-cutover"
        return self.run(tool, *args, check=check)

    def save(self):
        return self.cutover("save", "--snapshot", self.snapshot, "--ai", self.ai, "--ops", self.ops,
                            "--new-root", self.new_root)

    def fingerprint(self):
        """Everything rollback must restore, as comparable data."""
        def tree(root):
            return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
                    if p.is_file() and ".git" not in p.parts}
        return {"ai": tree(self.ai), "ops": tree(self.ops),
                "cfg": tree(self.tmp / "cfg" / "tasks"), "state": tree(self.tmp / "state" / "tasks"),
                "worktrees": os.readlink(self.ai / ".worktrees"),
                "agents": os.path.realpath(self.tmp / "home" / ".agents")}


@pytest.fixture
def box(tmp_path):
    return Sandbox(tmp_path).build()


def test_save_refuses_with_a_live_claim(box):
    tid = json.loads(box.run("tasks", "add", "three", "--process", "direct", cwd=box.ai).stdout)
    tid = tid.get("id") or tid["task"]["id"]
    box.run("tasks", "start", tid, cwd=box.ai)
    result = box.cutover("save", "--snapshot", box.snapshot, "--ai", box.ai, "--ops", box.ops,
                         "--new-root", box.new_root, check=False)
    assert result.returncode == 1
    assert "live claim" in result.stderr


def test_save_refuses_a_dirty_tree(box):
    (box.ops / "stray").write_text("x\n")
    result = box.cutover("save", "--snapshot", box.snapshot, "--ai", box.ai, "--ops", box.ops,
                         "--new-root", box.new_root, check=False)
    assert result.returncode == 1
    assert "not clean" in result.stderr


def test_rollback_before_commit_restores_everything(box):
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    assert (box.new_root / "tasks").is_dir() and not box.ai.exists()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before
    assert box.run("tasks", "check", cwd=box.ai).stdout == ""
    assert box.run("git", "status", "--porcelain", cwd=box.ai).stdout == ""


def test_rollback_after_commit_restores_everything(box):
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    box.run("git", "add", "-A", cwd=box.new_root)
    box.run("git", "commit", "-qm", "rename", cwd=box.new_root)
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_stops_on_foreign_untracked_file(box):
    """The check now runs before move_back: nothing has moved when it stops."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    (box.new_root / "tasks" / "note.md").write_text("mine\n")
    registry_before = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks/note.md" in result.stderr
    assert (box.new_root / "tasks" / "note.md").read_text() == "mine\n"
    assert box.new_root.exists() and not box.ai.exists()
    assert (box.tmp / "cfg" / "tasks" / "projects.toml").read_text() == registry_before


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
    assert box.new_root.exists() and not box.ai.exists()


def test_guard_stops_on_foreign_registry_change(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    registry.write_text(registry.read_text().replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n'))
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "zz" in result.stderr
    assert box.new_root.exists()                      # nothing was moved back


def test_rollback_after_rename_stopped_midway(box):
    """A rename stopped after moving its files leaves rename/ai.toml; rollback accepts
    this rename's own inventory and restores everything."""
    before = box.fingerprint()
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.ai, env=env, text=True, capture_output=True)
    assert (box.tmp / "state" / "tasks" / "rename" / "ai.toml").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_guard_rejects_an_inventory_for_another_root(box):
    """Same prefixes, a root that merely starts with the checkout's path: not ours."""
    box.save()
    env = {**box.env, "TASKS_RENAME_STOP_AFTER": "files"}
    subprocess.run(["tasks", "rename", "ai", "tack"], cwd=box.ai, env=env, text=True, capture_output=True)
    inventory = box.tmp / "state" / "tasks" / "rename" / "ai.toml"
    text = inventory.read_text()
    inventory.write_text(text.replace(f'"{box.ai}"', f'"{box.ai}-other"'))
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


# --- fix round 1 -------------------------------------------------------------


def test_rollback_refuses_when_the_worktrees_link_is_a_real_file(box):
    """move_back must not delete a real file sitting where the managed symlink goes."""
    box.save()
    link = box.ai / ".worktrees"
    link.unlink()
    link.write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "not a link" in result.stderr
    assert link.is_file() and not link.is_symlink()
    assert link.read_text() == "mine\n"


def test_rollback_refuses_when_the_worktrees_link_is_a_real_directory(box):
    """Same guard, the other failure mode of the old unconditional unlink() (a traceback)."""
    box.save()
    link = box.ai / ".worktrees"
    link.unlink()
    link.mkdir()
    (link / "note.txt").write_text("mine\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "not a link" in result.stderr
    assert link.is_dir() and not link.is_symlink()
    assert (link / "note.txt").read_text() == "mine\n"


def test_move_back_stops_when_both_checkout_and_new_root_exist(tmp_path):
    """Unit-tested directly: move_back must check both ends before moving either."""
    cutover = load_cutover()
    ai, new_root = tmp_path / "ai", tmp_path / "tack"
    ai.mkdir()
    new_root.mkdir()
    meta = {"ai": str(ai), "new_root": str(new_root), "storage_old": None,
            "storage_new": None, "worktrees_link": None}
    with pytest.raises(cutover.Stop, match="both"):
        cutover.move_back(meta)
    assert ai.is_dir() and new_root.is_dir()


def test_move_back_stops_when_neither_checkout_nor_new_root_exist(tmp_path):
    cutover = load_cutover()
    ai, new_root = tmp_path / "ai", tmp_path / "tack"
    meta = {"ai": str(ai), "new_root": str(new_root), "storage_old": None,
            "storage_new": None, "worktrees_link": None}
    with pytest.raises(cutover.Stop, match="neither"):
        cutover.move_back(meta)


def test_move_back_stops_when_both_storage_dirs_exist(tmp_path):
    cutover = load_cutover()
    ai, new_root = tmp_path / "ai", tmp_path / "tack"
    ai.mkdir()
    storage_old = tmp_path / "dw" / "ai" / ".worktrees"
    storage_new = tmp_path / "dw" / "tack" / ".worktrees"
    storage_old.parent.mkdir(parents=True)
    storage_old.mkdir()
    storage_new.parent.mkdir(parents=True)
    storage_new.mkdir()
    meta = {"ai": str(ai), "new_root": str(new_root), "storage_old": str(storage_old),
            "storage_new": str(storage_new), "worktrees_link": "../../dw/ai/.worktrees"}
    with pytest.raises(cutover.Stop, match="both"):
        cutover.move_back(meta)
    assert storage_old.parent.is_dir() and storage_new.parent.is_dir()


def test_move_back_stops_when_neither_storage_dir_exists(tmp_path):
    cutover = load_cutover()
    ai, new_root = tmp_path / "ai", tmp_path / "tack"
    ai.mkdir()
    storage_old = tmp_path / "dw" / "ai" / ".worktrees"
    storage_new = tmp_path / "dw" / "tack" / ".worktrees"
    meta = {"ai": str(ai), "new_root": str(new_root), "storage_old": str(storage_old),
            "storage_new": str(storage_new), "worktrees_link": "../../dw/ai/.worktrees"}
    with pytest.raises(cutover.Stop, match="neither"):
        cutover.move_back(meta)


def test_apply_renames_moves_and_relinks(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    assert not box.ai.exists()
    assert (box.new_root / "tasks").is_dir()
    assert any(p.name.startswith("tack-") for p in (box.new_root / "tasks").glob("*.md"))
    registry = (box.tmp / "cfg" / "tasks" / "projects.toml").read_text()
    assert f'tack = "{box.new_root}"' in registry and 'ai = "tack"' in registry
    assert os.path.realpath(box.tmp / "home" / ".agents") == str((box.new_root / "agents").resolve())
    assert (box.new_root / ".worktrees").resolve() == (box.sync.parent / ".dropbox-work" / "tack" / ".worktrees").resolve()
    box.cutover("verify", "--snapshot", box.snapshot)


def test_rollback_after_partial_apply(box):
    before = box.fingerprint()
    box.save()
    box.run("tasks", "rename", "ai", "tack", cwd=box.ai)
    os.rename(box.ai, box.new_root)              # interrupted before storage, init --force, links
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_rollback_stops_when_home_does_not_match_the_snapshot(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    other_home = box.tmp / "other-home"
    other_home.mkdir()
    env = {**box.env, "HOME": str(other_home)}
    tool = box.snapshot / "rename-cutover"
    result = subprocess.run([str(tool), "rollback", "--snapshot", str(box.snapshot)], env=env,
                            text=True, capture_output=True)
    assert result.returncode == 1
    assert "environment does not match the snapshot" in result.stderr
    assert "home" in result.stderr
    assert box.new_root.exists() and not box.ai.exists()


def test_rollback_stops_when_the_branch_changed_since_save(box):
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    box.run("git", "checkout", "-qb", "other", cwd=box.new_root)
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "other" in result.stderr
    assert box.new_root.exists() and not box.ai.exists()


def test_save_refuses_a_snapshot_path_inside_ai(box):
    result = box.cutover("save", "--snapshot", box.ai / "snap", "--ai", box.ai, "--ops", box.ops,
                         "--new-root", box.new_root, check=False)
    assert result.returncode == 1
    assert "lies inside ai" in result.stderr
    assert not (box.ai / "snap").exists()


def test_save_resolves_new_roots_parent_through_a_symlink(box, tmp_path):
    alias = tmp_path / "alias"
    alias.symlink_to(box.sync)
    box.cutover("save", "--snapshot", box.snapshot, "--ai", box.ai, "--ops", box.ops,
               "--new-root", alias / "tack")
    meta = json.loads((box.snapshot / "meta.json").read_text())
    assert meta["new_root"] == str(box.new_root.resolve())


def test_save_reset_patch_never_overwrites_an_earlier_patch(tmp_path):
    cutover = load_cutover()
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "a.txt").write_text("zero\n")
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                    "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], check=True)
    head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], check=True, text=True,
                          capture_output=True).stdout.strip()
    snap = tmp_path / "snap"
    snap.mkdir()
    (root / "a.txt").write_text("one\n")
    cutover.save_reset_patch(root, head, snap, "ai")
    first = snap / "rollback-ai-1.patch"
    assert first.is_file()
    first_content = first.read_text()
    assert "one" in first_content
    (root / "a.txt").write_text("two\n")
    cutover.save_reset_patch(root, head, snap, "ai")
    second = snap / "rollback-ai-2.patch"
    assert second.is_file()
    assert first.read_text() == first_content
    assert "two" in second.read_text()


def test_apply_refuses_when_new_root_already_exists(box):
    box.save()
    box.new_root.mkdir()
    result = box.cutover("apply", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert box.ai.exists()
    assert box.new_root.is_dir() and not (box.new_root / "tasks").exists()


def test_apply_refuses_when_storage_new_parent_already_exists(box):
    box.save()
    storage_new_parent = box.sync.parent / ".dropbox-work" / "tack"
    storage_new_parent.mkdir(parents=True)
    result = box.cutover("apply", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr
    assert box.ai.exists()
    assert not box.new_root.exists()


def test_rollback_saves_a_patch_of_edits_since_save(box):
    """git reset --hard is destructive; a tracked edit made after save must survive as a patch."""
    box.save()
    config_file = box.ops / "tasks" / ".config.toml"
    config_file.write_text(config_file.read_text() + "# stray edit\n")
    result = box.cutover("rollback", "--snapshot", box.snapshot)
    patch = box.snapshot / "rollback-ops-1.patch"
    assert patch.is_file()
    assert "stray edit" in patch.read_text()
    assert f"changes since save kept in {patch}" in result.stderr
    assert box.run("git", "status", "--porcelain", cwd=box.ops).stdout == ""


def test_second_host_adopts_the_rename(box):
    """A second host, sharing the synced checkout, adopts the first host's rename."""
    second = {**box.env, "XDG_CONFIG_HOME": str(box.tmp / "cfg2"), "XDG_STATE_HOME": str(box.tmp / "state2")}

    def run2(*cmd, cwd):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=second, text=True, capture_output=True)
        assert result.returncode == 0, f"{cmd}: {result.stdout}{result.stderr}"
        return result.stdout

    run2("tasks", "init", "--prefix", "ai", "--force", cwd=box.ai)
    added = json.loads(run2("tasks", "add", "on the second host", "--process", "direct", cwd=box.ai))
    tid = added.get("id") or added["task"]["id"]
    run2("tasks", "start", tid, cwd=box.ai)
    run2("tasks", "park", tid, "resume here", cwd=box.ai)
    box.run("git", "add", "-A", cwd=box.ai)
    box.run("git", "commit", "-qm", "second host work", cwd=box.ai)

    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    box.run("git", "add", "-A", cwd=box.new_root)
    box.run("git", "commit", "-qm", "rename", cwd=box.new_root)
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


# --- fix round 2 (empty foreign claims files, ops retargeting) --------------


def test_rollback_tolerates_empty_foreign_claims_files(box):
    """A `tasks` command run elsewhere (e.g. ops) during the window can create empty
    claims/<prefix>.{toml,lock} files for a project this cutover does not own. An empty
    claims file records no claim, so the guard must not treat it as a foreign change —
    and restore replaces the state dir, so the files simply disappear afterwards."""
    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    claims = box.tmp / "state" / "tasks" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / "ops.lock").write_text("")
    (claims / "ops.toml").write_text("")
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_guard_stops_on_a_nonempty_foreign_claims_file(box):
    """A non-empty claims file records a real claim; the guard must still stop, and
    nothing may be moved back before it does."""
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    claims = box.tmp / "state" / "tasks" / "claims"
    claims.mkdir(parents=True, exist_ok=True)
    (claims / "ops.toml").write_text('[claim]\nid = "ops-000000"\n')
    result = box.cutover("rollback", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "guard" in result.stderr and "claims/ops.toml" in result.stderr
    assert box.new_root.exists() and not box.ai.exists()


def test_apply_retargets_ops_dependencies_through_the_retired_prefix(box):
    """After the rename, an ops task that depends on an ai task through `tasks dep`
    trips `retired_prefix` in ops's `tasks check`; apply must retarget it so ops comes
    back clean, and `verify` (which requires a clean `tasks check` in ops) must pass."""
    added = json.loads(box.run("tasks", "add", "needs an ai task", "--process", "direct",
                               cwd=box.ai).stdout)
    ai_tid = added.get("id") or added["task"]["id"]
    box.run("git", "add", "-A", cwd=box.ai)
    box.run("git", "commit", "-qm", "add a task for ops to depend on", cwd=box.ai)

    added_ops = json.loads(box.run("tasks", "add", "depends on an ai task", "--process", "direct",
                                   cwd=box.ops).stdout)
    ops_tid = added_ops.get("id") or added_ops["task"]["id"]
    box.run("tasks", "dep", ops_tid, "--on", ai_tid, cwd=box.ops)
    box.run("git", "add", "-A", cwd=box.ops)
    box.run("git", "commit", "-qm", "depend on the ai task", cwd=box.ops)

    box.save()
    result = box.cutover("apply", "--snapshot", box.snapshot)
    hex_ = ai_tid.split("-", 1)[1]
    assert f"retarget: {ops_tid}: {ai_tid} -> tack-{hex_}" in result.stdout
    assert box.run("tasks", "check", cwd=box.ops).stdout == ""
    shown = json.loads(box.run("tasks", "show", ops_tid, cwd=box.ops).stdout)
    assert f"tack-{hex_}" in shown["task"]["depends"]
    box.cutover("verify", "--snapshot", box.snapshot)


# --- fix round 3 (a dead ops claim survives save, then gets pruned by retarget) -----


def test_save_refuses_a_dead_ops_claim(box):
    """`tasks dep` (like any task write) prunes dead claims from the project's own
    claims store as a side effect. If a dead ops claim were present at save time,
    apply's retarget step would silently drop it from claims/ops.toml when it runs
    `tasks dep` in ops, and rollback's guard would then stop on a non-empty change the
    cutover itself made. Refuse at save instead: ops must have no claim, live or dead.

    A dead claim is produced through the real CLI path: `tasks start` with an explicit
    session/pid pair whose pid does not exist, so the claim is dead (`live: false`) the
    moment it is written, per `tasks claims`."""
    tid = json.loads(box.run("tasks", "add", "orphaned claim", "--process", "direct",
                             cwd=box.ops).stdout)
    tid = tid.get("id") or tid["task"]["id"]
    ghost_env = {**box.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": "999999"}
    started = subprocess.run(["tasks", "start", tid], cwd=box.ops, env=ghost_env, text=True,
                             capture_output=True)
    assert started.returncode == 0, started.stdout + started.stderr
    box.run("git", "add", "-A", cwd=box.ops)
    box.run("git", "commit", "-qm", "start under a dead session", cwd=box.ops)

    claims = json.loads(box.run("tasks", "claims").stdout)["claims"]
    assert any(c["id"] == tid and not c["live"] for c in claims), claims

    result = box.cutover("save", "--snapshot", box.snapshot, "--ai", box.ai, "--ops", box.ops,
                         "--new-root", box.new_root, check=False)
    assert result.returncode == 1
    assert "ops has claims" in result.stderr
    assert tid in result.stderr
    assert not box.snapshot.exists()


def test_rollback_after_apply_with_no_ops_claims_restores_everything(box):
    """The companion to the retarget test above with no ops claim at all: the round
    trip through apply's retarget and rollback's restore must still land exactly on the
    saved fingerprint."""
    added = json.loads(box.run("tasks", "add", "needs an ai task", "--process", "direct",
                               cwd=box.ai).stdout)
    ai_tid = added.get("id") or added["task"]["id"]
    box.run("git", "add", "-A", cwd=box.ai)
    box.run("git", "commit", "-qm", "add a task for ops to depend on", cwd=box.ai)

    added_ops = json.loads(box.run("tasks", "add", "depends on an ai task", "--process", "direct",
                                   cwd=box.ops).stdout)
    ops_tid = added_ops.get("id") or added_ops["task"]["id"]
    box.run("tasks", "dep", ops_tid, "--on", ai_tid, cwd=box.ops)
    box.run("git", "add", "-A", cwd=box.ops)
    box.run("git", "commit", "-qm", "depend on the ai task", cwd=box.ops)

    before = box.fingerprint()
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before


def test_guard_stops_when_a_claims_file_is_emptied_live(box):
    """A claims file that was non-empty at save time is a real claim record; the guard
    must still stop even if it is later found empty live (e.g. pruned by some other
    `tasks` write) — only a file empty on both sides, or empty live with the saved copy
    absent, is tolerated."""
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
    assert box.new_root.exists() and not box.ai.exists()

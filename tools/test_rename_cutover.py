"""rename-cutover saves, guards and restores a rename in a sandbox that shares no live state."""
import importlib.machinery
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

TOOLS = Path(__file__).parent
LINK_TOOL = "tools/harness-links"
# A copy of the records repository's pre-commit hook (fixtures/records-hook/README.md).
RECORDS_HOOK = TOOLS / "fixtures" / "records-hook" / "pre-commit"


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


def start_under_a_dead_session(box, tid, cwd):
    """Claim `tid` for a session whose pid has ended. tasks records the PID view that lets
    it judge a pid only when the exported pid exists at the claim and the claim is written
    in the initial PID namespace; otherwise the claim reads `unverifiable`, held rather
    than dead. So export a real child's pid and reap the child once the claim is written."""
    nspid = next(line for line in Path("/proc/self/status").read_text().splitlines()
                 if line.startswith("NSpid:")).split()[1:]
    assert os.stat("/proc/self/ns/pid").st_ino == INITIAL_PID_NAMESPACE and len(nspid) == 1, (
        "tasks judges an exported pid only in the initial PID namespace; this test runs in "
        "another (a container or sandbox), where a claim whose session ended stays held")
    child = subprocess.Popen(["sleep", "60"], env=box.env)
    try:
        box.run("tasks", "start", tid, cwd=cwd,
                env={**box.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": str(child.pid)})
    finally:
        child.kill()
        child.wait()


# The initial PID namespace's nsfs inode, a kernel constant (PROC_PID_INIT_INO).
INITIAL_PID_NAMESPACE = 0xEFFFFFFC

KEPT = ("codex/config.toml", "local/codex/trust.toml")


class Sandbox:
    """A rename in a sandbox that shares no live state. The September shape: checkout
    `ai` (prefix ai) becomes `tack`, retargeting in `repos` (ops, unless a test asks).
    The hq shape (`hq=True`): checkout `tack`, renamed once before from `ai` so the
    registry holds `ai = "tack"`, in the group `agent-layer`, becomes `hq`; its Codex
    trust files are a filtered tracked file and an ignored one, saved with --keep.
    `detached=True` makes the checkout a detached project and `detached_repos` names the
    repos that are; their records live in the records repository `sync/records`, which only
    such a box creates, so in-tree boxes and their fingerprints are unchanged."""

    def __init__(self, tmp, repos=("ops",), hq=False, detached=False, detached_repos=()):
        if not set(detached_repos) <= set(repos):
            raise ValueError(f"detached_repos {detached_repos} must name repos in {repos}")
        if hq and (detached or detached_repos):
            raise ValueError("the hq shape is in-tree only")
        self.tmp = tmp
        self.env = {"PATH": os.environ["PATH"], "HOME": str(tmp / "home"), "USER": "test",
                    "XDG_CONFIG_HOME": str(tmp / "cfg"), "XDG_STATE_HOME": str(tmp / "state"),
                    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
                    "GIT_CEILING_DIRECTORIES": str(tmp), "GIT_AUTHOR_NAME": "t",
                    "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
                    "TASKS_SESSION": "rename-cutover-test", "TASKS_OWNER": "fixture"}
        for d in ("home", "cfg", "state"):
            (tmp / d).mkdir()
        self.sync = tmp / "sync"
        self.hq = hq
        self.old, self.new = ("tack", "hq") if hq else ("ai", "tack")
        self.checkout, self.new_root = self.sync / self.old, self.sync / self.new
        self.repos = [self.sync / name for name in repos]
        self.ops = self.repos[0]
        self.snapshot = tmp / "snap"
        # Detached projects keep their records in one records repository beside the code
        # checkouts, which runs its own copy of the records repository's hook.
        self.detached, self.detached_repos = detached, tuple(detached_repos)
        self.records = self.sync / "records" if detached or detached_repos else None
        self.hook = tmp / "hooks" / "pre-commit"
        # apply's stdout, which carries the records commit commit_rename() runs.
        self.applied = None

    def run(self, *cmd, cwd=None, check=True, env=None):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env or self.env, text=True,
                                capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def repo(self, path, prefix):
        path.mkdir(parents=True)
        self.run("git", "init", "-q", "-b", "main", path)
        assert Path(self.run("git", "rev-parse", "--show-toplevel", cwd=path).stdout.strip()).resolve() == path.resolve()
        assert Path(self.run("git", "rev-parse", "--absolute-git-dir", cwd=path).stdout.strip()).resolve().is_relative_to(path.resolve())
        self.run("tasks", "init", "--prefix", prefix, cwd=path)

    def code_repo(self, path, prefix):
        """A detached project: a code checkout with no tasks/, paired with records under
        the records repository. Its config is committed there at once: until it is in the
        index, the hook refuses every record commit under <prefix>/."""
        path.mkdir(parents=True)
        self.run("git", "init", "-q", "-b", "main", path)
        assert Path(self.run("git", "rev-parse", "--show-toplevel", cwd=path).stdout.strip()).resolve() == path.resolve()
        assert Path(self.run("git", "rev-parse", "--absolute-git-dir", cwd=path).stdout.strip()).resolve().is_relative_to(path.resolve())
        self.run("tasks", "init", "--prefix", prefix, "--records", self.records, cwd=path)
        self.commit(self.records, f"{prefix} records")

    def records_repo(self):
        """The records repository, its first commit, and the box's own copy of the hook,
        which a test may overwrite to make it fail; the tracked fixture is never edited."""
        self.hook.parent.mkdir()
        shutil.copy2(RECORDS_HOOK, self.hook)
        self.records.mkdir(parents=True)
        self.run("git", "init", "-q", "-b", "main", self.records)
        assert Path(self.run("git", "rev-parse", "--show-toplevel", cwd=self.records).stdout.strip()).resolve() == self.records.resolve()
        assert Path(self.run("git", "rev-parse", "--absolute-git-dir", cwd=self.records).stdout.strip()).resolve().is_relative_to(self.records.resolve())
        self.run("git", "commit", "-q", "--allow-empty", "-m", "init", cwd=self.records)
        self.run("git", "config", "core.hooksPath", self.hook.parent, cwd=self.records)

    def is_detached(self, root):
        """Whether `root` (the checkout or one of `repos`) keeps its records in the records repository."""
        if root == self.checkout:
            return self.detached
        return root in self.repos and root.name in self.detached_repos

    def commit(self, root, message):
        self.run("git", "add", "-A", cwd=root)
        self.run("git", "commit", "-qm", message, cwd=root)

    def commit_rename(self):
        """The runbook's commit after apply, run once per cutover. Detached: the one records
        commit line apply printed (`apply()` or `forward()` keeps its stdout), run as
        printed through the box's hook, after which HEAD holds <new>/ and no <old>/; a
        second call fails, since the line is consumed. In-tree: the new root, as the
        existing after-commit tests commit it."""
        if not self.detached:
            self.commit(self.new_root, "rename")
            return
        assert self.applied is not None, "commit_rename() runs once, after apply"
        lines = [line.strip() for line in self.applied.splitlines() if line.strip().startswith("git -C ")]
        assert len(lines) == 1, self.applied
        self.applied = None
        self.run("bash", "-c", lines[0], cwd=self.tmp)
        top = self.run("git", "-C", self.records, "ls-tree", "--name-only", "HEAD").stdout.split()
        assert self.new in top and self.old not in top, top

    def build(self):
        if self.records:
            self.records_repo()
        if self.detached:
            self.code_repo(self.checkout, "ai")
        else:
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
            if self.is_detached(root):
                self.code_repo(root, root.name)
                (root / "README").write_text("x\n")
            else:
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

    def apply(self):
        """apply, its stdout kept for commit_rename()."""
        result = self.cutover("apply", "--snapshot", self.snapshot)
        self.applied = result.stdout
        return result

    def forward(self):
        """The whole cutover up to the runbook's commits: apply, retarget everywhere, link."""
        self.apply()
        for root in self.repos:
            self.cutover("retarget", "--snapshot", self.snapshot, "--repo", root)
        self.cutover("link", "--snapshot", self.snapshot)

    def depend_on_checkout(self, root):
        """A task in `root` that depends on a checkout task, both committed: by this
        helper for an in-tree side, by tasks itself for a detached one, whose record
        writes commit themselves. Returns (checkout id, dependent id)."""
        target = task_id(self.run("tasks", "add", "depended on", "--process", "direct",
                                  cwd=self.checkout).stdout)
        if not self.is_detached(self.checkout):
            self.commit(self.checkout, "a task to depend on")
        dependent = task_id(self.run("tasks", "add", "depends", "--process", "direct", cwd=root).stdout)
        self.run("tasks", "dep", dependent, "--on", target, cwd=root)
        if not self.is_detached(root):
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
                          if (self.checkout / rel).exists()},
                # A detached box's records, with its directories, so empty docs/specs and
                # docs/plans count.
                **({"records": tree(self.records),
                    "records_dirs": sorted(str(p.relative_to(self.records)) for p in self.records.rglob("*")
                                           if p.is_dir() and ".git" not in p.relative_to(self.records).parts)}
                   if self.records else {})}

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
    claim is dead once written: its session's pid has ended."""
    lore = box2.repos[1]
    tid = task_id(box2.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=lore).stdout)
    start_under_a_dead_session(box2, tid, lore)
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
    assert f"save: no registered project has its root at {box.checkout}" in result.stderr
    assert not box.snapshot.exists()


@pytest.mark.parametrize("detached, detached_repos", [(True, ()), (True, ("ops",)), (False, ("ops",))])
def test_detached_sandbox_builds(tmp_path, detached, detached_repos):
    """The fixture the detached tests stand on: each detached project's code checkout holds
    no tasks/, its row is detached with records under sync/records, the fixture's own
    record writes committed themselves, and the records repository's hook is installed."""
    box = Sandbox(tmp_path, detached=detached, detached_repos=detached_repos).build()
    rows = {Path(row["root"]).resolve(): row for row in
            json.loads(box.run("tasks", "projects", "--json", cwd=box.checkout).stdout)["projects"]}
    detached_roots = ([box.checkout] if detached else []) + [box.sync / n for n in detached_repos]
    for root in detached_roots:
        assert not (root / "tasks").exists()
        row = rows[root.resolve()]
        assert row["kind"] == "detached"
        assert Path(row["records"]).resolve() == (box.records / row["prefix"]).resolve()
    for root in {box.checkout, *box.repos} - set(detached_roots):
        assert (root / "tasks" / ".config.toml").is_file()
    assert box.run("git", "status", "--porcelain", "--untracked-files=all", "--ignored",
                   cwd=box.records).stdout == ""
    (box.records / "zz").mkdir()
    (box.records / "zz" / "note.md").write_text("x\n")
    box.run("git", "add", "zz", cwd=box.records)
    result = box.run("git", "commit", "-qm", "zz", cwd=box.records, check=False)
    assert result.returncode == 1
    assert "pre-commit: zz/ has staged files but no tasks/.config.toml" in result.stderr


# --- save: detached projects ----------------------------------------------------


@pytest.fixture
def dbox(tmp_path):
    """A detached checkout and a detached --repo, ops, sharing the records repository."""
    return Sandbox(tmp_path, detached=True, detached_repos=("ops",)).build()


def load_meta(box):
    return json.loads((box.snapshot / "meta.json").read_text())


def head_of(box, root):
    return box.run("git", "rev-parse", "HEAD", cwd=root).stdout.strip()


def refused(box, message):
    """save exits 1 naming `message`, and writes no snapshot."""
    result = box.save(check=False)
    assert result.returncode == 1, result.stdout
    assert message in result.stderr, result.stderr
    assert not box.snapshot.exists()


def extra_detached(box, name, records_root):
    """A detached --repo `name`, added to the box after its build, whose records tasks
    places under `records_root`. Its code checkout has one commit; its records config is
    left for the caller to commit, since where it may be committed is what each test varies."""
    code = box.sync / name
    code.mkdir()
    box.run("git", "init", "-q", "-b", "main", code)
    (code / "README").write_text("x\n")
    box.commit(code, "init")
    box.run("tasks", "init", "--prefix", name, "--records", records_root, cwd=code)
    box.repos.append(code)
    return code


def nested_records_repo(box, outer):
    """A records repository at <outer>/recs, git-ignored in `outer` so that outer's clean
    check passes, holding the records of a detached --repo `nr`."""
    with (outer / ".gitignore").open("a") as f:
        f.write("recs/\n")
    box.commit(outer, "ignore recs")
    recs = outer / "recs"
    recs.mkdir()
    box.run("git", "init", "-q", "-b", "main", recs)
    box.run("git", "commit", "-q", "--allow-empty", "-m", "init", cwd=recs)
    extra_detached(box, "nr", recs)
    box.commit(recs, "nr records")
    return recs


def test_save_accepts_a_detached_checkout_and_records_its_records_repository(tmp_path):
    box = Sandbox(tmp_path, repos=("ops", "lore"), detached=True, detached_repos=("ops",)).build()
    box.save()
    meta = load_meta(box)
    records = box.records.resolve()
    assert meta["checkout"]["records"] == {
        "repo": str(records), "records_root": str(records),
        "dirs": ["ai/docs", "ai/docs/plans", "ai/docs/specs", "ai/tasks"]}
    assert meta["records_repos"] == [{"root": str(records), "head": head_of(box, records),
                                      "branch": "refs/heads/main", "owned": ["ai/", "ops/", "tack/"]}]
    assert {Path(r["root"]).name: r["kind"] for r in meta["repos"]} == {"ops": "detached", "lore": "in-tree"}


def test_save_with_an_in_tree_checkout_and_a_detached_repo_owns_only_p(tmp_path):
    box = Sandbox(tmp_path, detached_repos=("ops",)).build()
    box.save()
    meta = load_meta(box)
    records = box.records.resolve()
    assert meta["checkout"]["records"] is None
    assert meta["records_repos"] == [{"root": str(records), "head": head_of(box, records),
                                      "branch": "refs/heads/main", "owned": ["ops/"]}]
    assert [r["kind"] for r in meta["repos"]] == ["detached"]


def test_save_accepts_a_dirty_detached_repo_code_checkout(dbox):
    """The cutover never writes in a detached --repo's code checkout."""
    (dbox.ops / "stray").write_text("x\n")
    (dbox.ops / "README").write_text("edited\n")
    dbox.save()


def test_save_accepts_untracked_files_outside_the_owned_paths(dbox):
    # Build every project before any draft: code_repo commits the whole records repository.
    dbox.code_repo(dbox.sync / "zz", "zz")
    (dbox.records / "zz" / "docs" / "specs" / "draft.md").write_text("another session's draft\n")
    (dbox.records / "ops" / "docs" / "specs" / "draft.md").write_text("a draft in ops\n")
    dbox.save()


def linked(box):
    """A linked project lnk: its records in an overlay directory, its code beside it. The
    overlay is the registered root, so it holds the link tool save checks before the kind,
    and the cutover's own copy, which `Sandbox.cutover` runs from the checkout."""
    code = box.sync / "lnkcode"
    code.mkdir()
    box.run("git", "init", "-q", "-b", "main", code)
    (code / "README").write_text("x\n")
    box.commit(code, "init")
    overlay = box.sync / "overlay"
    overlay.mkdir()
    box.run("tasks", "init", "--prefix", "lnk", "--checkout", code, cwd=overlay)
    (overlay / "tools").mkdir()
    for name in ("harness-links", "rename-cutover"):
        shutil.copy2(TOOLS / name, overlay / "tools" / name)
    return overlay


LINKED = "is a linked project; this cutover renames and retargets only in-tree and detached projects"


def test_save_refuses_a_linked_checkout(box):
    overlay = linked(box)
    box.checkout, box.old, box.new, box.new_root = overlay, "lnk", "lnk2", box.sync / "lnk2"
    refused(box, f"save: {overlay.resolve()} {LINKED}")


def test_save_refuses_a_linked_repo(box):
    overlay = linked(box)
    box.repos.append(overlay)
    refused(box, f"save: {overlay.resolve()} {LINKED}")


def test_save_refuses_an_unreachable_repo(box):
    config = box.ops / "tasks" / ".config.toml"
    config.rename(config.with_name("config.aside"))
    row = next(r for r in json.loads(box.run("tasks", "projects", "--json", cwd=box.checkout).stdout)["projects"]
               if r["prefix"] == "ops")
    assert row["reachable"] is False and "kind" not in row
    refused(box, f"save: {box.ops.resolve()} (ops) is unreachable")


def test_project_kind_names_a_reachable_row_without_a_kind(tmp_path, monkeypatch):
    """A reachable row with no kind is not unreachable: tasks read its records but did not
    say what kind of project it is."""
    cutover = load_cutover()
    monkeypatch.setattr(cutover, "project_row", lambda root, command: {"prefix": "ops", "reachable": True})
    with pytest.raises(cutover.Stop) as stop:
        cutover.project_kind(tmp_path, "save")
    assert str(stop.value) == (f"save: {tmp_path} (ops) is reachable but tasks projects gives it no kind; "
                               f"update tasks to one that reports kind (records-home) first")


# Refusals on the records repository.


def test_save_refuses_a_records_repository_off_main(dbox):
    dbox.run("git", "checkout", "-qb", "side", cwd=dbox.records)
    refused(dbox, f"preconditions: {dbox.records.resolve()} is on refs/heads/side, not main")


def test_save_refuses_a_records_repository_with_a_stash(dbox):
    (dbox.records / "README").write_text("x\n")
    dbox.commit(dbox.records, "a top-level file")
    (dbox.records / "README").write_text("stashed\n")
    dbox.run("git", "stash", "-q", cwd=dbox.records)
    refused(dbox, f"preconditions: {dbox.records.resolve()} has stashes")


def test_save_refuses_a_records_repository_with_a_second_worktree(dbox):
    dbox.run("git", "worktree", "add", "-q", dbox.tmp / "wt", cwd=dbox.records)
    refused(dbox, f"preconditions: {dbox.records.resolve()} has more than one worktree")


def test_save_refuses_a_records_repository_with_an_unmerged_branch(dbox):
    dbox.run("git", "checkout", "-qb", "feature", cwd=dbox.records)
    (dbox.records / "README").write_text("x\n")
    dbox.commit(dbox.records, "unmerged")
    dbox.run("git", "checkout", "-q", "main", cwd=dbox.records)
    refused(dbox, f"preconditions: {dbox.records.resolve()} has branches with commits its current "
                  f"branch lacks: feature")


OLD_NOT_CLEAN = "has untracked, ignored or changed files under ai/"
OLD_REMEDY = ("every file there after the rename must be the rename's, so commit, discard or move "
              "them aside first")


def test_save_refuses_an_untracked_file_under_old(dbox):
    (dbox.records / "ai" / "docs" / "specs" / "draft.md").write_text("x\n")
    refused(dbox, f"preconditions: {dbox.records.resolve()} {OLD_NOT_CLEAN}: ?? ai/docs/specs/draft.md; "
                  f"{OLD_REMEDY}")


def test_save_refuses_an_ignored_file_under_old(dbox):
    with (dbox.records / ".git" / "info" / "exclude").open("a") as f:
        f.write("*.tmp\n")
    (dbox.records / "ai" / "docs" / "plans" / "x.tmp").write_text("x\n")
    assert dbox.run("git", "status", "--porcelain", cwd=dbox.records).stdout == ""
    refused(dbox, f"preconditions: {dbox.records.resolve()} {OLD_NOT_CLEAN}: !! ai/docs/plans/x.tmp; "
                  f"{OLD_REMEDY}")


def test_save_refuses_a_tracked_change_under_old(dbox):
    """The same check sees a tracked edit, which its message and remedy cover too."""
    spec = dbox.records / "ai" / "docs" / "specs" / "a.md"
    spec.write_text("x\n")
    dbox.run("git", "add", "ai/docs/specs/a.md", cwd=dbox.records)
    dbox.run("git", "commit", "-qm", "an ai spec", cwd=dbox.records)
    spec.write_text("changed\n")
    refused(dbox, f"preconditions: {dbox.records.resolve()} {OLD_NOT_CLEAN}: M ai/docs/specs/a.md; "
                  f"{OLD_REMEDY}")


def test_save_refuses_a_tracked_change_under_p(dbox):
    spec = dbox.records / "ops" / "docs" / "specs" / "a.md"
    spec.write_text("x\n")
    dbox.commit(dbox.records, "an ops spec")
    spec.write_text("changed\n")
    refused(dbox, f"preconditions: {dbox.records.resolve()} has tracked changes under ops/: "
                  f"M ops/docs/specs/a.md")


def test_save_refuses_a_staged_file_of_another_project(dbox):
    dbox.code_repo(dbox.sync / "zz", "zz")
    (dbox.records / "zz" / "docs" / "specs" / "d.md").write_text("x\n")
    dbox.run("git", "add", "zz/docs/specs/d.md", cwd=dbox.records)
    refused(dbox, f"preconditions: {dbox.records.resolve()} has staged changes (zz/docs/specs/d.md)")


def test_save_refuses_when_the_new_records_directory_exists(dbox):
    (dbox.records / "tack").mkdir()
    refused(dbox, f"save: {(dbox.records / 'tack').resolve()} already exists")


def test_save_refuses_a_dangling_link_at_the_new_records_directory(dbox):
    (dbox.records / "tack").symlink_to("nowhere")
    assert not (dbox.records / "tack").exists()
    refused(dbox, f"save: {dbox.records.resolve() / 'tack'} already exists")


@pytest.mark.parametrize("where", ["HEAD", "index"])
def test_save_refuses_a_new_records_directory_git_still_tracks(dbox, where):
    """tack/ gone from the working tree but still in HEAD or the index: tasks rename would
    write over it, and rollback's restore of the owned paths would then fail its check."""
    if where == "HEAD":
        # Another detached project tack, committed through the hook, then deleted from disk.
        dbox.code_repo(dbox.sync / "tackcode", "tack")
    else:
        (dbox.records / "tack").mkdir()
        (dbox.records / "tack" / "x.md").write_text("x\n")
        dbox.run("git", "add", "tack/x.md", cwd=dbox.records)
    shutil.rmtree(dbox.records / "tack")
    refused(dbox, f"save: {dbox.records.resolve()} still tracks tack/ in its {where} although "
                  f"{(dbox.records / 'tack').resolve()} is absent; remove it from git "
                  f"(git rm -r --cached tack/, then commit) first")


def test_save_refuses_a_records_directory_not_directly_under_its_top_level(dbox):
    (dbox.records / "sub").mkdir()
    extra_detached(dbox, "nest", dbox.records / "sub")
    # The only fixture that bypasses the hook: the layout under test is one the hook
    # refuses (sub/ is staged with no tasks/.config.toml at its top), so it cannot be
    # committed through it.
    dbox.run("git", "add", "-A", cwd=dbox.records)
    dbox.run("git", "commit", "-q", "--no-verify", "-m", "nest records", cwd=dbox.records)
    records = (dbox.records / "sub" / "nest").resolve()
    refused(dbox, f"save: nest's records directory {records} must be named nest and sit directly "
                  f"under its repository's top level {dbox.records.resolve()}")


def test_save_refuses_a_records_directory_not_named_for_its_prefix(dbox):
    registry = dbox.tmp / "cfg" / "tasks" / "projects.toml"
    dbox.run("git", "mv", "ops", "other", cwd=dbox.records)
    # The registry first: the hook's tasks check reads the moved records through it.
    registry.write_text(registry.read_text().replace(f'ops = "{dbox.records / "ops"}"',
                                                     f'ops = "{dbox.records / "other"}"'))
    dbox.run("git", "commit", "-qm", "move ops's records", cwd=dbox.records)
    records = (dbox.records / "other").resolve()
    refused(dbox, f"save: ops's records directory {records} must be named ops and sit directly "
                  f"under its repository's top level {dbox.records.resolve()}")


def test_save_refuses_a_records_repository_inside_the_checkout(box):
    recs = nested_records_repo(box, box.checkout)
    refused(box, f"save: nr's records repository {recs.resolve()} lies inside the checkout "
                 f"{box.checkout.resolve()}")


def test_save_refuses_a_records_repository_inside_a_repo(box):
    recs = nested_records_repo(box, box.ops)
    refused(box, f"save: nr's records repository {recs.resolve()} lies inside --repo {box.ops.resolve()}")


def test_save_refuses_a_records_repository_that_is_the_checkout(box):
    """pp's records at <checkout>/pp: their parent is the checkout's top level, so the
    parent-and-name check passes and the location check refuses. No tasks are written in
    pp: its records sit in a git-ignored path, so every record commit there fails."""
    with (box.checkout / ".gitignore").open("a") as f:
        f.write("pp/\n")
    box.commit(box.checkout, "ignore pp")
    extra_detached(box, "pp", box.checkout)
    assert box.run("git", "status", "--porcelain", cwd=box.checkout).stdout == ""
    refused(box, f"save: pp's records repository is the checkout {box.checkout.resolve()}")


def test_save_refuses_a_snapshot_inside_the_records_repository(dbox):
    dbox.snapshot = dbox.records / "snap"
    refused(dbox, f"lies inside records repository {dbox.records.resolve()}")


def test_save_refuses_a_records_directory_outside_any_git_repository(box):
    loose = box.tmp / "loose"
    loose.mkdir()
    extra_detached(box, "qq", loose)
    refused(box, f"git -C {(loose / 'qq').resolve()} rev-parse --show-toplevel: fatal: not a git repository")


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
        if cmd[:2] == ("tasks", "edit"):
            return '{"id":"ops-1","warnings":[]}'
        return ""

    monkeypatch.setattr(cutover, "run", fake_run)
    cutover.retarget_dependencies(tmp_path, "ai")
    writes = [c for c in calls if c[:2] in (("tasks", "edit"), ("tasks", "dep"))]
    assert writes == [("tasks", "edit", "ops-1", "--no-depends", "--depends", "tack-a",
                       "--depends", "ops-9", "--depends", "tack-b")]


@pytest.mark.parametrize("edit_output, message", [
    ("not json", "retarget: tasks edit ops-1 in {root} printed output that is not JSON"),
    ('["a list"]', "retarget: tasks edit ops-1 in {root} printed no warnings list"),
    ('{"id":"ops-1","warnings":["commit_failed: the hook refused"]}',
     "retarget: tasks edit ops-1 in {root} left its record uncommitted: commit_failed: the hook refused; "
     "no further task was edited; clear the cause, run `tasks commit` there, then rerun retarget --repo"),
])
def test_retarget_repo_stops_on_edit_output_it_cannot_trust(tmp_path, monkeypatch, edit_output, message):
    """Unparseable output is a stop, never "no warnings"; so is a failed record commit.
    The second task's edit never runs."""
    cutover = load_cutover()
    calls = []
    check = {"warnings": [
        {"id": f"ops-{n}", "kind": "retired_prefix",
         "detail": f'depends on ai-{n} through retired prefix "ai"; it is now tack-{n}'} for n in (1, 2)]}

    def fake_run(*cmd, cwd=None):
        calls.append(cmd)
        if cmd[:2] == ("tasks", "check"):
            return json.dumps(check)
        if cmd[:2] == ("tasks", "show"):
            return json.dumps({"task": {"depends": [f"ai-{cmd[2][4:]}"]}})
        return edit_output

    monkeypatch.setattr(cutover, "run", fake_run)
    with pytest.raises(cutover.Stop) as stop:
        cutover.retarget_dependencies(tmp_path, "ai")
    assert message.format(root=tmp_path) in str(stop.value)
    assert [c[2] for c in calls if c[:2] == ("tasks", "edit")] == ["ops-1"]


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
    assert not (box.snapshot / "forward.json").exists()


def test_forward_and_repo_are_one_or_the_other(box):
    """--forward selects its projects itself; naming one beside it is refused before anything runs."""
    box.save()
    box.forward()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", box.ops, "--forward", check=False)
    assert result.returncode == 2 and "not allowed with" in result.stderr
    assert not (box.snapshot / "forward.json").exists()


def test_retarget_refuses_the_renamed_checkout(box):
    """Its own ids were renamed, not retargeted; --forward on it would end rollback for nothing."""
    box.save()
    box.forward()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", box.new_root, check=False)
    assert result.returncode == 1
    assert "is the renamed checkout" in result.stderr and "--forward" not in result.stderr
    assert not (box.snapshot / "forward.json").exists()
    box.cutover("rollback", "--snapshot", box.snapshot)


def outside_project(box, name):
    path = box.sync / name
    box.repo(path, name)
    box.commit(path, "init")
    return path


def test_forward_retargets_every_project_outside_the_snapshot_and_records_each(box):
    """It selects relay and tasks itself, leaves the snapshot's ops for --repo, and records
    exactly the projects it wrote in, before writing."""
    _, in_ops = box.depend_on_checkout(box.ops)
    dependents = {name: box.depend_on_checkout(outside_project(box, name)) for name in ("relay", "tasks")}
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--forward")
    for name, (target, dependent) in dependents.items():
        root = box.sync / name
        assert f"retarget: {dependent}: {target} -> tack-{target[3:]}" in result.stdout
        assert f"retargeted in {root}" in result.stdout
        assert box.run("tasks", "check", cwd=root).stdout == ""
    assert sorted(json.loads((box.snapshot / "forward.json").read_text())) == sorted(
        str((box.sync / name).resolve()) for name in dependents)
    assert in_ops in box.run("tasks", "check", cwd=box.ops).stdout


def test_an_unrelated_renames_warning_selects_nothing_and_records_nothing(box):
    """relay depends through another rename's retired prefix: not this cutover's to fix."""
    relay, other = outside_project(box, "relay"), outside_project(box, "zed")
    target = task_id(box.run("tasks", "add", "depended on", "--process", "direct", cwd=other).stdout)
    box.commit(other, "a task to depend on")
    dependent = task_id(box.run("tasks", "add", "depends", "--process", "direct", cwd=relay).stdout)
    box.run("tasks", "dep", dependent, "--on", target, cwd=relay)
    box.commit(relay, "depend on zed")
    box.run("tasks", "rename", "zed", "zen", cwd=other)
    box.commit(other, "an unrelated rename")
    before = (relay / "tasks" / f"{dependent}.md").read_bytes()
    assert 'retired prefix \\"zed\\"' in box.run("tasks", "check", cwd=relay).stdout
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--forward")
    assert "nothing to retarget outside the snapshot" in result.stdout
    assert (relay / "tasks" / f"{dependent}.md").read_bytes() == before
    assert not (box.snapshot / "forward.json").exists()


def test_a_failing_check_stops_forward_before_any_write(box):
    """relay sorts before the broken project, so a write-as-you-go loop would have changed it."""
    relay = outside_project(box, "relay")
    _, dependent = box.depend_on_checkout(relay)
    broken = outside_project(box, "zzz")
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    (broken / "tasks" / "files" / "zzz-abcdef").mkdir(parents=True)
    (broken / "tasks" / "files" / "zzz-abcdef" / "x.txt").write_text("x\n")
    before = (relay / "tasks" / f"{dependent}.md").read_bytes()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--forward", check=False)
    assert result.returncode == 1
    assert f"tasks check fails in {broken.resolve()}" in result.stderr and "attachment_orphan" in result.stderr
    assert (relay / "tasks" / f"{dependent}.md").read_bytes() == before
    assert not (box.snapshot / "forward.json").exists()


def test_a_retired_project_that_needs_a_retarget_stops_forward_before_any_write(box):
    """A retired project refuses writes; its dependency on this rename's old ids is named,
    not skipped as nothing to do, and nothing is written anywhere."""
    relay = outside_project(box, "relay")
    _, in_relay = box.depend_on_checkout(relay)
    retired = outside_project(box, "old")
    _, in_retired = box.depend_on_checkout(retired)
    box.run("tasks", "drop", in_retired, "over", cwd=retired)
    box.commit(retired, "drop it")
    box.run("tasks", "retire", "--reason", "over", cwd=retired)
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    before = (relay / "tasks" / f"{in_relay}.md").read_bytes()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--forward", check=False)
    assert result.returncode == 1
    assert f"old is retired at {retired} and depends on retired ids in {in_retired}" in result.stderr
    assert (relay / "tasks" / f"{in_relay}.md").read_bytes() == before
    assert not (box.snapshot / "forward.json").exists()


def test_forward_never_checks_the_renamed_checkout(box):
    """The checkout's own ids were renamed: a finding there is not forward's to stop on."""
    relay = outside_project(box, "relay")
    box.depend_on_checkout(relay)
    box.save()
    box.cutover("apply", "--snapshot", box.snapshot)
    (box.new_root / "tasks" / "files" / "tack-abcdef").mkdir(parents=True)
    (box.new_root / "tasks" / "files" / "tack-abcdef" / "x.txt").write_text("x\n")
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--forward")
    assert f"retargeted in {relay.resolve()}" in result.stdout


def test_forward_with_nothing_to_change_records_nothing(box):
    """After the snapshot's own retargets nothing outside depends on a retired id. An
    unreachable project and a retired one are named as not checked."""
    gone, retired = outside_project(box, "gone"), outside_project(box, "old")
    shutil.rmtree(gone)
    box.run("tasks", "retire", "--reason", "over", cwd=retired)
    box.depend_on_checkout(box.ops)
    box.save()
    box.forward()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--forward")
    assert "nothing to retarget outside the snapshot" in result.stdout
    assert f"retarget: gone is unreachable at {gone}; not checked" in result.stdout
    assert f"retarget: old is retired at {retired}; nothing to retarget" in result.stdout
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
    box.cutover("retarget", "--snapshot", box.snapshot, "--forward")
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


# --- apply, retarget, link, verify: detached projects -----------------------------


def projects_row(box, prefix):
    return next(row for row in json.loads(box.run("tasks", "projects", "--json", cwd=box.tmp).stdout)["projects"]
                if row["prefix"] == prefix)


@pytest.mark.parametrize("make", ["directory", "dangling link"])
def test_apply_refuses_when_the_new_records_directory_exists(dbox, make):
    dbox.save()
    new = dbox.records / "tack"
    if make == "directory":
        new.mkdir()
    else:
        new.symlink_to("nowhere")
    result = dbox.cutover("apply", "--snapshot", dbox.snapshot, check=False)
    assert result.returncode == 1
    assert (f"apply: {dbox.records.resolve() / 'tack'} already exists; tasks rename writes tack's "
            f"records there, so move it aside first") in result.stderr
    assert dbox.checkout.exists() and not dbox.new_root.exists()
    assert (dbox.records / "ai" / "tasks" / ".config.toml").is_file()
    assert projects_row(dbox, "ai")["kind"] == "detached"


def commit_line(box):
    repo = shlex.quote(str(box.records.resolve()))
    return (f"git -C {repo} add -A -- ai tack && git -C {repo} commit -m "
            f"'chore(tasks): rename ai -> tack' -- ai tack")


def test_apply_repoints_a_detached_checkout_and_prints_the_records_commit(dbox):
    dbox.save()
    result = dbox.apply()
    row = projects_row(dbox, "tack")
    assert Path(row["root"]).resolve() == dbox.new_root.resolve()
    assert row["kind"] == "detached"
    assert Path(row["records"]).resolve() == (dbox.records / "tack").resolve()
    assert not (dbox.new_root / "tasks").exists()
    # [checkout] path is relative to the records directory.
    config = tomllib.loads((dbox.records / "tack" / "tasks" / ".config.toml").read_text())
    assert (dbox.records / "tack" / config["checkout"]["path"]).resolve() == dbox.new_root.resolve()
    assert commit_line(dbox) in [line.strip() for line in result.stdout.splitlines()]
    # Printed, not run: the rename is still uncommitted in the records repository.
    assert "?? tack/tasks/.config.toml" in dbox.run("git", "status", "--porcelain", "--untracked-files=all",
                                                    cwd=dbox.records).stdout


@pytest.mark.parametrize("detached", [True, False], ids=["detached-checkout", "in-tree-checkout"])
def test_the_whole_detached_cutover_retargets_links_and_verifies(tmp_path, detached):
    """A detached --repo, ops, sharing the records repository with a detached checkout, or
    with an in-tree checkout beside it; ops depends on a checkout task."""
    box = Sandbox(tmp_path, detached=detached, detached_repos=("ops",)).build()
    target, dependent = box.depend_on_checkout(box.ops)
    box.save()
    applied = box.apply()
    assert ("git -C " in applied.stdout) == detached
    box.commit_rename()
    result = box.cutover("retarget", "--snapshot", box.snapshot, "--repo", box.ops)
    assert f"retarget: {dependent}: {target} -> tack-{target.split('-', 1)[1]}" in result.stdout
    assert box.run("tasks", "check", cwd=box.ops).stdout == ""
    # The retarget's write committed itself in the records repository.
    assert box.run("git", "status", "--porcelain", "--untracked-files=all", cwd=box.records).stdout == ""
    last = box.run("git", "log", "-1", "--name-only", "--format=", cwd=box.records).stdout.split()
    assert last == [f"ops/tasks/{dependent}.md"]
    box.cutover("link", "--snapshot", box.snapshot)
    assert os.path.realpath(box.tmp / "home" / ".agents") == str((box.new_root / "agents").resolve())
    assert "verified" in box.cutover("verify", "--snapshot", box.snapshot).stdout


def detached_cutover(box):
    """The whole forward cutover of a detached box, the rename committed."""
    box.save()
    box.apply()
    box.commit_rename()
    for root in box.repos:
        box.cutover("retarget", "--snapshot", box.snapshot, "--repo", root)
    box.cutover("link", "--snapshot", box.snapshot)


def verify_refused(box, message):
    result = box.cutover("verify", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1, result.stdout
    assert message in result.stderr, result.stderr


def test_verify_fails_while_the_records_repository_holds_the_uncommitted_rename(dbox):
    dbox.save()
    dbox.forward()
    verify_refused(dbox, f"verify: {dbox.records.resolve()} has uncommitted changes under ai/: "
                         f"D ai/tasks/.config.toml")
    # The <old>/ deletions committed alone still leave <new>/ untracked.
    dbox.run("git", "commit", "-qm", "the old half", "--", "ai", cwd=dbox.records)
    verify_refused(dbox, f"verify: {dbox.records.resolve()} has uncommitted changes under tack/: "
                         f"?? tack/tasks/.config.toml")


def test_verify_fails_while_the_old_records_directory_exists(dbox):
    detached_cutover(dbox)
    (dbox.records / "ai").mkdir()
    verify_refused(dbox, f"verify: {dbox.records.resolve() / 'ai'} still exists; the rename moved every "
                         f"record out of it, so move it aside")


def test_verify_fails_when_the_row_names_other_records(dbox):
    """A copy at the same depth keeps [checkout] path (relative to the records directory)
    pointing at the new root, so project_row still finds the row."""
    detached_cutover(dbox)
    copy = dbox.sync / "records2" / "tack"
    shutil.copytree(dbox.records / "tack", copy)
    registry = dbox.tmp / "cfg" / "tasks" / "projects.toml"
    text = registry.read_text()
    assert f'tack = "{dbox.records / "tack"}"' in text
    registry.write_text(text.replace(f'tack = "{dbox.records / "tack"}"', f'tack = "{copy}"'))
    verify_refused(dbox, f"verify: tasks projects' row for tack at {dbox.new_root} does not match the "
                         f"rename: records is {copy.resolve()}, expected {(dbox.records / 'tack').resolve()}")


def test_verify_fails_on_a_tracked_change_under_p(dbox):
    spec = dbox.records / "ops" / "docs" / "specs" / "a.md"
    spec.write_text("x\n")
    dbox.commit(dbox.records, "an ops spec")
    detached_cutover(dbox)
    spec.write_text("changed\n")
    verify_refused(dbox, f"verify: {dbox.records.resolve()} has uncommitted changes under ops/: "
                         f"M ops/docs/specs/a.md")


def test_retarget_repo_stops_on_a_deferred_record_commit(dbox):
    """Another project's file staged after save makes tasks defer every record commit; the
    first edit's warning stops the retarget before the second edit runs."""
    dbox.code_repo(dbox.sync / "zz", "zz")
    dependents = [dbox.depend_on_checkout(dbox.ops)[1] for _ in range(2)]
    dbox.save()
    dbox.apply()
    dbox.commit_rename()
    (dbox.records / "zz" / "docs" / "specs" / "d.md").write_text("x\n")
    dbox.run("git", "add", "zz/docs/specs/d.md", cwd=dbox.records)

    def record(dependent):
        return (dbox.records / "ops" / "tasks" / f"{dependent}.md").read_bytes()

    before = {d: record(d) for d in dependents}
    result = dbox.cutover("retarget", "--snapshot", dbox.snapshot, "--repo", dbox.ops, check=False)
    assert result.returncode == 1
    edited = [d for d in dependents if record(d) != before[d]]
    assert len(edited) == 1, "the second edit ran"
    assert (f"retarget: tasks edit {edited[0]} in {dbox.ops.resolve()} left its record uncommitted: "
            f"commit_deferred: ") in result.stderr
    assert "staged changes: zz/docs/specs/d.md" in result.stderr
    assert "no further task was edited" in result.stderr


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


RECORDS_SAVED = ('[projects]\nai = "/c/ai"\nops = "/c/ops"\n'
                 '[records]\nai = "/r/ai"\nops = "/r/ops"\n')


def test_registry_view_reads_a_moved_records_key_as_the_renames_own(tmp_path):
    # tasks rename moves a detached project's [records] key with its prefix.
    cutover = load_cutover()
    saved, live = tmp_path / "saved.toml", tmp_path / "live.toml"
    saved.write_text(RECORDS_SAVED)
    live.write_text('[projects]\nops = "/c/ops"\ntack = "/c/tack"\n'
                    '[records]\nops = "/r/ops"\ntack = "/r/tack"\n')
    assert cutover.registry_view(live, "ai", "tack") == cutover.registry_view(saved, "ai", "tack")
    live.write_text(live.read_text().replace('ops = "/r/ops"', 'ops = "/r/elsewhere"'))
    changes = cutover.registry_changes(cutover.registry_view(live, "ai", "tack"),
                                       cutover.registry_view(saved, "ai", "tack"))
    assert changes == ["records.ops"]


@pytest.mark.parametrize("change, named", [
    (lambda t: t.replace('ops = "/r/ops"', 'ops = "/r/elsewhere"'), "records.ops"),
    (lambda t: t.replace('ops = "/r/ops"\n', ""), "records.ops"),
    (lambda t: t + 'zz = "/r/zz"\n', "records.zz"),
])
def test_registry_view_sees_any_other_records_change(tmp_path, change, named):
    cutover = load_cutover()
    saved, live = tmp_path / "saved.toml", tmp_path / "live.toml"
    saved.write_text(RECORDS_SAVED)
    live.write_text(change(RECORDS_SAVED))
    assert live.read_text() != RECORDS_SAVED
    live_view, saved_view = (cutover.registry_view(path, "ai", "tack") for path in (live, saved))
    assert live_view != saved_view
    assert cutover.registry_changes(live_view, saved_view) == [named]


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


# --- the resolver and the preparation's deferred minors --------------------------


def drop_former(registry, prefix):
    """The registry without the renamed project's former roots, as if never recorded."""
    kept, skipping = [], False
    for line in registry.read_text().splitlines(keepends=True):
        if line.startswith("["):
            skipping = line.strip() == f"[[locations.{prefix}.former]]"
        if not skipping:
            kept.append(line)
    registry.write_text("".join(kept))


def test_verify_asks_the_resolver_about_the_old_id_root_and_storage(box):
    box.save()
    box.forward()
    box.cutover("verify", "--snapshot", box.snapshot)
    rows = json.loads(box.run("tasks", "resolve", "--json", str(box.checkout),
                              str(box.sync.parent / ".dropbox-work" / "ai" / ".worktrees" / "x")).stdout)["results"]
    assert [(r["status"], r["prefix"], r["via"]) for r in rows] == [
        ("resolved", "tack", "former_root"), ("resolved", "tack", "former_storage")]


def test_verify_runs_from_a_working_directory_the_move_removed(box):
    """An operator's shell can still stand in the old checkout path that apply moved."""
    box.save()
    box.forward()
    gone = box.tmp / "gone"
    gone.mkdir()
    result = subprocess.run(f'cd {gone} && rmdir {gone} && {box.snapshot / "rename-cutover"} verify --snapshot {box.snapshot}',
                            shell=True, env=box.env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "verified" in result.stdout


def test_verify_refuses_when_the_old_root_no_longer_resolves(box):
    box.save()
    box.forward()
    registry = box.tmp / "cfg" / "tasks" / "projects.toml"
    assert "[[locations.tack.former]]" in registry.read_text()
    drop_former(registry, "tack")
    result = box.cutover("verify", "--snapshot", box.snapshot, check=False)
    assert result.returncode == 1
    assert "tasks resolve does not answer tack for" in result.stderr and str(box.checkout) in result.stderr


def test_save_refuses_an_existing_snapshot_without_a_traceback(box):
    box.snapshot.mkdir()
    result = box.save(check=False)
    assert result.returncode == 1
    assert "already exists" in result.stderr and "Traceback" not in result.stderr


@pytest.mark.parametrize("which", ["cfg", "state"])
def test_save_refuses_a_linked_tasks_directory(box, which):
    live = box.tmp / which / "tasks"
    real = box.tmp / f"{which}-real"
    live.rename(real)
    live.symlink_to(real)
    result = box.save(check=False)
    assert result.returncode == 1 and "must be a real directory" in result.stderr
    assert not box.snapshot.exists()


def test_save_refuses_a_kept_path_that_is_a_link(hq):
    # The behaviour exists (kept_paths); the preparation's review asked for its test.
    trust = hq.checkout / "local" / "codex" / "trust.toml"
    real = hq.tmp / "elsewhere.toml"
    trust.rename(real)
    trust.symlink_to(real)
    result = hq.save(check=False)
    assert result.returncode == 1 and "no regular file" in result.stderr
    assert not hq.snapshot.exists()


def test_sample_task_stops_without_a_task_under_the_new_prefix(tmp_path):
    cutover = load_cutover()
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "ai-123456.md").write_text("x\n")
    with pytest.raises(cutover.Stop, match=r"no tack-\*\.md task"):
        cutover.sample_task(tmp_path, "tack")
    (tmp_path / "tasks" / "tack-abcdef.md").write_text("x\n")
    assert cutover.sample_task(tmp_path, "tack") == "abcdef"


def test_reset_all_writes_every_patch_before_any_reset(tmp_path, monkeypatch):
    cutover = load_cutover()
    calls = []

    def patch(root, head, snap, label):
        if label == "lore":
            raise cutover.Stop("disk full")
        calls.append(("patch", label))

    monkeypatch.setattr(cutover, "save_reset_patch", patch)
    monkeypatch.setattr(cutover, "run", lambda *cmd, cwd=None: calls.append(("run", *map(str, cmd))))
    resets = [(tmp_path / "a", "h1", "checkout"), (tmp_path / "b", "h2", "lore")]
    with pytest.raises(cutover.Stop, match="disk full"):
        cutover.reset_all(resets, tmp_path)
    assert calls == [("patch", "checkout")]


def test_save_refuses_findings_from_tasks_check(box2):
    lore = box2.repos[1]
    a = task_id(box2.run("tasks", "add", "parked idea", "--process", "direct", cwd=lore).stdout)
    b = task_id(box2.run("tasks", "add", "waits on it", "--process", "direct", cwd=lore).stdout)
    box2.run("tasks", "dep", b, "--on", a, cwd=lore)
    box2.run("tasks", "shelve", a, "when it is needed", "--defer", "30d", cwd=lore)
    box2.commit(lore, "a dependency on a shelved task")
    assert "shelved_dep" in box2.run("tasks", "check", cwd=lore).stdout
    result = box2.save(check=False)
    assert result.returncode == 1
    assert "tasks check reports findings" in result.stderr and str(lore) in result.stderr
    assert not box2.snapshot.exists()


def test_rollback_restores_a_renamed_attachments_folder(box):
    """`tasks rename` renames tasks/files/<old>-<hex>/ with its task. After the reset the
    renamed folder is an untracked leftover: removed, emptied folders and all."""
    hex_ = task_id(box.run("tasks", "add", "with files", "--process", "direct", cwd=box.checkout).stdout).split("-", 1)[1]
    source = box.tmp / "notes.txt"
    source.write_text("evidence\n")
    box.run("tasks", "attach", f"ai-{hex_}", source, cwd=box.checkout)
    assert (box.checkout / "tasks" / "files" / f"ai-{hex_}" / "notes.txt").is_file()
    box.commit(box.checkout, "a task with an attachment")
    before = box.fingerprint()
    box.save()
    box.forward()
    assert (box.new_root / "tasks" / "files" / f"tack-{hex_}" / "notes.txt").is_file()
    box.cutover("rollback", "--snapshot", box.snapshot)
    assert box.fingerprint() == before
    assert not (box.checkout / "tasks" / "files" / f"tack-{hex_}").exists()


def test_leftover_original_names_records_and_attachments_only():
    cutover = load_cutover()
    assert cutover.leftover_original("tasks/hq-abc123.md", "tack", "hq") == "tasks/tack-abc123.md"
    assert cutover.leftover_original("tasks/files/hq-abc123/a/b.py", "tack", "hq") == "tasks/files/tack-abc123/a/b.py"
    for path in ("tasks/x/hq-abc123.md", "tasks/files/hq-abc123", "tasks/files/ops-abc123/b.py", "notes/hq-abc123.md"):
        assert cutover.leftover_original(path, "tack", "hq") is None, path


def test_a_retargeted_repository_with_claims_is_a_precondition_message(box2):
    lore = box2.repos[1]
    tid = task_id(box2.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=lore).stdout)
    start_under_a_dead_session(box2, tid, lore)
    box2.commit(lore, "start under a dead session")
    assert "preconditions: a retargeted repository has claims" in box2.save(check=False).stderr

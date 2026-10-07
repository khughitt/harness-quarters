"""The rename's rehearsal (docs/specs/2026-10-06-rename-to-hq-design.md §4).

Run only when named; `just test` never collects it, since its name does not match test_*.py:

    uv run -q --with pytest pytest tools/rehearse_rename_hq.py -q --basetemp <scratch dir>

It clones this host's tack, ops, lore, flows, tasks and obs (their committed state) into two
scratch hosts. Each host has its own HOME, XDG_CONFIG_HOME, XDG_STATE_HOME and worktree
storage, and a scratch registry in the live one's shape: the ai alias, the agent-layer
group, and tack's former roots. Projects it does not clone stay registered at their live
roots, read-only. Then it runs the cutover through the tools the live run uses:
rename-cutover from its snapshot copy, and rename-hq-steps. It reads the live registry,
checkouts and trust files, and writes only under the base directory. It never calls
systemctl: the timer's enable link is a fixture, checked by its target. Every scenario
starts from one pristine copy restored at the same path, because the scratch registries
hold absolute paths.
"""
import datetime
import json
import os
import shutil
import stat
import subprocess
import tomllib
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent
CUTOVER, STEPS = TOOLS / "rename-cutover", TOOLS / "rename-hq-steps"
LIVE_REGISTRY = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "tasks" / "projects.toml"
CLONED = ("tack", "ops", "lore", "flows", "tasks", "obs")
REPOS = ("ops", "lore", "flows")
KEPT = ("codex/config.toml", "local/codex/trust.toml")
OLD, NEW = "tack", "hq"
UNIT = Path(".config/systemd/user/session-archive-capture.timer")
WANTS = Path(".config/systemd/user/timers.target.wants/session-archive-capture.timer")
GIT_ID = {"GIT_AUTHOR_NAME": "rehearsal", "GIT_AUTHOR_EMAIL": "rehearsal@localhost",
          "GIT_COMMITTER_NAME": "rehearsal", "GIT_COMMITTER_EMAIL": "rehearsal@localhost"}
# The hooks the commits meet run uv; the live cache lets them resolve offline, as they do live.
UV_CACHE = subprocess.run(["uv", "cache", "dir"], text=True, capture_output=True, check=True).stdout.strip()
TODAY = datetime.date.today().isoformat()


def live():
    return tomllib.loads(LIVE_REGISTRY.read_text())


def toml(value):
    return json.dumps(str(value))


class Host:
    """One scratch host: <base>/<name>/{d, .dropbox-work, home, cfg, state}."""

    def __init__(self, base, name):
        self.root = base / name
        self.sync = self.root / "d"
        self.home, self.cfg, self.state = self.root / "home", self.root / "cfg", self.root / "state"
        self.registry = self.cfg / "tasks" / "projects.toml"
        self.env = {**os.environ, "HOME": str(self.home), "XDG_CONFIG_HOME": str(self.cfg),
                    "XDG_STATE_HOME": str(self.state), "UV_CACHE_DIR": UV_CACHE, **GIT_ID}
        for name_ in ("WORK_ROOT", "TASKS_SESSION", "TASKS_SESSION_PID", "GIT_DIR", "GIT_WORK_TREE"):
            self.env.pop(name_, None)

    def path(self, name):
        return self.sync / name

    def run(self, *cmd, cwd=None, check=True, env=None):
        result = subprocess.run([str(c) for c in cmd], cwd=cwd, env=env or self.env, text=True, capture_output=True)
        if check and result.returncode != 0:
            raise AssertionError(f"{cmd}: {result.stdout}{result.stderr}")
        return result

    def storage(self, name):
        return self.root / ".dropbox-work" / name / ".worktrees"

    @property
    def second_state(self):
        return self.root / "second-host.json"


def write_registry(host, roots, extra_former):
    """The live registry's shape over this host's roots: aliases and groups as they are,
    each live project's location history, and `extra_former` appended per prefix."""
    data = live()
    lines = ["[projects]"] + [f"{k} = {toml(v)}" for k, v in sorted(roots.items())]
    if data.get("aliases"):
        lines += ["", "[aliases]"] + [f"{k} = {toml(v)}" for k, v in sorted(data["aliases"].items())]
    if data.get("groups"):
        lines += ["", "[groups]"] + [f"{k} = [{', '.join(toml(m) for m in v)}]" for k, v in sorted(data["groups"].items())]
    locations = data.get("locations", {})
    for prefix in sorted(set(locations) | set(extra_former)):
        table = locations.get(prefix, {})
        former = list(table.get("former", [])) + extra_former.get(prefix, [])
        storage = table.get("storage") if prefix not in CLONED else None
        if not former and storage is None:
            continue
        lines += ["", f"[locations.{prefix}]"] + ([f"storage = {toml(storage)}"] if storage else [])
        for entry in former:
            lines += ["", f"[[locations.{prefix}.former]]"] + [f"{k} = {toml(v)}" for k, v in entry.items()]
    host.registry.parent.mkdir(parents=True, exist_ok=True)
    host.registry.write_text("\n".join(lines) + "\n")


def copy_local(host, clone, live_tack):
    """local/ is ignored and the trust tables are filtered: copy them as the cutover finds
    them, with this host's checkout in place of the live one in each trust table's key."""
    # Lock files too: codex-trust creates trust.toml.lock, and the live checkout has one.
    shutil.copytree(live_tack / "local", clone / "local", dirs_exist_ok=True)
    for rel in KEPT:
        text = (live_tack / rel).read_text()
        key = f'[projects."{live_tack}"]'
        assert text.count(key) == 1, f"live {rel} has no single trust table for {live_tack}"
        (clone / rel).write_text(text.replace(key, f'[projects."{clone}"]'))
        os.chmod(clone / rel, stat.S_IMODE((live_tack / rel).stat().st_mode))
    host.run("git", "add", "codex/config.toml", cwd=clone)
    assert host.run("git", "status", "--porcelain", "--untracked-files=all", cwd=clone).stdout == ""


def init_submodules(host, clone, live_root):
    """A clone does not fetch submodules (lore's vendor/superpowers, which links.toml
    targets). Fetch each from the live checkout's own copy, never from the network."""
    listed = host.run("git", "config", "-f", ".gitmodules", "--get-regexp", r"submodule\..*\.path",
                      cwd=clone, check=False).stdout.split()
    for key, path in zip(listed[::2], listed[1::2]):
        name = key[len("submodule."):-len(".path")]
        host.run("git", "config", f"submodule.{name}.url", live_root / path, cwd=clone)
        host.run("git", "-c", "protocol.file.allow=always", "submodule", "update", "--init", "--", path, cwd=clone)


def stand_in_for_the_rest(host, live_roots):
    """ops-projects check, which ops's commit hook runs, reads every registered project at
    its mirror path under the sync root. Each project this does not clone stands there
    as a link to its live checkout, read-only by everything the rehearsal runs."""
    live_sync = Path(live_roots["ops"]).resolve().parent
    for prefix, root in live_roots.items():
        live = Path(root).resolve()
        if prefix in CLONED or not live.exists() or live_sync not in live.parents:
            continue
        link = host.sync / live.relative_to(live_sync)  # mirror paths can nest: mindful/v3
        if not link.exists():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(live)


def install_hooks(host, clone, live_root):
    """A clone does not carry core.hooksPath: give each the live checkout's, so the
    rehearsal's commits meet the gates the live run's do."""
    hooks = subprocess.run(["git", "-C", str(live_root), "config", "core.hooksPath"], text=True,
                           capture_output=True).stdout.strip()
    if hooks:
        host.run("git", "config", "core.hooksPath", hooks, cwd=clone)
        assert (clone / hooks).is_dir(), f"{clone}: no {hooks}"
    assert host.run("git", "config", "core.hooksPath", cwd=clone, check=False).stdout.strip() == hooks


def link_home(host):
    host.run(host.path("tack") / "tools" / "harness-links", "--apply")
    wants = host.home / WANTS
    wants.parent.mkdir(parents=True, exist_ok=True)
    wants.symlink_to(os.readlink(host.home / UNIT))


def build_first(host, live_roots):
    host.sync.mkdir(parents=True)
    for d in (host.home, host.cfg, host.state):
        d.mkdir(parents=True)
    roots = dict(live_roots)
    for prefix in CLONED:
        clone = host.path(Path(live_roots[prefix]).name)
        host.run("git", "clone", "-q", "--no-hardlinks", Path(live_roots[prefix]).resolve(), clone)
        roots[prefix] = clone
    for prefix in CLONED:
        init_submodules(host, roots[prefix], Path(live_roots[prefix]).resolve())
        if prefix != "tack":
            install_hooks(host, roots[prefix], Path(live_roots[prefix]).resolve())
    stand_in_for_the_rest(host, live_roots)
    tack, live_tack = roots["tack"], Path(live_roots["tack"]).resolve()
    host.run("just", "setup", cwd=tack)
    copy_local(host, tack, live_tack)
    # The trust files are shared through the sync, so they also hold the other host's
    # table for its own checkout path, which differs from this one's.
    host.run("python3", STEPS, "trust", "--checkout", tack, "--old", tack, "--new",
             Host(host.root.parent, "h2").path("tack"), "--require")
    host.run("work-link", "--root", host.sync, "--ensure", ".worktrees", cwd=tack)
    # Sessions recorded under the live checkout resolve to the clone (Task 8's trial join).
    live_storage = (live_tack / ".worktrees").resolve()
    write_registry(host, roots, {OLD: [{"root": str(live_tack), "storage": str(live_storage), "until": TODAY}]})
    for prefix in CLONED:
        host.run("tasks", "init", "--prefix", prefix, "--force", cwd=roots[prefix])
    link_home(host)


def build_second(first, host, live_roots):
    """The other host: the same synced files, its own registry, storage and home. Its
    pre-move second-host-record refreshes and keeps its storage (tasks spec §2.3; Task 9 Step 5)."""
    host.sync.mkdir(parents=True)
    for d in (host.home, host.cfg, host.state):
        d.mkdir(parents=True)
    roots = dict(live_roots)
    for prefix in CLONED:
        name = Path(live_roots[prefix]).name
        subprocess.run(["cp", "-a", str(first.path(name)), str(host.path(name))], check=True)
        roots[prefix] = host.path(name)
    (host.path("tack") / ".worktrees").unlink()
    host.run("work-link", "--root", host.sync, "--ensure", ".worktrees", cwd=host.path("tack"))
    stand_in_for_the_rest(host, live_roots)
    write_registry(host, roots, {})
    for prefix in CLONED:
        if prefix != "tack":
            host.run("tasks", "init", "--prefix", prefix, "--force", cwd=roots[prefix])
    host.run("python3", STEPS, "second-host-record", "--root", host.path("tack"), "--state", host.second_state)
    link_home(host)


@pytest.fixture(scope="module")
def pristine(tmp_path_factory):
    base = tmp_path_factory.getbasetemp().resolve()
    run_dir = base / "run"
    live_roots = live()["projects"]
    first = Host(run_dir, "h1")
    build_first(first, live_roots)
    build_second(first, Host(run_dir, "h2"), live_roots)
    subprocess.run(["cp", "-a", str(run_dir), str(base / "pristine")], check=True)
    return base


@pytest.fixture
def hosts(pristine):
    run_dir = pristine / "run"
    shutil.rmtree(run_dir)
    subprocess.run(["cp", "-a", str(pristine / "pristine"), str(run_dir)], check=True)
    return Host(run_dir, "h1"), Host(run_dir, "h2")


class Cutover:
    """The live runbook's calls (Task 9 Steps 6 to 12), against the first scratch host."""

    def __init__(self, host):
        self.host = host
        self.snap = host.root.parent / "snap"

    def tool(self):
        copy = self.snap / "rename-cutover"
        return copy if copy.exists() else CUTOVER

    def save(self, check=True):
        h = self.host
        args = ["save", "--snapshot", self.snap, "--checkout", h.path("tack"), "--new-root", h.path("hq"),
                "--old", OLD, "--new", NEW]
        for rel in KEPT:
            args += ["--keep", rel]
        for name in REPOS:
            args += ["--repo", h.path(name)]
        return h.run(self.tool(), *args, check=check)

    def cut(self, command, check=True):
        return self.host.run(self.tool(), command, "--snapshot", self.snap, check=check)

    def step(self, *args):
        self.host.run("python3", STEPS, *args, "--snapshot", self.snap)

    def forward(self):
        self.cut("apply")
        self.step("tack")
        self.step("ops", "--date", TODAY)
        self.step("lore")
        self.step("flows")
        self.cut("link")
        reenable(self.host)
        self.cut("verify")


def reenable(host):
    """What `systemctl --user reenable` did in the plan's probe (systemd 262): the enable
    link follows the manifest-held unit link."""
    wants = host.home / WANTS
    wants.unlink()
    wants.symlink_to(os.readlink(host.home / UNIT))


def resolve(host, inputs):
    return json.loads(host.run("tasks", "resolve", "--json", *map(str, inputs)).stdout)["results"]


def fingerprint(host):
    """Everything rollback must restore on the first host, as comparable data."""
    def tree(root):
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
                if ".git" not in p.relative_to(root).parts and p.is_file() and not p.is_symlink()}

    def git(root, *args):
        return host.run("git", *args, cwd=root).stdout

    tack = host.path("tack")
    return {
        "repos": {name: {"head": git(host.path(name), "rev-parse", "HEAD"),
                         "branch": git(host.path(name), "symbolic-ref", "-q", "HEAD"),
                         "status": git(host.path(name), "status", "--porcelain", "--untracked-files=all"),
                         "files": tree(host.path(name))} for name in ("tack", *REPOS)},
        "cfg": tree(host.cfg / "tasks"), "state": tree(host.state / "tasks"),
        "modes": {rel: stat.S_IMODE((tack / rel).stat().st_mode) for rel in KEPT},
        "worktrees": os.readlink(tack / ".worktrees"),
        "home": {str(p.relative_to(host.home)): os.readlink(p) for p in sorted(host.home.rglob("*")) if p.is_symlink()},
    }


def carry(first, second):
    """What the file sync does to the other host: its checkouts become the first host's."""
    for name in ("tack", *REPOS):
        shutil.rmtree(second.path(name))
    for name in ("hq", *REPOS):
        subprocess.run(["cp", "-a", str(first.path(name)), str(second.path(name))], check=True)


# --- the scenarios ---------------------------------------------------------------------


def test_the_cutover_verifies_and_the_second_host_adopts(hosts):
    h1, h2 = hosts
    cutover = Cutover(h1)
    cutover.save()
    cutover.forward()
    for name in ("hq", *REPOS):
        assert h1.run("tasks", "check", cwd=h1.path(name)).stdout == "", name
        assert h1.run("git", "status", "--porcelain", "--untracked-files=all", cwd=h1.path(name)).stdout == "", name
    rows = resolve(h1, ["tack-dcb11a", "ai-4b1878", h1.path("tack"), h1.storage("tack") / "a-worktree"])
    assert [(r["status"], r.get("prefix")) for r in rows] == [("resolved", NEW)] * 4
    for rel in KEPT:
        text = (h1.path("hq") / rel).read_text()
        assert f'[projects."{h1.path("hq")}"]' in text and f'[projects."{h1.path("tack")}"]' in text
    assert tomllib.loads((h1.path("hq") / "identity.toml").read_text())["name"] == "harness-quarters"
    mirror = tomllib.loads((h1.path("ops") / "identity-mirror.toml").read_text())
    assert "tack" not in mirror and mirror["hq"]["name"] == "harness-quarters" and mirror["hq"]["path"] == "hq"
    assert "`hq` — harness-quarters" in (h1.path("lore") / "instructions" / "AGENTS.md").read_text()
    assert Path(os.readlink(h1.home / WANTS)).resolve() == (h1.path("hq") / "systemd/user/session-archive-capture.timer")

    first_host = {p: p.read_bytes() for d in (h1.cfg, h1.state) for p in sorted(d.rglob("*")) if p.is_file()}
    carry(h1, h2)
    h2.run("python3", STEPS, "second-host", "--root", h2.path("hq"), "--state", h2.second_state)
    assert_adopted(h2)
    assert {p: p.read_bytes() for d in (h1.cfg, h1.state) for p in sorted(d.rglob("*")) if p.is_file()} == first_host


def assert_adopted(h2):
    location = tomllib.loads(h2.registry.read_text())["locations"]["hq"]
    assert location["storage"] == str(h2.storage("hq"))
    assert {"root": str(h2.path("tack")), "storage": str(h2.storage("tack"))} in [
        {k: e.get(k) for k in ("root", "storage")} for e in location["former"]]
    rows = resolve(h2, ["tack-dcb11a", OLD, h2.path("tack"), h2.storage("tack") / "a-worktree"])
    assert [(r["status"], r.get("prefix")) for r in rows] == [("resolved", NEW)] * 4
    trust = (h2.path("hq") / "codex" / "config.toml").read_text()
    assert f'[projects."{h2.path("hq")}"]' in trust and f'[projects."{h2.path("tack")}"]' in trust
    for name in ("hq", *REPOS):
        assert h2.run("tasks", "check", cwd=h2.path(name)).stdout == "", name
        assert h2.run("git", "status", "--porcelain", "--untracked-files=all", cwd=h2.path(name)).stdout == "", name


def test_the_second_host_finishes_an_interrupted_adoption(hosts):
    h1, h2 = hosts
    cutover = Cutover(h1)
    cutover.save()
    cutover.forward()
    carry(h1, h2)
    # second-host got as far as the adoption, then stopped: the registry no longer names tack.
    h2.run("tasks", "rename", OLD, NEW, "--adopt", cwd=h2.path("hq"))
    # And tasks itself stopped between adopting the registry and removing the old claim
    # store: its resume_cleanup state, which only a rerun of the adoption finishes.
    old_store = h2.state / "tasks" / "claims" / f"{OLD}.toml"
    old_store.parent.mkdir(parents=True, exist_ok=True)
    old_store.write_text("")
    explained = json.loads(h2.run("tasks", "rename", OLD, NEW, "--adopt", "--explain", cwd=h2.path("hq")).stdout)
    assert "resume_cleanup" in json.dumps(explained), explained
    h2.run("python3", STEPS, "second-host", "--root", h2.path("hq"), "--state", h2.second_state)
    assert not old_store.exists()
    assert_adopted(h2)
    # A rerun of a finished adoption changes nothing and passes.
    h2.run("python3", STEPS, "second-host", "--root", h2.path("hq"), "--state", h2.second_state)
    assert_adopted(h2)


def test_rollback_before_the_commits_restores_everything(hosts):
    h1, _ = hosts
    cutover = Cutover(h1)
    before = fingerprint(h1)
    cutover.save()
    cutover.cut("apply")
    cutover.cut("rollback")
    reenable(h1)
    assert fingerprint(h1) == before


def test_rollback_after_the_commits_restores_everything(hosts):
    h1, _ = hosts
    cutover = Cutover(h1)
    before = fingerprint(h1)
    cutover.save()
    cutover.forward()
    cutover.cut("rollback")
    reenable(h1)
    assert fingerprint(h1) == before


@pytest.mark.parametrize("table, plant", [
    ("projects", lambda t: t.replace("[projects]\n", '[projects]\nzz = "/elsewhere"\n', 1)),
    ("aliases", lambda t: t.replace("[aliases]\n", '[aliases]\nzz = "hq"\n', 1)),
    ("groups", lambda t: t.replace("[groups]\n", '[groups]\nzz = ["ops"]\n', 1)),
])
def test_the_guard_stops_on_a_foreign_change(hosts, table, plant):
    h1, _ = hosts
    cutover = Cutover(h1)
    cutover.save()
    cutover.cut("apply")
    text = h1.registry.read_text()
    h1.registry.write_text(plant(text))
    assert h1.registry.read_text() != text
    result = cutover.cut("rollback", check=False)
    assert result.returncode == 1
    assert "guard: the registry changed" in result.stderr and f"{table}.zz" in result.stderr
    assert h1.path("hq").exists() and not h1.path("tack").exists()


def test_save_refuses_a_dead_claim_in_a_retargeted_repository(hosts):
    h1, _ = hosts
    ops = h1.path("ops")
    added = json.loads(h1.run("tasks", "add", "orphaned claim", "--process", "direct", cwd=ops).stdout)
    tid = added.get("id") or added["task"]["id"]
    h1.run("tasks", "start", tid, cwd=ops, env={**h1.env, "TASKS_SESSION": "ghost", "TASKS_SESSION_PID": "999999"})
    h1.run("git", "add", "-A", cwd=ops)
    h1.run("git", "commit", "-qm", "a claim under a dead session", cwd=ops)
    result = Cutover(h1).save(check=False)
    assert result.returncode == 1 and "a retargeted repository has claims" in result.stderr and tid in result.stderr
    assert not Cutover(h1).snap.exists()
